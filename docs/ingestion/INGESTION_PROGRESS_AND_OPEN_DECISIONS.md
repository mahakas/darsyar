# Darsyar Ingestion — Consolidated Progress & Open Decisions

**Last verification (2026-11-10).** Documentation-only snapshot; no production/runtime
deployment performed. The Outbox Publisher + Reconciliation (Slice 3) is implemented and
validated with synthetic events only (PostgreSQL + dedicated Redis queue namespace);
no real PDF worker/consumer is registered.

## 1. Executive summary

- Ingestion architecture is **conceptually approved with conditions**; the durable job/outbox persistence (Slice 1), transactional creation service (Slice 2), and Outbox Publisher + Reconciliation (Slice 3) are implemented and validated.
- Slice 2 PostgreSQL validation **PASSED** (9/9) on a disposable Docker-network runner against `darsyar_test`.
- Slice 3 PostgreSQL **and** Redis/ARQ validation **PASSED** (13/13) on the same disposable runner (`darsyar_test` + dedicated `arq:queue:ingestion` namespace).
- Application containers are operational (API/Worker/Frontend healthy; PostgreSQL/Redis healthy).
- Remaining work is gated on **owner decisions** (runtime/deployment params, Gate A renderer, Gate B limits, Gate C equivalence, licensing/authorization, Production).

## 2. Verified completed milestones

| Milestone | Status | Evidence |
|---|---|---|
| Conceptual architecture approved w/ conditions | Done | `INGESTION_ARCHITECTURE_OWNER_DECISION.md` |
| Implementation spec approved w/ conditions | Done | `DURABLE_INGESTION_JOB_IMPLEMENTATION_SPEC.md` |
| PostgreSQL = durable authority; ARQ/Redis = delivery | Done | spec + design docs |
| At-least-once + idempotent effects (not exactly-once) | Done | design/spec |
| Slice 1 persistence (model + 0018 migration) | Done | 14 DB tests passed |
| Slice 2 transactional creation service | Done | `app/services/ingestion_creation.py` |
| Slice 2 PostgreSQL validation | **PASSED** | 9/9 on `darsyar_test` (PG 18.6) |
| Slice 3 outbox publisher + reconciliation (synthetic) | Done | `app/services/outbox_publisher.py`, `app/services/outbox_reconciliation.py` |
| Slice 3 PostgreSQL + Redis/ARQ validation | **PASSED** | 13/13 on `darsyar_test` + `arq:queue:ingestion` |

## 3. Slice 1 / Slice 2 evidence

- **Slice 1:** `ingestion_documents`, `ingestion_jobs`, `outbox_events` (SQLAlchemy models), migration `0018_ingestion_persistence`; unique/check constraints + indexes; 14 PostgreSQL tests passed.
- **Slice 2:** service `create_ingestion_job(...)`; caller-owned transaction convention (`commit=False` default; `commit=True` for isolated tests); idempotency scope `(document_id, request_idempotency_key)`; equivalent duplicate returns existing job + creation outbox; conflicting hash → `IdempotencyConflictError`; deterministic outbox dedup `create:{job_id}`; missing creation-outbox = invariant violation.
- **Validation evidence:** disposable runner reused the existing `darsyar-ai-api` image, mounted `backend/` read-only, used network `darsyar-ai_default`, target `postgres`/`darsyar_test` (PG 18.6), command `pytest -p no:cacheprovider tests/test_ingestion_creation_db.py -q` → **9 passed, 0 failed, 0 skipped**. A test-only `DetachedInstanceError` correction was made; no production image/schema change.
- **Slice 3 evidence:** same disposable runner (`darsyar-api:test` base + mounted `backend/` read-only, network `darsyar-ai_default`), target `postgres`/`darsyar_test` (PG 18.6) and a dedicated Redis logical DB 15 on `redis` with the isolated queue `arq:queue:ingestion`; command `pytest -p no:cacheprovider tests/test_outbox_publisher_db.py -q` → **13 passed, 0 failed, 0 skipped**. Only test-owned Redis keys cleaned; nothing flushed; general Worker queue untouched. Full ingestion set (Slices 1+2+3): **36 passed**.

## 4. Current infrastructure snapshot (read-only)

