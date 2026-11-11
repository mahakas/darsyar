# Gate B-S0 — Synthetic PDF Validation Foundation (Implementation)

**Date:** 2026-11-11. Owner decision `GATE_B-S0 = APPROVE_WITH_CONDITIONS`.

## Scope implemented

- Reusable **Common PDF Validation Layer** (`backend/app/services/ingestion/pdf_validation.py`).
- Synthetic security fixtures + focused tests (`backend/tests/test_gate_b_pdf_validation.py`).
- Versioned **Parent/Child processing contract** at type-definition level (`backend/app/services/ingestion/parent_child_contract.py`). Design only; no child is spawned.
- Synthetic-only validation. No pilot PDF, no upload API, no rendering, no extraction, no PDFium, no embedding/indexing.

## Parser

- **pypdf 6.21.4** installed locally; **lockfile pins 6.21.3** (declared in `pyproject.toml` `rag` extra: `pypdf>=6.0,<7.0`). Both versions verified behaviorally identical for the audited resource-limit/validation surface (see `PYPDF_RESOURCE_LIMITS_AUDIT.md`). Parser only — not the approved renderer. No new dependency introduced; pypdfium2 remains an unapproved conditional renderer candidate; PyMuPDF is not used.

## Validation policy contract

- `PdfValidationPolicy(max_file_bytes: int, max_pages: int)` — **no defaults, no hidden values, no config fields**. All numeric thresholds are explicit, caller-supplied. Tests use small explicit synthetic thresholds. Not connected to any active route.

## Implemented safety checks (`validate_pdf(data, policy) -> PdfValidationResult`)

| Check | Result status |
|---|---|
| Empty input | `EMPTY` |
| Exceeds caller-supplied file-byte policy | `EXCEEDS_FILE_BYTES` |
| PDF signature by actual bytes (`%PDF-`), not filename/MIME | `INVALID_SIGNATURE` |
| Structural parse via pypdf; malformed xref/structure | `MALFORMED` |
| Truncated/stream-corrupted | `TRUNCATED` |
| Encrypted / password-protected detected; never decrypted | `ENCRYPTED` (`is_encrypted=True`) |
| Page count (no text extraction; does not decode streams) | returned on `VALID`; `EXCEEDS_PAGES` if over policy |
| Parser exceptions mapped to safe typed domain outcomes | never raised to callers |
| No text extraction / no rendering / no PDFium | by design (no such code path) |
| pypdf default Configuration (per-filter/stream caps) | active, unmodified (no code override) |
| Decode-filter caps (zlib/JBIG2/LZW/.../image) | NOT exercised by validation (no stream decode) |

## Parser / decompression limitations (recorded)

- pypdf 6.21.4 ships built-in **per-filter/per-stream** resource caps via
  `Configuration` (defaults: 75 MB output per filter — zlib/JBIG2/LZW/run-length/
  Brotli/image — plus 5 MB zlib recovery input, 16 max filters, work caps, page-tree
  caps). These are **not** a single document-wide decompression budget.
- **Darsyar's validator does not decode streams**: page counting walks the page tree
  only, so none of the per-filter decode caps are exercised by the current validation
  path. The only policy checks enforced are the caller-supplied byte-limit and
  page-count limit.
- Full **decompression-bomb protection is NOT claimed**: there is no enforced global/
  document-wide aggregate budget, and OS-level CPU/RAM/timeout/process-isolation
  controls are unimplemented in S0. See `PYPDF_RESOURCE_LIMITS_AUDIT.md`.
- Encrypted-document processing is rejected by policy (no password-handling feature).

## Synthetic tests (22) — results

All fixtures generated in-memory inside tests; no persistent files; tempdir verified unchanged after runs.

```
tests/test_gate_b_pdf_validation.py -> 22 passed, 0 failed
```

Version parity: the suite passes identically under the locked **pypdf 6.21.3**
(isolated venv) and the local **6.21.4**; Configuration API, defaults, and parser
behavior match (see `PYPDF_RESOURCE_LIMITS_AUDIT.md`).

Covered: valid accepted; empty rejected; bad signature rejected; byte-level (not filename/MIME) signature; truncated rejected; malformed xref rejected; encrypted identified not accepted; page count observed; explicit file-bytes limit; explicit page-count limit; filename/MIME cannot bypass; parser exceptions → safe domain errors; compressed synthetic objects parsed per capability; no text extraction; no render/PDFium; no persistent files; signature constant; plus pypdf resource-limit audit tests (default Configuration active, page count does not decode streams, tiny zlib cap rejects oversized decode, `LimitReachedError` is a `PyPdfError` subclass).

## Lint / type

```
ruff check app -> All checks passed!
mypy app      -> Success: no issues found in 115 source files
```

## Parent/Child contract (design only)

- `PARENT_CHILD_CONTRACT_VERSION = 1`.
- `ParentChildRequest`: `contract_version`, `attempt_id`, `document_bytes`, `limits` (reserved; no numeric values invented).
- `ParentChildResult`: `contract_version`, `attempt_id`, `outcome`, `error_category`, `page_count`, `artifact_metadata` (reserved).
- Child must never receive DB URLs, DB/Redis credentials, application secrets, or unnecessary personal info. Parent owns DB access and consequential commits.
- No child process, IPC, staging, or artifact publication is implemented in S0.

## Existing request-level controls (preserved)

- `max_request_bytes = 20971520` and nginx `client_max_body_size 20m` unchanged. This is an HTTP request-body limit, not a per-PDF file-size policy. No new numeric PDF-processing limits are approved or invented.

## Remaining Gate B decisions (open)

Max file size; page count; decompressed size; DPI & pixel bounds; PDF processing timeout; parent timeout; memory/CPU limits; child-process capacity; temporary storage quota & retention; concurrent upload capacity; rate limiting; admin authorization.

## Statuses

```text
GATE_B_S0: IMPLEMENTED
GATE_B_SYNTHETIC_VALIDATION: PASSED
GATE_B: OPEN / OWNER_DECISION_REQUIRED

UPLOAD_API: NOT_ACTIVATED
REAL_PDF_PROCESSING: NOT_AUTHORIZED
PILOT_MANIFESTS: needs_review

GATE_A: OPEN
GATE_C: OWNER_APPROVAL_REQUIRED

PHASE_4: PLANNED / GATED
PHASE_5: NOT_STARTED
PRODUCTION: NOT_APPROVED
```

Gate B is not passed.
