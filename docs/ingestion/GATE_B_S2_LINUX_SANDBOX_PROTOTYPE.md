# Gate B-S2 — Linux OS-Level PDF Sandbox Prototype

**Date:** 2026-11-11. Owner decision `GATE_B-S2 = APPROVE_WITH_CONDITIONS`.
Experimental Linux-only sandbox prototype. **Not Production approval; Gate B stays
OPEN.**

## Owner approval

`GATE_B-S2 = APPROVE_WITH_CONDITIONS (2026-11-11)` — limited to implementing and
testing an isolated Linux OS-level sandbox prototype using synthetic PDF fixtures and
synthetic workloads. Excludes Production, real textbook/pilot PDF processing, upload
API activation, PDFium/pypdfium2 integration, OCR/rendering/extraction/embedding/
indexing/retrieval/publication, and any change to the deployment Compose/runtime.

## Architecture & trust boundaries

```
Parent Supervisor (this process)
   |  ParentChildRequest (JSON on stdin): synthetic bytes + explicit test limits
   v
Isolated Linux sandbox container  -- enforcement provided by container runtime:
   |   --network none | --read-only | --memory | --cpus | --pids-limit
   |   --cap-drop ALL | --security-opt no-new-privileges | non-root user
   v
Restricted PDF Child (python -m app.services.ingestion.pdf_child)
   |  scoped pypdf Configuration; parse; optional content-stream decode
   v
ParentChildResult (JSON on stdout)
   v
Parent validates schema/contract/exit; Parent remains sole trusted infra-facing
   component (no DB/Redis connection in this prototype).
```

- The Parent owns all database/Redis/storage/application credentials. The Child
  receives only minimum synthetic input; no credentials, secrets, session objects,
  or client handles.
- Parent/Child IPC contract unchanged from S1 (`PARENT_CHILD_CONTRACT_VERSION = 1`).

## Isolation mechanisms (enforced by container runtime at `docker run`)

| Boundary | Mechanism | Observed |
|---|---|---|
| Network | `--network none` (only loopback `lo`) | `interfaces=['lo']`; connect to `8.8.8.8:53` blocked (OSError) |
| Filesystem | `--read-only` rootfs + `--tmpfs /tmp:rw,size=64m` | write to `/sandbox_write_probe` denied (OSError); dedicated writable `/tmp` |
| Docker socket | no `/var/run/docker.sock` mount | `docker.sock exists=False` |
| Host secrets | non-root user + read-only root | `/etc/shadow not readable` |
| Memory | `--memory 768m` (cgroup) | allocation probe killed (`rc=-9`, OOM) |
| CPU | `--cpus 0.75` | busy loop 2M iterations completed in 1.214s (throttled) |
| PID | `--pids-limit 96` | 105/200 concurrent child spawns failed (EAGAIN) |
| Capabilities | `--cap-drop ALL` | applied at runtime |
| no-new-privileges | `--security-opt no-new-privileges:true` | applied at runtime |
| Non-root | `--user 65534:65534` (nobody) | child never runs as root |

These are enforced at the container-runtime layer; the probe tests assert actual
behavior (not just config declarations). The child runs inside the same restricted
container and therefore inherits all fences. A sanitized environment + separate OS
process does **not** by itself provide fs/network isolation — here it is provided by
the container runtime flags, and the probes confirm denial.

## Files

- `backend/app/services/ingestion/linux_sandbox.py` — probes + `run_sandboxed_child`
  (reuses the S1 supervisor; same IPC contract).
- `backend/tests/test_gate_b_linux_sandbox.py` — synthetic Linux sandbox tests.
- `backend/tests/sandbox/Dockerfile.sandbox` — standalone experimental image
  (Python 3.13-slim, venv, **pypdf==6.21.3** locked, pytest). Not part of the
  application deployment Dockerfile/Compose (untouched).

## Test matrix (synthetic only)

| Category | Test | Result (Linux container) |
|---|---|---|
| Network isolation | probe_network_isolation | enforced |
| Filesystem read-only | probe_filesystem_readonly | enforced |
| Docker socket absent | probe_docker_socket_absent | enforced |
| Host secrets unreadable | probe_host_secrets_unreadable | enforced |
| Memory limit | probe_memory_exhaustion(2048) | enforced (rc=-9) |
| CPU quota | probe_cpu_quota(2M) | enforced (1.214s) |
| PID limit | probe_process_limit(200) | enforced (105/200 failed) |
| IPC valid PDF | run_sandboxed_child | success, pypdf 6.21.3 |
| Malformed PDF | run_sandboxed_child | FAILED (MALFORMED/TRUNCATED) |
| Oversized synthetic stream | run_sandboxed_child | FAILED (RESOURCE_LIMIT) |
| Child timeout/forced termination | mode="hang" timeout=1s | timed_out, terminated |
| Parent recovery | hang → next request | succeeds |
| Env allowlist (sentinels) | DATABASE_URL/SECRET_TOKEN | not present in child |

