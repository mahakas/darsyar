# Independent Knowledge Ingestion Architecture Audit

Date: 2026-11-10. Read-only audit of `docs/ingestion/*` against the current repository, AGENTS rules, and accepted ADRs.

## 1. Executive verdict

**PASS WITH CONDITIONS** — the design is coherent, faithful to ADR-024/037/038 and R-150–157, correctly labels all components as new proposals, and does not overstate pilot evidence. Implementation requires the corrections below (mostly precision/contract completion, not architectural rework).

## 2. Requirement compliance matrix (R-150 → R-157)

| Req | Source | Design doc/section | Satisfies | Notes |
|---|---|---|---|---|
| R-150 chunk provenance | AGENTS | `CHUNKING_AND_PROVENANCE.md` | Yes | All mandatory fields listed; page fields kept distinct |
| R-151 subject allowlist | AGENTS | `PIPELINE_STAGES.md` Stage 0; `ACCEPTANCE_CRITERIA.md` | Yes | `invalid_subject` failure |
| R-152 grade mapping | AGENTS | `PIPELINE_STAGES.md`; `EXTRACTION_STRATEGY.md` | Yes | no auto legacy mapping; `needs_review` |
| R-153 path/manifest | AGENTS | `ARCHITECTURE.md`; Stage 0 | Yes | ambiguous → fail/review, never guess |
| R-154 manifest fields | AGENTS | Stage 0; `ACCEPTANCE_CRITERIA.md` | Yes | R-154 fields enumerated |
| R-155 licensing | AGENTS + ADR-024 | `AUTHORIZATION_GATE.md` | Yes | fails closed; no auto-grant |
| R-156 state machine | AGENTS | `STATE_MACHINE_AND_FAILURES.md` | Yes | exact states; no skipped transitions |
| R-157 idempotency | AGENTS | `STATE_MACHINE_AND_FAILURES.md` | Yes | identity formula exact; atomic replacement |

## 3. ADR compliance matrix

| ADR | Design handling | Verdict |
|---|---|---|
| ADR-024 | Authorization gate; 13529 registered/pending; no independent-verification claim; license_note≠proof | PASS |
| ADR-037 | no auto legacy mapping; per-source review | PASS |
| ADR-038 | edition_year=printing year; ambiguity → `ambiguous_edition` | PASS |

## 4. Architecture contract audit

- Manifest validation, source registration, authorization, integrity, page inventory, text extraction, image handling, OCR eligibility, chunking, provenance, idempotency, state transitions, retry/recovery, audit/observability: all described with stage input/output/preconditions/failure.
- **Gap 1 (major):** no concrete documented/manifest **schema definition** (field types, enum values, required vs optional) beyond the R-154 field names. Add an explicit schema contract (e.g., a JSON Schema / field table with types+required) in `PIPELINE_STAGES.md` Stage 0 and `ACCEPTANCE_CRITERIA.md`.
- **Gap 2 (major):** persistence tables/fields are described as roles but no concrete field/schema mapping (document, page, asset, text, chunk). A schema decision is a prerequisite to implementation (do not invent a DB; define the table set).

## 5. Authorization safety audit

- Reference 13529 does **not** auto-grant; owner confirmation distinct from evidence; per-resource/per-operation; pending fails closed; reasons recorded; preflight observations not presented as production approval. No bypass path found. **PASS.**

## 6. Extraction strategy audit

- Mathematics and Physics designs match the verified profiles exactly (counts, six manually reviewed math pages, three physics pages, Method B canonical, methods A/C/D kept distinct). No overstatement. **PASS.**
- Correction: state explicitly in `EXTRACTION_STRATEGY.md` that **Method B metrics are PyMuPDF-semantics** and that the production PDF backend must implement an equivalent; the repository's locked PDF library is **pypdf** (in the `rag` extra), which does not expose `get_images(full=True)` identically — an interface mapping is required.

## 7. Chunking and provenance audit

- R-150 fields preserved; parent-child stable; printed page never inferred; image-only content retrievable with context; formulas/exercises/tables not split; citation reconstructible. **PASS.**
- Minor: add one worked example of a chunk record and a citation reconstruction to `CHUNKING_AND_PROVENANCE.md`.

## 8. Idempotency and recovery audit

- R-156/R-157 exact; atomic chunk replacement; duplicate prevention; interrupted recovery described; no successful-empty-extraction for authorization-blocked/corrupt docs. **PASS.**
- Minor: specify concurrent-processing protection (how two workers on same document are serialized/locked) explicitly in `STATE_MACHINE_AND_FAILURES.md`.

