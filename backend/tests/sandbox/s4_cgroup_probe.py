"""Gate B-S4 — cgroup evidence driver (run inside the Linux sandbox container).

Prints raw before/after counter snapshots and deltas for the S2 resource probes.
This is evidence capture for documentation; it does not modify anything.
"""

from __future__ import annotations

import sys
import time

from sandbox.s4_cgroup_lib import (
    cpu_probe,
    memory_probe,
    pids_probe,
    read_cgroup,
    snapshot,
)


def _print_snapshot(label: str, s: dict[str, str | None]) -> None:
    print(f"--- {label} ---")
    for k in sorted(s):
        print(f"  {k} = {s[k]}")


def main() -> int:
    print("kernel:", open("/proc/sys/kernel/osrelease", encoding="utf-8").read().strip())
    print("cgroup controllers:", read_cgroup("../cgroup.controllers") or read_cgroup("cgroup.controllers"))
    print("cgroup version marker:", read_cgroup("cgroup.v2") is not None if os_path_exists("cgroup.v2") else False)
    _print_snapshot("baseline", snapshot())

    print("\n== memory probe (allocation 1500 MB) ==")
    t0 = time.perf_counter()
    mp = memory_probe(allocate_mb=1500)
    print("elapsed_s:", round(time.perf_counter() - t0, 2))
    print("returncode:", mp["returncode"])
    print("events_before:", mp["events_before"])
    print("events_after:", mp["events_after"])
    print("oom_delta:", mp["oom_delta"], "oom_kill_delta:", mp["oom_kill_delta"])

    print("\n== cpu probe (6s busy) ==")
    t0 = time.perf_counter()
    cp = cpu_probe(seconds=6)
    print("elapsed_s:", round(time.perf_counter() - t0, 2))
    print("returncode:", cp["returncode"])
    print("cpu_max:", cp["cpu_max"])
    print("before_cpu_stat:", cp["before_cpu_stat"])
    print("after_cpu_stat:", cp["after_cpu_stat"])
    print("nr_periods_delta:", cp["nr_periods_delta"])
    print("nr_throttled_delta:", cp["nr_throttled_delta"])
    print("throttled_usec_delta:", cp["throttled_usec_delta"])

    print("\n== pids probe ==")
    pp = pids_probe()
    print("spawned:", pp["spawned"], "failed:", pp["failed"])
    print("before_pids_current:", pp["before_pids_current"], "after_pids_current:", pp["after_pids_current"])
    print("events_before:", pp["events_before"])
    print("events_after:", pp["events_after"])
    print("pids_max_event_delta:", pp["pids_max_event_delta"])

    _print_snapshot("final", snapshot())
    return 0


def os_path_exists(name: str) -> bool:
    import os

    return os.path.exists(name)


if __name__ == "__main__":
    sys.exit(main())
