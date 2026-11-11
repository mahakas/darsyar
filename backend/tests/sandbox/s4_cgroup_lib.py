"""Gate B-S4 — direct Linux cgroup counter probes (test-only).

Reads the container's cgroup v2 control files and runs bounded, child-process
workloads to produce before/after counter evidence. Nothing here modifies the
application, the deployment, or any cgroup configuration. Missing files are
reported as None (callers treat as NOT_TESTED).
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

CGROUP_DIR = "/sys/fs/cgroup"

CGROUP_FILES = (
    "memory.max",
    "memory.current",
    "memory.events",
    "memory.swap.max",
    "memory.oom.group",
    "cpu.max",
    "cpu.stat",
    "pids.max",
    "pids.current",
    "pids.events",
)


def cgroup_file(name: str) -> str | None:
    path = os.path.join(CGROUP_DIR, name)
    return path if os.path.exists(path) else None


def read_cgroup(name: str) -> str | None:
    path = cgroup_file(name)
    if path is None:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def snapshot() -> dict[str, str | None]:
    return {name: read_cgroup(name) for name in CGROUP_FILES}


def parse_stat(text: str | None) -> dict[str, int]:
    out: dict[str, int] = {}
    if not text:
        return out
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                out[parts[0]] = int(parts[1])
            except ValueError:
                pass
    return out


def parse_events(text: str | None) -> dict[str, int]:
    return parse_stat(text)


def memory_probe(allocate_mb: int = 1500, timeout: float = 60) -> dict[str, object]:
    before = snapshot()
    code = (
        "import sys; d = bytearray(int(sys.argv[1]) * 1024 * 1024); "
        "print('alloc_ok', len(d))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(allocate_mb)],
        capture_output=True,
        timeout=timeout,
    )
    after = snapshot()
    before_ev = parse_events(before.get("memory.events"))
    after_ev = parse_events(after.get("memory.events"))
    return {
        "returncode": proc.returncode,
        "before": before,
        "after": after,
        "events_before": before_ev,
        "events_after": after_ev,
        "oom_delta": after_ev.get("oom", 0) - before_ev.get("oom", 0),
        "oom_kill_delta": after_ev.get("oom_kill", 0) - before_ev.get("oom_kill", 0),
    }


def cpu_probe(seconds: int = 6) -> dict[str, object]:
    before = snapshot()
    code = (
        "import time, sys; end = time.time() + float(sys.argv[1]); x = 0\n"
        "while time.time() < end:\n    x += 1\nprint(x)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(seconds)],
        capture_output=True,
        timeout=seconds + 20,
    )
    after = snapshot()
    b = parse_stat(before.get("cpu.stat"))
    a = parse_stat(after.get("cpu.stat"))
    return {
        "returncode": proc.returncode,
        "before_cpu_stat": before.get("cpu.stat"),
        "after_cpu_stat": after.get("cpu.stat"),
        "cpu_max": after.get("cpu.max"),
        "nr_periods_delta": a.get("nr_periods", 0) - b.get("nr_periods", 0),
        "nr_throttled_delta": a.get("nr_throttled", 0) - b.get("nr_throttled", 0),
        "throttled_usec_delta": a.get("throttled_usec", 0) - b.get("throttled_usec", 0),
    }


def pids_probe(max_spawn: int = 200) -> dict[str, object]:
    before = snapshot()
    children: list[subprocess.Popen[Any]] = []
    failed: str | None = None
    spawned = 0
    try:
        for _ in range(max_spawn):
            try:
                children.append(
                    subprocess.Popen(
                        [sys.executable, "-c", "import time; time.sleep(5)"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                )
                spawned += 1
            except OSError as exc:
                failed = str(exc)
                break
    finally:
        # Terminate and reap every created child promptly.
        for p in children:
            try:
                p.kill()
            except (OSError, ProcessLookupError):
                pass
        for p in children:
            try:
                p.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                pass
    after = snapshot()
    b_ev = parse_events(before.get("pids.events"))
    a_ev = parse_events(after.get("pids.events"))
    return {
        "spawned": spawned,
        "failed": failed,
        "before_pids_max": before.get("pids.max"),
        "after_pids_max": after.get("pids.max"),
        "before_pids_current": before.get("pids.current"),
        "after_pids_current": after.get("pids.current"),
        "events_before": b_ev,
        "events_after": a_ev,
        "pids_max_event_delta": a_ev.get("max", 0) - b_ev.get("max", 0),
    }
