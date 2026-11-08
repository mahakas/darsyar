# Phase 4: Knowledge Ingestion

**Status:** Planned; requires license and grade mapping decisions  
**Dependencies:** Phase 0 and phase 3 inference/worker interfaces

## Governance decisions (2026-11-09)

The owner-approved governance choices are recorded in the ADRs:

- [x] **ADR-024 — strict licensing:** source provenance and operation-specific permissions are mandatory; unverified or ambiguous resources remain `needs_review`.
- [x] **ADR-037 — review:** `pre_university` and `grade_pre` are never automatically mapped; `OQ-009` is closed with legacy sources remaining `needs_review` until individually reviewed and explicitly mapped.
- [x] **ADR-038 — per_document:** every document must carry its own valid `edition_year`; no global 1403 fallback.
- [ ] **Resource-level production gate:** each real source must have its own recorded and approved license evidence before production ingestion.

This closes the **decision** prerequisites only. It does not claim that real textbook permissions have been obtained, that ingestion has been implemented, or that Phase 4 is complete.

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
