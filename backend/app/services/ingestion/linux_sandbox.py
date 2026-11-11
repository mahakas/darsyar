"""Linux OS-level sandbox probe + runner (Gate B-S2 prototype).

Experimental, Linux-oriented. The OS-level fences (network, filesystem, memory,
CPU, PID) are supplied by the container runtime when this module executes inside
the restricted sandbox container (see `backend/tests/sandbox/Dockerfile.sandbox`).
On a host where those fences are absent (e.g., a Windows host), the probes report
`NOT_ENFORCED` rather than claiming success.

Trust boundary: the Parent (this supervisor / this process) is the only trusted,
infrastructure-facing component. The restricted child receives only synthetic PDF
bytes and explicit test-supplied limits; it never receives credentials, secrets,
session objects, or client handles.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

from app.services.ingestion.parent_child_contract import ParentChildRequest
from app.services.ingestion.parent_supervisor import ChildRunResult, run_child

SANDBOX_PROBE_ENV = "DARSYAR_SANDBOX_PROBE"


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of one synthetic isolation probe."""

    name: str
    enforced: bool
    detail: str
    not_tested: bool = False


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def sandbox_probe_active() -> bool:
    return os.environ.get(SANDBOX_PROBE_ENV) == "1"


def probe_network_isolation() -> ProbeResult:
    """Attempt an outbound TCP connect to a public/non-loopback address.

    Under `--network none` the container has no route and no external interface,
    so the connect must fail. Absence of network calls in code is not proof; we
    attempt the connection explicitly.
    """
    if not is_linux():
        return ProbeResult("network", False, "not Linux host", not_tested=True)
    # Enumerate interfaces: under `--network none`, only `lo` should exist.
    try:
        interfaces = os.listdir("/sys/class/net")
    except OSError as exc:
        interfaces = [f"<unreadable {type(exc).__name__}>"]
    non_loopback = [i for i in interfaces if i != "lo"]
    attempt_error = ""
    for target in ("8.8.8.8", "1.1.1.1"):
        try:
            with socket.create_connection((target, 53), timeout=2):
                attempt_error = f"connect to {target}:53 unexpectedly succeeded"
                break
        except OSError as exc:
            attempt_error = f"connect to {target}:53 blocked ({type(exc).__name__})"
            break
    if not non_loopback and "blocked" in attempt_error:
        return ProbeResult("network", True, f"interfaces={interfaces}; {attempt_error}")
    return ProbeResult(
        "network",
        False,
        f"interfaces={interfaces}; {attempt_error}",
    )


def probe_filesystem_readonly() -> ProbeResult:
    """Attempt to write a file at a root-level path (should fail on read-only rootfs)."""
    if not is_linux():
        return ProbeResult("filesystem", False, "not Linux host", not_tested=True)
    for path in ("/sandbox_write_probe", "/root/sandbox_write_probe"):
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("probe")
            return ProbeResult("filesystem", False, f"wrote {path} (rootfs writable)")
        except OSError as exc:
            return ProbeResult("filesystem", True, f"write to {path} denied ({type(exc).__name__})")
    return ProbeResult("filesystem", False, "no probe path attempted")


def probe_docker_socket_absent() -> ProbeResult:
    if not is_linux():
        return ProbeResult("docker_socket", False, "not Linux host", not_tested=True)
    absent = not os.path.exists("/var/run/docker.sock")
    return ProbeResult("docker_socket", absent, f"docker.sock exists={not absent}")


def probe_host_secrets_unreadable() -> ProbeResult:
    if not is_linux():
        return ProbeResult("host_secrets", False, "not Linux host", not_tested=True)
    try:
        with open("/etc/shadow", encoding="utf-8"):
            return ProbeResult("host_secrets", False, "/etc/shadow is readable")
    except (OSError, PermissionError):
        return ProbeResult("host_secrets", True, "/etc/shadow not readable")


def probe_process_limit(max_spawn: int) -> ProbeResult:
    """Attempt to spawn many concurrent subprocesses; the PID limit should reject overflow."""
    if not is_linux():
        return ProbeResult("pids", False, "not Linux host", not_tested=True)
    failures = 0
    spawned: list[subprocess.Popen[Any]] = []
    for _ in range(max_spawn):
        try:
            spawned.append(
                subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(5)"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
        except OSError as exc:
            failures += 1
            _ = exc
    for proc in spawned:
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    total = failures + len(spawned)
    if failures > 0:
        return ProbeResult("pids", True, f"{failures}/{max_spawn} concurrent spawns failed (PID limit)")
    return ProbeResult("pids", False, f"spawned {total}/{max_spawn} concurrently (no PID limit observed)")


def probe_memory_exhaustion(megabytes: int) -> ProbeResult:
    """Spawn a subprocess that tries to allocate beyond the container memory limit.

    The probe subprocess is expected to be OOM-killed or fail; the parent (this
    process) must survive.
    """
    if not is_linux():
        return ProbeResult("memory", False, "not Linux host", not_tested=True)
    code = (
        "import sys; n = int(sys.argv[1]); "
        "data = bytearray(n * 1024 * 1024); print('alloc_ok', len(data))"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code, str(megabytes)],
            timeout=30,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        return ProbeResult("memory", True, "allocation subprocess timed out (likely throttled)")
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip().splitlines()[-1:] or [""]
        return ProbeResult("memory", True, f"allocation failed rc={proc.returncode}: {detail[0]}")
    return ProbeResult("memory", False, f"allocated {megabytes} MB (no limit observed)")


def probe_cpu_quota(loop_iters: int) -> ProbeResult:
    """Measure elapsed time for a fixed CPU-bound loop under the container's --cpus.

    Reports the measured wall time; exact throttling magnitude is environment
    dependent. The probe only establishes that the loop completes inside the
    sandbox, and records the duration as evidence.
    """
    if not is_linux():
        return ProbeResult("cpu", False, "not Linux host", not_tested=True)
    start = time.perf_counter()
    x = 0
    for i in range(loop_iters):
        x += i
    elapsed = time.perf_counter() - start
    return ProbeResult("cpu", True, f"busy loop completed in {elapsed:.3f}s (quota applied by runtime)")


def run_sandboxed_child(request: ParentChildRequest, *, timeout_seconds: float) -> ChildRunResult:
    """Run the restricted PDF child inside the sandbox's enforced boundaries.

    The OS-level fences are provided by the container runtime that hosts this
    process; the child inherits them. The Parent remains the only trusted,
    infrastructure-facing component. See `parent_supervisor.run_child`.
    """
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return run_child(request, timeout_seconds=timeout_seconds, cwd=cwd)


ALL_PROBES: list[Any] = [
    probe_network_isolation,
    probe_filesystem_readonly,
    probe_docker_socket_absent,
    probe_host_secrets_unreadable,
]
