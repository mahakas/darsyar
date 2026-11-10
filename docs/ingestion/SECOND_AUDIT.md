# Second Independent Audit — Knowledge Ingestion Architecture

Date: 2026-11-10. Independent second review of `docs/ingestion/*` after the remediation pass.

## 1. Executive verdict

**PASS WITH CONDITIONS** — the seven original findings appear documented and internally consistent. Remaining conditions are **external governance / implementation gates**, not documentation defects: renderer backend decision, owner-approved numeric security limits, and PDF-backend equivalence test.

## 2. Seven-finding verification matrix

| Finding | Result | Evidence |
|---|---|---|
| Manifest/document schema | `VERIFIED_COMPLETE` (one clarification added below) | `PIPELINE_STAGES.md` §Stage 0 manifest contract table; `ARCHITECTURE.md` document-registration contract; `ACCEPTANCE_CRITERIA.md` manifest tests |
| PDF backend contract | `VERIFIED_COMPLETE` | `PIPELINE_STAGES.md` §Stage 3 capability matrix; `EXTRACTION_STRATEGY.md` §Metric use — `pypdf` 6.21.3 (rag) vs PyMuPDF explicit |
| Persistence schema | `VERIFIED_COMPLETE` | `ARCHITECTURE.md` §Logical persistence schema (10 entities) |
| Chunk/citation examples | `VERIFIED_COMPLETE` | `CHUNKING_AND_PROVENANCE.md` §Illustrative chunk records (both `ILLUSTRATIVE — NOT PERSISTED`) |
| Concurrency/locking | `VERIFIED_COMPLETE` | `STATE_MACHINE_AND_FAILURES.md` §Concurrency and locking |
| Security defaults/R-181 | `VERIFIED_COMPLETE` | `ARCHITECTURE.md` §Security defaults and R-181 |
| Legal-status wording | `VERIFIED_COMPLETE` | `README.md`, `AUTHORIZATION_GATE.md`, `DESIGN_REVIEW.md` |

## 3. Manifest/document schema audit

- Mandatory R-154 fields present; allowed subjects exact; grade 1–12; edition_year = printing year; academic_year distinguished; book_code kept string; path-safety; sha256 hex; file size/page count integer; publisher/provenance fields; license_note reference-only.
- Valid/invalid examples present; duplicate document identity and new-edition/changed-PDF identity defined.
- **Clarification required (minor):** the validation prose says integer fields "reject booleans", but the contract should require an explicit strict check that a YAML `true`/`false` is rejected (Python `bool` is a subclass of `int`, so naive `isinstance(int)` would pass). Recommend stating: reject `bool` explicitly before integer cast. Not a data-model error; a parser-contract precision item.

## 4. PDF adapter capability audit (`pypdf` 6.21.3)

Independently confirmed:
- Page count `len(reader.pages)`; encryption `reader.is_encrypted`; text `page.extract_text()`; geometry `page.mediabox`; referenced image resources via `page.images` (xrefs); PDF metadata `reader.metadata`.
- **Not supported by pypdf:** displayed-occurrence inventory (`get_image_info(xrefs=True)`), `get_images(full=True)`, structured-text image blocks (`get_text("dict")`), placement rectangles (`get_image_rects()`), vector-drawing detection, page rendering. These are PyMuPDF-only APIs; the design correctly marks them `UNSUPPORTED`/`NOT_COMPARABLE` where unreproducible.
- Methods A–D kept distinct; Method B retained as historical reference. No unsupported equivalence claim found.

## 5. Rendering dependency audit

- `pypdf` is not described as a renderer; PyMuPDF is not adopted; rendering is an explicit architectural dependency; rendering-dependent stages stay blocked until a backend decision; a future decision must address dependency/operational/deployment/licensing implications. Correct.

## 6. Persistence schema audit

- 10 logical entities defined with fields, PostgreSQL types, PK/FK/unique/indexes/nullability/lifecycle.
- Checks: document identity vs extraction-generation identity distinct; active-generation publication atomic; failed generations cannot become active; old generations roll back safely; asset dedup safe (content-hash + FK); page numbers distinct; chunk provenance preserves R-150 fields; citation reconstruction supported.
- No conflicts found with existing backend models (no such models exist yet; all are new proposals).
- Minor: `extracted_text` and `page_extraction` could be merged; acceptable as-is; note that `image_asset` dedup must use a transaction-safe unique insert.

