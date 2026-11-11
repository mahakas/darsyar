# Phase 4: Knowledge Ingestion

**Status:** Partial synthetic implementation exists; Phase remains Planned / Gated and is not accepted. ADR-024, ADR-037 and ADR-038 are accepted, but source-specific authorization, PDF processing gates and operational intake remain prerequisites.  
**Dependencies:** Phase 0 and phase 3 inference/worker interfaces

### Implemented safely (synthetic only)
- Manifest validation and canonical grade/edition checks.
- Two-level parent/child chunking and Persian normalization.
- Embedding adapter with bounded batch/retry/dimension validation.
- PostgreSQL/pgvector chunk indexing and synthetic integration tests.
- Durable ingestion document/job/outbox persistence and publisher/reconciliation slices.

These components do not constitute an operational textbook-ingestion workflow. No real textbook has been processed under this synthetic test path.

### Remaining gates (not yet met)
1. Real source-specific license evidence must be registered and reviewed in `docs/licenses/`.
2. Each legacy source must carry explicit owner-approved grade metadata (per source, not automatic).
3. Required manifest metadata (provenance, publisher, edition_year, license evidence) must be complete for each source in scope.
4. Gate A renderer selection/licensing and Gate B/C PDF security/equivalence conditions remain open.
5. An authenticated intake route and registered worker consumer must be implemented and accepted before operational ingestion; current publisher/worker boundaries do not themselves perform PDF processing.
6. OCR/image/formula fidelity and the pilot acceptance criteria remain unverified.

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
