# Durable Ingestion Jobs, Idempotency and Recovery Architecture

**Date:** 2026-11-10. Architecture design only; no implementation authorized.

## 1. Existing architecture findings (paths/lines)

- `backend/app/services/worker.py` (WorkerSettings, `functions=[worker_probe]`, `max_jobs=4`, `job_timeout=300`; arq 0.28.0 with `_job_id`/`_job_try`).
- `backend/app/models/`: no ingestion/document/chunk models exist. Latest migration `0017_stream_lease_billable`.
- R-157: document key `(checksum, edition_year, subject, grade)`; R-150 chunk provenance; R-156 document states.
- `docs/ingestion/ARQ_PDF_JOB_INTEGRATION_AUDIT.md` verdict `BLOCKED_BY_MISSING_IDEMPOTENCY_OR_RECOVERY`; `PDFIUM_CONCURRENCY_DECISION.md` proposes Option C.
- `.specify/memory/constitution.md` does not exist; governance is AGENTS + accepted ADRs.

## 2. Architectural principles

1. PostgreSQL = durable source of truth for ingestion jobs/state.
2. Redis/ARQ = delivery/execution queue, not authoritative store.
3. Tolerate duplicate delivery.
4. Do **not** promise exactly-once; design at-least-once + durable idempotent effects.
5. DB transactions protect critical transitions.
6. Worker/subprocess crash must not silently lose a job.
7. Old attempts must not overwrite newer successful attempt.
8. Authorization + provenance checks precede protected PDF operations.
9. PDFium child process must **not** own DB transactions or update DB.

## 3. Document identity vs request idempotency

- **Document identity (R-157):** canonical unique on `(checksum, edition_year, subject, grade)`. Resource identity is enforced via a DB unique constraint on those four fields. Do not let dedup erase distinct authorization/provenance/source-origin records — keep those on the document/authorization record, not lost by dedup.
- **Request idempotency (separate):** an explicit `request_idempotency_key` scoped to (requesting user/admin, operation) + normalized `request_hash`. Same key + same request → return existing job; same key + different hash → conflict; retry/reprocessing under a new `pipeline_version`; duplicate API requests and duplicate ARQ delivery handled.
- **Why ARQ `_job_id` alone is insufficient:** `_job_id` is queue-scoped dedup, not durable; it does not survive Redis loss, does not carry DB guarantees, and does not prevent duplicate DB effects under at-least-once. Durable idempotency must live in PostgreSQL.

## 4. Proposed durable DB architecture (minimum)

### A. IngestionDocument
- Canonical identity + resource metadata (provenance, publisher, edition_year, subject, grade, checksum, source_origin, state per R-156, authorization_ref). Avoid duplicating provenance already in manifest.

### B. IngestionJob (proposed fields, justified)
- `id` (PK), `document_id` (FK), `request_idempotency_key`, `request_hash`, `status` (job state), `attempt_count`, `pipeline_version`, timestamps (`created_at/updated_at/started_at/finished_at`), `available_at` (delay/backoff), `lease_owner`, `lease_token`, `lease_expires_at`, `last_error_code`, `last_error_summary`.
- Unique: `(request_idempotency_key, document_id)` for request dedup; index on `(status, available_at)` for claim scanning; index on `document_id`; check on `status` allowed set.
- Fields are proposals; identify existing equivalents (R-156 states on document; error codes from R-156).

### C. OutboxEvent
- Transactional outbox: in the **same** DB transaction as job creation, insert an outbox row referencing the job; a dispatcher publishes to ARQ and marks the event acked. Covers publish retry after Redis failure, duplicate publish (unique outbox id + deterministic ARQ job id), and recovery of unpublished events.

## 5. Resource lifecycle vs execution lifecycle

- Document/resource state: preserve R-156 (`pending → processing → ready | failed | needs_review`). Do not reuse these as ARQ execution states.
- **Job state machine (proposed):** `Queued → Running → Retry waiting → Succeeded | Terminal failure`; plus `Cancellation requested → Cancelled`.
  - `Queued → Running` (atomic claim; running if lease available).
  - `Running → Retry waiting` (recoverable failure; attempt_count+1; available_at backoff).
  - `Running → Succeeded` (terminal; valid lease; parent commit).
  - `Running → Terminal failure` (non-retryable error).
  - `Running → Cancellation requested → Cancelled` (user/admin cancellation).
  - Transitions are **not reversible** after terminal states; each transition is a DB transaction with conditions (status + lease ownership).
- No undocumented transitions/statuses invented beyond the above.

## 6. Atomic claim, leases, fencing

- Atomic claim: `SELECT … FOR UPDATE SKIP LOCKED` over jobs in `Queued`/`Retry waiting` and `available_at <= now()`; claim sets `status=Running`, `lease_owner` (worker id), `lease_token` (uuid), `lease_expires_at`.
- Lease heartbeat renews `lease_expires_at` (token-guarded).
- Monotonic fencing: `pipeline_version`/attempt counter; stale worker's results accepted only if it still holds the current valid `lease_token` and its fencing version matches.
- Conditional completion updates: `UPDATE … WHERE id=:id AND status='Running' AND lease_token=:tok` (RETURNING), so a stale/expired attempt cannot overwrite a newer success.
- Lease duration/heartbeat interval: `TO_BE_MEASURED / OWNER_DEPLOYMENT_DECISION_REQUIRED`.

## 7. ARQ integration contract

`DB Job + Outbox → ARQ Delivery → Durable Job Claim → Parent Supervisor → Spawned PDFium Child → Staged Result → Parent Validation → Database Commit`