## Commands and results

```
# Build standalone sandbox image (context = backend)
docker build -f backend/tests/sandbox/Dockerfile.sandbox -t darsyar-linux-sandbox:test backend

# Run with OS-level fences
docker run --rm \
  --network none --read-only --tmpfs /tmp:rw,size=64m \
  --memory 768m --cpus 0.75 --pids-limit 96 \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --user 65534:65534 \
  darsyar-linux-sandbox:test

Result: 52 passed in 88.49s
(S2 Linux + S1 parent/child + S0 validation, all under the sandbox container)
```

Host (Windows) run for regression:
```
pytest tests/test_gate_b_pdf_validation.py tests/test_gate_b_parent_child.py tests/test_gate_b_linux_sandbox.py -q
-> 39 passed, 13 skipped (Linux enforcement tests skip on non-sandbox host)
```

Static checks: `ruff check app tests` → all passed; `mypy app` → no issues
(118 files).

## Enforced / Not enforced / Not tested matrix

| Control | Status | Note |
|---|---|---|
| Network isolation | **ENFORCED** | verified in container |
| Filesystem read-only | **ENFORCED** | verified |
| Docker socket absence | **ENFORCED** | verified |
| Host secrets unreadable | **ENFORCED** | verified |
| Memory limit | **ENFORCED** | cgroup; probe killed |
| CPU quota | **ENFORCED** | `--cpus` throttling observed |
| PID/process limit | **ENFORCED** | 105/200 spawns failed |
| Capabilities dropped | **ENFORCED** | `--cap-drop ALL` at runtime |
| no-new-privileges | **ENFORCED** | runtime flag |
| Non-root child | **ENFORCED** | `--user 65534` |
| Parent/Child IPC | **ENFORCED** | schema/version validated |
| Credential/env isolation | **ENFORCED** | allowlist + sentinel probe |
| OS-level fs sandbox (seccomp/LSM) | **NOT_ENFORCED** | not applied in this prototype |
| Per-child cgroup (separate from container) | **NOT_ENFORCED** | child shares container fences |
| Real production numeric limits | **NOT_ENFORCED / PENDING** | await owner decision |

## Host/runtime prerequisites

- Docker Desktop (Linux backend) on the Windows host was required to run the Linux
  container; the engine was started for this experiment.
- The enforcement is demonstrable only inside the restricted container; on a plain
  host the probes report `NOT_ENFORCED` / tests are skipped.
- Exact pypdf `6.21.3` is installed in the sandbox image (lockfile version). The
  local host venv was aligned to `6.21.3` for parity (no lockfile/code change).

## Known limitations

- The sandbox is a **container** boundary: the child shares the container's limits
  with the parent; there is no separate per-child cgroup in this prototype.
- No seccomp/LSM (e.g., AppArmor/SELinux) profile is applied.
- CPU throttling magnitude is environment-dependent; we record completion time, not a
  precise quota ratio.
- The parent and child are in the same OS container; isolation is the container fence,
  not a stricter child-only jail.

## Remaining Gate B owner decisions

Max file size; page count; decompressed size; DPI/pixel bounds; PDF processing
timeout; parent timeout; memory/CPU limits; child-process capacity; temporary storage
quota/retention; concurrent upload capacity; rate limits; admin authorization. All
remain `PENDING_OWNER_DECISION`.

## Statuses

```text
GATE_B_S0: IMPLEMENTED
GATE_B_S1: IMPLEMENTED
GATE_B_S1_SYNTHETIC_VALIDATION: PASSED
GATE_B_S2: IMPLEMENTED
GATE_B_S2_LINUX_SANDBOX_VALIDATION: PASSED

GATE_B: OPEN / OWNER_DECISION_REQUIRED
UPLOAD_API: NOT_ACTIVATED
REAL_PDF_PROCESSING: NOT_AUTHORIZED
PILOT_MANIFESTS: needs_review

GATE_A: OPEN
GATE_C: OWNER_APPROVAL_REQUIRED

PHASE_4: PLANNED / GATED
PHASE_5: NOT_STARTED
PRODUCTION: NOT_APPROVED
```

This prototype does not close Gate B and is not a Production readiness statement.
