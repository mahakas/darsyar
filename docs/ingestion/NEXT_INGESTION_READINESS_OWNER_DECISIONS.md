# Next Ingestion Readiness — Consolidated Owner Decision Package

**Date:** 2026-11-10. **Documentation and read-only technical assessment only.**
This package prepares decisions; it does **not** approve or implement any change.
No migration, model change, schema change, publisher change, cron registration,
scheduling, consumer registration, PDF processing, or runtime operation occurred
in producing it.

## Preserved status baseline (verified against repository)

```text
R-1: OWNER_DECIDED_OPTION_B
R-2: OWNER_APPROVED
R-3: OWNER_DECIDED_DEFER_ARCHIVAL

S-1: OWNER_APPROVED_WITH_CONDITIONS
S-2: OWNER_APPROVED_WITH_CONDITIONS

SLICE_1_PERSISTENCE: IMPLEMENTED
SLICE_2: CLOSED
SLICE_3: CLOSED

RUNTIME_CONFIGURATION: PENDING_OWNER_APPROVAL
LICENSING_AND_AUTHORIZATION: PENDING
PRODUCTION: NOT_APPROVED

Phase 3: COMPLETE
Phase 4: PLANNED / GATED
Phase 5: NOT_STARTED
```

### Verified Slice 3 facts (from repository records)

- PostgreSQL integration tests: **13 passed** (`tests/test_outbox_publisher_db.py`).
- Combined Slice 1–3 tests: **36 passed**.
- PostgreSQL **18.6** (`darsyar_test`).
- arq **0.28.0**; Redis server 7.4.12.
- Dedicated queue: **`arq:queue:ingestion`** (distinct from general `arq:queue`).
- No real ingestion consumer registered (`WorkerSettings.functions == [worker_probe]`).
- No automatic Publisher scheduling; `cron_jobs` unchanged (two recovery crons only).

---

## Part A — R-1 implementation readiness (`ON DELETE RESTRICT`)

> Status update (2026-11-11): **R1-IMPL approved with conditions and implemented**;
> **migration `0019` applied to the application database `darsyar`** under
> `APPLICATION_DATABASE_MIGRATION = APPROVE_WITH_CONDITIONS` after a verified backup
> (SHA-256 `4FA4F3B2...`) and PASSED restore drill. `darsyar` revision `0018_ingestion_persistence`
> → `0019_outbox_job_fk_restrict`; FK now RESTRICT (`confdeltype='r'`); table counts
> preserved; application healthy. Production and `darsyar_test` were NOT migrated.
> The subsections below retain the original assessment; A.1 reflects the original
> (pre-change) definition for the record.

### A.1 Exact current FK definition

- **SQLAlchemy model** `backend/app/models/outbox_event.py:38`:
  `job_id = mapped_column(ForeignKey("ingestion_jobs.id", ondelete="CASCADE"), nullable=False)`.
- **Migration `0018`** `backend/alembic/versions/0018_ingestion_persistence.py:91`:
  `sa.ForeignKeyConstraint(["job_id"], ["ingestion_jobs.id"], ondelete="CASCADE", name="fk_outbox_events_job")`.
- Related: `ingestion_jobs.document_id → ingestion_documents.id` is already `ON DELETE RESTRICT` (model `ingestion_job.py:45`; migration line 66).

**Implemented change:** model now declares `ondelete="RESTRICT"`; new migration
`0019_outbox_job_fk_restrict` drops `fk_outbox_events_job` and recreates it with
`ON DELETE RESTRICT` (downgrade restores CASCADE). No ORM `relationship()` cascade
exists on these models (FK-only), so database-level RESTRICT is the sole guard.

### A.2 Proposed future migration sequence (NOT created)

> **Superseded by implementation** (2026-11-10): migration `0019_outbox_job_fk_restrict`
> was created and validated on `darsyar_test`. The original proposal is retained below
> for the record.

A single new revision (e.g. `0019_outbox_job_fk_restrict`) after `0018`:

- `upgrade()`:
  1. `op.drop_constraint("fk_outbox_events_job", "outbox_events", type_="foreignkey")`
  2. `op.create_foreign_key("fk_outbox_events_job", "outbox_events", "ingestion_jobs", ["job_id"], ["id"], ondelete="RESTRICT")`
  3. In the same implementation change, sync the model `ondelete="RESTRICT"` so ORM metadata matches the database.
