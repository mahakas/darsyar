# Phase 4: Knowledge Ingestion

**Status:** Planned / Gated — ADR-024, ADR-037, ADR-038 accepted (owner approval 2026-11-09) and OQ-009 closed, but real per-source authorization and metadata are still prerequisites.  
**Dependencies:** Phase 0 and phase 3 inference/worker interfaces

### Remaining gates (not yet met)
1. Real source-specific license evidence must be registered and reviewed (`docs/licenses/` currently has no registered source evidence).
2. Each legacy source must carry explicit owner-approved grade metadata (per source, not automatic).
3. Required manifest metadata (provenance, publisher, edition_year, license evidence) must be complete for each source in scope.

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
