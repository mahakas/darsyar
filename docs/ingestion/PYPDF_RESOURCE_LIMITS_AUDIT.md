# pypdf 6.21.4 Resource-Limit Audit — Darsyar Gate B-S0

**Date:** 2026-11-11. **Synthetic-only audit.** Verifies the actual resource-protection
behavior of the installed pypdf and reconciles it with the Gate B documentation. No
dependency was changed, upgraded, or downgraded. No operational policy was introduced.

## 1. Installed and locked versions

| Source | Version |
|---|---|
| Installed (local venv used for tests) | **pypdf 6.21.4** |
| Locked (`backend/uv.lock`) | **pypdf 6.21.3** |

The two differ because the lockfile was frozen at 6.21.3 while the working venv has
6.21.4. This audit reflects the **installed 6.21.4** (source of test behavior). No
dependency change was made; the discrepancy is recorded and should be reconciled by a
separate, authorized dependency update if desired.

### Version-parity audit (2026-11-11) — isolated pypdf 6.21.3

A separate isolated environment was created (`uv venv`, Python 3.13.14) with exactly
`pypdf==6.21.3` (the locked version). The full synthetic test suite was re-run there.

- **Configuration API identical (verified by introspection):** all audited fields and
  defaults match 6.21.4 exactly: `maximum_declared_stream_length=75M`,
  `zlib/jbig2/lzw/run_length/brotli_maximum_output_length=75M`,
  `zlib_maximum_recovery_input_length=5M`, `image_maximum_buffer_size=75M`,
  `stream_filters_maximum_length=16`, `stream_decoding_work_maximum_length=300M`,
  `stream_parsing_work_maximum_count=2M`, `page_tree_maximum_entries=100k`.
- **`get_configuration` / `apply_configuration` / `overwrite_configuration` signatures
  identical**, and configuration is scoped via `ContextVar`
  (`CURRENT_CONFIGURATION`).
- **`PdfReader.__init__` signature identical:** `(stream, strict=False, password=None,
  *, root_object_recovery_limit=10000, xref_stream_maximum_entries=2000000)`; no
  `configuration=` kwarg → default Configuration active.
- **Test results under 6.21.3:** `pytest tests/test_gate_b_pdf_validation.py -q` →
  **22 passed, 0 failed** (identical set, including the new
  `test_pypdf_scoped_configuration_is_restored_after_context_exit`).
- **Test results under 6.21.4:** same suite → **22 passed, 0 failed**.

**Conclusion:** 6.21.3 and 6.21.4 are behaviorally identical for all audited resource
limits, Configuration API, parser behavior, and the Darsyar validation path. No
version-specific difference was found for the security-relevant behavior examined.
Unverified by this audit: any change between the two versions outside the exercised
paths (e.g., unrelated parser fixes or new features) — parity is established only for
the audited surface.

---

## 2. pypdf `Configuration` capabilities (6.21.4)

`pypdf.Configuration` (module `pypdf._configuration`) provides a dataclass of per-filter
and per-stream resource limits. Defaults (verified by introspection):

| Field | Default | What it limits |
|---|---|---|
| `maximum_declared_stream_length` | 75,000,000 | A single stream's declared `/Length`; guards against absurd declared sizes |
| `array_based_stream_maximum_output_length` | 75,000,000 | Output of array-based stream decoding |
| `array_maximum_element_count` | 100,000 | Elements in a parsed array |
| `dictionary_maximum_element_count` | 100,000 | Entries in a parsed dictionary |
| `jbig2_maximum_output_length` | 75,000,000 | JBIG2 decode output (per stream) |
| `lzw_maximum_output_length` | 75,000,000 | LZW decode output (per stream) |
| `run_length_maximum_output_length` | 75,000,000 | RunLength decode output (per stream) |
| `zlib_maximum_output_length` | 75,000,000 | zlib (FlateDecode) output per `decompress` call |
| `zlib_maximum_recovery_input_length` | 5,000,000 | Input budget for zlib error recovery |
| `brotli_maximum_output_length` | 75,000,000 | Brotli decode output (per stream) |
| `flate_maximum_columns` | 250,000 | Columns when decoding Flate row data |
| `flate_maximum_row_length` | 4,000,000 | Flate row length bound |
| `image_maximum_buffer_size` | 75,000,000 | Image pixel buffer bound |
| `stream_filters_maximum_length` | 16 | Max chained stream filters |
| `stream_decoding_work_maximum_length` | 300,000,000 | Work budget for a single decoding operation |
| `stream_parsing_work_maximum_count` | 2,000,000 | Work count for stream parsing |
| `xmp_maximum_input_length` | 5,000,000 | XMP input bound |
| `outline_maximum_entries` / `_depth` | 100,000 / 100 | Outline (bookmark) bounds |
| `page_tree_maximum_entries` | 100,000 | Page-tree node entries |
| `page_tree_maximum_depth` | 100 | Page-tree depth |
| `page_tree_maximum_page_entries` | 2,000,000 | Total pages bound in page tree |
| `form_fields_maximum_entries` / `_depth` | 100,000 / 100 | Form-field bounds |
| `xform_maximum_invocations_per_extraction` | 5,000 | XObject form invocations per extraction |

**Important:** these are **per-filter / per-stream** safeguards. They are **not** a
single global, document-wide decompression budget. An aggregate document with many
streams each under their individual caps is not bounded as a whole by Configuration
alone.

