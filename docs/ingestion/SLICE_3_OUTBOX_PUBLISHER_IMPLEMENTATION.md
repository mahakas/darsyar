# Slice 3 — Transactional Outbox Publisher & Reconciliation (Implementation)

**Date:** 2026-11-10. Implementation spec for the bounded Slice 3, synthetic-only.

Statuses:
- `S-1: OWNER_APPROVED_WITH_CONDITIONS` (2026-11-10)
- `S-2: OWNER_APPROVED_WITH_CONDITIONS` (2026-11-10)
- `SLICE_3_CODE: IMPLEMENTED`
- `SLICE_3_POSTGRESQL_VALIDATION: PASSED` (2026-11-10, `darsyar_test`, PG 18.6)
- `SLICE_3_REDIS_ARQ_VALIDATION: PASSED` (2026-11-10, dedicated `arq:queue:ingestion` namespace)
- `SLICE_3: CLOSED`
- `RUNTIME_CONFIGURATION: PENDING_OWNER_APPROVAL`
- `LICENSING_AND_AUTHORIZATION: PENDING`
- `PRODUCTION: NOT_APPROVED`

---

## 1. Owner approvals (recorded)

| ID | Decision | Date | Scope |
|---|---|---|---|
| S-1 | `APPROVE_WITH_CONDITIONS` | 2026-11-10 | Bounded Slice 3 implementation (Outbox Publisher and Reconciliation) |
| S-2 | `APPROVE_WITH_CONDITIONS` | 2026-11-10 | Publication of synthetic ingestion events to ARQ and testing actual delivery through existing Redis infrastructure |

**Does NOT authorize:** a real PDF ingestion consumer/worker; processing real textbook documents; PDFium execution; production deployment; unapproved numerical runtime settings; unapproved schema changes.

Preserved decisions (unchanged): `R-1 = OWNER_DECIDED_OPTION_B` (future `ON DELETE RESTRICT`); `R-2 = OWNER_APPROVED` (no job deletion while outbox history subject to retention); `R-3 = OWNER_DECIDED_DEFER_ARCHIVAL` (archival deferred). Migration `0018` still uses `ON DELETE CASCADE`; the R-1 RESTRICT migration is not implemented; none of R-1/R-2/R-3 independently authorize schema changes.

---

## 2. Scope

1. PostgreSQL-backed discovery of unpublished outbox events.
2. Safe coordination between concurrent publishers.
3. Actual ARQ message publication through the existing Redis infrastructure.
4. At-least-once publication semantics.
5. Stable ARQ job identity derived from the outbox deduplication identity.
6. Duplicate publication tolerance.
7. Recovery after Redis publication succeeds but PostgreSQL publication-state commit fails.
8. Reconciliation of eligible unpublished events.
9. Structured logging and observability.
10. Focused PostgreSQL and Redis integration tests.

The publisher only delivers events; it does not execute textbook ingestion.

---

## 3. Design audit (existing schema compatibility)

Inspected: `backend/app/models/outbox_event.py`, `backend/app/models/ingestion_job.py`, `backend/app/services/ingestion_creation.py`, `backend/app/services/worker.py`, `backend/alembic/versions/0018_ingestion_persistence.py`.

| Question | Finding |
|---|---|
| Available publication states | `pending`, `publishing`, `published`, `failed` (`ck_outbox_events_state_valid`) |
| Attempt counter semantics | `attempt_count INTEGER NOT NULL DEFAULT 0`; `ck_outbox_events_attempt_nonneg` |
| `available_at` / `published_at` | `available_at timestamptz NOT NULL DEFAULT now()`; `published_at timestamptz NULL` |
| Unique dedup constraint | `uq_outbox_events_dedup` on `dedup_key` |
| Claim index | `ix_outbox_events_claim (publication_state, available_at)` |
| Transaction/session ownership | Caller-owned `AsyncSession`; `commit=False` default convention (e.g. `ingestion_creation.py`) |
| ARQ RedisSettings / queue | arq 0.28.0; `create_pool(RedisSettings.from_dsn(url))`; default queue `arq:queue` |
| Safe concurrent publisher with current schema? | Yes — `FOR UPDATE SKIP LOCKED` within a single short transaction (no schema change needed) |

No model columns or state values were invented. No schema/migration change is required or made.

---

## 4. Publisher / ARQ contract

- **Function name (contract, not registered):** `process_ingestion_event` (constant `INGESTION_EVENT_FUNCTION`). No consumer is registered; no worker executes it in this slice.
- **Queue:** `arq:queue:ingestion` (constant `INGESTION_EVENT_QUEUE`), distinct from the general application Worker's default `arq:queue`. The general Worker does not consume this queue.
- **Stable identity:** deterministic ARQ `_job_id = "ingestion:" + <identifier derived from dedup_key>` (dedup_key format `create:<job_id>`). Bounded, reproducible, and used for enqueue dedup.
- **Minimal versioned payload:** `event_id`, `job_id`, `dedup_key`, `event_type`, `schema_version`, `contract_version` (`PUBLISH_CONTRACT_VERSION = 1`). No credentials, raw document content, or unnecessary personal information.
- **Version gate:** `event_type` must be in `("ingestion_create",)` and `schema_version` in `(1,)`. Unsupported contracts fail permanently (state `failed`).
- **Enqueue semantics (arq):** `enqueue_job(..., _job_id=..., _queue_name=...)` returns a `Job` or `None` when a job with that ID already exists (queue or result key). None ⇒ the message is already present ⇒ tolerated as success.

