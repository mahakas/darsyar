# Outbox Retention & Slice 3 Owner Decision Package

**Date:** 2026-11-10. Documentation-only. The owner's "OK" approves the planning direction only — it does **not** authorize Slice 3 implementation beyond the recorded decision.

## A. Outbox retention decision

### A.1 Current implementation (verified)
- `outbox_events.job_id → ingestion_jobs.id` **ON DELETE CASCADE** (model and migration `0018`).
- `ingestion_jobs.document_id → ingestion_documents.id` **ON DELETE RESTRICT**.
- Related `dedup_key` unique; `publication_state` check; indexes `(publication_state, available_at)` and `(job_id)`.
- Sources: `backend/app/models/outbox_event.py`, `backend/app/models/ingestion_job.py`, `backend/alembic/versions/0018_ingestion_persistence.py`.

### A.2 Implications
- Deleting a job deletes its outbox history (incl. **pending, published, failed, historical** events) under the current CASCADE rule.

### A.3 Options
| Option | Data integrity | Recovery/reconcile | Auditability | Complexity | Migration | Publisher compatibility |
|---|---|---|---|---|---|---|
| **A Preserve CASCADE + retain rule** | if job deletion prohibited while history needed | unaffected | if history retained | low | none | fine |
| **B RESTRICT deletion** | prevents job delete while events exist | unaffected | high | low | required (FK change) | fine |
| **C Soft delete / archival** | preserves records | needs lifecycle | high | medium | required | compatible |
| **D Separate long-term archive** | archive boundary; pending kept | needs archival process | high | higher | required | compatible |

### A.4 Owner decision (R-1 = OPTION_B)

**`OWNER_DECIDED: OPTION_B`** (2026-11-10): **ON DELETE RESTRICT** is selected.

- Deleting an ingestion job is **prevented while associated outbox records exist**.
- A future schema migration is required to replace `ON DELETE CASCADE` with `ON DELETE RESTRICT` (FK `outbox_events.job_id → ingestion_jobs.id`).
- Current schema and migration `0018` remain **unchanged**; the migration is not implemented here.
- Archival and long-term retention timing: resolved by R-3 (defer archival; see A.6).

### A.5 Owner decision (R-2 = APPROVE)
**`OWNER_APPROVED`** (2026-11-10): ingestion jobs must **not** be deleted while their associated outbox history remains subject to retention requirements. Deletion after the retention period is permitted only under a separately approved archival and cleanup policy.
- Policy vs implementation: current migration `0018` **still uses `ON DELETE CASCADE`**; the future migration to `ON DELETE RESTRICT` is **not implemented**; no schema or application-code changes are authorized by this documentation task.

### A.6 Owner decision (R-3 = DEFER_ARCHIVAL)
**`OWNER_DECIDED_DEFER_ARCHIVAL`** (2026-11-10): no separate Outbox archive is required in the current scope. Archival design will be reconsidered when operational audit requirements and retention periods are established. Deferring archival does **not** authorize deleting Outbox history, nor does it imply indefinite retention. R-1/R-2/R-3 do not independently authorize schema changes.

## B. Proposed Slice 3 scope (bounded)

**Slice 3 — Transactional Outbox Publisher and Reconciliation** (synthetic events only):
1. PostgreSQL-backed unpublished-event discovery.
2. Safe concurrent publisher coordination.
3. Event publication through existing ARQ infrastructure.
4. At-least-once delivery semantics (duplicate-tolerant).
5. Stable event identity + duplicate delivery tolerance.
6. Recovery when publish succeeds but publication status not committed.
7. Reconciliation of unpublished/unclaimed work.
8. Publisher observability + structured errors.
9. PostgreSQL integration tests.
10. Synthetic-only event processing.

**Clarification:** publishing an ARQ message ≠ PDF job processed. No real PDF ingestion worker is registered in this slice.

