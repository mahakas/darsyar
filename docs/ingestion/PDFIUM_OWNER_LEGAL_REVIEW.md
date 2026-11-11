# pypdfium2 Owner/Legal Decision Brief

**Date:** 2026-11-10. This document is a decision brief for the owner/legal reviewer; it is **not** a legal analysis, clearance, approval, or production authorization.

## 1. Executive summary

`pypdfium2 5.15.2` is an **owner-approved conditional candidate** for continued Gate A evaluation. It is **not production-approved**. The licensing decision is `PENDING` and must be decided by the owner/legal reviewer.

## 2. Verified technical facts

- **Wheels (exact):**
  - Linux: `pypdfium2-5.15.2-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`, SHA-256 `dc31aea5b0fb9fefc9b537a65f4113980b2c40798445736a7e6565bc85161e37`.
  - Windows: `pypdfium2-5.15.2-py3-none-win_amd64.whl`, SHA-256 `74d1bace34fb01c660d0b64344d5a4b7d276942b7c6623c88ab59ea21c5acfbd`.
- **License declarations:** pypdfium2 `BSD-3-Clause, Apache-2.0, dependency licenses` (METADATA); PDFium BSD-style; docs/examples CC-BY-4.0.
- **Wheel-shipped notices:** `LICENSES/` (Apache-2.0, BSD-3-Clause, CC-BY-4.0) and full `BUILD_LICENSES/` tree (pdfium.txt, pdfium-binaries.txt, freetype, harfbuzz, icu, zlib, libpng, libjpeg_turbo, libtiff, libopenjpeg, lcms, agg23, highway, simdutf, dragonbox, abseil, brotli, libyuv, v8_xfa/*, llvm-libc, musl, `cibw_musl/libgcc_and_libstdc++.txt`, …).
- **Linux dynamic dependency:** `libgcc_s.so.1` is explicitly in `DT_NEEDED`; the wheel ships the **GCC Runtime Library Exception v3.1** notice. `libstdc++.so.6` is not in `DT_NEEDED` for this binary.
- **Windows PE imports:** `KERNEL32.dll`, `ADVAPI32.dll`, `GDI32.dll`, `USER32.dll` (OS-provided).
- **Pillow:** separate existing project dependency (12.3.0), not bundled inside the pypdfium2 wheels.
- **PyPI provenance:** **No PEP 740 attestations found** for the 5.15.2 release → cryptographic provenance verification is not possible.
- **Third-party component-to-binary provenance:** not independently established (`NOT_INDEPENDENTLY_VERIFIED` for per-component binary linkage).

## 3. Explicit owner/legal decisions required

Each decision is `PENDING`; evidence reviewed is noted. Do not presume an answer.

1. **Intended-use license review** — Has the exact 5.15.2 package licensing been reviewed for the intended commercial use? (Evidence: §5–7 of PDFIUM_LICENSE_INVENTORY.md)
2. **PDFium + bundled notices review** — Have PDFium and all bundled third-party notices been reviewed? (Evidence: BUILD_LICENSES tree)
3. **Notice preservation** — Are the required notices/license texts to be preserved in Darsyar's source distributions, containers, and binary distributions? (Evidence: METADATA "must be shipped with binary distributions")
4. **libgcc_s + GCC RLE** — Has the `libgcc_s.so.1` dependency and the GCC Runtime Library Exception been reviewed for the intended distribution model? (Evidence: DT_NEEDED + cibw_musl/libgcc_and_libstdc++.txt)
5. **Provenance absence** — Is the absence of PyPI provenance attestation acceptable, or is publisher-supplied provenance required? (Evidence: no attestations exist)
6. **Component provenance gap** — Is the remaining third-party component-to-binary provenance gap acceptable, or is further publisher/build evidence required? (Evidence: not independently verified)
7. **Authorization scope (13529)** — What is the exact scope of permitted operations under authorization reference 13529? Do not assume all rights. (Evidence: `docs/licenses/13529.md` = `pending_evidence_and_scope_review`, `not_independently_verified`; AUTHORIZATION_GATE marks operations `scope_pending`)

For each: **Decision: `PENDING`** · Evidence reviewed (above) · Required owner/legal response (explicit answer).

## 4. Final decision record (blank fields)

- Reviewer: ______
- Review date: ______
- Intended distribution model: ______
- Decision: (choose one: `ACCEPTABLE_WITH_RECORDED_CONDITIONS` / `MORE_EVIDENCE_REQUIRED` / `REJECTED`)
- Conditions: ______
- Evidence references: _____ _INGEST_PILOT.md`, `GATE_A_RENDERER_DECISION.md`, `OWNER_DECISIONS.md`, `PDFIUM_LICENSE_INVENTORY.md`

No decision is preselected.

## 5. Next-step sequence

1. Owner/legal review of this brief.
2. Record the explicit decision and any conditions.
3. Decide the concurrency model separately.
4. Complete native memory/crash isolation assessment.
5. Resolve authorization scope before any real-textbook test.
6. Perform controlled visual validation only after authorization.

## Governance (preserved)

- Gate A: OPEN
- pypdfium2: `OWNER_APPROVED_CONDITIONAL_CANDIDATE`
- Production approval: `NOT_APPROVED`
- Gate B: OPEN / OWNER_DECISION_REQUIRED
- Gate C: OWNER_APPROVAL_REQUIRED
- Phase 4: PLANNED / GATED
- Phase 5: NOT_STARTED
- concurrency_model: owner_decision_pending
- Real-textbook validation: not_run
- Authorization reference 13529: pending_evidence_and_scope_review
- Both pilot manifests: needs_review