- `downgrade()`: reverse — drop RESTRICT, recreate CASCADE (keeps the migration reversible).

### A.3 Existing data compatibility

- Data-only migration is **not** required; existing `outbox_events`/`ingestion_jobs` rows remain valid.
- RESTRICT changes only **delete** behavior; no backfill or normalization required.
- No orphans are expected (FK integrity already enforced); a pre-flight `LEFT JOIN` check for outbox rows referencing missing jobs is a cheap safety assertion (optional).

### A.4 Upgrade / downgrade behavior

- **Upgrade:** metadata-only FK change. PostgreSQL `DROP CONSTRAINT` / `CREATE CONSTRAINT` does not rewrite table data, but acquires a brief `ACCESS EXCLUSIVE` lock on both tables; run via the dedicated `migrate` service in a controlled window (R-084), before API/worker start (R-085).
- **Downgrade:** reversible; re-applies CASCADE; also requires the controlled migrate window.

### A.5 Potential blocking conditions

- After RESTRICT, any `DELETE FROM ingestion_jobs WHERE id = …` that has referencing `outbox_events` rows fails with a foreign-key violation. This is the intended protection (R-1/R-2: no job deletion while outbox history is subject to retention).
- Any ORM `session.delete(job)` reaches the same DB-level guard (the models define **no** `relationship()` ORM cascade, so behavior is DB-determined).
- A job with **no** outbox rows remains deletable — consistent with R-2 (post-retention deletion under a separate archival/cleanup policy).

### A.6 PostgreSQL tests required (when authorized)

- `alembic upgrade head` reaches the new head and schema-baseline tests still pass.
- Delete a job that has outbox rows → `IntegrityError` (FK restrict) and no outbox rows are removed.
- Delete a job with no outbox rows → succeeds.
- Downgrade round-trip re-applies CASCADE (assert via `information_schema.referential_constraints`).
- Concurrent ingestion/creation unaffected (creation adds rows; never deletes).

### A.7 Effect on application deletion / ORM behavior

- No application code attempts Job or Outbox deletion (verified by grep: the only delete-related code paths are user soft-delete, cookie deletion, and FK `ondelete` definitions; `ingestion_creation.py`, publisher, reconciliation, and repositories never delete).

### A.8 Distinctions (not conflated)

1. **R-1 policy** — already decided by owner (`OWNER_DECIDED_OPTION_B`).
2. **Authorization to implement the migration** — separate owner decision (decision `R1-IMPL`, approved with conditions 2026-11-10; implemented as `0019`).
3. **Actual migration execution** — its own controlled scope (migrate service, test suite, window).

### A.9 Recommended safest approach

- Implement as a single, reversible migration revision executed only through the `migrate` service, with the model synced in the same change and the full integration suite (incl. new FK-restrict + downgrade tests) green before any deployment.
- Because R-2 already prohibits deleting jobs while history is subject to retention, RESTRICT simply enforces agreed policy at the database; there is no existing cascade-dependent cleanup to break.
- Do **not** assume CASCADE→RESTRICT is harmless without the above checks — the deletion-path inspection (A.7) confirms no current reliance on cascade cleanup, so the risk is low, but the test coverage is still required.

---

## Part B — Publisher runtime configuration

Inspected: `backend/app/services/outbox_publisher.py`, `outbox_reconciliation.py`, `backend/app/repositories/outbox_events.py`, `backend/app/services/worker.py`, `backend/app/core/metrics.py`, `backend/app/core/config.py` (pydantic-settings conventions).

### B-1. Publisher batch size