## C. Slice 3 boundaries (synthetic-only; gated items)
- Requires: synthetic events, existing outbox schema, ARQ delivery, PostgreSQL tests.
- **Independent of:** PDFium, real textbook render/extract, OCR, real-book embedding/indexing, pilot authorization, production deployment.
- Preserved: Gate A OPEN; Gate B OPEN/OWNER_DECISION_REQUIRED; Gate C OWNER_APPROVAL_REQUIRED; 13529 pending; manifests 
eeds_review`; Phase 4 PLANNED/GATED; Phase 5 NOT_STARTED.

## D. Dependencies & acceptance criteria
- Publisher transaction boundaries; claim/publish concurrency strategy; duplicate-delivery handling; Redis outage; PostgreSQL outage; reconciliation invariants; retry/backoff config points (no numeric values); integration tests; failure injection; observability.
- All runtime numerical parameters remain `PENDING_OWNER_APPROVAL`.
- Use PostgreSQL integration test infra (no SQLite). Do **not** treat ARQ job ID alone as durable/exactly-once.

## E. Explicit owner decisions
| ID | Decision | Recommendation/status | Status |
|---|---|---|---|
| R-1 | Outbox retention strategy | **Option B (ON DELETE RESTRICT)** — owner-decided | OWNER_DECIDED: OPTION_B (2026-11-10) |
| R-2 | Prohibit job deletion while associated outbox history is subject to retention | Approve | OWNER_APPROVED (2026-11-10) |
| R-3 | Separate outbox archival | Defer | OWNER_DECIDED_DEFER_ARCHIVAL (2026-11-10) |
| S-1 | Approve bounded Slice 3 implementation | Approved scope as §B | OWNER_APPROVED_WITH_CONDITIONS (2026-11-10) |
| S-2 | Approve ARQ publication of synthetic events | Yes (synthetic only) | OWNER_APPROVED_WITH_CONDITIONS (2026-11-10) |
| S-3 | Additional operational parameters | Identified; values later | PENDING_OWNER_DECISION |
| R1-IMPL | Authorize RESTRICT migration | Approve with conditions | OWNER_APPROVED_WITH_CONDITIONS (2026-11-10) |

Recommendations are not decisions; owner must select remaining items.

## F. Slice 3 approval — recorded (2026-11-10)

**S-1: `APPROVE_WITH_CONDITIONS`** — the owner authorizes implementation of the
bounded Slice 3 (Transactionalalbox Publisher and Reconciliation).

**S-2: `APPROVE_WITH_CONDITIONS`** — the owner authorizes publication of synthetic
ingestion events to ARQ and testing actual delivery through the existing Redis
infrastructure.

The owner's approval does **not** authorize:
- A real PDF ingestion consumer/worker.
- Processing real textbook documents.
- PDFium execution.
- Production deployment.
- Unapproved numerical runtime settings.
- Unapproved schema changes.

Implementation boundary preserved: migration `0018` still uses `ON DELETE CASCADE`;
the future R-1 RESTRICT migration is **not** implemented; R-1/R-2/R-3 do not
independently authorize schema modifications; no jobs/outbox records are deleted;
no archival or cleanup functionality is added. See
`SLICE_3_OUTBOX_PUBLISHER_IMPLEMENTATION.md` for the implemented scope, concurrency
mechanism, at-least-once semantics, runtime parameters remaining pending, and
validation evidence.

## G. R-1 implementation — recorded (2026-11-10)

**R1-IMPL: `APPROVE_WITH_CONDITIONS`** — owner authorized implementation of the
R-1 `ON DELETE RESTRICT` data-integrity hardening:

- Update the SQLAlchemy relationship/FK definition (`outbox_events.job_id`).
- Create a new reversible Alembic migration.
- Add PostgreSQL integration tests.
- Validate migration upgrade/downgrade using only the disposable test database `darsyar_test`.
- Update governance and implementation documentation.

This authorization does **not** cover applying the migration to the application
database `darsyar`, Production changes, or real textbook processing.

Implemented:
- Migration `0019_outbox_job_fk_restrict` (revision `0018_ingestion_persistence` → `0019_outbox_job_fk_restrict`): drops `fk_outbox_events_job` and recreates it with `ON DELETE RESTRICT`; downgrade restores `ON DELETE CASCADE`.
- Model `backend/app/models/outbox_event.py`: `ondelete="CASCADE"` → `ondelete="RESTRICT"`. No ORM `relationship()` cascade exists (FK-only models), so database-level RESTRICT is the sole guard.
- PostgreSQL tests: `backend/tests/test_ingestion_restrict_db.py` (7 tests).
- Migration upgrade/downgrade/re-upgrade validated on `darsyar_test` only (PostgreSQL 18.6).

Application database applicationdarsyar` was **NOT** migrated in the earlier R-1
implementation step. **On 2026-11-11, owner-approved `APPLICATION_DATABASE_MIGRATION =
APPROVE_WITH_CONDITIONS` was applied** after a verified restore drill:

- Backup: `D:\darsyar_backups\darsyar_0018_20261110_2128.dump` (SHA-256 `4FA4F3B2D4A72A6F1DFC35F1B865636F78BD8ED79F2851AA9CE529202B739778`); manifest at `D:\darsyar_backups\darsyar_0018_20261110_2128.manifest.yaml`; restore drill PASSED (isolated PG 18.6).
- Migration `0019_outbox_job_fk_restrict` applied to `darsyar`: revision `0018_ingestion_persistence` → `0019_outbox_job_fk_restrict`; `fk_outbox_events_job` now `ON DELETE RESTRICT` (catalog `confdeltype = 'r'`).
- Data preserved: table counts unchanged across migration; no Job/Outbox records deleted/modified.
- Application healthy (API/Worker/Frontend/PostgreSQL/Redis). Production and `darsyar_test` were NOT migrated.
- R-2 and R-3 remain unchanged.

## Sources & statuses
Sources: `backend/app/models/outbox_event.py`, `backend/app/models/ingestion_job.py`, `0018` migration, `app/services/ingestion_creation.py`, `backend/app/services/worker.py`, ingestion design/spec/progress docs.

```text
R-1: OWNER_DECIDED_OPTION_B
R1-IMPL: OWNER_APPROVED_WITH_CONDITIONS
R-2: OWNER_APPROVED
R-3: OWNER_DECIDED_DEFER_ARCHIVAL
R1_MODEL_AND_MIGRATION: IMPLEMENTED
R1_POSTGRESQL_VALIDATION: PASSED
BACKUP_INTEGRITY: VERIFIED
RESTORE_DRILL: PASSED
APPLICATION_DATABASE_MIGRATION: APPLIED
APPLICATION_DB_REVISION: 0019
APPLICATION_DB_FK: RESTRICT
SLICE_1_PERSISTENCE: IMPLEMENTED
SLICE_2: CLOSED
SLICE_3_CODE: IMPLEMENTED
SLICE_3_POSTGRESQL_VALIDATION: PASSED
SLICE_3_REDIS_ARQ_VALIDATION: PASSED
SLICE_3: CLOSED
OUTBOX_RETENTION: OWNER_DECIDED_OPTION_B
S-1: OWNER_APPROVED_WITH_CONDITIONS
S-2: OWNER_APPROVED_WITH_CONDITIONS
RUNTIME_CONFIGURATION: PENDING_OWNER_APPROVAL
LICENSING_AND_AUTHORIZATION: PENDING
PRODUCTION: NOT_APPROVED
```
