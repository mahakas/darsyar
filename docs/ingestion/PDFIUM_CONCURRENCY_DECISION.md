# PDFium Process-Isolation Architecture Assessment

**Date:** 2026-11-10. Architecture assessment only. This is **not** an owner decision and does not approve implementation.

## 1. Existing Darsyar architecture (verified)

- FastAPI app with async lifespan + shutdown drain (`active_streams`, `pending_cleanups`, engine dispose).
- arq worker **0.28.0**: `WorkerSettings`, `functions=[worker_probe]`, `cron_jobs`, `max_jobs=4`, `job_timeout=300`.

- Backend Python 3.13; `pypdf` (rag) parser; `Pillow 12.3.0` (rag); proposed renderer `pypdfium2 5.15.2` (conditional candidate). Ingestion pipeline is designed, not implemented.

## 2. Technical baseline

- pypdfium2 5.15.2 = owner-approved **conditional** candidate, not production-approved.
- PDFium is **not thread-safe**: concurrent calls from different threads can crash/corrupt a process (source: official docs, `https://pypdfium2.readthedocs.io/en/stable/python_api.html`, accessed 2026-11-10).
- Official pypdfium2 documentation recommends processes for parallel PDFium workloads.
- Linux/Windows synthetic preflight passed; native memory/crash isolation **not yet validated**; no real textbook processed.

## 3. Option comparison

| Criterion | A: single-process serialized | B: threaded + global mutex | C: bounded spawned subprocess workers | D: one subprocess per job |
|---|---|---|---|---|
| Thread safety | Safe (single-threaded) | Safe for PDFium (mutex), but async threads run | Safe (one child owns PDFium serially) | Safe (one child per job) |
| Parallel throughput | None for PDFium | None for PDFium (serialized) | Bounded parallel across children | Max parallel but high spawn cost |
| Crash containment | Poor (whole process) | Poor (whole process) | Good (child crash isolated) | Good |
| Native memory growth containment | Weak | Weak | Requires recycling | Best (fresh per job) |
| Worker restart/recovery | Process-died | Process-died | Parent replaces child | New child each job |
| Startup overhead | None | Low | Medium (bounded pool) | High (per-job spawn) |
| Memory overhead | Low | Low | Bounded pool | Per-job peak |
| Windows/Linux portability | High | High | Medium (spawn semantics) | Medium |
| arq integration | Trivial | Requires careful async/mutex | Needs subprocess supervisor boundary | Needs per-job spawn supervisor |
| Shutdown/cancellation | With process | Mutex-aware | Kill child on cancel/timeout | Kill child on cancel/timeout |
| Observability | In-process | In-process | Child logs/structured results | Child logs |
| Operational complexity | Low | Medium | Higher | Highest |

## 4. Recommendation

Recommended evaluation candidate: **Option C — bounded spawned subprocess workers**.

- Explicit `spawn` process start method.
- No PDFium handles/document/bitmap/native pointers shared across processes.
- One active PDFium operation per child at a time.
- Strict max worker count; per-job wall-clock timeout; parent-controlled cancellation + child termination; worker health monitoring + replacement after crash; recycling policy to contain native memory growth; bounded input/output sizes; temp output dirs with controlled cleanup; no large image payloads via IPC unnecessarily; structured failure results.

Controls split:
- **Architectural recommendations:** spawn method; no cross-process PDFium state; one op per child; parent-coordinated cancellation/timeout; structured results; replacement after crash.
- **Require implementation/testing:** worker count, memory limits, timeout values, recycling threshold → `OWNER/DEPLOYMENT DECISION REQUIRED` or `TO_BE_MEASURED`. No values invented here.

## 5. arq integration assessment

- arq runs async tasks; with `max_jobs=4` there can be 4 concurrent async tasks in **one process**. If PDFium were called directly in those async tasks, it could be invoked in parallel → unsafe. Therefore a **subprocess boundary / spawned-process supervisor** is required so PDFium work runs in isolated children, not in the arq process's threads.
- Parent (arq job) should orchestrate a child: spawn, submit a single job, wait with timeout, cancel by terminating the child, collect structured result, replace crashed child.
- Worker cancellation/timeout must terminate the stuck child (not leave an orphaned native call). A crashed child must be replaced **without silently losing/duplicating a job** — job identity must survive via the existing idempotency/retry rules.
- Missing information to confirm in repo: how arq will host the subprocess supervisor (worker-facing service vs per-job spawn) and the exact IPC/return contract; this is a design gap to resolve before implementation. See `ARQ_PDF_JOB_INTEGRATION_AUDIT.md` (verdict: `BLOCKED_BY_MISSING_IDEMPOTENCY_OR_RECOVERY`).

## 6. Failure & resource lifecycle

Expected lifecycle:
1. Validate job metadata + authorization before any PDF work.
2. Start/acquire isolated child process.
3. Process only inside the child boundary.
4. Close all PDFium/Python resources deterministically.
5. Return bounded result or structured error.
6. Terminate/recycle the child per policy.
7. Parent records outcome and recovers.

Failure scenarios addressed: malformed PDF (controlled rejection), native crash (child dies; parent replaces), child timeout (parent terminates), parent cancellation (terminate child), worker shutdown (reap children), child OOM (terminate), IPC failure (structured error), duplicate job delivery (idempotency), orphaned temp files (controlled cleanup). None executed against real PDFs.

## 7. Decision record (owner)

- Recommended option: C
- Recommendation status: `PROPOSED_NOT_APPROVED`
- Selected option: `OWNER_DECISION_PENDING`
- Process start method: `PROPOSED_SPAWN`
- Worker count: `OWNER/DEPLOYMENT_DECISION_REQUIRED`
- Timeout policy: `OWNER/DEPLOYMENT_DECISION_REQUIRED`
- Memory limits: `OWNER/DEPLOYMENT_DECISION_REQUIRED`
- Recycling threshold: `TO_BE_MEASURED`
- Production implementation: `NOT_AUTHORIZED`
- **Owner decision: PENDING**

## 8. Future validation plan (synthetic only until authorized)

- Synthetic multi-process concurrency stress test.
- Repeated create/render/close lifecycle test.
- Child crash + parent recovery test.
- Timeout and cancellation test.
- Memory-growth measurement over repeated jobs.
- Worker shutdown/restart test.
- Windows and Linux process-start compatibility.
- Resource-limit enforcement test.
- No shared PDFium object/state across processes.

All use synthetic PDFs until the authorization gate permits real-textbook tests.

## Governance (preserved)

- Gate A OPEN; pypdfium2 `OWNER_APPROVED_CONDITIONAL_CANDIDATE`; production `NOT_APPROVED`; Gate B OPEN/OWNER_DECISION_REQUIRED; Gate C OWNER_APPROVAL_REQUIRED; Phase 4 Planned/Gated; Phase 5 Not Started; concurrency_model owner_decision_pending; real-textbook validation not_run; 13529 pending_evidence_and_scope_review; manifests needs_review.
