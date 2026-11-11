# Gate B-S4.2 — Parse-Time Decompression, Process Isolation, pypdf Security Version Review

**Date:** 2026-11-11. Owner decision `GATE_B_S4_2 = APPROVE_WITH_CONDITIONS`. Bounded
laboratory + source-review task. **No dependency upgrade, production implementation,
renderer selection, upload activation, or real PDF processing.**

## 1. Owner authorization

`GATE_B_S4_2 = APPROVE_WITH_CONDITIONS` (2026-11-11): investigate implicit parse-time
decompression (Object Streams / Cross-Reference Streams), whether aggregate accounting can
cover parsing from the start, evaluate one isolated child process per document, and review
decoder limits / security-relevant changes across pypdf 6.21.3 / 6.21.4 / 7.0.0 / 7.0.1.

## 2. Package identity

Locked project version remains **pypdf==6.21.3** (`PYPDF_LOCKED_VERSION`). Probe
environments (isolated, Python 3.13.14, Windows 10/amd64):

| Version | wheel/package file | zlib-limit runtime |
|---|---|---|
| 6.21.3 | `...\pvx\pypdf_6.21.3\...\pypdf\__init__.py` | `LimitReachedError` raised ✓ |
| 6.21.4 | `...\pvx\pypdf_6.21.4\...\pypdf\__init__.py` | ✓ |
| 7.0.0 | `...\pvx\pypdf_7.0.0\...\pypdf\__init__.py` | ✓ |
| 7.0.1 | `...\pvx\pypdf_7.0.1\...\pypdf\__init__.py` | ✓ |

## 3. Parse-time call graph (6.21.3)

`PdfReader.__init__` performs, in order:
1. `_root_object_recovery_limit` assignment; 2. `_initialize_stream(stream)` — reads
   header, trailer, xref tables/streams (including `_read_xref`, `_process_xref_stream`,
   `_read_pdf15_xref_stream`); 3. `_handle_encryption(password)`.

Object streams and XRef streams are therefore **decoded during construction**, before the
S4.1 accounting hook becomes active (our hook runs only after `PdfReader` returns).
Content streams are decoded lazily on `get_data()` under our scoped budget.

## 4. Experiment A — parse-time coverage

- Object streams: implicit decode during indirect-object resolution (`_get_object_from_stream`)
  — occurs at parse/lazy-resolve time, **not covered** by the S4.1 budget. No reliable
  synthetic ObjStm fixture generated → `SOURCE_REVIEW_ONLY`, fixture `NOT_TESTED`.
- Cross-reference streams: implicit decode during `_read_pdf15_xref_stream`
  /`_process_xref_stream` — **not covered**. No reliable synthetic XRef-stream fixture →
  `SOURCE_REVIEW_ONLY`, fixture `NOT_TESTED`.
- Content streams: lazy; covered by S4.1 (tested).
- Parse-time aggregate coverage determination: **NO** (PARTIALLY if limited to content
  paths). From the first pypdf operation, object/xref-stream decompression occurs outside
  the aggregate budget; currently contained only by OS/process-level limits, not by an
  aggregate decompressed-byte ceiling.

## 5. Experiment B — one isolated child process per document

Reused production `parent_supervisor.run_child` as a library (no production module
modified). Results (17 host tests; verified in container too):

- Two normal docs sequential/concurrent in separate children: SUCCESS, correct page counts.
- One child exhausts its synthetic budget → `RESOURCE_LIMIT`; other succeeds.
- Malformed child → `MALFORMED`/`TRUNCATED`; other healthy.
- Timeout (`mode="hang"`, 1 s) → `timed_out`, terminated.
- Parent survives; subsequent independent doc succeeds after a failure.
- No orphan children; `forbidden_env_seen == []` (sentinel secrets never reach child).
- **Note:** graceful `terminate()` handled the hang; the forced-`kill()` branch was not
  deterministically exercised (it is code-covered in S1) → that sub-scenario `NOT_TESTED`.
- **Container-level cgroup is shared by all children** (no per-child cgroup); process
  isolation ≠ per-child cgroup isolation. Explicitly reported.

## 6. Experiment C — advisory & version matrix