---

## 5. Queue isolation

- Publisher uses a dedicated Redis ZSET key `arq:queue:ingestion`; the general Worker consumes `arq:queue` only.
- Integration tests target a dedicated Redis logical DB (15) and the isolated queue namespace; only test-owned keys are cleaned; nothing is flushed; the application Worker queue is never touched.

---

## 6. At-least-once semantics

PostgreSQL and Redis cannot participate in a single atomic distributed transaction; **exactly-once is not claimed**. Delivery is at-least-once:

- `A. PostgreSQL commit before Redis publication:` event stays `pending` until successful publication.
- `B. Redis publication succeeds, PostgreSQL commit fails:` the event may be published again; the deterministic ARQ job ID reduces duplicate queue entries while the corresponding ARQ job remains present. Downstream idempotency remains required; ARQ job IDs alone do not guarantee exactly-once execution.
- `C. Redis unavailable:` event is not marked published; it is preserved for later reconciliation; safe failure metadata is recorded (`last_error_details`, `attempt_count+1`), state remains `pending`.
- `D. PostgreSQL unavailable:` no successful publication state is claimed; the DB failure is classified/propagated (`OutboxPublishCommitError` + `outbox_pg_commit_failure_after_enqueue`); the event is not silently dropped.
- `E. Concurrent publishers:` a PostgreSQL-backed mechanism (`FOR UPDATE SKIP LOCKED`) prevents two publishers from processing the same event in a way that loses or corrupts publication state.
- `F. Permanent vs retryable:` structured categories — retryable/transient (Redis/network) keep the event `pending`; permanent (unsupported contract) transition to `failed`. No arbitrary retry limits/backoff numbers are invented; no licensing/authorization failures are treated as ordinary processing retries.

---

## 7. Recovery & reconciliation

- One-shot `reconcile_pending_outbox_events(...)` reuses the publisher contract.
- Reconciliation is idempotent: `published` records are never republished; reruns produce safe results; transient failures do not lose pending work; no deletion/archival occurs.
- Recovery of enqueue-success-but-commit-failure is achieved by re-selecting the still-`pending` event and re-enqueuing with the same deterministic `_job_id` → arq returns `None` ⇒ dedup, then state committed to `published`.
- Reconciliation never claims a published ARQ message was consumed or processed.

---

## 8. Concurrency mechanism

Within one short PostgreSQL transaction:

1. `SELECT ... WHERE publication_state IN ('pending') AND available_at <= now() ORDER BY available_at, id LIMIT :batch FOR UPDATE SKIP LOCKED` — atomically claims disjoint rows; concurrent publishers skip locked rows.
2. For each claimed row: validate contract → enqueue to ARQ (dedicated queue) → on success `UPDATE ... SET publication_state='published', published_at=now(), attempt_count=attempt_count+1`; on transient Redis failure `UPDATE ... SET publication_state='pending', last_error_details=..., attempt_count=attempt_count+1`; on permanent failure `UPDATE ... SET publication_state='failed', ...`.
3. `COMMIT` at the end.

**Trade-off evaluated explicitly:** this design holds the row lock across the bounded Redis call. Because `enqueue_job` is a Redis command bounded by the client connection timeout, the lock hold is short (typically milliseconds). Alternatives requiring a committed intermediate `publishing` claim plus staleness-based recovery were rejected because the current outbox schema has **no lease/timestamp claim columns**, so a committed `publishing` state would be unrecoverable without inventing a staleness threshold (which is a runtime number not approved). The single-transaction approach is crash-safe: any failure before/at commit rolls back and the event remains `pending` — there is no stuck transient state. No schema change is required.

---

## 9. Implementation files

Added:
- `backend/app/repositories/outbox_events.py` — claim (`FOR UPDATE SKIP LOCKED`), `mark_published`, `record_transient_failure`, `record_permanent_failure`.
- `backend/app/services/outbox_publisher.py` — `publish_pending_outbox_events`, `run_outbox_publisher`, `PublishResult`, contract/queue constants, deterministic `_job_id`.
- `backend/app/services/outbox_reconciliation.py` — `reconcile_pending_outbox_events`.
- `backend/tests/test_outbox_publisher_db.py` — PostgreSQL + Redis/ARQ integration tests.

Modified:
- `backend/app/core/metrics.py` — added low-cardinality outbox metrics (published/deferred/failed/duplicate/commit-failure/invocations/reconciliation/discovered), included in Prometheus text output.

No migrations or schema changes (authorization not needed and not granted).

---

## 10. Observability

Structured JSON logs (`get_logger`) and metrics (`METRICS`):