- **Current state:** `batch_size: int` is a **required keyword argument** on `publish_pending_outbox_events`, `reconcile_pending_outbox_events`, and `run_outbox_publisher`. There is **no** setting field and **no** default; a value must be supplied by the caller.
- **Why it matters:** the claim runs in one short PostgreSQL transaction; `FOR UPDATE SKIP LOCKED` row locks are held while each event is enqueued to Redis (bounded by the Redis call). Batch size therefore bounds lock-hold duration, transaction length, and in-memory ORM object count, and raises Redis round-trip frequency when small.
- **Owner decision B1 = `OWNER_APPROVED_WITH_CONDITIONS`** (2026-11-11): **`batch_size=50`** is approved **exclusively for explicit manual, one-shot Outbox Publisher invocations**. The value remains an explicit invocation argument — no default argument, no implicit configuration fallback, no automatic value injection, and no change to the Publisher's existing required-input contract.
- **Evidence (synthetic):** `OUTBOX_PUBLISHER_BATCH_BENCHMARK.md` — PostgreSQL 18.6 + isolated Redis DB15; 5 repetitions per candidate; Batch 10: 24.1 events/sec, p95 transaction/lock 0.345s; Batch 50: 44.5 events/sec, p95 0.737s; Batch 100: 41.5 events/sec, p95 1.893s. Batch 50 offered the best measured throughput/lock-duration balance.
- **Limits of evidence:** results are synthetic and are not Production validation; `tracemalloc` does not represent full process RSS.
- **Not granted by B1:** no standing authorization to publish pending application events; any actual invocation against live application Outbox events requires its own explicit authorization; synthetic benchmark publication is not equivalent to real ingestion execution.
- **B1 does not authorize** automatic scheduling or Production approval. B1's scope is manual one-shot invocation only.

### B-2. Publisher scheduling

| Mode | Operational complexity | Duplicate behavior | Recovery | Observability | Required params | Risk |
|---|---|---|---|---|---|---|
| **Manual / one-shot** | Lowest. Call `publish...`/`reconcile...` on demand with session + redis + batch_size. | Safe (deterministic ARQ `_job_id` dedup; `published` rows excluded). | Reconciliation invoked manually re-attempts pending events. | Existing structured logs + metrics. | `batch_size`; session/redis. | Minimal; nothing automatic. |
| **Administrative invocation** | Low–medium. A future admin endpoint/CLI calls the one-shot services behind auth/audit. | Same as manual. | Same. | Adds auth/audit to trigger. | `batch_size`; auth. | Low; human-in-the-loop. |
| **Periodic via ARQ cron** | Medium. Add a cron function to `WorkerSettings.cron_jobs` (arq 0.28.0 supports this without changing default queue consumption). | Same (idempotent). | Periodic reconciliation is the recovery vehicle. | Existing logs/metrics + cron timing. | `batch_size` + cadence. | **Automatic publishing begins**; unapproved cadence/numerics could stress Redis/DB; larger operational surface. |

- **Can current WorkerSettings support scheduling without changing general queue behavior?** Yes — `cron_jobs` can host an additional function without altering the default queue (`arq:queue`) consumption. However, doing so registers automatic publishing, which is not approved; the existing `WorkerSettings` is unchanged.
- **Recommendation:** start **manual / one-shot** (optionally administrative) until cadence and numeric parameters are owner-approved. Defer periodic scheduling (decision `B2`).

### B-2. Owner decision — recorded (2026-11-11)

**`B2 = APPROVE_MANUAL_ONE_SHOT`** — the owner approves manual, explicit, one-shot
invocation as the initial operating mode for the Outbox Publisher.

- Manual explicit invocation is the **approved initial operating mode**.
- Periodic automatic scheduling remains **unapproved and disabled**.
- No ARQ cron registration is authorized.
- `batch_size` remains a required explicit input, with no implicit default (approved manual value = 50 per B1).
- Other numerical Publisher parameters remain pending owner approval.
- Existing ARQ queue isolation and at-least-once semantics are preserved.
- No real ingestion consumer is registered or started.
- This decision is **not** permission to publish currently pending application Outbox events (live publication stays gated).
- R-1, R-2, R-3, S-1, S-2 remain unchanged.

`B3` (other runtime parameters) was **deferred by the owner until scheduling/Production is considered** (`OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION`, 2026-11-11). Synthetic benchmark evidence for B1 was collected and the owner approved `batch_size=50` (manual one-shot only); see `OUTBOX_PUBLISHER_BATCH_BENCHMARK.md` and B-1 above. Further measurements were recommended before deciding B3/Production values: cross-host/co-located load, real queue-depth backlog drain, and long-running memory/RSS observation. No B3 values are selected.