| Service | Status (2026-11-10) | Endpoint |
|---|---|---|
| PostgreSQL | healthy | (container, 5432) |
| Redis | healthy | (container, 6379) |
| API | healthy | `http://127.0.0.1:8000/health` → 200 |
| Worker | healthy | arq running; cron jobs ok |
| Frontend | healthy | `http://127.0.0.1:5173/` → 200 |
| Inference | not running | n/a (not started; not required for these paths) |

## 5. Architecture / technical baseline

- Parent supervisor owns DB access; child isolated from DB credentials; fencing required for consequential commits; staging→validation→recoverable publication.
- `guard`/security boundaries per AGENTS; no real-pilot processing.

## 6. Open technical issues

- Outbox history retention (see 7A).
- Runtime parameter measurement (see 7B).
- Renderer/equivalence/authorization gates (see 7C–7G).

## 7. Pending owner decisions

### A. Outbox history retention
- FK `outbox_events.job_id → ingestion_jobs.id ON DELETE RESTRICT` (schema in `darsyar` after migration `0019`; `confdeltype = 'r'`). No deletion implemented in Slices 1–3.
- **Owner decision R-1 = Option B (ON DELETE RESTRICT)** (2026-11-10): job deletion is prevented while outbox records exist; archival timing resolved by R-3.
- **Owner decision R-2 = APPROVE** (2026-11-10): ingestion jobs must not be deleted while their outbox history is subject to retention; post-retention deletion requires a separately approved archival/cleanup policy.
- **Owner decision R-3 = DEFER_ARCHIVAL** (2026-11-10): no separate outbox archive required now; reconsider when audit/retention periods are established.
- **R1-IMPL = OWNER_APPROVED_WITH_CONDITIONS** (2026-11-10): RESTRICT migration authorized; implemented as migration `0019_outbox_job_fk_restrict` and model `outbox_event.py` `ondelete="RESTRICT"`; validated on `darsyar_test` (PG 18.6).
- **Application database `darsyar` migrated on 2026-11-11** under `APPLICATION_DATABASE_MIGRATION = APPROVE_WITH_CONDITIONS`, after backup + restore drill PASSED (backup SHA-256 `4FA4F3B2...`). Revision `0018_ingestion_persistence` → `0019_outbox_job_fk_restrict`; FK now RESTRICT; table counts preserved; application healthy. Production and `darsyar_test` were NOT migrated.

### B. Runtime configuration (values to be measured; owner-approved)
ARQ worker count; max concurrent ingestion jobs; child-process capacity; lease duration; heartbeat interval; child execution timeout; memory/CPU limits; retry limits/backoff; worker/process recycling; staging retention/cleanup thresholds; outbox publisher batch size; automatic publisher scheduler cadence. **No numeric values invented.** Slice 3 exposes `batch_size` as a required function input.

**Owner decision B2 = `APPROVE_MANUAL_ONE_SHOT`** (2026-11-11): manual, explicit, one-shot invocation is the approved initial operating mode for the Outbox Publisher. Automatic scheduling remains unapproved/disabled; no ARQ cron registration is authorized; `batch_size` stays a required explicit input with no implicit default; other numerical Publisher parameters remain pending. Live publication of currently pending application Outbox events is NOT authorized by B2. The one-shot `publish_pending_outbox_events` / `reconcile_pending_outbox_events` services remain callable but are not invoked by this decision.

**B1 = OWNER_APPROVED_WITH_CONDITIONS** (2026-11-11): `batch_size=50` approved **exclusively for explicit manual one-shot Publisher invocation**. The value remains an explicit invocation argument (no default/fallback/injection; required-input contract unchanged). Evidence: synthetic PostgreSQL 18.6 + isolated Redis DB15 benchmark (`OUTBOX_PUBLISHER_BATCH_BENCHMARK.md`), 5 reps per candidate — Batch 50 gave 44.5 events/sec / p95 transaction-lock 0.737s (best measured balance). Results are synthetic, not Production validation. No standing authorization to publish pending application events is granted by B1; live invocation requires its own authorization.

**B3 = OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION** (2026-11-11): owner deferred the remaining Publisher runtime parameters (execution timeout, DB transaction timeout, Redis enqueue timeout override, retry/backoff, concurrency policy, reconciliation cadence, resource limits, monitoring thresholds) until periodic scheduling or Production is considered. Manual one-shot operation requires none beyond `batch_size=50`; this deferral does not approve live application Outbox publication. Assessment: `OUTBOX_PUBLISHER_RUNTIME_PARAMETERS.md`. No values invented; no defaults/config fields added.