---

## 3. Actual validator behavior (verified)

`pdf_validation.py` constructs `pypdf.PdfReader(io.BytesIO(data), strict=False)`:

1. **Default Configuration is active.** `PdfReader.__init__` accepts no `configuration=`
   argument (verified); no code in `pdf_validation.py` calls `apply_configuration` /
   `overwrite_configuration` / `set_configuration`. Therefore pypdf's process-global
   default Configuration is in effect. Nothing overrides or disables the built-in limits.
2. **Page-count parsing does not decode embedded content streams.** `len(reader.pages)`
   walks the page tree; it does not decompress content streams. Verified: a synthetic
   FlateDecode content stream validates successfully even under a deliberately tiny
   test-only `zlib_maximum_output_length=1` — page counting stays `VALID`.
3. **Decompression limits are exercised only when streams are actually decoded.** The
   current validation path therefore exercises **none** of the per-filter decode caps
   (zlib/JBIG2/LZW/run-length/Brotli/image) because it never decodes streams.
4. **No unnecessary stream decoding.** The validator never calls `.get_data()` /
   `extract_text()`; it never reads stream bytes beyond parsing metadata.
5. **Unsupported compression filters.** Because the validator does not decode streams,
   it cannot be bypassed by an unknown filter in validation; but it also does not
   verify filter safety. A document whose streams use exotic filters would still pass
   structural validation and page-count checks — the filter is only ever evaluated
   when a future rendering/extraction stage decodes it.
6. **Aggregate document-wide bounds are absent.** Configuration caps per stream; there is
   no enforced aggregate memory/CPU budget for a full document. Combined with (2)-(3),
   the validator does not deliver global decompression-bomb protection.
7. **OS-level controls are unimplemented.** No child-process isolation, CPU quota, RAM
   limit, or wall-clock timeout is enforced by the validator or the surrounding S0 code
   (consistent with the Gate B assessment).

### Verified vs assumed

- **Verified:** default Configuration active; no override; page count does not decode
  streams; tiny zlib cap does not affect page count; decoding under a tiny cap raises
  `LimitReachedError` (a `PyPdfError` subclass → safely mappable).
- **Assumed/absent:** aggregate document-wide budget, OS isolation, filter-safety
  verification, and any operational threshold.

---

## 4. Synthetic tests (test-only Configuration)

Added to `backend/tests/test_gate_b_pdf_validation.py`:

| Test | Result |
|---|---|
| `test_pypdf_default_configuration_is_active_and_unmodified` | PASS — asserts the documented defaults are active and unmodified |
| `test_page_count_does_not_decode_content_streams` | PASS — tiny `zlib_maximum_output_length=1` does not trip page-count validation |
| `test_pypdf_builtin_zlib_limit_rejects_oversized_stream_on_decode` | PASS — decoding an oversized synthetic stream under a tiny cap raises `LimitReachedError` |
| `test_pypdf_parser_limit_exceptions_are_safe_pypdf_error_subclass` | PASS — `LimitReachedError < PyPdfError` |
| `test_pypdf_scoped_configuration_is_restored_after_context_exit` | PASS — `apply_configuration` scopes and restores the prior value |

Full run (6.21.3 and 6.21.4): `pytest tests/test_gate_b_pdf_validation.py -q` →
**22 passed, 0 failed** each.

No real decompression bomb was created; test configs are deliberately small, synthetic,
and scoped via `apply_configuration` context managers (restored after each test). No
pilot PDF was opened; no rendering/extraction occurred.

---

## 5. Documentation reconciliation

Distinction recorded in `GATE_B_PDF_VALIDATION_IMPLEMENTATION.md` and
`GATE_B_PDF_SECURITY_LIMITS_OWNER_DECISION.md`:

- **pypdf built-in per-filter/per-stream safeguards** — present, default-enabled
  (75 MB per filter; 5 MB zlib recovery; 16 filters; work caps; page-tree caps).
- **Limits actually exercised by Darsyar's validator** — none of the decode filters
  (page count does not decode streams); only the sized byte-limit + page-count policy
  are exercised (caller-supplied).
- **Global/document-wide limits** — absent (no aggregate decompression budget).
- **OS-level CPU/RAM/timeout/process-isolation controls** — unimplemented in S0.
- **Darsyar operational limits** — awaiting owner approval (file size, pages, DPI,
  timeouts, memory/CPU, child capacity, temp quota, concurrency, rate limits, admin auth).

The previous statement in the implementation doc is corrected to be precise: pypdf's
75 MB defaults are **per-filter** decode caps, not a document-wide budget; and the
validator does not currently trigger them.

---

## 6. Final status

```text
GATE_B_S0: IMPLEMENTED
GATE_B_SYNTHETIC_VALIDATION: PASSED
GATE_B: OPEN / OWNER_DECISION_REQUIRED

UPLOAD_API: NOT_ACTIVATED
REAL_PDF_PROCESSING: NOT_AUTHORIZED
PILOT_MANIFESTS: needs_review

GATE_A: OPEN
GATE_C: OWNER_APPROVAL_REQUIRED
PRODUCTION: NOT_APPROVED
```

No production policy change was made. If a production decompression budget or OS
isolation is desired, it requires a separate, authorized design and owner approval.