### B-3. Publisher operational parameters inventory

See `OUTBOX_PUBLISHER_RUNTIME_PARAMETERS.md` (2026-11-11) for the full read-only
assessment, per-parameter inventory (code location, exists/mandatory, operating-mode
requirements), and owner decision table (B3). Summary: the approved manual one-shot
operation requires no additional numeric parameter beyond `batch_size=50`; scheduling,
timeout, retry/backoff, concurrency, memory/CPU and observability-threshold parameters
are deferred until scheduling or Production is considered. No numeric values are invented.

| Parameter | Source / current | Required for manual | Required for scheduled | Required for Production | Needed for current one-shot test path |
|---|---|---|---|---|---|
| `batch_size` | Required kwarg (no default/setting). Approved manual one-shot value = 50 (B1). | Yes (50) | Yes (50) | Yes (re-validate) | Yes (explicit 50) |
| Redis enqueue timeout | inherited from ARQ `RedisSettings`; no override | No | Recommend | Yes | No |
| Publisher wall-clock timeout | none | No | Yes | Yes | No |
| Database transaction timeout | none (batch_size bounds lock) | No | Recommend | Yes | No |
| Publisher concurrency | none (caller-managed) | No (single invocation) | Yes | Yes | No |
| Retry limit / backoff | none (transient → pending; reconcile is retry) | No | Yes | Yes | No |
| Reconciliation interval | none (one-shot) | No | Yes | Yes | No |
| Scheduling cadence | none (B2 manual) | No | Yes | Yes | No |
| Observability thresholds | metrics exist; no alert thresholds | No | Yes | Yes | No |
| Memory/CPU limits | none (publisher) | No | Recommend | Yes | No |

Approved manual one-shot operation requires **no additional input** beyond `batch_size=50`
(explicit) plus session/Redis client.

---

## Part C — Gate A: PDF renderer readiness

Inspected (all present, none moved/renamed): `GATE_A_RENDERER_DECISION.md`, `PDFIUM_LICENSE_INVENTORY.md`, `PDFIUM_OWNER_LEGAL_REVIEW.md`, `PDFIUM_CONCURRENCY_DECISION.md`, `PDFIUM_LINUX_PREFLIGHT.md`.