### C. Gate A — PDF renderer
- `pypdfium2 5.15.2` is a **conditional candidate**; not Production-approved; synthetic Windows/Linux evidence only (no real-Persian-textbook fidelity); licensing/provenance inventory incomplete; legal/owner review pending.

### C2. Phase 4 — knowledge ingestion pipeline (synthetic, owner-delegated)

Under owner-delegated full technical authority, the Phase 4 ingestion pipeline was
implemented and integration-tested against real PostgreSQL (`darsyar_test`), using only
synthetic fixtures and a deterministic fake embedding provider (no real textbook processed;
13529 remains `pending_evidence_and_scope_review`).

- **Models/migrations:** `ingestion_chunks` (parent/child, Vector(1024), metadata per
  R-150) — migrations `0020` (table, transactional) and `0021` (heavy HNSW + GIN +
  grade-filter indexes, `CONCURRENTLY` in autocommit).
- **Services:** `services/ingestion/manifest.py` (R-153/154 validation), `chunking.py`
  (two-level, R-158/159), `normalize.py` (Persian normalization R-164), `embedding_service.py`
  (batch/timeout/retry/dim validation), `indexing.py` (idempotent atomic re-index), `retrieval.py`
  (dense pgvector + lexical pg_trgm, RRF k=60 deterministic tie-break, grade filter in SQL both
  branches, top-20 rerank).
- **Property enforced:** `chunk.grade_level <= student.selected_grade` in both retrieval
  branches (R-148); citations/provenance preserved; no invented page/source.
- **Tests:** `tests/test_phase4_ingestion_pipeline_db.py` — 10 integration tests (manifest
  valid/invalid, chunking, embedding dim validation, re-index idempotency, grade-ceiling
  retrieval, document isolation). Full DB regression after additions: **126 passed**;
  synthetic gate suites: **80 passed**; `ruff`/`mypy` clean (125 files).
- **Real-source gate remains:** 13529 evidence/scope pending → real textbook ingestion
  still blocked; only synthetic pipeline is operationally present.
- **Phase 5 retrieval orchestration (synthetic):** `services/ingestion/retrieval_service.py`
  (plumbs live embedding + rerank providers into `hybrid_retrieve`; citation template with
  `-` guard for unknown pages) and `services/ingestion/evaluation.py` (synthetic gold
  evaluator). Tests `tests/test_phase5_rag_evaluation_db.py` enforce RAG gates on synthetic
  data (grade leakage == 0, invalid citation == 0). Final DB regression through Phase 5:
  **128 passed**.