- Publisher invocation, eligible-event claim count.
- Publication start/success/failure.
- Duplicate enqueue (`outbox_duplicate_enqueue`).
- PostgreSQL commit failure after enqueue (`outbox_pg_commit_failure_after_enqueue`).
- Reconciliation attempt/result.
- Concurrent claim/skip (claim result logged per run; contended rows are skipped by `SKIP LOCKED`).

Correlation identifiers: `attempt_id` (per-run UUID), `event_id`, `job_id`, `dedup_key`, `arq_job_id`, `source` (`publish`/`reconciliation`). No secrets, DB URLs, credentials, or raw document content are logged.

---

## 11. Runtime parameters remaining pending

| Parameter | Status |
|---|---|
| Publisher `batch_size` | Required function input (no implicit default). **B1 = OWNER_APPROVED_WITH_CONDITIONS (2026-11-11): `batch_size=50` approved for explicit manual one-shot invocation only.** |
| Automatic publisher scheduling cadence | **NOT_AUTHORIZED** — B2 = OWNER_APPROVED_MANUAL_ONE_SHOT (2026-11-11); manual explicit one-shot is the approved initial mode; no cron registered; one-shot services are callable but not invoked by B2 |
| Publisher timeouts / retry / backoff / concurrency ceilings | No values set; **B3 = OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11)** — deferred until scheduling/Production. See `OUTBOX_PUBLISHER_RUNTIME_PARAMETERS.md` |
| ARQ worker/capacity/retry/backoff numbers | Unchanged; PENDING_OWNER_APPROVAL |

The publisher makes no periodic calls and does not self-schedule. **Owner decision B2
= `APPROVE_MANUAL_ONE_SHOT`** (2026-11-11) approves manual, explicit, one-shot
invocation as the initial operating mode; automatic scheduling and ARQ cron
registration are not authorized. **Owner decision B1 = `OWNER_APPROVED_WITH_CONDITIONS`**
(2026-11-11) approves `batch_size=50` for explicit manual one-shot invocation only:
the value stays a required explicit argument (no default/fallback/injection). Live
publication of currently pending application Outbox events is NOT authorized by B1/B2,
and no real ingestion consumer is registered. B3 (other runtime parameters) remains
deferred until scheduling/Production is considered — see `OUTBOX_PUBLISHER_RUNTIME_PARAMETERS.md`.

---

## 12. Tests executed

Command (disposable runner on `darsyar-ai_default`, PG 18.6, isolated Redis DB 15):
`pytest -p no:cacheprovider tests/test_outbox_publisher_db.py -q` → **13 passed, 0 failed, 0 skipped**.

Covered scenarios: single pending event discovered+published; successful enqueue followed by publication-state commit; reconciliation does not republish completed events; stable dedup ⇒ stable ARQ job id; Redis unavailable leaves event recoverable; PostgreSQL commit failure does not report false success; enqueue-success-then-commit-failure recoverable; duplicate delivery tolerated; concurrent publishers coordinate (no loss/duplication); published events do not return to pending; malformed/unsupported contract fails safely; no Job/Outbox deletion; existing application Worker functions unchanged.

Full ingestion set (Slices 1+2+3): **36 passed**. `mypy app` clean (113 files); `ruff check app` clean.

---

## 13. Application health

API `/health` → 200; Worker running (`arq app.services.worker.WorkerSettings`, default queue, cron intact); PostgreSQL/Redis healthy. No production/consumer/workflow changes were made; no automatic publisher scheduling is active.

---

## 14. Schema limitations (R-1/R-2/R-3)

- **R-1 implemented and applied:** migration `0019_outbox_job_fk_restrict` changed `fk_outbox_events_job` to `ON DELETE RESTRICT`, validated on `darsyar_test` and applied to the application database `darsyar` (2026-11-11; revision `0019`, FK RESTRICT). Production not migrated.
- Publisher never deletes outbox/job records and adds no archival/cleanup.
- Exactly-once is not provided; at-least-once requires downstream idempotency.

---

## 15. Final status

```text
R-1: OWNER_DECIDED_OPTION_B
R-2: OWNER_APPROVED
R-3: OWNER_DECIDED_DEFER_ARCHIVAL
S-1: OWNER_APPROVED_WITH_CONDITIONS
S-2: OWNER_APPROVED_WITH_CONDITIONS
SLICE_1_PERSISTENCE: IMPLEMENTED
SLICE_2: CLOSED
SLICE_3_CODE: IMPLEMENTED
SLICE_3_POSTGRESQL_VALIDATION: PASSED
SLICE_3_REDIS_ARQ_VALIDATION: PASSED
SLICE_3: CLOSED
B2: OWNER_APPROVED_MANUAL_ONE_SHOT
B1: OWNER_APPROVED_WITH_CONDITIONS
B3: OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION
APPROVED_MANUAL_BATCH_SIZE: 50
AUTOMATIC_PUBLISHER_SCHEDULING: NOT_AUTHORIZED
LIVE_APPLICATION_OUTBOX_PUBLICATION: NOT_AUTHORIZED
REAL_INGESTION_CONSUMER: NOT_REGISTERED
RUNTIME_CONFIGURATION: PENDING_OWNER_APPROVAL
LICENSING_AND_AUTHORIZATION: PENDING
PRODUCTION: NOT_APPROVED
```
