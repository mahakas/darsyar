# Extraction Strategy

General principles: original PDF remains authoritative; native text stays distinct from normalized text; a page is never held blank purely from empty native text; OCR is optional and separately authorized; assets are deduplicated by content hash.

## Mathematics 2051 (pilot)

Verified preflight profile:
- 188 physical pages; 158 pages >80 native chars; 30 pages ≤80 chars; 181 pages with referenced image resources (Method B, total 2,496); Method A displayed occurrences 7,060.
- 10 `image_only`, 16 `mixed`, 4 confirmed blank (182/184/186/188) — manual review.
- Pages 36 (mixed, intact) and 37 (image-only illustration, intact) are the named visual cases.

Strategy:
- Use native text for the 158 text-dominant pages.
- Retain original page images for image-only and mixed pages.
- Preserve the illustration↔neighbor relationship (e.g., page 37 with the instructional pages around it).
- Do not generate content from blank pages.
- Optional selective future OCR only where authorized and genuinely needed; not executed.
- Keep original page renders as visual evidence.

## Physics 112209 (pilot)

Verified preflight profile:
- 176 pages; 176 pages >80 native chars; 103 pages with referenced image resources (Method B, total 415); Method A displayed occurrences 3,345; 176 pages with vector drawings.
- Selected visual review: pages 16 (graph/axes readable), 54 (formulas/exponents/subscripts/diagrams intact), 92 (graph/labels readable).

Strategy:
- Native text is a usable baseline.
- Preserve original page as authoritative reference for formulas/graphs.
- Require visual validation for scientific notation and important diagrams during future extraction.
- Special care: equations, superscripts/subscripts, fractions, Greek letters, vectors, units, Persian/Latin numerals, decimal notation, graph axes, legends.
- Native text alone is **not** proof that scientific notation is preserved.
- Do not claim all 176 pages are visually validated.

## General educational-document strategy

- Text-dominant → native text.
- Image-dominant/mixed → retain images + relationship.
- Blank → no content synthesized.
- Legacy/ambiguous grade or edition → never guessed (ADR-037/038).
- All output obeys R-150 provenance and R-156 states.

## Metric use

- **Method B** (`page.get_images(full=True)`) = canonical comparison to the historical pilot reference.
- Methods A (`page.get_image_info(xrefs=True)`), C (`page.get_text("dict")` image blocks) and D (`page.get_image_rects()`) plus unique-asset counts are separate diagnostics; never summed with B.
- **Backend semantics:** Method B values above were produced with **PyMuPDF**. The production PDF backend (currently `pypdf` in the `rag` extra) does not expose identical APIs. Therefore:
  - do not force a different backend to claim Method-B equivalence unless demonstrated;
  - normalize metrics by recording `(backend, method, version)`;
  - if an exact metric cannot be reproduced, report `UNSUPPORTED` / `NOT_COMPARABLE`; never fabricate equivalence;
  - a controlled equivalence test (page count, native text, image resources, occurrences, page-level inventory, vector support) is **DESIGNED — NOT RUN**.

## Rendering decision

- `pypdf` is not a rendering library; original-page rendering is a design dependency requiring an explicit decision. Stages requiring rendering stay blocked until that capability is approved. PyMuPDF is not selected merely because it was used in temporary preflight.