- Deterministic ARQ job ID: from the outbox/job id (idempotent publish).
- Duplicate delivery: claim is idempotent; duplicate run hits `Running`/completed and no-ops.
- Parent-owned DB access only; child does not touch PostgreSQL.
- Child boundary: `spawn`, one PDFium op per child, bounded pool, per-job timeout, parent cancellation → child terminate/join (never rely on asyncio cancel), structured child result, worker restart/orphan recovery, and bounded total subprocess capacity across multiple ARQ instances (deployment bound).

## 8. Result publication & crash recovery

- Per-job/per-attempt staging dirs; deterministic artifact identity; atomic publish/rename where supported; parent validation before publication; DB transaction when marking resource `ready`; cleanup of incomplete artifacts.
- Recovery: child succeeds but parent crashes before commit → job may be re-claimed; stage idempotent (deterministic artifacts).
- DB commit succeeds but ARQ ack fails → outbox publish-retry dedups; duplicate delivery is safe due to idempotent claim.
- Stale/expired attempt must not overwrite a newer successful attempt (fencing + conditional publish).
- No real textbook content used.

## 9. Failure/recovery matrix

| Case | Detection | Safe state | Recovery | Idempotency protection |
|---|---|---|---|---|
| Duplicate API request | key+hash | existing job returned | return existing | unique(key, document) |
| Duplicate ARQ delivery | `_job_id`/claim | claim already Running/Succeeded | no-op | atomic claim |
| Redis unavailable | publish error | job + outbox persist | dispatcher retry | outbox unique |
| Outbox dispatcher crash | unpublished events | job persists | recovery scan | unique outbox |
| ARQ worker crash | lease expiry | job recoverable | re-claim | lease/fencing |
| Child crash | exit code | job Running | retry/re-place | attempt/fencing |
| Child OOM | exit | job Running | retry | attempt/fencing |
| Job timeout | wall-clock | Running→retry/terminal | terminate child, backoff | lease |
| Cancellation | requested | Cancelled | stop child, cleanup | conditional |
| Stale lease | expiry | recoverable | re-claim | token-guard |
| DB commit failure | exception | rollback | retry | transaction |
| Parent crash after child success | staged result exists | job pending | parent recovery publishes | deterministic artifact |
| Redis ack failure | outbox unpublished | job committed | republish dedup | outbox unique |
| Duplicate chunk insertion | unique chunk identity | skip | no-op | unique(document, chunk_index) |
| Orphaned temps | staged leftover | cleaned | sweep | controlled cleanup |
| Reprocessing new pipeline | version bump | new generation | atomic publish | version/fencing |

## 10. SQLAlchemy / Alembic alignment

- Proposed tables: `ingestion_documents`, `ingestion_jobs`, `outbox_events` (+ staging artifact records). FK, unique constraints (document identity; job request key; outbox id), CHECK constraints (status sets), indexes (claim scan, document_id, status+available_at).
- Transaction boundaries: claim in one txn; completion+publish in one txn (outbox in same txn as state change); staged artifact publish + document `ready` in one txn.
- Migration order: `ingestion_documents` → `ingestion_jobs` → `outbox_events` (append after `0017`). Rollback considerations documented; reversible in design.
- No model/migration code created.

## 11. Missing architectural decisions

- Lease duration / heartbeat interval / retry backoff / max attempts → `OWNER_DEPLOYMENT_DECISION_REQUIRED`.
- Subprocess pool capacity per ARQ instance and across replicas → deployment decision.
- Outbox dispatcher process placement (worker vs separate supervisor).
- Child IPC result contract details.
- Exact `pipeline_version` bump semantics.

## 12. Acceptance criteria (design)

- Durable job identity + idempotent transitions; duplicate delivery no-ops; stale worker rejected; child crash recoverable without loss; no child DB writes; old attempts cannot overwrite newer; outbox retry/recovery; state transitions match matrix; repository aligns with SQLAlchemy/Alembic conventions.

## 13. Sources

AGENTS (R-150/156/157), ARQ_PDF_JOB_INTEGRATION_AUDIT.md, PDFIUM_CONCURRENCY_DECISION.md, PDFIUM_LICENSE_INVENTORY.md, PHASE4_INGEST_PILOT.md, backend/app/services/worker.py, backend/app/models/, alembic/versions/0017.

## 14. Verdict

**`READY_FOR_OWNER_DESIGN_REVIEW`** — coherent design covering durability, idempotency, fencing, outbox, and subprocess integration; numerical/deployment decisions remain for the owner.

**Owner decision: PENDING**

## Slice 2 implementation record (2026-11-10)
- Service ackend/app/services/ingestion_creation.py: transactional job + initial outbox creation.
- Transaction ownership: caller-owned (default commit=False); commit=True for isolated tests.
- Idempotency: same (document_id, key) + same hash -> existing job + creation outbox; different hash -> IdempotencyConflictError; different document same key -> independent.
- Concurrency: unique-constraint race resolved by re-select; one logical job/event.
- Code implemented; PostgreSQL validation BLOCKED (host asyncpg handshake fails; container DB healthy).

## Slice 2 validation (2026-11-10)
- Ephemeral runner on darsyar-ai_default; target postgres/darsyar_test; PostgreSQL 18.6.
- pytest tests/test_ingestion_creation_db.py -q → 9 passed.
- SLICE_2_POSTGRESQL_VALIDATION: PASSED; SLICE_2: CLOSED.
