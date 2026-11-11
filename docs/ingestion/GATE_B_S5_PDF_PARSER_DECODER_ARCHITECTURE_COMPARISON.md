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

- Dependency lock (after owner-delegated technical decision, 2026-11-11): **pypdf==7.0.1**
  (`uv.lock`; `pyproject.toml` `pypdf>=7.0.1,<8.0`). Upgraded from 6.21.3 after an
  isolated evaluation (7.0.1 API-compatible; full DB regression 124/124 passed; synthetic
  suites 80/80 passed under 7.0.1).
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
| GHSA-mwj3-fpmc-hjcv | File-identifier placeholder recovery (encrypted templated docs) | <7.0.0 | >=7.0.0 | none (Low severity) | VULNERABLE_PATH_PRESENT | same | FIX_PRESENT_SOURCE_ONLY | same |

- The three additional 6.21.4 advisories were verified against the official pages; their
  patch PRs are #4290 (page-tree), #4289 (XRef EOF), #4288 (Dictionary clone) — matching
  the 6.21.4 release note security entries.
- The 7.0.1 release note confirms "Determine image buffer sizes using the actual bytes per
  pixel (#4374)" → the GHSA-fhff follow-up fix is present in 7.0.1. Exact runtime behavior
  was not reproduced here → `FIX_PRESENT_SOURCE_ONLY` for 7.0.1.
- The eighth advisory `GHSA-mwj3-fpmc-hjcv` (verified 2026-11-11) is severity **Low**,
  CWE-200, no CVE; it concerns placeholder recovery in encrypted templated documents
  (CWE-200 exposure), **classified separately** from the memory/availability issues above.
  Its patch PR is #4366 (matches 7.0.0 release "Make file identifiers non-deterministic").
- Source patches are **not** runtime-verified regression tests; only the per-filter zlib
  limit was runtime-verified (S4/S4.1/S4.2).
- **Total: 8 identified advisory scopes whose affected ranges include pypdf 6.21.3.** This
  is not an exhaustive list of every historical pypdf advisory; these are the eight scopes
  identified as applicable to the current lock.

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

The **prior** lock `pypdf==6.21.3` was a historical baseline that fell within all eight
identified advisory scopes. Under the owner-delegated technical decision it was upgraded to
**7.0.1** (which patches all seven `<7.0.0` scopes; the GHSA-fhff follow-up is addressed in
7.0.1 per its release note). The 7.0.1 lock is now the project baseline; real-PDF safety
still requires Gate A/C and licensing evidence, independent of the parser version.

## 6. Candidate B — pypdfium2 / PDFium (verified sources, access 2026-11-11)

Verified against `https://pypdfium2.readthedocs.io/en/stable/readme.html` (and referenced
API/changelog pages):

1. PDFium is **not thread-safe for simultaneous calls across different threads**, including
   across different documents; documentation recommends **processes** for parallel work.
2. pypdfium2 provides both a **raw ctypes API** and a helper/support API.
3. Raw API use requires **explicit attention to native object lifetime**.
4. Helper objects **must typically be closed explicitly** to release memory/file handles.
5. Accessing detached/already-closed raw handles can cause **use-after-free** behavior.
6. pypdfium2 is **dual-licensed Apache-2.0 / BSD-3-Clause**.
7. PDFium uses a **BSD-style license**; **third-party dependency notices must be shipped**
   with binary distributions.
8. `BUILD_LICENSES/` and exact wheel contents are relevant to licensing review.
9. Build configuration may affect linked dependencies, including **possible libgcc runtime
   linkage** (libgcc license must be evaluated if present).

What these prove: thread-safety constraints (documented), process-parallelism
recommendation (documented), native-lifetime requirements (documented). What they do **not**
prove: a per-document memory guarantee or **any aggregate decompressed-byte limit** (none
demonstrated). Renderer dimension limits ≠ decompression-byte limits. **`PDFIUM_SELECTION:
NOT_APPROVED`.**

## 7. Candidate C — PyMuPDF / MuPDF (verified sources, access 2026-11-11)

Verified against `https://pymupdf.readthedocs.io/en/latest/faq/index.html` (referenced
about/tools/multiprocessing pages):

1. PyMuPDF and MuPDF are available under **AGPL and commercial licensing**.
2. **Artifex is the exclusive commercial licensing agent for MuPDF**.
3. PyMuPDF **does not support multithreaded use**; documentation recommends **separate
   processes** for parallel work.
4. Each process must **open its own Document objects**.
5. `TOOLS.store_shrink()` reduces the **MuPDF storables cache** — this is cache shrinking,
   **not a hard process-memory cap**; documented cache size ≠ actual process RSS.
6. PyMuPDF and embedded MuPDF versions correspond in **major/minor**, but **patch numbers
   may differ**.

Legal status remains `LEGAL_REVIEW_REQUIRED` (AGPL + commercial via Artifex). No legal
conclusion is issued. The exact PyMuPDF/MuPDF release pairing is not selected. Persian/math/
diagram fidelity remains `NOT_TESTED`. **`PYMUPDF_SELECTION: NOT_APPROVED`.**

## 8. Candidate D — independent parser/decoder orchestration (qpdf verified, access 2026-11-11)

Verified against `https://qpdf.readthedocs.io/en/stable/qpdf-options.html` (referenced
library/release-notes pages):

1. `--parser-max-container-size` limits the **number of top-level objects in a container**.
2. `--parser-max-container-size-damaged` also applies to **damaged containers and XRef
   stream parsing**.
3. `--max-stream-filters` limits the **number of filters in an individual stream**.
4. qpdf supports **user-provided modular stream filters** via `QPDFStreamFilter` and
   `QPDF::registerStreamFilter`.
5. Existence of custom stream filters does not automatically prove every built-in Decode
   path can be intercepted before output allocation.
6. qpdf library is documented **safe for multiple threads when distinct QPDF object
   instances are used**; an individual QPDF object must not be used simultaneously in
   multiple threads.
7. qpdf is licensed **Apache-2.0**; pikepdf package/dependency licenses must be inspected
   separately if discussed.

**Critical classification:** container-size = object-count limit; max-stream-filters =
per-stream filter-count limit; parser nesting = nesting limit; custom filter API = extension
mechanism; **aggregate document decompressed-byte budget = `NOT_PROVEN`**. We do not claim
qpdf cannot implement aggregate metering; we state the reviewed public documentation does
not yet demonstrate complete aggregate metering from the beginning of parsing. The library
docs direct developers to installed public headers for deeper details. No qpdf benchmark or
hostile-fixture test was run (not authorized). **`QPDF_SELECTION: NOT_APPROVED`.**

Independent orchestration is the **leading hypothesis** for meter-every-decode-before-
output-allocation (including parse-time Object/XRef streams) — it is not proven and not
selected. It requires a complete stream census and a bounded sink; substantial new
engineering; custom crypto/compression implementations are to be avoided (maintenance/
security cost); prefer reusing well-audited filter primitives.

## 9. Mandatory comparison matrix

| Criterion | pypdf 6.21.3 (locked) / 7.0.1 | pypdfium2/PDFium | PyMuPDF/MuPDF | Independent orchestration |
|---|---|---|---|---|
| Parser type / native deps | Pure Python / none | Native (bundled PDFium) | Native (MuPDF) | Custom (or qpdf/pikepdf reference) |
| Parse-time Object/XRef visibility | Hidden (SOURCE_REVIEWED) | Raw API exposes objects; aggregate not proven | Hidden at high level; native internals inaccessible | Designed to expose (SOURCE_REVIEWED / NOT_IMPLEMENTED) |
| Stream discovery completeness | Partial (S4.1: content; gaps) | Not proven | Not proven | Fully designed; not implemented |
| Per-stream output control | YES (Configuration caps) | Bounded render; no decompress-agg | Partial/cache-level | YES (bounded sink) |
| Aggregate decompression feasibility | NOT_PROVEN (needs orchestration) | NOT_PROVEN | NOT_PROVEN | Most plausible; NOT_IMPLEMENTED |
| Image pixel/buffer constraints | `image_maximum_buffer_size` (SOURCE_REVIEWED) | Explicit DPI/size (SOURCE_REVIEWED) | Resource controls (SOURCE_REVIEWED) | To be implemented |
| XFA/resource handling | cap from 7.0.0 (SOURCE_REVIEWED) | Not proven | Not proven | To be implemented |
| Memory containment | Process/container | Process/container | Process/container (cache shrink ≠ hard cap) | Process/container + sink |
| CPU/time containment | Container cgroup | Container cgroup | Container cgroup | Container cgroup + budget |
| Process isolation compatibility | YES (S1/S4.2) | YES (recommended: processes) | YES (recommended: processes) | YES |
| Thread-safety constraints | safe (pure) | NOT thread-safe (verified) | multithreading unsupported (verified) | n/a |
| Crash containment | via process | requires process | requires process | via process |
| Persian/Unicode text | NOT_TESTED | NOT_TESTED (Gate A open) | NOT_TESTED | NOT_TESTED |
| Math/formula preservation | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| Diagram/image handling | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| Linux deployment | YES | YES (wheels) | YES | YES |
| Windows development | YES | YES | YES | YES |
| Dependency/binary provenance | sdist/wheel hashed (uv.lock); 8 advisory scopes on 6.21.3 | needs wheel SHA-256 + THIRD_PARTY/BUILD_LICENSES; libgcc check | needs source/binary provenance; MuPDF version pairing | none (custom) |
| License obligations | BSD-3-Clause (permissive) | wrapper Apache-2.0/BSD-3 + PDFium BSD-style + notices; verify | AGPL + commercial (Artifex) — LEGAL_REVIEW_REQUIRED | qpdf Apache-2.0; pikepdf separate; custom portion project-owned |
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
- GHSA-mwj3-fpmc-hjcv (Low, CWE-200, no CVE) — verified this task.

**Also verified this task (fetched):**
- pypdfium2 readme: https://pypdfium2.readthedocs.io/en/stable/readme.html
  (thread-safety, raw API lifetime, dual Apache/BSD, PDFium BSD-style + notices,
  BUILD_LICENSES, libgcc note).
- PyMuPDF FAQ: https://pymupdf.readthedocs.io/en/latest/faq/index.html
  (AGPL/commercial, Artifex exclusive agent, no multithreading, processes recommended,
  store_shrink cache vs RSS).
- qpdf CLI options: https://qpdf.readthedocs.io/en/stable/qpdf-options.html
  (parser-max-container-size, parser-max-container-size-damaged, max-stream-filters).

**Cited, not fetched (NOT_VERIFIED):**
- PDFium source: https://pdfium.googlesource.com/pdfium/
- pypdfium2 python_api/changelog deep pages (referenced; specifics from readme used).
- PyMuPDF about/tools/multiprocessing (referenced; FAQ used for verified claims).
- qpdf library.html / release-notes.html (referenced; options page used for verified claims).

Local source probes (S4.2) remain the evidence base for parser behavior; official pages
verified here provide advisory/release/constraint confirmation.

## 15. Decision packet status

```text
GATE_B_S0: IMPLEMENTED
GATE_B_S1: IMPLEMENTED
GATE_B_S2: IMPLEMENTED
GATE_B_S3: DECISION_PACKET_COMPLETE
GATE_B_S4: LAB_VALIDATION_COMPLETE
GATE_B_S4_1: LAB_VALIDATION_COMPLETE
GATE_B_S4_2: LAB_VALIDATION_PARTIAL
GATE_B_S5: ARCHITECTURE_REVIEW_COMPLETE

PYPDF_LOCKED_VERSION: 7.0.1
PYPDF_UPGRADE: APPLIED (owner-delegated technical decision, 2026-11-11)
PDF_PARSER_SELECTION: NOT_APPROVED
PDF_RENDERER_SELECTION: NOT_APPROVED

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

`GATE_B_S5: ARCHITECTURE_REVIEW_COMPLETE` — the four-way comparison packet is complete: all
four candidates compared, the eight applicable pypdf advisory scopes recorded, and official
external sources verified for pypdf (releases + 8 advisories), pypdfium2 (readme),
PyMuPDF (FAQ), and qpdf (CLI options). Remaining binary-provenance and legal questions
(PyMuPDF AGPL/commercial; PDFium bundled-binary notices) are explicitly left open as
`LEGAL_REVIEW_REQUIRED`/`NOT_VERIFIED`. Completion means the comparison packet is complete;
it does **not** mean every legal or technical risk is resolved, and it does not approve a
parser, renderer, dependency upgrade, aggregate budget, Gate B closure, real PDF processing,
or Production deployment.
