# Phase 4: Knowledge Ingestion

**Status:** Partial synthetic implementation exists; Phase remains Partial / Gated and is not accepted. ADR-024, ADR-037 and ADR-038 are accepted, but source-specific authorization, PDF processing gates and operational intake remain prerequisites.  
**Dependencies:** Phase 0 and phase 3 inference/worker interfaces

### Implemented safely (synthetic only)
- Manifest validation and canonical grade/edition checks.
- Two-level parent/child chunking and Persian normalization.
- Embedding adapter with bounded batch/retry/dimension validation.
- PostgreSQL/pgvector chunk indexing and synthetic integration tests.
- Child overlap enforcement and strict parent size/coverage bounds.
- Fail-closed active `index_meta` registry enforcement for indexing; provider model, vector dimension and metric must match the active registry before replacing existing chunks.
- Durable ingestion document/job/outbox persistence and publisher/reconciliation; PostgreSQL claim/lease/fencing/retry/cancellation (PR #21).
- Attempt-scoped synthetic artifact staging, integrity verification, lease/fencing-guarded immutable publish, and explicit orphan cleanup (PR #22).
- Low-cardinality process-local metrics for job claims, renewals, fixed transitions, and successful artifact operations (PR #23); no job/document/worker IDs or file metadata are labels.
- Synthetic PostgreSQL end-to-end tests cover job claim → isolated Parent/Child subprocess → metadata-only artifact publish → successful terminal state, plus malformed-child failure with no artifact publication (PR #24).

These components do not constitute an operational textbook-ingestion workflow. No real textbook has been processed under this synthetic test path. The active-index registry code does not auto-seed any active model: a real index remains unavailable until an operator provisions a verified record that matches the physical 1024-dimensional cosine vector index and the selected provider.

### Remaining gates (not yet met)
1. Real source-specific license evidence must be registered and reviewed in `docs/licenses/`.
2. Each legacy source must carry explicit owner-approved grade metadata (per source, not automatic).
3. Required manifest metadata (provenance, publisher, edition_year, license evidence) must be complete for each source in scope.
4. Gate A renderer selection/licensing and Gate B/C PDF security/equivalence conditions remain open.
5. An authenticated intake route and registered worker consumer must be implemented and accepted before operational ingestion; current publisher/worker boundaries do not themselves perform PDF processing.
6. OCR/image/formula fidelity and the pilot acceptance criteria remain unverified.
7. No operational active index row is provisioned; without exactly one active registry row, indexing/retrieval fail closed. Synthetic PostgreSQL tests create and remove only a test-scoped `embedding_model=test, dimension=1024, cosine` row.

### Implementation CI evidence — 2026-11-12

PR #24 (`test/phase4-synthetic-job-child-artifact-e2e`), head `886e9d53612e409f6299dc56c18e8f5b7dd3fcf8`, GitHub Actions Runs [43254207065](https://github.com/mahakas/darsyar/actions/runs/43254207065) and [43254283612](https://github.com/mahakas/darsyar/actions/runs/43254283612):
- Backend: **545 passed, 21 skipped, 1 warning**; Ruff and mypy clean (132 source files), Alembic migration smoke PASS.
- Frontend lint/typecheck/build: PASS.
- Linux SIGTERM acceptance: PASS.
- Nginx config/header smoke: PASS.
- Trivy report-only filesystem/image scans: PASS (report generation only; not zero vulnerabilities).

PR #24 is merged to `main` (`385a3d1fdedb429250e478ed836c96e9e1422a9e`). These checks validate synthetic-only paths, not legal authorization, sandbox enforcement, PDF renderer approval, operational consumer readiness, or real textbook quality.

## Goal

Ingest authorized textbooks with source metadata and traceability.

## In scope

- [ ] Manifest/schema/license registry, checksums and idempotent ingestion.
- [ ] PDF/DOCX/HTML extraction, Persian OCR in worker, page metadata.
- [ ] Quarantine and upload safety for any user files.
- [ ] Parent/child chunking and ingestion status/error taxonomy.
- [ ] Edition_year and grade mapping review for legacy sources.

## Out of scope

- Unlicensed production resources
- Guessing metadata or silently mapping old pre-university materials

## Acceptance criteria

- [ ] Invalid/missing metadata fails or needs_review.
- [ ] Duplicate ingestion does not duplicate chunks.
- [ ] Persian OCR smoke test must not silently return empty text.
- [ ] Every ready document has source/license/edition metadata.

## Required evidence

- Commands actually executed, exit code and important output.
- Files changed and references to applicable `R-NNN` rules.
- Risks, assumptions, and `NOT RUN` checks with exact blocker.
- New decisions in an ADR before code when required.
