# Gate A — Renderer Decision Assessment

**Date:** 2026-11-10. This is an assessment and recommendation for owner approval. It does **not** approve a production dependency.

## 1. Executive Recommendation

`pypdfium2` → `PREFERRED_CANDIDATE_FOR_OWNER_APPROVAL` (subject to licensing review + real-textbook validation). Not production-approved.

## 2. Existing Stack

- Backend Python 3.13 (`requires-python >=3.13,<3.14`); `python:3.13-slim` Docker base; `pypdf` (rag extra) for parsing; `Pillow` (rag extra) for imaging; arq worker `max_jobs=4`, `job_timeout=300`.

## 3. Candidate Comparison Matrix

| Candidate | Status | Rendering | Notes |
|---|---|---|---|
| `pypdfium2` (PDFium) | `PREFERRED_CANDIDATE_FOR_OWNER_APPROVAL` | yes (native) | Windows+Linux synthetic PASS; needs licensing review + real-textbook validation |
| PyMuPDF | `AVAILABLE_BUT_NOT_APPROVED` | yes | AGPL/commercial implications; differs from pypdf+Pillow path |
| Poppler | `REQUIRES_EXTERNAL_REVIEW` | yes (binary) | GPL; Docker-slim packaging + maintenance cost |
| No renderer | `NOT_SUPPORTED_BY_CURRENT_STACK` | no | native-text pipeline can proceed; image/mixed/formula/graph pages stay blocked |

## 4. Windows / Linux Technical Evidence

- Windows: CPython 3.13.14, pypdfium2 5.15.2, Pillow 12.3.0, synthetic 3-page, 72/150 DPI, PNG save/reopen, 20/20 lifecycle, malformed rejection → PASS.
- Linux (GitHub Actions Run #6): commit `fffd51bc…`, Python 3.13.18, x86_64, pypdfium2 5.15.2, Pillow 12.3.0, 6 PNG, 30/30 lifecycle, malformed rejection, `ldd` no missing dependency → PASS. (Source: `PDFIUM_LINUX_PREFLIGHT.md`.)

## 5. Licensing and Distribution Review

- Wheels ship bundled PDFium + third-party notices (pdfium.txt, freetype, harfbuzz, icu, zlib, etc.) and LICENSES (Apache-2.0, BSD-3-Clause, CC-BY-4.0); Pillow ships its own license/notice.
- **This inventory is technical, not legal clearance.** Exact-wheel legal review and the requirement to preserve LICENSE/NOTICE on redistribution remain **PENDING**. Any build-specific dependency (e.g., libgcc) is `UNKNOWN` pending the exact wheel inspection. Do not assume approval.

## 6. Thread Safety and Concurrency

- PDFium is documented as **not thread-safe** for concurrent same-process use. Recommended design: a **single dedicated rendering process** (process-based isolation) or **serialization** via a mutex in one process. Given Worker `max_jobs=4`, process isolation is the safer model (no shared native state, crash isolation). No production code implemented here.

## 7. Docker Packaging

- Target `python:3.13-slim`; a `manylinux2014/x86_64` wheel for CPython 3.13 was available for download (temp-only evidence; actual in-Docker execution was verified in Run #6). Wheel fit remains to be confirmed for the exact slim image (no OS libs added).

## 8. Security and Isolation

- Disposable, non-privileged rendering path (no `--privileged`, no host networking/ports, pinned image ID, read-only root, `--user` UID/GID, /work-only mount). Malformed PDFs are rejected without process crash. Native memory/crash isolation favored via process isolation.

## 9. Functional Limitations

- Synthetic tests do **not** validate Persian fonts, real Iranian textbooks, scientific formulas, or complex layouts. Real-textbook rendering is **NOT RUN**.
- Methods A–D metrics stay distinct; `pypdf` continues to provide parsing/native-text/metadata/image-resource references.

## 10. Risks and Mitigations

- Licensing/redistribution uncertainty → owner/legal review before approval.
- Thread-safety → process isolation.
- Real-layout fidelity → real-textbook validation gate (after authorization).
- Memory leak proof → not established (tracemalloc is Python-only).

## 11. Recommended Decision

Recommend **`pypdfium2`** as the candidate to take to owner approval, contingent on licensing review and subsequent real-textbook validation.

## 12. Explicit Owner Approval Section

```yaml
gate_a:
  recommendation: pypdfium2
  recommendation_status: preferred_candidate_for_owner_approval
  production_approval: not_approved
  licensing_review: pending
  real_textbook_validation: not_run
  concurrency_validation: not_run
  gate_status: open
```

Decision fields to be filled by the owner; not filled here.

## Owner Decision — Conditional Candidate Selection

Owner-approved decision (recorded 2026-11-10):

> «انتخاب pypdfium2 را به‌عنوان نامزد منتخب مشروط برای ادامه ارزیابی Gate A تأیید می‌کنم؛ نه تأیید Production.»

Machine-readable status:

```yaml
gate_a:
  candidate: pypdfium2
  decision_type: conditional_candidate_selection
  decision_status: owner_approved
  decision_recorded_on: "2026-11-10"
  production_approval: not_approved
  licensing_review: pending
  real_textbook_validation: not_run
  concurrent_rendering_validation: not_run
  concurrency_model: owner_decision_pending
  authorization_gate: pending
  gate_status: open
```

Open conditions (not assumed complete):

1. Full license/NOTICE review of the exact wheel + bundled PDFium (technical inventory: `PDFIUM_LICENSE_INVENTORY.md`; verdict `INCOMPLETE` — PyPI attestation not available for 5.15.2 and third-party component-version provenance not independently verified; Linux ELF + Windows PE now independently confirmed via pyelftools/pefile).
2. Record binary distribution and third-party notice requirements.
3. Decide concurrency model (current proposal: **Option C — bounded spawned subprocess workers**; see `PDFIUM_CONCURRENCY_DECISION.md`; still owner decision).
4. Assess native memory, crash isolation, resource cleanup.
5. Obtain authorization for controlled real-textbook tests.
6. Visual validation of real Persian pages/diagrams/images/formulas after the authorization gate.