- `pypdfium2 5.15.2` remains an **owner-approved conditional candidate**, **not** Production-approved (`gate_status: open`).
- **Windows synthetic preflight: PASS** (CPython 3.13.14; 72/150 DPI; 20/20 lifecycle; malformed rejection).
- **Linux synthetic preflight (Run #6): PASS** (3.13.18, x86_64; 6 PNG; 30/30 lifecycle; malformed rejection; `ldd` no missing dep; ELF `DT_NEEDED` confirmed).
- **Thread safety:** PDFium is documented not thread-safe; recommended design is **Option C — bounded spawned subprocess workers** (proposed, `OWNER_DECISION_PENDING`).
- **Native memory/resource safety evidence:** not established (tracemalloc is Python-only; no native leak proof).
- **Persian textbook fidelity:** not verified (synthetic PDFs only; no real textbook rendered).
- **License / provenance gaps:** wheel/license/notice inventory is technical, not legal clearance; **no PEP 740 PyPI attestation exists for 5.15.2**; third-party component→binary provenance not independently verified; `libgcc_s.so.1` is a real dynamic dependency (GCC Runtime Library Exception notice shipped).
- **Owner/legal review:** PENDING.

Separation:
1. **Renderer technical suitability** — evidence exists (synthetic PASS; thread-unsafe → process isolation).
2. **Licensing / third-party notice clearance** — PENDING (no clearance claimed).
3. **Production approval** — NOT_APPROVED.

Gate A stays OPEN; no pilot PDF is opened or processed.

---

## Part D — Gate B: upload and PDF processing security

Inspected: `AGENTS.md` R-118, `docs/ingestion/ARCHITECTURE.md` (Large PDF compatibility + security defaults), `docs/ingestion/OWNER_DECISIONS.md` (Gate B inventory), `backend/app/core/config.py`, `infra/nginx/nginx.conf` references.

Decision matrix (every numeric value remains pending; fail-closed principle: block if unset):

| Setting | Existing requirement/source | Evidence-backed value | Benchmark/security test needed | Status |
|---|---|---|---|---|
| Max upload size (document bytes) | R-118; transport 20 MiB (`max_request_bytes=20971520`, nginx `client_max_body_size 20m`); math pilot is ~35.74 MiB > 20 MiB (documented incompatibility). | None approved; separate document-admission vs transport limit. | Benchmark both pilots; decide transport vs document limit. | PENDING_OWNER_DECISION |
| Max page count | No source value; pilots 188/176 pages. | None. | Profile real resource distribution; size with headroom. | PENDING |
| File/decompressed size | R-118 decompression/malformed guards required (ARCHITECTURE). | None. | Zip-bomb / malformed-PDF guard test. | PENDING |
| Render DPI/pixel limits | Synthetic only 72/150 DPI used. | None. | Resource benchmark at candidate DPIs. | PENDING |
| Processing timeout | Worker `job_timeout=300s`; nginx proxy read/send 360s (general). No ingestion-specific value. | None. | Conflict resolution (job vs document vs proxy); measurement. | PENDING |
| Memory / CPU bounds | Container limits not documented (`CONFIGURATION_REQUIRED`); `max_jobs=4`. | None. | Measure per-document peak; set container limit. | PENDING |
| Child-process isolation | Option C process-isolation proposal (not implemented). | n/a (architectural). | Spawn/isolation tests once implemented. | PENDING |
| Temporary storage quota | `upload_dir` convention only; no quota. | None. | Define temp quota + enforcement test. | PENDING |
| Cleanup / orphan recovery | Required by design (R-199; session-scoped uploads). | None implemented. | Sweep/orphan-recovery tests. | PENDING |
| Rate limits / abuse handling | Existing chat/OTP rate limits; no ingestion-specific abuse control. | None. | Abuse/rate-limit tests for intake endpoints. | PENDING |
| Administrative authorization | R-097 admin auth; intake requires auth; Path B admin upload. | Existing auth pattern. | AuthZ tests on intake endpoints. | PENDING |

Gate B stays **OPEN / OWNER_DECISION_REQUIRED**. No arbitrary limits are selected.

---

## Part E — Gate C and authorization reference 13529

### Authorization 13529 (status preserved)

```text
reference_id: "13529"
record_status: pending_evidence_and_scope_review
verification_status: not_independently_verified
```

- **Verifiable evidence artifact:** not supplied; none reviewed.
- **Issuing authority / validity period / covered resources:** not recorded.
- **Covered operations:** all listed operations remain `scope_pending`: acquisition/download; local storage/backup; text extraction; OCR (optional, separately authorized); image/page rendering; embedding/indexing; retrieval/AI processing; display/quotation.
- ADR-024 (accepted 2026-11-09) requires traceable source + explicit per-operation permission evidence; `license_note` is a reference, not proof. ADR-024 is **not** declared fully satisfied.

### Gate C (controlled equivalence test)

- Status: `OWNER_APPROVAL_REQUIRED`; **not executed**.
- Explicit owner authorization is still required before running the controlled PDF-backend equivalence test against the two pilots (defined in `OWNER_DECISIONS.md` §4: exact inputs, distinct metrics A–D, temporary outputs only, no repository writes, no OCR/ingestion).

### Pilot textbooks

- Both manifests remain `needs_review` (`resources/math/grade2/manifest.yaml`, `resources/physics/grade12/manifest.yaml`).
- Neither pilot is currently approved for processing. No pilot PDF is opened or processed in this task.

---

## Part F — Recommended dependency order

Owner decisions vs implementation tasks:

1. **Decide + authorize the R-1 RESTRICT migration** (decision `R1-IMPL`) — done (approved 2026-11-10; migration `0019` implemented and validated on `darsyar_test`; `darsyar` not migrated).
2. **Decide Publisher manual vs scheduled operation** (decision `B2`) — done (approved manual one-shot 2026-11-11; periodic scheduling/cron not authorized).
3. **Approve numerical Publisher parameters based on measurements** (decisions `B1`, `B3`) — B1 done (approved 50, manual one-shot, 2026-11-11); B3 pending.
4. **Complete Gate B security limits** (decision `GATE-B`) — owner decision after evidence/benchmarks.
5. **Resolve Gate A technical renderer assessment + license evidence** (decision `GATE-A`) — owner/legal decision.
6. **Obtain and assess authorization evidence for 13529** (decision `AUTH-13529`) — owner decision after documentary evidence.
7. **Obtain separate Gate C approval for controlled equivalence testing** (decision `GATE-C`) — owner decision.
8. **Perform only the explicitly authorized testing** — implementation task (only after 7).
9. **Real textbook processing only after all relevant approvals** — implementation task (only after 4–7).
10. **Consider Production separately** — separate decision; currently `NOT_APPROVED`.

**Independent synthetic-only engineering can proceed without the PDF gates:** publisher/reconciliation already implemented and validated; further synthetic tests, observability/metrics design, and outbox schema reviews do not require Gate A/B/C or textbook authorization.

Phase statuses are not changed.

---

## Part G — Owner decision register

| Decision ID | Decision | Options | Recommendation | Owner status |
|---|---|---|---|---|
| R1-IMPL | Authorize RESTRICT migration | Approve / defer / request changes | Based on audit: approve as a single reversible migration (model synced) executed via migrate service with FK-restrict + downgrade tests | OWNER_APPROVED_WITH_CONDITIONS (2026-11-10) |
| B1 | Publisher batch size | Evidence-based numeric choice / keep required input | Approved `batch_size=50` for manual one-shot invocation only (synthetic benchmark: best throughput/lock balance; not Production validation) | OWNER_APPROVED_WITH_CONDITIONS (2026-11-11) |
| B2 | Publisher scheduling | Manual / administrative / periodic | Recommend **manual/one-shot** (optionally administrative) initially; defer periodic | OWNER_APPROVED_MANUAL_ONE_SHOT (2026-11-11) |
| B3 | Other Publisher runtime values | Approve measured values / defer | Owner decided to defer remaining runtime parameters until scheduling/Production is considered — full assessment in `OUTBOX_PUBLISHER_RUNTIME_PARAMETERS.md` | OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11) |
| GATE-B | Security limits | Approve measured limits / request evidence | Assessment ready in `GATE_B_PDF_SECURITY_LIMITS_OWNER_DECISION.md`; **S0 implemented** (`GATE_B_PDF_VALIDATION_IMPLEMENTATION.md`, 22 synthetic tests) + **S1 prototype** (`GATE_B_S1_PARENT_CHILD_PROTOTYPE.md`, 17 tests; isolated parent/child, scoped pypdf 6.21.3, timeout/termination, env isolation); numerical limits still pending — approve only after benchmarks; fail-closed until then | PENDING_OWNER_DECISION |
| GATE-A | Renderer and licensing direction | Approve conditional candidate / request more evidence | Preserve conditional status; legal/notice review required; not Production-approved | PENDING_OWNER_DECISION |
| AUTH-13529 | Evidence and scope | Accept verified evidence / request more evidence | Based on documentary evidence; no independent verification claimed | PENDING_OWNER_DECISION |
| GATE-C | Controlled equivalence authorization | Approve defined test / defer | Preserve current gate; requires Gate A + 13529 evidence first | PENDING_OWNER_DECISION |

