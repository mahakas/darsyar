# Phase 4 Ingestion Pilot — Acceptance Criteria

Two pilot textbooks:
- Mathematics, grade 2, book code `2051` — `resources/math/grade2/manifest.yaml`
- Physics (3), grade 12 (math/physics track), book code `112209` — `resources/physics/grade12/manifest.yaml`

> Status: this document defines the acceptance criteria. It is **not** evidence that they have passed. Do not report the pilot as `ready` until each gate below succeeds on the actual local files.

## A. Manifest & metadata validation

1. Required manifest fields present and valid (`path`, `subject`, `grade`, `edition_year`, `title`, `publisher`, `license_note`).
2. `subject` ∈ allowed R-151 list.
3. `grade` integer in 1–12.
4. `edition_year` is publication/printing year, not academic year.
5. Publisher, title, source origin and book code traceable to the source.
6. `license_note` is not treated as legal proof by itself (ADR-024).
7. Missing/ambiguous metadata → `needs_review` or documented ingestion failure.
8. No automatic legacy grade mapping.
9. File path, size and SHA-256 validated against the actual local PDF.
10. Idempotency identity per R-157: checksum + edition year + subject + grade.

## B. PDF integrity & page accounting

For each PDF:
- Opens without encryption.
- Physical page count confirmed.
- PDF page index vs printed textbook page number kept distinct (never conflated).
- Blank/image-only/low-text pages are not silently dropped.
- Page-level extraction outcomes recorded.

Pilot reference values:

| Metric | Mathematics 2051 | Physics 112209 |
|---|---:|---:|
| Physical PDF pages | 188 | 176 |
| File size | 37,478,046 bytes | 12,821,822 bytes |
| Pages >80 extracted text chars | 158 | 176 |
| Pages with image references | 181 | 103 |
| Total image references | 2,496 | 415 |
| SHA-256 | per manifest | per manifest |

Image references are not necessarily unique; deduplicate assets by content hash before reporting unique-image counts.

## C. Persian text extraction & OCR

1. Extract native PDF text layer first.
2. Classify page: text-dominant / image-dominant / mixed / intentionally blank.
3. Low text length = screening signal, not automatic failure.
4. Apply Persian OCR only where meaningful content exists but native text is insufficient.
5. Do not OCR genuinely blank pages.
6. A visually non-empty page yielding no text or image must not silently become an empty "successful" page.
7. Record OCR language, engine/version, confidence (where available), page index.
8. Keep original extracted text separate from normalized search text.

Math pilot note: 30 pages with <80 characters need inspection; 26 have image refs, 4 appear blank. Image-heavy pages must not be discarded for empty text layer. Math pages 36–37: page 37 has a meaningful illustration with no native text layer; its relationship to neighboring instruction must be retained.

## D. Image / illustration / diagram preservation

- Every extracted asset has stable id + content hash.
- Asset retains source document + PDF page index.
- Retain bounding-box/location metadata where available.
- Keep image↔nearby-text/question/exercise relationship.
- OCR is not a replacement for the original image.
- No unsupported image descriptions/captions generated.
- A page with a meaningful diagram remains retrievable even when OCR returns no text.

## E. Formula / graph / scientific notation (physics PDF)

Principal checks: pages 16, 54, plus one more graph-heavy page.
- Mathematical symbols and reading order correct.
- Superscripts, subscripts, fractions, Greek letters, vectors, units not silently lost.
- Decimal notation and Persian/Latin digits handled consistently without altering meaning.
- Graph axes, units, labels, legends, diagram relationships tied to correct page.
- Formula extraction visually cross-checked against source page.
- Text extraction alone is not sufficient evidence of formula/graph preservation.
- Original page/image remains the authoritative visual reference.

## F. Chunking & provenance

- Chunk boundaries do not split a formula, table, exercise instruction, or essential diagram relationship.
- Each child chunk retains `document_id`, `grade_level`, `subject`, `edition_year`, `chapter`, `page_number`, `chunk_index`, `source_origin` (R-150).
- Parent-child links stable.
- PDF page index vs printed page number not conflated.
- Source citation reconstructible from stored metadata.
- Chunking preserves context for image-heavy exercises.

## G. Idempotency & state transitions

- Re-ingesting the same PDF yields no duplicate documents/chunks.
- Controlled reprocessing replaces previous chunks atomically.
- Checksum mismatch detected.
- Invalid/incomplete metadata cannot reach `ready`.
- State transitions per R-156: `pending → processing → ready | failed | needs_review`.
- OCR failure and empty extraction have explicit error codes visible to operators.

## H. Final pilot acceptance gate