| Capability/security issue | 6.21.3 | 6.21.4 | 7.0.0 | 7.0.1 | Evidence |
|---|---|---|---|---|---|
| Object-stream offset validation | `VULNERABLE_PATH_PRESENT` | same | `FIX_PRESENT_SOURCE_ONLY` | same | `_get_object_from_stream` changed 6.21.4→7.0.0 (len 7800→8055) |
| XRef stream duplicate offsets (GHSA-59jv-x5x2-gg4c) | `VULNERABLE_PATH_PRESENT` | same | `FIX_PRESENT_SOURCE_ONLY` | same | `_read_pdf15_xref_stream` changed 6.21.4→7.0.0 (len 2702→2690) |
| XFA work limits (GHSA-cmpx-464x-82c3) | `VULNERABLE_PATH_PRESENT` | same | `FIX_PRESENT_SOURCE_ONLY` | same | `xfa` limit field absent in 6.x; present in 7.0.0+ |
| Image output-size limits (GHSA-rfv5-695j-j993) | `VULNERABLE_PATH_PRESENT` | same | `FIX_PRESENT_SOURCE_ONLY` | same | DCTDecode/JPXDecode changed 6.21.4→7.0.0 |
| Image follow-up (GHSA-fhff-j4m8-439h) | n/a (<7.0.1) | n/a | vulnerable | `INCONCLUSIVE` | 7.0.1 differs per advisory; coarse scan didn't isolate a distinct token delta |
| Image buffer estimation (bytes/pixel) | `NOT_TESTED` (marker absent) | same | `INCONCLUSIVE` | `INCONCLUSIVE` | no `bytes_per_component` token found in any version; source-level |
| per-filter limits (zlib etc.) | `ENFORCED` (zlib) | same | same | same | runtime `LimitReachedError` verified in all four |
| Parse-time aggregate accounting | `NOT_COVERED` | same | same | same | parsing performs relevant stream (object/xref) processing; the experimental aggregate accounting does not cover it from the start |

> Note: the 7.0.0/7.0.1 cells above are `FIX_PRESENT_SOURCE_ONLY` — source-level
> findings, **not** runtime-verified fixes. The only runtime-`ENFORCED` row is the
> per-filter zlib limit (verified in all four versions). Source review must not be
> treated as a successful runtime test.

Advisory ranges (official): GHSA-rfv5/59jv/cmpx affected `< 7.0.0`, patched `>= 7.0.0`;
GHSA-fhff affected `< 7.0.1`, patched `>= 7.0.1`. **6.21.3 and 6.21.4 are within all four
affected ranges.** The project lock stays 6.21.3; upgrade is `NOT_AUTHORIZED`.

### Incomplete evidence (reconciliation)

S4.2 implemented tests and source review were completed, but the following validation
evidence remains unavailable; the overall S4.2 status is **`LAB_VALIDATION_PARTIAL`**:

1. Synthetic Object Stream fixture: `NOT_TESTED`.
2. Synthetic XRef Stream fixture: `NOT_TESTED`.
3. Parse-time aggregate accounting: `NOT_COVERED`.
4. Forced `kill()` termination branch: `NOT_TESTED`.
5. Per-child cgroup isolation: `NOT_ENFORCED` (children share the container-level cgroup).
6. pypdf 7.0.1 image follow-up regression (GHSA-fhff): `INCONCLUSIVE`.
7. Image buffer estimation across 7.0.0 / 7.0.1: `INCONCLUSIVE`.
8. Process isolation does **not** establish an aggregate decompressed-byte budget.

None of the above are relabeled as successful runtime tests.

## 7. Experiment D — decoder/filter coverage (6.21.3)

Configuration defaults: `zlib/lzw/run_length/jbig2/brotli_maximum_output_length=75M`,
`image_maximum_buffer_size=75M`, `stream_filters_maximum_length=16`,
`stream_decoding_work_maximum_length=300M`, `stream_parsing_work_maximum_count=2M`,
`flate_maximum_columns=250k`, `flate_maximum_row_length=4M`, `array_based_stream_maximum_output_length=75M`.

