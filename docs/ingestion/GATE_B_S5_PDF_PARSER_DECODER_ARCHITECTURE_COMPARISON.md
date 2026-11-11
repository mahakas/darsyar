# Gate B-S5 — PDF Parser/Decoder Architecture and Security Comparison

**Date:** 2026-11-11. Owner decision `GATE_B_S5 = APPROVE_WITH_CONDITIONS`. Research,
source inspection, security analysis, licensing/provenance inventory, architectural
comparison, and documentation only. **No parser selection, no dependency upgrade, no
architecture change in Production, no real PDF processing.**

## 1. Owner authorization

`GATE_B_S5 = APPROVE_WITH_CONDITIONS` (2026-11-11): compare four candidates —
(A) pypdf (6.21.3 baseline vs 7.0.1 reviewed candidate), (B) pypdfium2/PDFium,
(C) PyMuPDF/MuPDF, (D) independent explicit parser/decoder orchestration (incl.
qpdf/pikepdf where evidence supports). Documentation-only; not a selection.

## 2. Current project baseline (preserved)

- Dependency lock: **pypdf==6.21.3** (`uv.lock` line 2052-2053; `pyproject.toml`
  `pypdf>=6.0,<7.0`). `PYPDF_UPGRADE: NOT_AUTHORIZED`.
- S0/S1/S2/S3/S4/S4.1 evidence as documented; **S4.2 = LAB_VALIDATION_PARTIAL**.
- Parse-time Object/XRef stream processing is **not** covered by S4.1 aggregate accounting.
- Process-per-document provides process containment, not an aggregate decompressed-byte
  guarantee; S2 resource limits are container-level unless proven otherwise.
- No pilot PDF processed; Gate A open; Gate C owner-approval-required; Gate B open.

## 3. Housekeeping — S4.2 filename

The actual report path is correctly spelled:
`docs/ingestion/GATE_B_S4_2_PARSE_TIME_DECOMPRESSION_AND_PYPDF_SECURITY_REVIEW.md`.
No `DECOMPRISSION` (misspelled) file exists and no such references exist in `docs/`.
No rename was required.

## 4. Files inspected

- `backend/pyproject.toml`, `backend/uv.lock`.
- `backend/app/services/ingestion/` (`pdf_validation.py`, `parent_child_contract.py`,
  `parent_supervisor.py`, `pdf_child.py`, `linux_sandbox.py`).
- Tests: S0–S4.2 (`tests/test_gate_b_*.py`, `tests/sandbox/`).
- Docs: `GATE_A_RENDERER_DECISION.md`, `PDFIUM_LICENSE_INVENTORY.md`,
  `GATE_B_S3_NUMERIC_POLICY_OWNER_DECISION.md`,
  `GATE_B_S4_1_AGGREGATE_DECOMPRESSION_COVERAGE.md`,
  `GATE_B_S4_2_PARSE_TIME_DECOMPRESSION_AND_PYPDF_SECURITY_REVIEW.md`,
  `INGESTION_PROGRESS_AND_OPEN_DECISIONS.md`, `docs/FILE_MAP.md`.

## 5. Candidate A — pypdf 6.21.3 vs 7.0.1

### Version history (verified via official releases page, access 2026-11-11)

| Version | Release date | Role |
|---|---|---|
| 6.21.3 | 2026-10-27 | locked baseline |
| 6.21.4 | 2026-10-28 | intermediate security release |
| 7.0.0 | 2026-11-06 | security-related major |
| 7.0.1 | 2026-11-10 | follow-up security (Latest) |

### Advisory matrix (verified via official GitHub advisory pages, access 2026-11-11)

