# Durable Ingestion Job — Implementation Specification

**Date:** 2026-11-10; implementation status refreshed 2026-11-12. This specification tracks the durable ingestion lifecycle from persistence through synthetic artifact staging; see the Statuses section for merged and in-review slices.

Statuses:
- `CONCEPTUAL_ARCHITECTURE: APPROVED_WITH_CONDITIONS` (owner, 2026-11-10)
- `IMPLEMENTATION_SPECIFICATION: OWNER_APPROVED_WITH_CONDITIONS` (owner authorized implementation, 2026-11-10; Slice 1 only)
- `SLICE_1_PERSISTENCE: IMPLEMENTED` (2026-11-10)
- `SLICE_2_CODE: IMPLEMENTED` (service + tests written; ruff/mypy clean)
- `SLICE_2_POSTGRESQL_VALIDATION: PASSED` (2026-11-10: 9/9 in ephemeral runner on `darsyar_test`, PostgreSQL 18.6)
- `SLICE_2: CLOSED`
- `SLICE_3_OUTBOX_PUBLISHER: CLOSED` (2026-11-11; PostgreSQL + Redis/ARQ synthetic validation 13/13; see `SLICE_3_OUTBOX_PUBLISHER_IMPLEMENTATION.md`)
- `SLICE_4_CLAIM_LEASE_FENCING: IMPLEMENTED` (2026-11-12; PostgreSQL CI: 528 passed, 21 skipped, 1 warning; commit merged via PR #21)
- `SLICE_6_STAGING_ARTIFACT_LIFECYCLE: IMPLEMENTATION_UNDER_REVIEW` (PR #22; synthetic-only; CI pending; not operational intake or document processing)
- `RUNTIME_CONFIGURATION: PENDING_OWNER_APPROVAL`
- `LICENSING_AND_AUTHORIZATION: PENDING`
- `PRODUCTION: NOT_APPROVED`

Execution model: **at-least-once**. Do not claim or design exactly-once execution; idempotency is achieved through durable, idempotent database effects.

## Current implementation status — 2026-11-12

- Slice 1–3 (durable persistence, transactional creation, manual outbox publisher/reconciliation) are implemented and closed with synthetic PostgreSQL/Redis evidence.
- Slice 4 (atomic claim, lease renewal, fencing, retry/failure, cancellation and expired-cancellation finalization) is implemented in `backend/app/services/ingestion_jobs.py`; PostgreSQL tests use unique synthetic job types. CI run [43246224745](https://github.com/mahakas/darsyar/actions/runs/43246224745): Backend 528 passed, 21 skipped, 1 warning; Ruff, mypy, migration smoke, frontend, SIGTERM, Nginx and report-only supply-chain jobs passed. RAG evaluation was skipped because the reviewed golden dataset is not present.
- Slice 5 Parent/Child remains a synthetic Gate B-S1 prototype, not an ARQ-integrated execution path.
- Slice 6 staging artifact lifecycle is the next synthetic-only implementation slice; it must pass its own PostgreSQL and adversarial filesystem tests before closure.

These code slices do not authorize a real PDF or register an ARQ consumer.

## A. Existing-system compatibility audit (verified)

- **SQLAlchemy:** async, 2.x `Mapped[]`/`mapped_column` (e.g., `app/models/reservation.py`), `Base` from `app.db.base`; `DateTime(timezone=True)`; `gen_random_uuid()`; check/unique constraints via `__table_args__`.
- **Alembic:** versions in `backend/alembic/versions/`; the initial compatibility baseline was `0017_stream_lease_billable`; `main` has since advanced through `0023_admin_audit_append_only` as of 2026-11-12. Tests use `alembic upgrade head` (`make test-db`) on PostgreSQL only.
- **ARQ:** `backend/app/services/worker.py` `WorkerSettings` (`functions=[worker_probe]`, cron, `max_jobs=4`, `job_timeout=300`, arq 0.28.0 with `_job_id`/`_job_try`). No ingestion job registered.
- **Redis:** used via `RedisSettings.from_dsn(settings.redis_url)`; arq delivery only.
- **Transactions:** async sessions + commit/rollback; existing patterns (reservation/recovery) — chat/heartbeat recovery is **not** reusable verbatim for ingestion idempotency.
- **Logging/observability:** structured logs (`get_logger`), metrics registry (`core/metrics.py`).
- **Tests:** `tests/conftest.py` uses real PostgreSQL + Alembic; DB-gated tests exist. SQLite prohibited.

## B. Durable data model (proposed)

**ingestion_jobs**
- `id` uuid PK; `job_type` string; `schema_version` int; `status` string (job state); `document_id` uuid FK→ingestion_documents; `request_idempotency_key` string; `request_hash` string; `attempt_count` int; `lease_owner` string null; `lease_token` uuid null; `lease_expires_at` timestamptz null; `heartbeat_at` timestamptz null; `fencing_token` bigint (monotonic); `retry_available_at` timestamptz; `last_error_code`, `last_error_summary`; `cancellation_requested` bool; `created_at/started_at/updated_at/finished_at`.
- Unique: `(document_id, request_idempotency_key)`; check `status IN (...)`.

**outbox_events**
- `id` uuid PK; `event_type`; `schema_version`; `job_id` FK; `dedup_key` (stable unique); `payload` jsonb; `publication_state` (`pending/publishing/published/failed`); `attempt_count`; `available_at`, `published_at`; `last_error_details`.
- Unique `dedup_key`.

**ingestion_documents**
- Canonical R-157 unique `(checksum, edition_year, subject, grade_level)`; provenance + authorization refs kept on separate related records so dedup never erases them.

Indexes for: claim scan (`(status, retry_available_at)`), expired leases (`lease_expires_at`), unpublished outbox (`(publication_state, available_at)`), idempotent request (`(document_id, request_idempotency_key)`), reconciliation (jobs not delivered/claimed).

## C. Separate identity

- Canonical document identity = R-157 `checksum + edition_year + subject + grade`.
- Provenance/authorization live on separate multi-valued records (no identity change).
- Request idempotency independent (`request_idempotency_key`+`request_hash`); repeated same request returns existing job; different hash → conflict.
- Respect R-150/R-156/R-157, ADR-024/037/038; no auto legacy grade mapping.

## D. Job lifecycle & transaction boundaries

- Resource lifecycle (R-156) is **separate** from job state. Job states: `Queued → Running → {Retry waiting | Succeeded | Terminal failure}` + `Cancellation requested → Cancelled`.
- Atomic creation: insert job + outbox event in one transaction.
- Outbox eligibility → publish → ARQ.
- If publish succeeds but outbox ack fails: republish is safe via `dedup_key`; duplicate delivery handled by idempotent claim.
- Claim: `SELECT … FOR UPDATE SKIP LOCKED` on eligible jobs; set `Running`, `lease_owner`, `lease_token`, `lease_expires_at`, `fencing_token+=1`.
- Heartbeat renews lease (token-guarded).
- Every consequential commit re-checks `status='Running'` + `lease_token` + `fencing_token`.
- Success / retryable / permanent failure committed separately; never rely on Redis job id alone.

## E. Outbox publisher & reconciliation

- Multiple concurrent publishers safe via unique dedup_key + transactional claim of outbox rows.
- Crash cases: before enqueue (retry), after enqueue before ack (republish dedup), duplicate delivery (idempotent), Redis outage (retry later), lost/unclaimed ARQ message (reconciliation rescans unpublished/unclaimed).
- Reconciliation reads PostgreSQL outbox/jobs; no invented intervals/limits.

## F. Lease, heartbeat, fencing

- Fencing token persists and increments per claim; checked on all consequential commits.
- Expired lease detection reclaims work; stale worker rejected by token/fencing (lease expiration alone insufficient because a stale child may still be alive and writing artifacts).

## G. Parent supervisor & child protocol

- Parent owns all DB, lease, heartbeat, child start/monitor/terminate, result validation, fencing, final commit, staging cleanup.
- Child: receives minimal task input; **no DB credentials/access**; returns structured status + artifact metadata; never commits state.
- Versioned IPC request/response (error categories + artifact metadata). No fixed process counts/limits (owner pending); no fixed start method assumed beyond approved Option C direction.

## H. Staging, validation, publication

- Implementation-neutral staging boundary; unique artifact names; metadata + checksum validation; validation-failure handling; atomic/recoverable publication; idempotent cleanup; recovery across artifact-creation→commit and commit-failure; stale attempts cannot publish (fencing). No unapproved storage infra/migration.

## I. Retry & recovery policy

- Retryable vs permanent categories; configurable retry/backoff (values owner-pending).
- Covers worker crash, child crash, parent cancellation, Redis/PostgreSQL outage, expired lease, invalid/incomplete artifact, repeated-failure/max-attempt, manual admin recovery.
- Authorization/licensing failures are **not** ordinary retryable processing errors.

## J. Security & authorization

- No real textbook processing; no OCR/render/extract/embed/index/retrieve pilot PDFs; reference 13529 not treated as independently verified/sufficient; no legal clearance; Gate A/B/C unchanged; no production dependency/deployment approval; API responses free of `organizationReference`; synthetic-only test data.

## K. Observability & administration

- Structured logs + metrics for job creation, outbox publish, claim, lease renewal, fencing rejection, child start/exit, artifact validation, retry/recovery, final transitions. Correlation id spans request→job→outbox→ARQ→attempt→child. No credentials/sensitive/raw content logged.

## L. Test plan & acceptance criteria (synthetic/PostgreSQL)

1. Atomic job+outbox creation. 2. Repeated idempotent request → no duplicate work. 3. Concurrent publishers lose no events. 4. Crash after enqueue → safe duplicate delivery. 5. Concurrent workers cannot claim same active job. 6. Expired lease recovery. 7. Fencing rejects stale commits. 8. Heartbeat renewal. 9. Child crash detected. 10. Child cancel/terminate verified. 11. Parent-only DB ownership. 12. Invalid/corrupt staging artifacts rejected. 13. Artifact publication recoverable after interruption. 14. Reconciliation recovers undelivered/unclaimed work. 15. Resource lifecycle valid and independent of job state. 16. No real pilot PDF opened/processed.
PostgreSQL integration tests (not SQLite); synthetic fixtures + fakes for child protocol.

## M. Implementation sequence (dependency-ordered)

1. Durable job + outbox persistence (models/migration schema).
2. Transactional job creation + request idempotency.
3. Outbox publisher + reconciliation.
4. Durable claim/lease/fencing.
5. Parent supervisor + fake child protocol.
6. Staging artifact lifecycle + recovery.
7. ARQ integration + PostgreSQL integration tests.
8. Observability + admin recovery.

Each slice: objective, likely files (based on inspected repo), dependencies, acceptance criteria, tests, exclusions.

- Slices 1–6 and 8 can proceed **without Gate A / textbook authorization** (synthetic only).
- Slice 7 ARQ integration is blocked until deployment config + licensing/authorization are resolved; real-textbook processing remains blocked.

## Runtime parameters (PENDING_OWNER_APPROVAL)

| Parameter | Why it matters | Measurement/test needed | Evidence required | Status |
|---|---|---|---|---|
| ARQ worker count | concurrency ceiling | load test | measured | PENDING_OWNER_APPROVAL |
| Max concurrent ingestion jobs | bounded work | load test | measured | PENDING |
| Child-process capacity | PDFium parallelism | stress test | measured | PENDING |
| Lease duration | reclaim dead workers | timeout test | measured | PENDING |
| Heartbeat interval | liveness | lease test | measured | PENDING |
| Child execution timeout | stuck child | timeout test | measured | PENDING |
| Memory/CPU limits | containment | resource test | measured | PENDING |
| Retry limits / backoff | convergence | failure tests | measured | PENDING |
| Recycling thresholds | memory containment | long-run | measured | PENDING |
| Staging retention/cleanup | temp lifecycle | cleanup test | measured | PENDING |

## Governance (preserved)

Gate A OPEN; pypdfium2 `OWNER_APPROVED_CONDITIONAL_CANDIDATE`; production `NOT_APPROVED`; Gate B OPEN/OWNER_DECISION_REQUIRED; Gate C OWNER_APPROVAL_REQUIRED; Phase 4 Planned/Gated; Phase 5 Not Started; concurrency_model owner_decision_pending; real-textbook validation not_run; 13529 pending_evidence_and_scope_review; manifests `needs_review`.
