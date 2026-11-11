# Gate B-S4 — Aggregate Decompression Experiment and Linux cgroup Evidence

**Date:** 2026-11-11. Owner decision `GATE_B_S4 = APPROVE_WITH_CONDITIONS`.
Bounded laboratory task only. **Not** GB-04 approval, not a production limit, not
Gate B closure.

## 1. Owner authorization

`GATE_B_S4 = APPROVE_WITH_CONDITIONS` (2026-11-11): investigate and experimentally
validate an aggregate document-level decompression budget using synthetic PDFs only,
and obtain direct Linux cgroup counter evidence for the existing S2 container-level
memory/CPU/PID limits. GB-04, production limits, upload activation, real PDF
processing, and deployed-infrastructure changes are excluded.

## 2. Files inspected

- `backend/app/services/ingestion/` — `pdf_validation.py`, `parent_child_contract.py`,
  `parent_supervisor.py`, `pdf_child.py`, `linux_sandbox.py`.
- `backend/tests/` — `test_gate_b_pdf_validation.py`, `test_gate_b_parent_child.py`,
  `test_gate_b_linux_sandbox.py`, `sandbox/Dockerfile.sandbox`.
- Docs: `GATE_B_S0*`, `GATE_B_S1_PARENT_CHILD_PROTOTYPE.md`,
  `GATE_B_S2_LINUX_SANDBOX_PROTOTYPE.md`, `GATE_B_S3_NUMERIC_POLICY_OWNER_DECISION.md`,
  `INGESTION_PROGRESS_AND_OPEN_DECISIONS.md`.
- **pypdf==6.21.3** (locked) verified: `Configuration` (per-filter/per-stream caps,
  default zlib output 75 MB), `apply_configuration` scoping via ContextVar,
  `EncodedStreamObject.get_data()`, `PdfReader` signature (no `configuration=` kwarg).

## 3. Files created (test-only)

- `backend/tests/test_gate_b_s4_aggregate_decompression.py`
- `backend/tests/test_gate_b_s4_cgroup_evidence.py`
- `backend/tests/sandbox/__init__.py`
- `backend/tests/sandbox/s4_cgroup_lib.py`
- `backend/tests/sandbox/s4_cgroup_probe.py`

No production module (`backend/app`) was modified. The standalone `Dockerfile.sandbox`
was not changed (new test files are picked up by the existing `COPY tests`); the image
remains separate from Deployment.

## 4. pypdf 6.21.3 findings

- `Configuration` is applied via `apply_configuration(...)` (ContextVar scoped) and is
  read at decode time by `_decompress_with_limit` in `pypdf.filters` (zlib cap → raises
  `LimitReachedError` when exceeded).
- A single `Configuration` value is active per context; pypdf does **not** expose a
  running aggregate budget. However, because `get_data()` uses the config active at the
  moment of the call, we can drive each stream decode inside its own scoped
  `Configuration(zlib_maximum_output_length=effective)` where
  `effective = min(per_stream_limit, remaining_document_budget)`. This enforces the
  aggregate ceiling **during** decoding, not merely after.

## 5. Experiment A — aggregate decompression budget

### Design

`decode_with_aggregate_budget(data, per_stream_limit, aggregate_budget)` iterates pages,
and for each FlateDecode content stream decodes it under
`min(per_stream_limit, remaining)`. On `LimitReachedError` the run is rejected. Budget
decrements per actual decode operation; repeated references to an already-decoded
indirect object reuse cached output and do **not** re-consume budget. A failed/partial
decode aborts and consumes no successful bytes.

### Synthetic fixtures

- Multi-stream PDF: one independent FlateDecode content stream per page (deterministic
  payloads; exact encoded/decoded sizes recorded). Correct xref/startxref.
- Repeated-reference PDF: two pages referencing the same indirect stream object.
- Malformed-stream PDF: valid structure, corrupt zlib payload.

### Measurements (representative)