| Advisory | Issue | Affected | Patched | CVE | 6.21.3 | 6.21.4 | 7.0.0 | 7.0.1 |
|---|---|---|---|---|---|---|---|---|
| GHSA-rfv5-695j-j993 | image size limits | <7.0.0 | >=7.0.0 | — | VULNERABLE_PATH_PRESENT | same | FIX_PRESENT_SOURCE_ONLY | same |
| GHSA-59jv-x5x2-gg4c | XRef duplicate offsets | <7.0.0 | >=7.0.0 | — | VULNERABLE_PATH_PRESENT | same | FIX_PRESENT_SOURCE_ONLY | same |
| GHSA-cmpx-464x-82c3 | XFA forms | <7.0.0 | >=7.0.0 | — | VULNERABLE_PATH_PRESENT | same | FIX_PRESENT_SOURCE_ONLY | same |
| GHSA-fhff-j4m8-439h | image buffer-size follow-up | <7.0.1 | >=7.0.1 | — | n/a | n/a | vulnerable | INCONCLUSIVE |
| GHSA-cggf-277g-3q54 | page-tree large memory usage | <6.21.4 | >=6.21.4 | CVE-2026-119204 | VULNERABLE_PATH_PRESENT | FIX_PRESENT_SOURCE_ONLY | N/A | N/A |
| GHSA-5849-834g-hvw5 | XRef EOF infinite loop | <6.21.4 | >=6.21.4 | CVE-2026-119203 | VULNERABLE_PATH_PRESENT | FIX_PRESENT_SOURCE_ONLY | N/A | N/A |
| GHSA-mfr5-77xh-9j7h | Dictionary clone infinite loop | <6.21.4 | >=6.21.4 | CVE-2026-119205 | VULNERABLE_PATH_PRESENT | FIX_PRESENT_SOURCE_ONLY | N/A | N/A |

- The three additional 6.21.4 advisories were verified against the official pages; their
  patch PRs are #4290 (page-tree), #4289 (XRef EOF), #4288 (Dictionary clone) — matching
  the 6.21.4 release note security entries.