| Filter | Config field(s) referenced | Category |
|---|---|---|
| FlateDecode | `flate_maximum_columns`, `flate_maximum_row_length` (zlib cap enforced in shared decompress) | byte-output |
| LZWDecode | `lzw_maximum_output_length` | byte-output |
| RunLengthDecode | `run_length_maximum_output_length` | byte-output |
| BrotliDecode | `brotli_maximum_output_length` | byte-output |
| JBIG2Decode | `jbig2_maximum_output_length` | byte-output |
| DCTDecode / JPXDecode / CCITTFaxDecode | image buffer control consumed at decode-call site | image |
| ASCIIHex/ASCII85 | (no config field found) | trivial |
| Crypt | n/a | filter pipeline |

Limit categories are **separate**: byte-output caps ≠ image pixel/dimension caps ≠
intermediate-buffer memory ≠ parser work caps ≠ CPU/time ≠ aggregate document accounting. A
limit in one category is not presented as covering another.

## 8. Commands / results

```
Host: pytest ... (S0-S4.2, 11 files) -> 88 passed, 20 skipped (cgroup/linux enforcement skip off-container)
Container: same files under restricted sandbox -> 108 passed (incl. cgroup + linux enforcement)
ruff check app tests -> all passed
mypy app -> no issues (118 files)
Isolated version probes: run `pypdf_version_probe.py` in each pvx env -> JSON summaries captured above.
```

## 9. GB-04 assessment (not approved)

- Aggreg decode ceiling from the very first parse operation: **NO** (parse-time object/xref
  decompression precedes the budget).
- All decode-path discovery: **incomplete** (implicit/on-demand categories).
- Malformed/partial: fail-closed abort on exception; tolerated-malformed=0 gap remains.
- One child per document: provides process fault/resource containment, but **not** a
  decompressed-byte ceiling, and children share the container-level cgroup.
- Image/XFA limits are independent and necessary.
- 256 MiB technically feasible on content paths; **not suitable** as Production policy until
  complete coverage architecture exists. 128 MiB / alternatives remain open for evaluation.
- **GB-04 stays `PENDING_OWNER_DECISION`; 256 MiB not approved.**

## 10. Architecture recommendation

Compare A (extend S4.1 model), B (one isolated child per document), C (explicit
parser/decoder orchestration incl. parse-time + lazy decode), D (defer aggregate budgeting
until complete coverage, retain OS/container limits as separate containment).

Recommendation: **B + C + D**. Run one isolated child per document (fault isolation) with
an explicit orchestration layer that performs a complete stream census **including**
parser-implicit object/xref decode, and only then introduce aggregate budgeting; meanwhile
retain OS/container-level limits as the containment. Do not implement Production behavior.

## 11. Evidence classification

- `ENFORCED`: zlib per-filter limit (runtime), process isolation, timeout/termination/reaping,
  no-credential child, container cgroup limits (S2).
- `SOURCE_REVIEW_ONLY`: object/xref stream parse-time decode; advisory fixes in 7.0.0.
- `FIX_PRESENT_SOURCE_ONLY`: object-offset, xref-duplicate, XFA, image-size in 7.0.0.
- `INCONCLUSIVE`: GHSA-fhff follow-up detail; image buffer estimation.
- `NOT_TESTED`: reliable synthetic object/xref-stream fixtures; forced-kill branch; DCT/JPX
  large-throughput behavioral fixtures.
- `NOT_COVERED`: parse-time aggregate accounting (object/xref stream processing occurs
  during parsing but is not covered by the experimental accounting from the start).
- `INCONCLUSIVE`: GHSA-fhff follow-up detail; image buffer estimation.

## 12. Statuses

```text
GATE_B_S0: IMPLEMENTED
GATE_B_S1: IMPLEMENTED
GATE_B_S2: IMPLEMENTED
GATE_B_S3: DECISION_PACKET_COMPLETE
GATE_B_S4: LAB_VALIDATION_COMPLETE
GATE_B_S4_1: LAB_VALIDATION_COMPLETE
GATE_B_S4_2: LAB_VALIDATION_PARTIAL

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

`GATE_B_S4_2: LAB_VALIDATION_PARTIAL` — implemented tests and source review were
completed, but several required validation evidence remain unavailable (see "Incomplete
evidence"). This does not describe a failure of all S4.2 work, and it does not imply full
coverage, Production readiness, GB-04 approval, or Gate B closure.