| Case | per-stream | aggregate budget | Result | total decoded | remaining | peak MiB | elapsed s |
|---|---|---|---|---|---|---|---|
| 1 stream, 1 MiB | 32 MiB | 4 MiB | ok | 1 MiB | 3 MiB | 2.4 | ~0.03 |
| 4×2 MiB streams | 32 MiB | 4 MiB | rejected `aggregate_budget_exhausted` | 4 MiB | 0 | 6.1 | ~0.04 |
| 2×2 MiB streams | 32 MiB | 4 MiB | ok | 4 MiB | 0 | ~6 | ~0.04 |
| 1×3 MiB stream | 1 MiB | 4 MiB | rejected `limit_reached_stream_or_remaining` | 0 | — | — | — |
| 3+3 MiB streams | 32 MiB | 5 MiB | rejected on last stream | 3 MiB | 2 MiB | — | — |
| Repeated reference 2 MiB | 32 MiB | 4 MiB | ok, counted once | 2 MiB | 2 MiB | ~6 | ~0.03 |
| Malformed stream | 32 MiB | 4 MiB | pypdf tolerates → 0 bytes | 0 | 4 MiB | 0.06 | ~0.01 |
| GB-04 candidate 8×32 MiB | 32 MiB | 256 MiB | **ok** | 256 MiB | 0 | 288.6 | ~1.0 |

The 256 MiB candidate was **technically enforceable** in this experiment through
per-stream bounded decoding (`effective = min(32 MiB, remaining)`); peak memory stayed
≈289 MiB (bounded single-stream buffers), well under the 768 MiB container.

### Accounting semantics (documented)

- Distinct stream objects consume budget once each; repeated references to an
  already-decoded object do **not** re-consume (cached reuse).
- Each actual decode operation consumes budget; a rejected decode (LimitReachedError)
  consumes no successful bytes and aborts the run.
- A tolerated-corrupt stream yields 0 bytes and consumes 0 budget (no partial bytes).
- The effective per-stream cap prevents bypass via many small streams: once `remaining`
  reaches 0, the next stream is rejected before decoding. This is **bounded
  decompression through the decoder**, not merely post-decompression accounting.

### Attack surface / limitations

- The experiment enumerates page content streams only. A real document's other
  decodable streams (images, object streams, cross-ref streams) are not enumerated by
  this prototype; production enforcement would need a complete stream census.
- pypdf does not expose a single "decode everything" hook with an aggregate budget; the
  orchestrator must drive each decode, meaning any stream type not visited bypasses the
  budget. This is the central remaining implementation limitation.
- A post-decompression-only check would be insufficient; the experiment enforces during
  decode, which is stronger.

### GB-04 recommendation (not approved)

- Technically enforceable at 256 MiB with the per-stream-bounded decoder; strongest
  evidence: 8×32 MiB stream run decoded exactly 256 MiB with peak ≈289 MiB in ≈1 s.
- Peak memory and time are acceptable in the 768 MiB container, but real-document
  stream census and CPU cost are unmeasured.
- Remaining attack surfaces: un-enumerated stream categories, object-stream/xref-stream
  decompression, and per-document CPU cost.
- Consider a smaller first candidate (e.g., 128 MiB) or a streaming decoder as
  alternatives; additional benchmarking on a full synthetic corpus is required.
- **GB-04 stays `PENDING_OWNER_DECISION`.**

## 6. Experiment B — direct Linux cgroup evidence

Environment inside the restricted sandbox container:
- Kernel: `6.18.58.1-microsoft-standard-WSL2` (Docker Desktop/WSL2 backend).
- cgroup v2 (controllers present: cpuset cpu io memory hugetlb pids rdma); files under
  `/sys/fs/cgroup`.
- Effective controls: `memory.max=805306368` (768 MiB), `cpu.max=75000 100000`
  (0.75 vCPU), `pids.max=96`, `memory.swap.max=805306368` (default swap enabled),
  `memory.oom.group=0`.