### D. Gate B — upload/PDF processing security
- **OPEN / OWNER_DECISION_REQUIRED**. Assessment prepared in `GATE_B_PDF_SECURITY_LIMITS_OWNER_DECISION.md` (2026-11-11): no upload endpoint/file-validation/storage/child-process code exists; no ingestion-specific limit is enforced; documented conflict — math pilot 37,478,046 B (~35.7 MiB) > current 20 MiB transport limit (physics pilot 12.8 MiB fits). Synthetic-only test plan and owner-decision table provided; no limit approved.
- **Gate B-S0 implemented** (`GATE_B-S0 = APPROVE_WITH_CONDITIONS`, 2026-11-11): Common PDF Validation Layer (`services/ingestion/pdf_validation.py`, pypdf 6.21.4), Parent/Child contract (type-level, design only), synthetic fixtures + tests `test_gate_b_pdf_validation.py` → 22 passed (incl. pypdf resource-limit audit: default `Configuration` active; per-filter/stream caps, not a document-wide budget; page-count path does not decode streams). Version parity verified: same 22 tests pass under locked pypdf 6.21.3 (isolated) and installed 6.21.4. No pilot PDF / upload API / rendering / extraction / PDFium; no numeric limit approved. See `GATE_B_PDF_VALIDATION_IMPLEMENTATION.md` and `PYPDF_RESOURCE_LIMITS_AUDIT.md`.
- **Gate B-S1 implemented** (`GATE_B-S1 = APPROVE_WITH_CONDITIONS`, 2026-11-11): Parent Supervisor + spawned PDF Child prototype (`parent_supervisor.py`, `pdf_child.py`), versioned IPC contract v1, scoped pypdf 6.21.3 Configuration with explicit synthetic content-stream decode under test-only limits, timeout/termination/escalation, secret-env isolation (allowlist), synthetic tests → 17 passed (joint 39 passed). Parent is sole DB/infrastructure owner; no PG/Redis connection; no upload route; no production limits; memory/CPU NOT_ENFORCED on host; no OS-level filesystem/network sandbox claimed. See `GATE_B_S1_PARENT_CHILD_PROTOTYPE.md`.
- **Gate B-S2 implemented** (`GATE_B-S2 = APPROVE_WITH_CONDITIONS`, 2026-11-11): Linux OS-level sandbox prototype (`linux_sandbox.py`, `tests/test_gate_b_linux_sandbox.py`, standalone `tests/sandbox/Dockerfile.sandbox`). Enforced and probe-verified in a restricted Linux container: network none, read-only rootfs, docker socket absent, host secrets unreadable, memory limit (rc=-9), CPU quota (1.214s/2M iter), PID limit (105/200 failed), capabilities dropped, non-root. pypdf==6.21.3 locked. Results: **52 passed** in sandbox container; host regression 39 passed + 13 enforcement tests skipped. NOT_ENFORCED: seccomp/LSM fs sandbox, separate per-child cgroup, production numeric limits. Deployment Dockerfile/Compose untouched. See `GATE_B_S2_LINUX_SANDBOX_PROTOTYPE.md`.
- **Gate B-S3 partial owner decision** (`GATE_B_S3_PARTIAL_OWNER_DECISION = APPROVE_WITH_CONDITIONS`, 2026-11-11): **six policies approved with conditions** — GB-01 (40 MiB per-document; transport limits unchanged), GB-02 (250 pages; admission ceiling), GB-03 (32 MiB per stream; not aggregate), GB-08 (120 s child timeout; no runtime config), GB-09 (200 s parent timeout), GB-18 (require_admin + audit; not a legal/resource authorization). **Twelve remain pending**: GB-04, GB-05, GB-06, GB-07, GB-10, GB-11, GB-12, GB-13, GB-14, GB-15, GB-16, GB-17. Policy approvals ≠ implemented runtime configuration; no upload/real-PDF processing authorized. See `GATE_B_S3_NUMERIC_POLICY_OWNER_DECISION.md`.
- **Gate B-S4 lab validation** (`GATE_B_S4 = APPROVE_WITH_CONDITIONS`, 2026-11-11): Experiment A demonstrated an aggregate decompression ceiling enforced **during** decoding via per-stream `effective = min(per_stream, remaining)` (pypdf 6.21.3 scoped Configuration); the 256 MiB GB-04 candidate was technically feasible (8×32 MiB streams decode to exactly 256 MiB, peak ≈289 MiB). Experiment B collected direct cgroup v2 evidence: memory OOM (oom/oom_kill +1 under controlled no-swap invocation), CPU throttling (nr_throttled +59, throttled_usec +1,440,633), PID limit (EAGAIN at 94, pids.events max +1), no orphans. GB-04 stays PENDING. See `GATE_B_S4_AGGREGATE_DECOMPRESSION_AND_CGROUP_EVIDENCE.md`.
- **Gate B-S4.1 lab validation** (`GATE_B_S4_1 = APPROVE_WITH_CONDITIONS`, 2026-11-11): stream-coverage audit (page content covered; Form/Image XObjects coverable via resource-walk; object/xref/font/shading/embedded/nested streams are implicit/on-demand bypasses), failure accounting (tolerated-malformed = 0 bytes; fail-closed abort-on-exception; finite bounded enumeration), concurrency isolation (threads + async tasks tested and isolated; processes by construction). Q1=PARTIALLY, Q3 isolation holds, GB-04 not approved. See `GATE_B_S4_1_AGGREGATE_DECOMPRESSION_COVERAGE.md`.
- **Gate B-S4.2 lab validation (PARTIAL)** (`GATE_B_S4_2 = APPROVE_WITH_CONDITIONS`, 2026-11-11): parse-time decompression (object/xref streams decoded during `PdfReader.__init__`, before the S4.1 hook → aggregate budget cannot cover parsing from the start; contained only by OS/process limits), one isolated child process per document verified (timeout/termination/reaping/no-credential; container-level cgroup shared — not per-child), pypdf version review (lock stays 6.21.3; 6.21.3/4 within all four advisory ranges; 7.0.0 adds XFA field + xref/object/image fixes; 7.0.1 follow-up INCONCLUSIVE). **Status LAB_VALIDATION_PARTIAL**: synthetic Object/XRef-stream fixtures NOT_TESTED; parse-time aggregate accounting NOT_COVERED; forced kill() branch NOT_TESTED; per-child cgroup NOT_ENFORCED; 7.0.1 image follow-up + buffer estimation INCONCLUSIVE; process isolation ≠ aggregate decompressed-byte budget. GB-04 not approved. See `GATE_B_S4_2_PARSE_TIME_DECOMPRESSION_AND_PYPDF_SECURITY_REVIEW.md`.
- **Gate B-S5 architecture review (COMPLETE)** (`GATE_B_S5 = APPROVE_WITH_CONDITIONS`, 2026-11-11): four-candidate comparison (pypdf 6.21.3 vs 7.0.1, pypdfium2/PDFium, PyMuPDF/MuPDF, independent orchestration incl. qpdf/pikepdf). No selection/upgrade beyond the dependency lock decision. pypdf official sources verified: releases + **8 advisory scopes affecting the prior lock 6.21.3** (4 × <7.0.0 incl. GHSA-mwj3 Low; 3 × <6.21.4). External docs verified: pypdfium2 readme, PyMuPDF FAQ, qpdf CLI options. Remaining open: PyMuPDF licensing LEGAL_REVIEW_REQUIRED; PDFium bundled-binary provenance; aggregate decompression NOT_PROVEN. Research direction (hybrid D+A): **pypdf lock upgraded to 7.0.1** under owner-delegated decision (2026-11-11; full DB regression 126/126, synthetic 80/80) while retaining the orchestration approach as the leading hypothesis for aggregate metering in a one-process-per-document sandbox; rendering later via Gate A. Fallback: Option A. GB-04 not approved. See `GATE_B_S5_PDF_PARSER_DECODER_ARCHITECTURE_COMPARISON.md`.
- **Gate B-S5 lock/addendum (2026-11-11):** forward-only Alembic downgrade guard added to `alembic/env.py` (R-241): `downgrade` blocked by default, allowed only with `DARSYAR_ALLOW_DOWNGRADE=1`; matches the existing `*_downgrade_guard` tests. This resolved a pre-existing full-suite corruption where guard tests actually downgraded the shared test DB.