**Implications/boundaries (exact):**
- **R1-IMPL:** owner approved with conditions and implemented as migration `0019_outbox_job_fk_restrict` + model `outbox_event.py` `ondelete="RESTRICT"`, validated on `darsyar_test`. **On 2026-11-11 the migration was applied to `darsyar`** (authorized, with verified backup + restore drill); `darsyar` now at revision `0019`, FK RESTRICT. Production was not migrated (separate controlled scope).
- **B1:** owner approved `batch_size=50` with conditions (2026-11-11), exclusively for explicit manual one-shot invocation. The value stays an explicit invocation argument (no default/fallback/injection; required-input contract unchanged). No standing authorization to publish pending application events is granted; live invocation requires its own authorization. Synthetic benchmark evidence is not Production validation; B1 does not authorize automatic scheduling or Production.
- **B2:** owner approved **manual one-shot** as the initial operating mode (`APPROVE_MANUAL_ONE_SHOT`, 2026-11-11). Periodic scheduling/cron is not authorized; `batch_size` remains a required explicit input; live publication of pending application events is not authorized by B2.
- **B3:** owner decided to **defer remaining Publisher runtime parameters until periodic scheduling or Production is considered** (`OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION`, 2026-11-11). Deferred: publisher execution timeout, database transaction timeout, Redis enqueue timeout override (if needed), retry/backoff controls, concurrency policy, reconciliation cadence, resource limits, and monitoring thresholds. Manual-only operation requires none; this deferral does not approve live application Outbox publication. See `OUTBOX_PUBLISHER_RUNTIME_PARAMETERS.md`.
- **GATE-B:** approving limits is separate from implementation; until approved, unset limits block (fail-closed). Assessment: `GATE_B_PDF_SECURITY_LIMITS_OWNER_DECISION.md` — no upload/validation/storage/child-process code exists; no ingestion-specific limit enforced; pilot conflict documented (math 37.5MB > 20MiB). **S0 implemented** (`GATE_B_PDF_VALIDATION_IMPLEMENTATION.md`): Common PDF Validation Layer + Parent/Child contract + 17 synthetic tests; no numeric limit approved.
- **GATE-A:** approving direction is not Production approval and does not clear licensing/notices.
- **AUTH-13529:** accepting evidence is a documentary-review decision; it does not constitute independent legal verification.
- **GATE-C:** approving authorizes only the defined controlled equivalence test against the pilots; it does not authorize production ingestion.