### Memory

Baseline (swap enabled): a 1500 MB allocation **succeeded** (rc=0); `memory.events`
`max` rose (0→3466) but `oom`/`oom_kill` stayed 0. This reflects Docker's default swap
behavior (768 MiB RAM + 768 MiB swap), not a hard-memory failure.

Controlled deviation (separate one-off container with `--memory-swap 768m` to disable
swap, documented as a deviation from the S2 baseline; baseline and deployment
unchanged):

```
ALLOC_MB 1200
RC -9
BEFORE memory.events {low:0, high:0, max:0, oom:0, oom_kill:0, oom_group_kill:0}
AFTER  memory.events {low:0, high:0, max:44, oom:1, oom_kill:1, oom_group_kill:0}
OOM_DELTA 1 OOM_KILL_DELTA 1
MEMORY_MAX 805306368
```

This is **direct cgroup OOM evidence** (SIGKILL `-9` plus `oom`/`oom_kill` counter
increments), not a declaration.

### CPU (throttling counters)

`cpu.stat` before/after a bounded 6 s busy workload inside the 0.75 vCPU container:

| Counter | Before | After | Delta |
|---|---:|---:|---:|
| nr_periods | 90 | 152 | +62 |
| nr_throttled | 77 | 136 | +59 |
| throttled_usec | 1,647,760 | 3,088,393 | +1,440,633 |

`cpu.max = 75000 100000`. The `nr_throttled`/`throttled_usec` deltas are direct
throttling evidence.

### PID

`pids.max=96`. Probe spawned 94 children before the first `OSError [Errno 11]
Resource temporarily unavailable`. `pids.events` `max` went 0→1 (delta +1). After
terminate/reap, `pids.current` returned to baseline (2). No orphan children remained.

## 7. Child termination / orphan verification

- PID probe kills and reaps every created child; `pids.current` returns to 2.
- S1/S2 timeout/forced-termination tests still pass; no orphan processes remain after
  the full suite (`pids.current` baseline).

## 8. Evidence classification matrix

| Claim | Class |
|---|---|
| cgroup v2 present & effective max/CPU/PID | `ENFORCED` (read from /sys/fs/cgroup) |
| Memory hard ceiling (OOM) | `ENFORCED` under controlled no-swap invocation (oom/oom_kill +1); baseline-with-swap = `INCONCLUSIVE` (allocation succeeded) |
| CPU throttling | `ENFORCED` (nr_throttled +59, throttled_usec ~1.44e6 delta) |
| PID limit | `ENFORCED` (EAGAIN at 94; pids.events max +1) |
| Aggregate decompression ceiling | `ENFORCED` in experiment (bounded per-stream decode) |
| Per-child cgroup isolation | `NOT_ENFORCED` / `NOT_TESTED` (container-level only) |
| seccomp/LSM enforcement | `NOT_TESTED` (not independently demonstrated) |
| Host-secret isolation | `NOT_TESTED` as a claim (rootfs read-only ≠ host-secret proof) |
| Production-safe resource values | `NOT_ENFORCED` / `PENDING` |

## 9. Reproducible commands