### E. Gate C — controlled PDF-backend equivalence
- **OWNER_APPROVAL_REQUIRED**; not executed; no real-pilot processing in this task.

### F. Authorization reference 13529
- `pending_evidence_and_scope_review`; not independently verified; operation scopes unresolved; no legal clearance claimed.

### G. Pilot books
- Both manifests remain 
eeds_review`; real PDF processing restricted (no open/render/extract here).

## 8. Governance / phase status

```text
Phase 3: COMPLETE
Phase 4: PLANNED / GATED          (ROADMAP: “برنامهریزیشده / گیتشده”)
Phase 5: NOT STARTED

Gate A: OPEN
Gate B: OPEN / OWNER_DECISION_REQUIRED
Gate C: OWNER_APPROVAL_REQUIRED

Slice 1: IMPLEMENTED
Slice 2: CLOSED
Slice 3: CLOSED (synthetic; PostgreSQL + Redis/ARQ validation PASSED)
Slice 3 scheduler: DEFERRED (no automatic publisher cron registered); B2 = OWNER_APPROVED_MANUAL_ONE_SHOT (2026-11-11); B1 = OWNER_APPROVED_WITH_CONDITIONS (2026-11-11, manual batch 50)

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

Runtime configuration: PENDING_OWNER_APPROVAL
Licensing and authorization: PENDING
Production: NOT_APPROVED
```

(Exact ROADMAP wording retained; Phase 4 not opened; Phase 5 not started.)

## 9. Dependency-ordered future backlog

1. **Owner decisions first:** Gate B numeric limits; Gate A renderer + licensing; Gate C equivalence approval; 13529 evidence/scope; outbox retention policy.
2. **Synthetic-safe work (no Gate A/textbook auth needed):** outbox schema/publisher design reviews; additional synthetic tests; observability/metrics design.
3. **Slice 3 (completed):** durable outbox publisher + reconciliation implemented and validated (synthetic only). Owner decision B2 = APPROVE_MANUAL_ONE_SHOT (2026-11-11): manual/one-shot invocation is the approved initial mode; automatic scheduling cadence remains unapproved; the one-shot `publish_pending_outbox_events` / `reconcile_pending_outbox_events` services are callable but not invoked by B2.
4. **Blocked by Gate A/B/C:** real PDF rendering/metrics/limits enforcement.
5. **Requires authorization evidence:** any real-textbook processing.
6. **Requires Production approval:** production deployment.

## 10. Explicit prohibitions / boundaries

No migrations, schema changes, runtime config changes, container start/stop, Compose/Dockerfile changes, `.env`/secrets, PDF processing, OCR/render/extract/embed/index/retrieve, Git, Gate/Phase changes in this documentation-only task.

## 11. Last verification & evidence references

- Verified 2026-11-10 (docs, ROADMAP, `docker compose ps`).
- References (relative): `docs/ingestion/` docs listed in §1 of this file; `AGENTS.md`; `ROADMAP.md`; `backend/app/services/ingestion_creation.py`; `backend/tests/test_ingestion_creation_db.py`; `backend/alembic/versions/0018_ingestion_persistence.py`.

## 12. Final status table

| Item | Status |
|---|---|
| Phase 4 | PLANNED / GATED |
| Gate A | OPEN |
| Gate B | OPEN / OWNER_DECISION_REQUIRED |
| Gate B-S0 | IMPLEMENTED |
| Gate B-S1 | IMPLEMENTED (synthetic validation PASSED) |
| Gate B-S2 | IMPLEMENTED (Linux sandbox validation PASSED) |
| Gate B-S3 | DECISION_PACKET_COMPLETE; PARTIAL_OWNER_DECISION = APPROVED_WITH_CONDITIONS (6 approved / 12 pending) |
| Gate B-S4 | LAB_VALIDATION_COMPLETE (aggregate decompression experiment + cgroup evidence) |
| Gate B-S4.1 | LAB_VALIDATION_COMPLETE (stream coverage + failure accounting + concurrency isolation) |
| Gate B-S4.2 | LAB_VALIDATION_PARTIAL (parse-time decompression + process isolation + pypdf version/advisory review; several evidence gaps remain) |
| Gate B-S5 | ARCHITECTURE_REVIEW_COMPLETE (4-candidate comparison; 8 pypdf advisory scopes; official external sources verified: pypdf/pypdfium2/PyMuPDF/qpdf; legal/provenance questions left open) |
| pypdf lock | UPGRADED to 7.0.1 (owner-delegated technical decision 2026-11-11; DB regression 124/124, synthetic 80/80) |
| Gate C | OWNER_APPROVAL_REQUIRED |
| Slice 1 | IMPLEMENTED |
| Slice 2 | CLOSED |
| Slice 3 | CLOSED (synthetic; PostgreSQL + Redis/ARQ validation PASSED) |
| R-1 | OWNER_DECIDED_OPTION_B |
| R1-IMPL | OWNER_APPROVED_WITH_CONDITIONS |
| R-2 | OWNER_APPROVED |
| R-3 | OWNER_DECIDED_DEFER_ARCHIVAL |
| R1_MODEL_AND_MIGRATION | IMPLEMENTED |
| R1_POSTGRESQL_VALIDATION | PASSED |
| BACKUP_INTEGRITY | VERIFIED |
| RESTORE_DRILL | PASSED |
| APPLICATION_DATABASE_MIGRATION | APPLIED (darsyar, 2026-11-11) |
| APPLICATION_DB_REVISION | 0019_outbox_job_fk_restrict |
| APPLICATION_DB_FK | RESTRICT |
| B2 | OWNER_APPROVED_MANUAL_ONE_SHOT (2026-11-11) |
| B1 | OWNER_APPROVED_WITH_CONDITIONS (2026-11-11; manual batch 50) |
| B3 | OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11) |
| APPROVED_MANUAL_BATCH_SIZE | 50 |
| AUTOMATIC_PUBLISHER_SCHEDULING | NOT_AUTHORIZED |
| LIVE_APPLICATION_OUTBOX_PUBLICATION | NOT_AUTHORIZED |
| REAL_INGESTION_CONSUMER | NOT_REGISTERED |
| Runtime config | PENDING_OWNER_APPROVAL |
| Licensing/authorization | PENDING |
| Production | NOT_APPROVED |
