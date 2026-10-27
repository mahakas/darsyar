# Phase 4: Knowledge Ingestion

**Status:** Planned; requires license and grade mapping decisions  
**Dependencies:** Phase 0 and phase 3 inference/worker interfaces

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
