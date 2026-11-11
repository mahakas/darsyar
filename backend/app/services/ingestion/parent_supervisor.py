"""Parent Supervisor — Gate B-S1 prototype.

Spawns the Isolated PDF Child as a separate OS process via an explicit subprocess
invocation (no shell), with an allowlisted environment, an explicit working
directory, and controlled stdio. It owns all interaction with the child: it sends
a minimal versioned JSON request, waits bounded by a test-supplied timeout,
validates the structured result, and performs graceful-then-forced termination on
timeout or abnormal exit, then ensures no orphan remains and stays usable.

Security invariants:
- The Parent is the only component that may own database/application-infrastructure
  access. Nothing here connects to PostgreSQL or Redis.
- The Child receives only minimal synthetic document bytes + explicit test-supplied
  limits. The Parent does NOT pass database/Redis credentials, application secrets,
  session objects, or client handles.
- The Child environment is an explicit allowlist; the full parent environment is
  never inherited. No secret values are logged.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.ingestion.parent_child_contract import (
    PARENT_CHILD_CONTRACT_VERSION,
    ParentChildRequest,
    ParentChildResult,
)

logger = get_logger(__name__)

CHILD_MODULE = "app.services.ingestion.pdf_child"

# Allowlisted child environment keys (minimum to launch Python + import app).
ALLOWLISTED_ENV_KEYS = (
    "PATH",
    "PYTHONPATH",
    "SYSTEMROOT",
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
)

# Env key fragments that must never reach the child; child reports presence only.
FORBIDDEN_ENV_FRAGMENTS = (
    "DATABASE_URL",
    "POSTGRES",
    "REDIS",
    "API_KEY",
    "SECRET",
    "PEPPER",
    "PASSWORD",
    "SENTINEL",
)


def _forbidden_present(env: dict[str, str]) -> list[str]:
    return [k for k in env if any(f in k.upper() for f in FORBIDDEN_ENV_FRAGMENTS)]


@dataclass(frozen=True)
class ChildRunResult:
    """Outcome of a single Parent→Child invocation."""

    ok: bool
    result: ParentChildResult | None = None
    exit_code: int | None = None
    timed_out: bool = False
    terminated: bool = False
    forced_terminated: bool = False
    message: str = ""
    forbidden_env_seen: list[str] = field(default_factory=list)


def _allowlisted_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for key in ALLOWLISTED_ENV_KEYS:
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    # Ensure app importability for `python -m app...` under the test cwd.
    env.setdefault("PYTHONPATH", os.getcwd())
    return env


def run_child(
    request: ParentChildRequest,
    *,
    timeout_seconds: float,
    cwd: str,
    python_executable: str | None = None,
) -> ChildRunResult:
    """Spawn the child, send the request, await a typed result.

    Uses no shell, an allowlisted env, an explicit cwd, and piped stdio. On
    timeout it attempts graceful termination then escalates to forced termination,
    verifying exit and that no orphan remains.
    """
    child_env = _allowlisted_env()
    # Env that goes to the child must not contain forbidden entries.
    child_forbidden = _forbidden_present(child_env)

    exe = python_executable or sys.executable
    cmd = [exe, "-m", CHILD_MODULE]

    proc: subprocess.Popen[Any] | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=child_env,
            shell=False,
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(request.to_json().encode("utf-8"))
        proc.stdin.close()

        timed_out = False
        terminated = False
        forced = False
        try:
            stdout_bytes, _stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            # Graceful termination attempt.
            proc.terminate()
            terminated = True
            try:
                stdout_bytes, _stderr = proc.communicate(timeout=5.0)
            except subprocess.TimeoutExpired:
                forced = True
                proc.kill()
                stdout_bytes, _stderr = proc.communicate(timeout=5.0)

        exit_code = proc.returncode
        stdout = stdout_bytes.decode("utf-8", errors="replace").strip() if stdout_bytes else ""

        result_obj: ParentChildResult | None = None
        if stdout:
            try:
                result_obj = ParentChildResult.from_json(stdout)
            except Exception as exc:  # noqa: BLE001
                logger.warning("parent_child_result_unparsable", extra={"error_type": type(exc).__name__})
                return ChildRunResult(
                    ok=False,
                    exit_code=exit_code,
                    timed_out=timed_out,
                    terminated=terminated,
                    forced_terminated=forced,
                    message="child result JSON could not be parsed",
                    forbidden_env_seen=child_forbidden,
                )

        if result_obj is not None and result_obj.contract_version != PARENT_CHILD_CONTRACT_VERSION:
            return ChildRunResult(
                ok=False,
                result=result_obj,
                exit_code=exit_code,
                timed_out=timed_out,
                terminated=terminated,
                forced_terminated=forced,
                message="contract version mismatch",
                forbidden_env_seen=child_forbidden,
            )

        if timed_out:
            return ChildRunResult(
                ok=False,
                result=result_obj,
                exit_code=exit_code,
                timed_out=True,
                terminated=terminated,
                forced_terminated=forced,
                message="child timed out and was terminated",
                forbidden_env_seen=child_forbidden,
            )

        if exit_code != 0:
            return ChildRunResult(
                ok=False,
                result=result_obj,
                exit_code=exit_code,
                message=f"child exited abnormally (code={exit_code})",
                forbidden_env_seen=child_forbidden,
            )

        if result_obj is None:
            return ChildRunResult(
                ok=False,
                exit_code=exit_code,
                message="child produced no result",
                forbidden_env_seen=child_forbidden,
            )

        return ChildRunResult(
            ok=True,
            result=result_obj,
            exit_code=exit_code,
            message="ok",
            forbidden_env_seen=child_forbidden,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("parent_child_spawn_failure", extra={"error_type": type(exc).__name__})
        return ChildRunResult(ok=False, message=f"spawn failure: {type(exc).__name__}")
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5.0)
