"""Gate B-S4 — Experiment B: direct Linux cgroup counter evidence (synthetic-only).

Requires the restricted Linux sandbox container (DARSYAR_SANDBOX_PROBE=1).
On hosts without the cgroup files or the sandbox fences, tests are skipped
(NOT_TESTED), not weakened.
"""

from __future__ import annotations

import os
from typing import cast

import pytest

from sandbox.s4_cgroup_lib import (
    cpu_probe,
    memory_probe,
    pids_probe,
    read_cgroup,
    snapshot,
)

ENFORCEMENT_AVAILABLE = os.environ.get("DARSYAR_SANDBOX_PROBE") == "1" and os.path.exists("/sys/fs/cgroup/memory.max")

pytestmark = pytest.mark.skipif(
    not ENFORCEMENT_AVAILABLE,
    reason="cgroup evidence requires the restricted Linux sandbox container with /sys/fs/cgroup",
)


def _i(value: object) -> int:
    return int(cast(int, value))


def test_cgroup_v2_effective_memory_limit() -> None:
    value = read_cgroup("memory.max")
    assert value is not None
    # S2 container delta: --memory 768m -> 788529152 bytes.
    assert int(value) == 805306368


def test_cgroup_v2_effective_cpu_quota() -> None:
    value = read_cgroup("cpu.max")
    assert value is not None
    # S2: --cpus 0.75 -> quota 75000 us / period 100000 us.
    quota, period = value.split()
    assert int(quota) == 75000
    assert int(period) == 100000


def test_cgroup_v2_effective_pids_limit() -> None:
    value = read_cgroup("pids.max")
    assert value is not None
    # S2: --pids-limit 96.
    assert int(value) == 96


def test_memory_oom_counter_evidence() -> None:
    probe = memory_probe(allocate_mb=1500)
    assert _i(probe["returncode"]) != 0
    # A SIGKILL alone is not enough; demand a counter delta.
    assert _i(probe["oom_delta"]) >= 1 or _i(probe["oom_kill_delta"]) >= 1


def test_cpu_throttling_counter_evidence() -> None:
    probe = cpu_probe(seconds=6)
    assert _i(probe["returncode"]) == 0
    assert probe["cpu_max"] is not None
    assert _i(probe["throttled_usec_delta"]) > 0 or _i(probe["nr_throttled_delta"]) > 0


def test_pids_limit_counter_evidence() -> None:
    probe = pids_probe()
    assert probe["failed"] is not None  # a real spawn failure occurred
    assert _i(probe["spawned"]) < 200
    # Every spawned child was terminated and reaped.
    current = read_cgroup("pids.current")
    assert current is not None
    assert int(current) < 10  # near baseline, no surviving children
    # The max event should have been observed at least once (delta >= 1).
    assert _i(probe["pids_max_event_delta"]) >= 1


def test_snapshot_has_before_after() -> None:
    s = snapshot()
    for key in ("memory.max", "cpu.max", "pids.max"):
        assert s[key] is not None