---

## Restrictions honored

Preparing this decision package involved no migration, model change, schema change,
publisher code change, `batch_size` default/cadence, ARQ cron, automatic publishing,
consumer registration, pilot PDF processing, OCR/rendering/extraction/embedding/indexing/retrieval,
`.env`/secrets change, Compose/Dockerfile change, runtime infrastructure change,
Gate A/B/C or Phase 4/5 change, or Git operations.

**Application migration (separate authorized step 2026-11-11):** migration `0019_outbox_job_fk_restrict`
was applied to the application database `darsyar` (not to `darsyar_test` or Production)
under `APPLICATION_DATABASE_MIGRATION = APPROVE_WITH_CONDITIONS`, preceded by a verified
backup and PASSED restore drill. Both the backup and the restore drill are documented above.

---

## Sources (inspected)

- `backend/app/models/outbox_event.py`, `backend/app/models/ingestion_job.py`, `backend/alembic/versions/0018_ingestion_persistence.py`
- `backend/app/services/outbox_publisher.py`, `outbox_reconciliation.py`, `backend/app/repositories/outbox_events.py`, `backend/app/services/worker.py`, `backend/app/core/metrics.py`, `backend/app/core/config.py`
- `docs/ingestion/{GATE_A_RENDERER_DECISION,PDFIUM_LICENSE_INVENTORY,PDFIUM_OWNER_LEGAL_REVIEW,PDFIUM_CONCURRENCY_DECISION,PDFIUM_LINUX_PREFLIGHT,OWNER_DECISIONS,ARCHITECTURE,AUTHORIZATION_GATE,INGESTION_PROGRESS_AND_OPEN_DECISIONS,OUTBOX_RETENTION_AND_SLICE_3_OWNER_DECISION,SLICE_3_OUTBOX_PUBLISHER_IMPLEMENTATION}.md`
- `docs/licenses/13529.md`, `docs/adr/ADR-024-resource-licensing.md`, `docs/PHASE4_INGEST_PILOT.md`
- `resources/math/grade2/manifest.yaml`, `resources/physics/grade12/manifest.yaml`

## Final status (2026-11-11)

```text
APPLICATION_DATABASE: darsyar
APPLICATION_DB_REVISION: 0019_outbox_job_fk_restrict
APPLICATION_DB_FK: RESTRICT

BACKUP_INTEGRITY: VERIFIED
RESTORE_DRILL: PASSED
APPLICATION_DATABASE_MIGRATION: APPLIED

SLICE_1_PERSISTENCE: IMPLEMENTED
SLICE_2: CLOSED
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
