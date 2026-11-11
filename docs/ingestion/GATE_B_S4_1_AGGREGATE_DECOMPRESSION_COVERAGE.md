# Gate B-S4.1 — Aggregate Decompression Coverage, Failure Accounting, Concurrent Isolation

**Date:** 2026-11-11. Owner decision `GATE_B_S4_1 = APPROVE_WITH_CONDITIONS`.
Bounded laboratory task. **Not** GB-04 approval, not Production policy, not Gate B
closure.

## 1. Owner authorization

`GATE_B_S4_1 = APPROVE_WITH_CONDITIONS` (2026-11-11): (A) audit stream discovery/decode
coverage in `pypdf==6.21.3`; (B) investigate malformed/failed/partial decoding accounting;
(C) demonstrate independent aggregate budgets / scoped decoder configuration under
concurrent processing. Excluded: GB-04 / 256 MiB candidate, Production decompression
policy, real/pilot PDFs, upload activation, runtime changes, renderer/PDFium, Gate A/C,
Phase 4/5, Production.

## 2. pypdf 6.21.3 identity

`pypdf==6.21.3` (locked). Confirmed decoding surfaces: `EncodedStreamObject.get_data()`
under scoped `Configuration` (ContextVar via `apply_configuration`); implicit object/xref
stream decoding during reading (`_get_object_from_stream`, `_process_xref_stream`,
`_read_pdf15_xref_stream`).

## 3. Files (all test-only)

- Created: `backend/tests/sandbox/s4_1_lib.py`, `backend/tests/test_gate_b_s4_1_stream_coverage.py`,
  `backend/tests/test_gate_b_s4_1_failure_accounting.py`,
  `backend/tests/test_gate_b_s4_1_concurrency_isolation.py`.
- No production module modified; no new runtime dependency; container/Deployment unchanged.

## 4. Stream coverage matrix (Experiment A)

| Stream category | pypdf decodes? | Trigger | S4 content-only observes? | Per-stream config applies? | Consumes budget before overflow? | Cached? | Bypass? | Proven by |
|---|---|---|---|---|---|---|---|---|
| Page content stream | Yes | `get_data()` | Yes | Yes | Yes | Yes (reuse) | No | Synthetic test |
| Form XObject stream | Yes | `get_data()` on XObject | **No** | Yes (if walked) | Yes (if walked) | Yes | **Yes in S4 content-only** | Synthetic test (resource-walk covers) |
| Image XObject stream | Yes | `get_data()` on XObject | **No** | Yes (if walked) | Yes (if walked) | Yes | **Yes in S4 content-only** | Synthetic test (resource-walk covers) |
| Object stream (/Type/ObjStm) | Yes (implicit) | reading/resolving objects | **No** | Yes (parser config) | **No (implicit)** | Yes | **Yes** | Source review |
| Cross-reference stream (/Type/XRef) | Yes (implicit) | reading xref | **No** | Yes (parser config) | **No (implicit)** | Yes | **Yes** | Source review |
| Font streams | Yes (when extracted) | font extraction | No | Yes | No | Yes | Yes | Source review |
| Pattern/shading streams | Yes (when used) | render/extract | No | Yes | No | Yes | Yes | Source review |
| Embedded-file streams | Yes (when accessed) | attachment access | No | Yes | No | Yes | Yes | Source review |
| Nested/indirect stream refs | Yes | per-object decode | No | Yes | No | Yes | Yes | Source review |
| Repeated reference (same object) | cached | — | counted once | n/a | charged once | Yes | No | Synthetic test |
| Lazy decode + cache | yes | `get_data()` | yes | yes | yes (on first) | yes | no (for content) | Synthetic test |

The S4 experimental design covers **page content streams**; the resource-walk extension
proves Form/Image XObjects are coverable. Object streams, cross-reference streams, fonts,
shading/patterns, embedded files, and nested indirect refs are decoded implicitly/on-demand
and are **not** intercepted by the experimental budget.

## 5. Failure / partial accounting (Experiment B)

- Valid stream: decodes, charges budget.
- Malformed FlateDecode: **tolerated** by pypdf → 0 bytes, 0 budget (S4 finding reproduced).
- Truncated compressed stream: decoder error → orchestrator rejects (`malformed`/`limit_reached`).
- Exceeds per-stream limit or remaining aggregate: rejected before/at decode (LimitReachedError).
- Multiple malformed streams: tolerated; total stays 0; bounded (no overshoot).
- Valid-before-and-after malformed: valid streams counted; malformed contribute 0.
- Repeated access to failed stream: cached; no extra decompression work observed.
- Parse failure before any stream: `parse_error=True`, total 0.
- **Security property:** enumeration is finite and never charges more than the budget; no
  unbounded unaccounted decompression was demonstrated. However, the tolerated-zero malformed
  case undervalues attempted work (a malformed stream that costs CPU to attempt but yields 0
  is not charged). This is a residual gap, bounded by the finite enumeration and per-stream
  decode cap, but should be closed by fail-closed abort-on-error if adopted.

## 6. Accounting semantics (explicit)