## 9. Backend compatibility audit

| Proposed component | Actual backend | Classification |
|---|---|---|
| Ingestion stages | none | New design proposal |
| Worker/job host | `backend/app/services/worker.py` (arq WorkerSettings + cron) | Existing implementation — should host ingestion jobs |
| PDF parsing backend | pypdf/Pillow in `rag` extra (not default) | Existing approved dependency (extra) — design must target pypdf semantics or a provider abstraction |
| Page/image metrics (A–D) | PyMuPDF preflight only | Unverified assumption for production unless mapped to a chosen backend |
| Storage | no doc/page/asset/chunk models | New design proposal (schema prerequisite) |
| Audit/observability | existing logging/metrics patterns | Reuse; new stage-specific schema |

- No contradictions; the main unverified assumption is the PDF-backend equivalence (pypdf vs PyMuPDF).

## 10. Security findings

- Path traversal, size/page limits, MIME, malformed-PDF, untrusted-content handling, and audit are specified. Good.
- Minor: add explicit instruction that untrusted document content must never be executed/interpreted as instructions (align with R-181) and a size/page-limit default set.

## 11. Critical defects

- None.

## 12. Major gaps

1. Concrete manifest/document schema definition (types + required) — `PIPELINE_STAGES.md`, `ACCEPTANCE_CRITERIA.md`.
2. PDF-backend interface contract (pypdf vs PyMuPDF Method B equivalence) — `EXTRACTION_STRATEGY.md`, `ARCHITECTURE.md`.
3. Persistence schema (tables/fields) prerequisite — `ARCHITECTURE.md`, `ACCEPTANCE_CRITERIA.md`.

## 13. Minor improvements

- Worked chunk + citation example (`CHUNKING_AND_PROVENANCE.md`).
- Concurrent-processing protection detail (`STATE_MACHINE_AND_FAILURES.md`).
- Security defaults (page-count/size limits; R-181 alignment) (`ARCHITECTURE.md`).

## 14. Required corrections (target doc/section)

1. Add manifest schema to `PIPELINE_STAGES.md` §Stage 0 and `ACCEPTANCE_CRITERIA.md` §Registration.
2. Add PDF-backend contract + Method B equivalence to `EXTRACTION_STRATEGY.md` §Metric use and `ARCHITECTURE.md` §Boundaries.
3. Add persistence table/field schema proposal to `ARCHITECTURE.md` §Storage roles and `ACCEPTANCE_CRITERIA.md`.
4. Add chunk + citation example to `CHUNKING_AND_PROVENANCE.md`.
5. Add concurrency/locking to `STATE_MACHINE_AND_FAILURES.md`.
6. Add security defaults to `ARCHITECTURE.md` §Security.

## 15. Final readiness verdict

SkillPASS WITH CONDITIONS** — coherent and lawful; address the three major gaps (schema, PDF-backend contract, persistence schema) before implementation. No code changes made by this audit.

## 16. Remediation ledger

| Finding | Original severity | Target document | Remediation status |
|---|---|---|---|
| Manifest/document schema | Major | PIPELINE_STAGES.md, ARCHITECTURE.md, ACCEPTANCE_CRITERIA.md | DOCUMENTED |
| PDF backend contract | Major | ARCHITECTURE.md, EXTRACTION_STRATEGY.md, PIPELINE_STAGES.md | DOCUMENTED |
| Persistence schema | Major | ARCHITECTURE.md, ACCEPTANCE_CRITERIA.md | DOCUMENTED |
| Chunk/citation example | Minor | CHUNKING_AND_PROVENANCE.md | DOCUMENTED |
| Concurrency/locking | Minor | STATE_MACHINE_AND_FAILURES.md | DOCUMENTED |
| Security defaults/R-181 | Minor | ARCHITECTURE.md | DOCUMENTED |
| Legal-status wording precision | Minor | README.md, DESIGN_REVIEW.md, AUTHORIZATION_GATE.md | DOCUMENTED |

Per policy, statuses are `DOCUMENTED` (not `CLOSED`); all remediation entries require a second independent audit before closure.

Second audit (2026-11-10) confirms each item's documentation is present and consistent (`docs/ingestion/SECOND_AUDIT.md`). One minor parser-contract clarification remains (reject YAML bool before integer cast). Statuses remain `DOCUMENTED`; none are CLOSED.

Owner-confirmed decision `hybrid_textbook_intake` (2026-11-10) is recorded in `OWNER_DECISIONS.md`; ARCHITECTURE/PIPELINE/ACCEPTANCE updated accordingly. This does not close any audit finding or Gate A/B/C.