A source becomes `ready` only when:
- Manifest validation passes.
- Actual local file matches registered checksum.
- Physical PDF page count accounted for.
- Every meaningful page has a retained text or image representation.
- Image-only/mixed pages not silently lost.
- Formula/graph visual checks pass for physics sample.
- Citation metadata recoverable.
- Idempotency criteria pass.
- Required authorization reference registered per ADR-024.

> These gates define the design; they have not been executed in this task. Executed results will be reported separately.

---

# Preflight Execution Results — 2026-11-10

## A. Source integrity

**Mathematics 2051:** 188 physical PDF pages; 37,478,046 bytes; SHA-256 matches registered reference; PDF opens and is not encrypted; subject math, grade 2, edition year 1405.

**Physics 112209:** 176 physical PDF pages; 12,821,822 bytes; SHA-256 matches registered reference; PDF opens and is not encrypted; subject physics, grade 12, edition year 1405.

## B. Native text profiling

| Metric | Math 2051 | Physics 112209 |
|---|---:|---:|
| Physical pages | 188 | 176 |
| Pages >80 text characters | 158 | 176 |
| Pages ≤80 text characters | 30 | 0 |
| Pages with image resources (Method B) | 181 | 103 |
| Total image resource references (Method B) | 2,496 | 415 |
| Pages with displayed image occurrences (Method A) | 181 | 155 |
| Displayed image occurrences (Method A) | 7,060 | 3,345 |

Counting methods:

- Method A: `page.get_image_info(xrefs=True)` — displayed image occurrences.
- Method B: `page.get_images(full=True)` — referenced image resources.
- Method C: image blocks from `page.get_text("dict")`.
- Method D: image placement rectangles via `page.get_image_rects()`.

State:

- **Method B reproduces the historical pilot reference counts exactly** and is the canonical metric for comparison.
- Methods A, C and D are separate diagnostic metrics and must not be added to Method B.
- Resource references, displayed image occurrences, and placement rectangles have different semantics.
- Do not claim every counted reference is a unique image asset.
- Do not claim the exact cause of every difference is known unless supported by profiling evidence.

## C. Mathematics low-text pages

30 pages were classified using the technical profile. Initial heuristic: 10 `image_only`, 16 `mixed`, 4 `blank`.

Owner-reported manual visual review (only these six pages marked as manually visually reviewed):

| Physical PDF page | Manual review result |
|---|---|
| 36 | Mixed educational content and image are visually intact |
| 37 | Image-only educational illustration is visually intact |
| 182 | Confirmed blank |
| 184 | Confirmed blank |
| 186 | Confirmed blank |
| 188 | Confirmed blank |

The other 24 low-text pages retain their **provisional heuristic** classifications and are not manually verified. No OCR has been run; no OCR acceptance is claimed.

## D. Physics visual review

Owner-reported visual review of the three selected pages:

| Physical PDF page | Result |
|---|---|
| 16 | Graph and axes readable |
| 54 | Formulas, exponents, subscripts and diagrams visually intact |
| 92 | Graph and associated labels readable |

These three pages passed the selected visual review. No claim is made that all 176 physics pages were visually reviewed.

## E. Extraction strategy

**Mathematics:**
- Native text extraction is usable for the 158 pages with more than 80 extracted characters.
- Preserve original page images for image-only and mixed low-text pages.
- Retain the relationship between page 37's illustration and neighboring instructional content.
- Do not treat the four confirmed blank pages as extraction failures.
- Treat the other 24 low-text classifications as provisional pending a broader quality audit.
- OCR remains a future selective option; it has not been executed.

**Physics:**
- Native text extraction is usable as a baseline.
- Preserve the original PDF page as the authoritative visual reference for formula and graph content.
- Require visual validation for scientific notation and important diagrams during future extraction.
- The selected pages 16, 54 and 92 passed owner-reported visual review.
- Do not claim all formula-heavy pages have been visually validated.

**Both:** preserve PDF page index, physical PDF page number, and printed textbook page number as separate fields; preserve document/page provenance; deduplicate extracted assets by content hash in future ingestion.

## F. Remaining governance gate

- Owner-provided reference: **13529**.
- Registry record: **`docs/licenses/13529.md`**.
- Documentary evidence review: **pending**.
- Resource/operation scope confirmation: **pending**.
- Independent legal verification: **not performed**.

The project owner confirmed that the required permissions exist and supplied authorization reference `13529`; the owner-provided reference is registered, but no source-specific evidence artifact is yet reviewed. `license_note` remains an owner-provided reference (not proof). Neither source can be marked `ready` until the ADR-024 registry requirements are satisfied (evidence + scope review). ADR-024 is not declared fully satisfied.