```
# Aggregate + cgroup + S0-S2 suites inside the restricted container
docker run --rm --network none --read-only --tmpfs /tmp:rw,size=64m \
  --memory 768m --cpus 0.75 --pids-limit 96 \
  --cap-drop ALL --security-opt no-new-privileges:true --user 65534:65534 \
  darsyar-linux-sandbox:test sh -lc \
  '/opt/venv/bin/python -m pytest tests/test_gate_b_s4_aggregate_decompression.py \
     tests/test_gate_b_s4_cgroup_evidence.py tests/test_gate_b_linux_sandbox.py \
     tests/test_gate_b_parent_child.py tests/test_gate_b_pdf_validation.py -q -p no:cacheprovider'
# -> 67 passed

# cgroup evidence driver
docker run --rm --network none --read-only --tmpfs /tmp:rw,size=64m \
  --memory 768m --cpus 0.75 --pids-limit 96 \
  --cap-drop ALL --security-opt no-new-privileges:true --user 65534:65534 \
  -e PYTHONPATH=/app/tests darsyar-linux-sandbox:test \
  sh -lc '/opt/venv/bin/python tests/sandbox/s4_cgroup_probe.py'

# Deterministic memory OOM (controlled deviation: swap disabled)
docker run --rm --network none --read-only --tmpfs /tmp:rw,size=64m \
  --memory 768m --memory-swap 768m --cpus 0.75 --pids-limit 96 \
  --cap-drop ALL --security-opt no-new-privileges:true --user 65534:65534 \
  -e PYTHONPATH=/app/tests \
  -v <host>/s4_mem_probe.py:/probe/s4_mem_probe.py:ro \
  darsyar-linux-sandbox:test sh -lc '/opt/venv/bin/python /probe/s4_mem_probe.py 1200'

# Host runs
pytest tests/test_gate_b_s4_aggregate_decompression.py tests/test_gate_b_s4_cgroup_evidence.py \
       tests/test_gate_b_parent_child.py tests/test_gate_b_pdf_validation.py -q
# -> 47 passed, 7 skipped (cgroup tests skip off-container)
ruff check app tests ; mypy app
```

## 10. Environment-specific limitations

- Linux enforcement was demonstrated only inside the restricted Docker container (WSL2
  kernel, cgroup v2). On the Windows host, cgroup tests are skipped (`NOT_TESTED`).
- The S2 baseline used default swap; the OOM demonstration required a documented,
  one-off `--memory-swap` deviation (deployment unchanged).
- Aggregate budget experiment is synthetic and enumerated only page content streams.

## 11. Outstanding policy decisions

- **GB-04 (aggregate decompressed/document): stays `PENDING_OWNER_DECISION`** (candidate
  256 MiB technically enforceable; approval pending). GB-05/06/07/10/11/12/13/14/15/
  16/17 remain pending. The six approved GB decisions (01/02/03/08/09/18) are
  unchanged.

## 12. Statuses

```text
GATE_B_S0: IMPLEMENTED
GATE_B_S1: IMPLEMENTED
GATE_B_S2: IMPLEMENTED
GATE_B_S3: DECISION_PACKET_COMPLETE
GATE_B_S4: LAB_VALIDATION_COMPLETE

GB_01: APPROVED_WITH_CONDITIONS
GB_02: APPROVED_WITH_CONDITIONS
GB_03: APPROVED_WITH_CONDITIONS
GB_08: APPROVED_WITH_CONDITIONS
GB_09: APPROVED_WITH_CONDITIONS
GB_18: APPROVED_WITH_CONDITIONS

GB_04: PENDING_OWNER_DECISION
GB_05: PENDING_OWNER_DECISION
GB_06: PENDING_OWNER_DECISION
GB_07: PENDING_OWNER_DECISION
GB_10: PENDING_OWNER_DECISION
GB_11: PENDING_OWNER_DECISION
GB_12: PENDING_OWNER_DECISION
GB_13: PENDING_OWNER_DECISION
GB_14: PENDING_OWNER_DECISION
GB_15: PENDING_OWNER_DECISION
GB_16: PENDING_OWNER_DECISION
GB_17: PENDING_OWNER_DECISION

GATE_B: OPEN / OWNER_DECISION_REQUIRED
UPLOAD_API: NOT_ACTIVATED
REAL_PDF_PROCESSING: NOT_AUTHORIZED

GATE_A: OPEN
GATE_C: OWNER_APPROVAL_REQUIRED
PHASE_4: PLANNED / GATED
PHASE_5: NOT_STARTED
PRODUCTION: NOT_APPROVED
```

`GATE_B_S4: LAB_VALIDATION_COMPLETE` describes completion of **this experiment only**;
it does not close Gate B and does not approve GB-04.