## 7. Chunking and citation audit

- Both illustrative examples include all mandatory R-150 fields (document_id, grade_level, subject, edition_year, chapter, page_number, chunk_index, source_type, source_origin, is_valid, parent_id); parent-child coherent; page-number semantics (one-based physical) correct; asset references traceable; retrieval context present; citation reconstructible per `[کتاب: {title} | پایه {grade} | صفحه {page} | قطعه {chunk_index}]`.
- Both explicitly labeled `ILLUSTRATIVE — NOT PERSISTED`; no textbook wording falsely presented as extracted chunk.

## 8. Concurrency/leases/recovery audit

- PostgreSQL authoritative coordination; duplicate queue delivery no-ops via idempotent claim; lease expiry → recovery; stale-worker fencing defined; heartbeat/lease renewal coherent; interrupted work recoverable; concurrent editions independent; asset dedup safe under uniqueness constraint; generation publication transactionally safe.
- No undefined race found. (Not executed as tests.)

## 9. Security/R-181 audit

- All numeric limits have an explicit source status: `OWNER_DECISION_REQUIRED` or `CONFIGURATION_REQUIRED`; no arbitrary production defaults introduced.
- File-type/MIME, path traversal, temporary quotas, timeouts, malformed-PDF, cleanup, access control, per-stage authorization, and fail-closed unset behavior all documented.
- Untrusted extracted text cannot override system/developer instructions (R-181).

## 10. Authorization audit

- Reference 13529 consistently owner-provided, registered, evidence pending, resource scope pending, operation scope pending, not independently verified. No operation proceeds merely from a license_note path. No legal clearance claimed.

## 11. Readiness classification

- **A. Documentation completeness:** COMPLETE — contracts and responsibilities specified.
- **B. Implementation readiness:** CONDITIONAL — an engineer can proceed without inventing contracts, but **must not** implement rendering-dependent stages or finalize PDF-metric equivalence until the backend decision/equivalence test exists.
- **C. External governance readiness:** NOT READY — renderer decision, owner-approved security numeric limits, and PDF-backend equivalence test remain unresolved.

## 12. Requirement/ADR compliance (R-150–R-157, R-181; ADR-024/037/038)

- R-150–157: satisfied in design (matrix consistent with first audit).
- R-181: aligned (untrusted content isolation).
- ADR-024: fail-closed; 13529 pending; no satisfaction claim.
- ADR-037: no auto legacy mapping.
- ADR-038: edition_year=printing year; ambiguity → `ambiguous_edition`.

## 13. Remaining defects/ambiguities

1. Strict bool-as-int rejection must be explicit in the manifest validator contract (minor).
2. Rendering backend decision — unresolved (external governance).
3. Owner-approved numeric security limits — unresolved (external governance).
4. PDF-backend equivalence test — DESIGNED, not run (implementation gate).

## 14. Corrective actions (targets)

- `PIPELINE_STAGES.md` §Manifest contract: state that YAML `true`/`false` must be explicitly rejected before integer handling.
- No document changes required for items 2–4; they are owner/implementation decisions.

## 15. Checks executed / NOT RUN

- Executed: full read of the eight (now nine) ingestion docs; verified pypdf locked version (6.21.3) and capability matrix; cross-referenced R-150–157/R-181/ADR-024/037/038; verified manifests, license record, phase docs; checked remediation ledger.
- NOT RUN: no concurrency tests, PDF processing, OCR, chunking, embeddings, indexing, DB/ORM, dependency installs, or application tests.

## 16. Status of remediation ledger

All seven findings remain `DOCUMENTED` (policy: not CLOSED until a third independent gate). The second audit confirms the documentation, with the single minor parser-contract clarification above.

## 17. Post-audit owner decision

Owner-confirmed decision `hybrid_textbook_intake` (2026-11-10) was recorded after this audit in `OWNER_DECISIONS.md`, with ARCHITECTURE/PIPELINE/ACCEPTANCE updates. This decision does not alter the audit verdict and does not close any finding or Gate A/B/C.