- Distinct stream identity: each actual decode charges once.
- Repeated indirect reference: cached output reused; charged once (not per access).
- Failed/partial: abort document on exception (fail-closed); tolerated-malformed charged 0.
- After a decoder error, the document is rejected by the orchestrator; subsequent stream
  decoding for that document is not performed.
- A new independent document starts with a fresh budget (no global state).

## 7. Concurrent document isolation (Experiment C)

Tested models:

- **Threads:** two threads decoding A (small budget) and B (larger budget) concurrently →
  results identical to sequential baselines; A's budget never mutated by B and vice versa;
  failures in A did not affect B.
- **Async tasks:** `asyncio.gather` of A and B → each task's scoped config/budget isolated.
- **Processes:** not re-tested here; isolation is by construction (separate OS process per
  S1 child). Marked `NOT_TESTED` in this experiment (architecturally isolated).

Additional assertions: context config restored after `apply_configuration` exit; exception
does not leave stale config; repeated calls start fresh; no global budget state.

## 8. Memory/time observations

Synthetic fixtures: content/XObject streams of 1–4 MiB; budgets 4–10 MiB. Peak memory in
the 256 MiB run ~289 MiB (S4). Concurrency runs use `measure=False` (no tracemalloc) to
avoid instrumentation contention; durations are sub-second per document.

## 9. Remaining attack surfaces

- Implicit object/xref stream decoding occurs during parsing before/independent of the
  experimental budget.
- Tolerated-malformed streams charge 0 despite attempted work.
- Fonts/shading/embedded/nested streams are un-accounted.
- No post-decompression check substitutes for decoder-bounded cumulative control on those
  implicit paths.

## 10. GB-04 recommendation (not approved)

- Feasibility along the tested (content) paths: **yes** (per-stream bounded decode enforced
  the 256 MiB sum).
- Coverage of all decoding paths: **no** (implicit object/xref streams etc. are bypasses).
- Failure-path safety: partial (tolerated-malformed gap).
- Concurrency safety: demonstrated for threads/async; processes by construction.
- Suitability of 256 MiB: **not established** for production (coverage + CPU cost).

GB-04 stays `PENDING_OWNER_DECISION`.

## 11. Q&A conclusions

- Q1 Stream coverage: **PARTIALLY** — content (+ Form/Image via resource-walk) covered;
  object/xref/font/shading/embedded/nested not covered.
- Q2 Failed decoding: tolerant-malformed yields 0 bytes and can undervalue attempted work,
  but no repeated/unbounded unaccounted decompression was demonstrated; fail-closed
  abort-on-exception is recommended.
- Q3 Concurrent documents: threads and async tasks **isolated** (tested); processes not
  re-tested (isolated by construction).
- Q4 GB-04 feasibility: technically feasible on tested paths; not production-suitable
  without complete stream census; 256 MiB candidate not endorsed.
- Q5 Architecture: recommend **independently isolated child process per document** plus an
  explicit decoder/stream orchestration that performs a full stream census (including
  parser-implicit object/xref streams), pending a complete coverage design. Defer
  production aggregate budgeting until then.

## 12. Reproducible commands

```
pytest tests/test_gate_b_s4_1_stream_coverage.py \
       tests/test_gate_b_s4_1_failure_accounting.py \
       tests/test_gate_b_s4_1_concurrency_isolation.py -q
# host: 24 passed
# container (full S0-S4 + S4.1): 91 passed
ruff check app tests ; mypy app
```

## 13. Evidence classification

| Claim | Class |
|---|---|
| Content stream covered + budgeted | `COVERED_AND_TESTED` |
| Form/Image XObject not covered by S4 content-only | `NOT_COVERED` (tested; extendable) |
| Object/xref streams implicit decode | `COVERED_SOURCE_REVIEW_ONLY` / `NOT_COVERED` (bypass) |
| Fonts/shading/embedded/nested | `NOT_COVERED` / `NOT_TESTED` |
| Tolerated-malformed = 0 bytes | `ENFORCED` observation (gap noted) |
| Fail-closed on exception | `ENFORCED` (tested) |
| Threads/async isolation | `ENFORCED` (tested) |
| Process isolation | `NOT_TESTED` here (by construction) |
| Production suitability | `NOT_ENFORCED` / `PENDING` |

## 14. Statuses

```text
GATE_B_S0: IMPLEMENTED
GATE_B_S1: IMPLEMENTED
GATE_B_S2: IMPLEMENTED
GATE_B_S3: DECISION_PACKET_COMPLETE
GATE_B_S4: LAB_VALIDATION_COMPLETE
GATE_B_S4_1: LAB_VALIDATION_COMPLETE

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

GATE_B: OPEN / OWNER_DECISION_REQUIRED
UPLOAD_API: NOT_ACTIVATED
REAL_PDF_PROCESSING: NOT_AUTHORIZED

GATE_A: OPEN
GATE_C: OWNER_APPROVAL_REQUIRED
PHASE_4: PLANNED / GATED
PHASE_5: NOT_STARTED
PRODUCTION: NOT_APPROVED
```

`GATE_B_S4_1: LAB_VALIDATION_COMPLETE` reflects completion of this bounded experiment only;
it does not imply full stream coverage, Production readiness, GB-04 approval, or Gate B
closure.