- The 7.0.1 release note confirms "Determine image buffer sizes using the actual bytes per
  pixel (#4374)" → the GHSA-fhff follow-up fix is present in 7.0.1. Exact runtime behavior
  was not reproduced here → `FIX_PRESENT_SOURCE_ONLY` for 7.0.1.
- Source patches are **not** runtime-verified regression tests; only the per-filter zlib
  limit was runtime-verified (S4/S4.1/S4.2).

### Parser/decoder architecture

- Pure-Python; parse-time Object/XRef stream decode hidden in `PdfReader.__init__`
  (S4.2) → not coverable from the first operation without orchestration.
- Lazy content decode under scoped `Configuration`; per-filter/per-stream caps exist
  (zlib/lzw/runlength/jbig2/brotli = 75M; image buffer 75M; flate columns/row; script
  caps). No public aggregate document-level budget; XFA cap only from 7.0.0.
- Complete interception would require monkey-patching internals → not clean; an explicit
  orchestration layer is the leading approach in this analysis (a candidate, not the only
  possible solution). Process isolation via subprocess is fine.

### Locked-version risk statement

The current lock `pypdf==6.21.3` is a **historical project baseline**, not an approved
version for processing untrusted real PDFs. It remains within all **seven** advisory
ranges (four `<7.0.0` + three `<6.21.4`). It is not upgraded; `PYPDF_UPGRADE:
NOT_AUTHORIZED`.

## 6. Candidate B — pypdfium2 / PDFium

- Native (bundled PDFium) wrapper; permissive wrapper license; **low provenance /
  license clearance** requires verifying the exact wheel's THIRD_PARTY notices and the
  bundled binary SHA-256 (PDFIUM_LICENSE_INVENTORY.md already flags gaps).
- Low-level bindings; page rendering with explicit width/height/DPI/buffers; **PDFium is
  not thread-safe** — official docs recommend processes; fits our one-process-per-document
  model and Linux sandbox.
- No public API enforces a document-wide decompressed-byte budget; bounded rendering is
  not a decompression budget. Native crash containment requires process termination.

## 7. Candidate C — PyMuPDF / MuPDF

- Rich native binding; AGPL (open) plus commercial licensing; MuPDF embedded; official docs
  advise separate processes over threads.
- Resource/cache controls exist (e.g., `TOOLS.store_shrink()`), but that is **cache
  management, not a hard memory bound**; no demonstrated pre-output aggregate
  decompressed-byte budget.
- AGPL/commercial implications require qualified legal/licensing review for Darsyar's
  web/service model; no legal conclusion offered; commercial scope/cost not verified.
- Not selected; not installed.

## 8. Candidate D — independent parser/decoder orchestration

- Approaches: structural parser exposing every stream pre-output; explicit decoder pipeline
  with a bounded output sink; custom stream-filter registration/callbacks; low-level
  object/xref parser + independently controlled filters; qpdf/pikepdf as reference.
- qpdf (C++ library, JSON output, object/xref streams, container-size and filter-count
  limits, stream-filter registration) provides **useful building blocks**, but does not by
  itself expose a strict aggregate decoded-byte budget before expansion (`NOT_PROVEN`).
- **qpdf clarification:** qpdf's *container size* is an object-count (and nesting) limit;
  its *maximum stream-filter count* is a filter-count limit. Neither, by itself, is a
  document-wide decoded-byte budget. No claim is made that qpdf enforces an aggregate
  decompression budget; its API is not fully verified for that purpose (`NOT_VERIFIED`
  for the specific aggregate-metering question).
- Independent orchestration is the **leading hypothesis** for meter-every-decode-before-
  output-allocation (including parse-time Object/XRef streams) — it is not proven and not
  selected. It requires a complete stream census and a bounded sink; substantial new
  engineering; custom crypto/compression implementations are to be avoided (maintenance/
  security cost); prefer reusing well-audited filter primitives.

## 9. Mandatory comparison matrix

| Criterion | pypdf 7.0.1 | pypdfium2/PDFium | PyMuPDF/MuPDF | Independent orchestration |
|---|---|---|---|---|
| Parser type / native deps | Pure Python / none | Native (bundled PDFium) | Native (MuPDF) | Custom (or qpdf/pikepdf reference) |
| Parse-time Object/XRef visibility | Hidden (SOURCE_REVIEWED) | Exposed at lib level; wrapper-level aggregate not proven | Hidden at high level; native internals inaccessible | Designed to expose (SOURCE_REVIEWED / NOT_IMPLEMENTED) |
| Stream discovery completeness | Partial (S4.1: content; gaps) | Not proven for infl | Not proven | Fully designed; not implemented |
| Per-stream output control | YES (Configuration caps) | Bounded render; no decompress-agg | Partial/cache-level | YES (bounded sink) |
| Aggregate decompression feasibility | NOT_PROVEN (needs orchestration) | NOT_PROVEN | NOT_PROVEN | Most plausible; NOT_IMPLEMENTED |
| Image pixel/buffer constraints | `image_maximum_buffer_size` (SOURCE_REVIEWED) | Explicit DPI/size (SOURCE_REVIEWED) | Resource controls (SOURCE_REVIEWED) | To be implemented |
| XFA/resource handling | cap from 7.0.0 (SOURCE_REVIEWED) | Not proven | Not proven | To be implemented |
| Memory containment | Process/container | Process/container | Process/container | Process/container + sink |
| CPU/time containment | Container cgroup | Container cgroup | Container cgroup | Container cgroup + budget |
| Process isolation compatibility | YES (S1/S4.2) | YES (recommended) | YES (recommended) | YES |
| Thread-safety constraints | safe (pure) | NOT thread-safe | advises processes | n/a |
| Crash containment | via process | requires process | requires process | via process |
| Persian/Unicode text | NOT_TESTED | NOT_TESTED (Gate A open) | NOT_TESTED | NOT_TESTED |
| Math/formula preservation | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| Diagram/image handling | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| Linux deployment | YES | YES (wheels) | YES | YES |
| Windows development | YES | YES | YES | YES |
| Dependency/binary provenance | sdist/wheel hashed (uv.lock) | needs wheel SHA-256 + notices | needs source/binary provenance | none (custom) |
| License obligations | BSD-3-Clause (permissive) | wrapper permissive + PDFium notices; verify | AGPL + commercial | project-owned |
| Operational complexity | Low | Medium (native lifetime) | Medium (native) | High (build/maintain) |
| Aggregate-budget evidence quality | NOT_PROVEN | NOT_PROVEN | NOT_PROVEN | DESIGN (not proven) |

Classifications used: `DOCUMENTED`, `SOURCE_REVIEWED`, `EXPERIMENTALLY_PROVEN` (only zlib
per-filter limit in pypdf), `NOT_PROVEN`, `NOT_SUPPORTED`, `NOT_TESTED`, and
`LEGAL_REVIEW_REQUIRED` (PyMuPDF). No candidate received an overall score; unresolved
critical limitations remain explicit.

## 10. Darsyar-specific suitability

- FastAPI async backend: keep parsing/rendering out of the web event loop (worker/child).
- Parent Supervisor + Child model: any candidate fits a one-process-per-document child;
  PDFium/MuPDF especially require it (thread-safety/native).
- Linux container sandbox / Windows dev: all four run on both.
- Official Iranian textbook ingestion: Persian/Arabic Unicode, math/formulas/tables/graphs
  — **all NOT_TESTED** (no pilot processed; marketing/benchmarks are not evidence).
- Page citations/provenance: engine-agnostic; our outbox/citation layers already separate.
- Future OCR/rendering separately authorized → renderer selection remains a Gate A matter.
- Separation of resource authorization from parser security is maintained.

## 11. Architecture recommendation (evidence-bounded shortlist)

| Dimension | Shortlist candidate | Bounding note |
|---|---|---|
| Aggregate decompression | Independent orchestration (D) | **Leading hypothesis**, not proven; not selected |
| Future compatibility/security baseline | pypdf 7.0.1 | Candidate for isolated compatibility/security evaluation only |
| Licensing | pypdf (BSD-3-Clause) | Current baseline; not a selection |
| Future controlled rendering | pypdfium2/PDFium | Unselected **Gate A candidate** only |
| Best aggregate-decompression candidate | Independent orchestration (D) | Leading hypothesis, not proven |

**Recommended research direction (hybrid D+A + process sandbox):** retain pypdf 6.21.3 as
the structural-validation engine now; pursue independent orchestration (D) as the leading
hypothesis for metering parse-time + lazy stream decode into a bounded sink (so GB-04
could become technically enforceable, pending a complete stream census and adversarial
validation); keep the one-process-per-document sandbox; evaluate pypdf 7.0.1 as a future
baseline after compatibility/security testing; keep rendering (future) in a separately
sandboxed engine under Gate A. **This is a research direction, not selected Production
architecture.**

**Fallback (Option A):** retain pypdf and defer strict aggregate budgeting while
strengthening OS/process + container containment; do not claim GB-04 enforceability.

### Licensing / provenance reconciliation

- **pypdf**: declares BSD-3-Clause; pure-Python; no native binary; dependency/license
  inventory is in the project lock (sdist/wheel hashed). No external binary provenance
  question.
- **pypdfium2/PDFium**: separate the *wrapper* license from the *bundled native PDFium*
  and its third-party components. Exact wheel SHA-256 + bundled THIRD_PARTY notices remain
  required; build-specific notices are unresolved. Renderer dimension limits ≠
  decompression-byte limits.
- **PyMuPDF/MuPDF**: AGPL (open) and commercial licensing exist; MuPDF version
  correspondence must be confirmed. Legal suitability for Darsyar's web/service model is
  `LEGAL_REVIEW_REQUIRED` (no incompatibility or clearance inferred).
- **qpdf/pikepdf / independent architecture**: verify the actual component licenses and
  native-de dependency obligations. The independent orchestration architecture is **not**
  blanket "project-owned" if it incorporates third-party components (e.g., qpdf/pikepdf);
  record the specific licenses.

## 12. Unresolved risks

- No engine exposes a complete, pre-output aggregate decompressed-byte budget (S4.2 gap).
- PDFium/MuPDF native provenance + exact bundled-binary license inventory unverified.
- PyMuPDF AGPL/commercial requires legal review.
- Persian/math/diagram fidelity unverified for all candidates.
- Writing/maintaining a custom parser is high-cost and must reuse audited filter primitives.

## 13. Evidence classification summary

- `EXPERIMENTALLY_PROVEN`: only the pypdf per-filter zlib limit (S4/S4.1/S4.2).
- `SOURCE_REVIEWED`: pypdf 7.0.0 advisory fixes; config fields; parse-time call graph;
  pdfium/MuPDF docs-level claims (not fetched live).
- `NOT_TESTED`: Persian/math/diagram fidelity; aggregate-budget behavior of B/C/D.
- `VERIFIED_OFFICIAL_PAGE`: pypdf releases page + the seven advisory pages (fetched
  2026-11-11; see §14).
- `NOT_VERIFIED`: web documentation for pypdfium2/PDFium, PyMuPDF, and qpdf that was not
  fetched during this task.
- `LEGAL_REVIEW_REQUIRED`: PyMuPDF licensing.

## 14. External sources (access date 2026-11-11)

**Verified this task (fetched):**
- pypdf releases: https://github.com/py-pdf/pypdf/releases — 6.21.3 (2026-10-27),
  6.21.4 (2026-10-28), 7.0.0 (2026-11-06), 7.0.1 (2026-11-10, Latest); confirms the
  6.21.4 security entries (#4290/#4289/#4288) and 7.0.1 image-byte-per-pixel (#4374).
- GHSA-rfv5-695j-j993, GHSA-59jv-x5x2-gg4c, GHSA-cmpx-464x-82c3, GHSA-fhff-j4m8-439h
  (original four) — previously reviewed; re-referenced.
- GHSA-cggf-277g-3q54 (CVE-2026-119204), GHSA-5849-834g-hvw5 (CVE-2026-119203),
  GHSA-mfr5-77xh-9j7h (CVE-2026-119205) — verified this task.

**Cited, not fetched (NOT_VERIFIED):**
- pypdfium2 readme/API/changelog: https://pypdfium2.readthedocs.io/en/stable/readme.html etc.
- PDFium: https://pdfium.googlesource.com/pdfium/
- PyMuPDF about/FAQ/tools: https://pymupdf.readthedocs.io/en/latest/about.html etc.
- qpdf docs/library: https://qpdf.readthedocs.io/en/stable/ and /library.html

Local source probes (S4.2) remain the evidence base for parser behavior; official pages
verified here provide advisory/release confirmation.

## 15. Decision packet status

```text
GATE_B_S0: IMPLEMENTED
GATE_B_S1: IMPLEMENTED
GATE_B_S2: IMPLEMENTED
GATE_B_S3: DECISION_PACKET_COMPLETE
GATE_B_S4: LAB_VALIDATION_COMPLETE
GATE_B_S4_1: LAB_VALIDATION_COMPLETE
GATE_B_S4_2: LAB_VALIDATION_PARTIAL
GATE_B_S5: ARCHITECTURE_REVIEW_PARTIAL

GB_01: APPROVED_WITH_CONDITIONS
GB_02: APPROVED_WITH_CONDITIONS
GB_03: APPROVED_WITH_CONDITIONS
GB_08: APPROVED_WITH_CONDITIONS
GB_09: APPROVED_WITH_CONDITIONS
GB_18: APPROVED_WITH_CONDITIONS

GB_04: PENDING_OWNER_DECISION
GB_05: PENDING_OWNER_DECISION
GB_06: PENDING_OWNER_DECISION
GB_07: PENDING_OWNER_DECISION
GB_10: PENDING_OWNER_DECISION
GB_11: PENDING_OWNER_DECISION
GB_12: PENDING_OWNER_DECISION
GB_13: PENDING_OWNER_DECISION
GB_14: PENDING_OWNER_DECISION
GB_15: PENDING_OWNER_DECISION
GB_16: PENDING_OWNER_DECISION
GB_17: PENDING_OWNER_DECISION

PYPDF_LOCKED_VERSION: 6.21.3
PYPDF_UPGRADE: NOT_AUTHORIZED
PDF_PARSER_SELECTION: NOT_APPROVED
PDF_RENDERER_SELECTION: NOT_APPROVED
GB_04: NOT_APPROVED

GATE_B: OPEN / OWNER_DECISION_REQUIRED
UPLOAD_API: NOT_ACTIVATED
REAL_PDF_PROCESSING: NOT_AUTHORIZED

GATE_A: OPEN
GATE_C: OWNER_APPROVAL_REQUIRED
PHASE_4: PLANNED / GATED
PHASE_5: NOT_STARTED
PRODUCTION: NOT_APPROVED
```

`GATE_B_S5: ARCHITECTURE_REVIEW_PARTIAL` — the four-way comparison packet exists and the
pypdf official-source portion is verified, but external verification of pypdfium2/PDFium,
PyMuPDF, and qpdf documentation remains `NOT_VERIFIED`, and PyMuPDF licensing remains
`LEGAL_REVIEW_REQUIRED`. It may be promoted to `ARCHITECTURE_REVIEW_COMPLETE` only after
those official-source corrections are documented. This does not approve a parser, renderer,
dependency upgrade, aggregate budget, Gate B closure, real PDF processing, or Production
deployment.
