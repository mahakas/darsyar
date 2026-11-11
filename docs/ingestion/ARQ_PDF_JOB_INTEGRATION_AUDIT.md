# ARQ ↔ PDF Job Integration Audit

**Date:** 2026-11-10. Read-only architecture audit; no implementation authorized.

## 1. Actual worker architecture (path/line references)

- `backend/app/services/worker.py`:
  - `WorkerSettings` (line 156): `functions = [worker_probe]`, `cron_jobs = [expire_reservation_deadlines, recover_orphan_stream_messages]`, `redis_settings = RedisSettings.from_dsn(settings.redis_url)`, `max_jobs = 4`, `job_timeout = 300`.
  - Registered functions: `worker_probe` (line 34), cron `expire_reservation_deadlines` (39), `expire_plan_entitlements` (52), `recover_orphan_stream_messages` (65).
- arq version: **0.28.0**. `enqueue_job` supports `_job_id` (dedup) and `_job_try` (retry/attempts).
- No ingestion job is registered; no `document`/`chunk`/ingestion-job models exist in `app/models/` (verified: only financial/chat/auth/usage models; `index_meta.py` exists but is index metadata, not an ingestion job model).

## 2. ARQ concurrency assessment

- `max_jobs=4` → up to 4 concurrent async tasks in **one process** (arq default single process unless replicas are run separately). This is **not** a PDFium concurrency-safety mechanism.
- `job_timeout=300`s.
- All registered functions are async; none are blocking/CPU-heavy today. A PDFium call would block the event loop if invoked directly in an async job → must run in a child process, not in the arq task.
- Multiple Worker instances/replicas could spawn multiplied subprocess pools — a deployment consideration, no value chosen.

## 3. Idempotency & duplicate delivery

Findings:
- **Queue-level uniqueness:** arq supports `_job_id` for dedup, but this is only used if the caller supplies it; it is **not** currently used for ingestion (no ingestion jobs exist). Redis job ID ≠ durable exactly-once.
- **Database-level idempotency:** no ingestion/document tables exist. Chat/recovery idempotency relies on unique constraints and state transitions, but these are **chat/reservation-specific**, not ingestion-job idempotency.
- **Resource-level identity:** R-157 document identity (`checksum+edition_year+subject+grade`) is designed in docs, **not implemented** (no models).
- **Retry:** `_job_try` exists in arq but no ingestion job uses it; no explicit ingestion retry logic.
- **Exactly-once vs at-least-once:** not defined for ingestion; absence of DB constraints means at-least-once is not safely handled today.

## 4. Option C supervisor feasibility

Proposed: `ARQ Job → Async Supervisor → Bounded Spawned PDFium Workers → Structured Result → Database State Update`.

- `spawn` method: feasible (Windows/Linux). Parent uses `multiprocessing.get_context("spawn")`.
- Per-child serialization: a child runs one PDFium op at a time; no cross-process PDFium handles/objects shared.
- Worker-pool ownership/lifecycle, parent cancellation, child timeout/forced termination, crash detection, replacement: all **not implemented** (design only).
- **Critical risk:** Python asyncio task cancellation does NOT terminate a child process. If an ARQ job times out/cancels, a child may remain alive (orphaned PDFium op). A supervisor must explicitly `terminate()`/`kill()` the child and join it; parent shutdown must reap children. This is a required safeguard, not present today.
- IPC/temp cleanup: bounded result + controlled temp dirs required; not implemented.
- Multiple ARQ instances → multiplied child pools; require a pool bound + deployment control.

## 5. Failure / recovery matrix

| Failure | Existing behavior | Required for PDF jobs | Evidence / gap |
|---|---|---|---|
| Duplicate enqueue | arq `_job_id` possible, unused | Use durable `_job_id`/DB unique | NOT_IMPLEMENTED |
| Duplicate execution | no ingestion DB constraints | DB idempotent transition | NOT_IMPLEMENTED |
| Worker shutdown | main app drain exists (chat) | supervisor reaps children on shutdown | GAP |
| ARQ task cancellation | asyncio cancel does not kill child | supervisor terminate+join child | GAP |
| Job timeout | `job_timeout=300` (no child handling) | per-job timeout → terminate child | GAP |
| Child native crash | none | parent detects exit, replaces, structured error | NOT_IMPLEMENTED |
| Child OOM | none | exit detection + replacement | NOT_IMPLEMENTED |
| Parent process crash | chat/ecovery recovery only | ingestion job recoverable via DB state | NOT_IMPLEMENTED |
| DB commit failure | rollback patterns exist | transaction rollback + retry | PARTIAL |
| Redis interruption | arq depends on Redis | queue-level; DB remains source of truth | DESIGNED |
| IPC failure | none | structured error + cleanup | NOT_IMPLEMENTED |
| Orphaned temp files | none | controlled temp cleanup | NOT_IMPLEMENTED |

## 6. Recommended integration contract (proposal)

- Durable ingestion job identity (DB unique on R-157 id).
- Idempotent state transitions (`pending→processing→ready|failed|needs_review`).
- Parent-owned subprocess supervisor bound to the ARQ job lifecycle.
- Explicit `spawn` context; bounded child capacity; one active PDFium op per child.
- Per-job timeout + cancellation → child terminate/join (never rely on task cancel alone).
- Structured child success/failure response; parent-owned DB updates; recovery after worker restart; safe repeated ARQ delivery.

Capabilities vs future: any existing (arq, DB session, state patterns) vs **not implemented** (ingestion models, supervisor, idempotent ingestion transitions, child lifecycle, IPC contract). A durable design proposal addressing these gaps is in `INGESTION_JOB_IDEMPOTENCY_DESIGN.md` (READY_FOR_OWNER_DESIGN_REVIEW).

## 7. Architectural verdict

**`BLOCKED_BY_MISSING_IDEMPOTENCY_OR_RECOVERY`** — no ingestion job, no durable ingestion/idempotency schema, and no subprocess supervisor exist today. The Chat-stream heartbeat/orphan recovery is **not** transferable to ingestion-job idempotency. Option C requires these gaps to be addressed first. (Not an owner decision; Option C not selected.)

## 8. Evidence references

- `backend/app/services/worker.py` (WorkerSettings, functions, cron, max_jobs, job_timeout).
- arq 0.28.0 `enqueue_job` signature (`_job_id`, `_job_try`).
- `backend/app/models/` (no ingestion models), `backend/app/core/config.py` (chunk settings exist = design only).
- Docs: `PDFIUM_CONCURRENCY_DECISION.md`, `GATE_A_RENDERER_DECISION.md`, `OWNER_DECISIONS.md`, `PHASE4_INGEST_PILOT.md`, `ARCHITECTURE.md`.
