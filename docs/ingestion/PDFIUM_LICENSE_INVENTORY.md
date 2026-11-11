# PDFium License & Third-Party Notice Inventory — pypdfium2 5.15.2

**Date:** 2026-11-10. **Evidence inventory only — not legal advice, license clearance, owner approval, or production approval.**

## 1. Purpose and scope

Technical inventory of the exact `pypdfium2==5.15.2` wheels inspected for the Gate A conditional candidate (PDFium rendering). Covers the Linux and Windows wheels, bundled PDFium binary, bundled third-party notices, native runtime dependencies (incl. `libgcc`), and Pillow separately.

## 2. Non-legal-advice statement

This document records technical facts and shipped license/notice artifacts. It is **not** legal advice and grants **no clearance**. Owner/legal review remains required before any production/distribution decision.

## 3. Exact artifact table

| Wheel | Platform | Size (bytes) | SHA-256 | Origin |
|---|---|---|---|---|
| `pypdfium2-5.15.2-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl` | Linux x86_64 (glibc) | 4,020,833 | `dc31aea5b0fb9fefc9b537a65f4113980b2c40798445736a7e6565bc85161e37` | PyPI |
| `pypdfium2-5.15.2-py3-none-win_amd64.whl` | Windows x86_64 | 4,187,589 | `74d1bace34fb01c660d0b64344d5a4b7d276942b7c6623c88ab59ea21c5acfbd` | PyPI |

- These wheels were downloaded fresh from PyPI to an isolated temp dir and hashed at download time.
- **Provenance verification:** hashes were recorded from the downloaded artifacts themselves; PyPI attestation/provenance metadata was **not separately verified** in this task. Not equated with independent verification of every bundled component.

## 4. Wheel content inventory

Both wheels contain:
- `pypdfium2-5.15.2.dist-info/METADATA` (declares `License: BSD-3-Clause, Apache-2.0, dependency licenses`; lists many `License-File` entries).
- `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/**` (pdfium.txt, pdfium-binaries.txt, freetype, harfbuzz, icu, zlib, libpng, libjpeg_turbo, libtiff, libopenjpeg, lcms, agg23, highway, simdutf, dragonbox, abseil, brotli, libyuv, v8_xfa/*, llvm-libc, musl, `cibw_musl/libgcc_and_libstdc++.txt`, Apache-2.0, etc.).
- `pypdfium2-5.15.2.dist-info/licenses/LICENSES/` (Apache-2.0.txt, BSD-3-Clause.txt, CC-BY-4.0.txt).
- Native binary: Linux `pypdfium2_raw/libpdfium.so` (8,271,176 bytes; sha256 `…` computed) / Windows `pypdfium2_raw/pdfium.dll`.
- `pypdfium2_raw/version.json`: PDFium `159.0.8149` (origin `sourcebuild-toolchained`).

## 5. pypdfium2 license findings

- Declared: **BSD-3-Clause, Apache-2.0, dependency licenses** (METADATA); SPDX headers in source; documentation/examples CC-BY-4.0. METADATA notes "PDFium's license as well as dependency licenses have to be shipped with binary distributions."
- The exact wheels ship the corresponding `LICENSES/` and `BUILD_LICENSES/` trees. Wheel metadata and shipped files agree. Source-vs-data distinction noted (docs/examples CC-BY-4.0).

## 6. PDFium license findings

- PDFium: **BSD-style license** (see `BUILD_LICENSES/pdfium.txt`), shipped in the wheel.

## 7. Bundled third-party components

| Component | Version/build evidence | Origin | Bundled | License declaration | License/notice file in wheel | Status |
|---|---|---|---|---|---|---|
| PDFium | 159.0.8149 (version.json) | pdfium | yes (native) | BSD-style | pdfium.txt | present |
| FreeType | build notice | pdfium build | yes | FTL/GPL-ish | freetype.txt | present |
| HarfBuzz | build notice | pdfium build | yes | MIT/OFL | harfbuzz.txt | present |
| ICU | build notice | pdfium build | yes | Unicode/ICU | icu.txt | present |
| zlib | build notice | pdfium build | yes | zlib | zlib.txt | present |
| libpng / libjpeg-turbo / libtiff / libopenjpeg / lcms | build notices | pdfium build | yes | various | libpng.txt, libjpeg_turbo.*, libtiff.txt, libopenjpeg.txt, lcms.txt | present |
| agg23 / highway / simdutf / dragonbox / fast_float / abseil / brotli / libyuv / v8_xfa/* / llvm-libc / musl (musl builds) | build notices | pdfium build | yes | various | present in BUILD_LICENSES | present |
| libgcc / libstdc++ (runtime dependency notice) | `cibw_musl/libgcc_and_libstdc++.txt` | GCC runtime | external/dynamic | GCC Runtime Library Exception v3.1 | present in wheel | present |

Completeness: matches the wheel-shipped `BUILD_LICENSES/` tree. Some component-version-specific details are not independently re-derived in this inventory; where exact evidence was not independently re-established it is treated as incomplete rather than assumed exhaustive.

## 8. Native runtime dependency findings

### Linux
- Bundled ELF: `pypdfium2_raw/libpdfium.so`.
- String presence of dynamic `DT_NEEDED` names in the binary: **`libgcc_s.so.1`**, `libm.so.6`, `libc.so.6`, `ld-linux-x86-64.so.2`, and (not matched in this scan) libstdc++ presence checked via the shipped notice.
- **`libgcc_s.so.1` is dynamically required** by the Linux binary. The wheel ships the GCC Runtime Library Exception notice for it (`cibw_musl/libgcc_and_libstdc++.txt`).
- The container/host glibc provides `libc`/`libm`/`ld-linux`; `libgcc_s`/`libstdc++` may be provided by the base image or linked subset — this is a runtime-provider item to confirm in the actual Darsyar image.
- Distinguish: physically bundled (PDFium .so) vs dynamically required (glibc, libgcc_s) vs OS-provided.

### Windows
- Bundled `pypdfium2_raw/pdfium.dll`; PE-import tooling unavailable on this host, so the exact external runtime DLL set is **UNKNOWN** pending a tool that can read PE imports. (No claim made.)

## 9. Pillow (separate scope)

- Pillow `12.3.0` is an existing project dependency (rag extra; not bundled inside pypdfium2 wheels). Its own distribution metadata carries Pillow's license/notice; not audited exhaustively here. Distinguish: existing project dependency, not part of the pypdfium2 wheel.

## 10. Required notices / redistribution obligations

- METADATA explicitly requires shipping PDFium + dependency licenses with binary distributions.
- The wheels carry the corresponding notice tree; redistribution of the wheel/binary should preserve these notices (including the GCC Runtime Library Exception notice for libgcc/libstdc++ if those are linked/used).
- Exact obligations for Darsyar's production image (whether libgcc_s is dynamically pulled from the base image and whether a notice must accompany it) require owner/legal review.

## 11. Evidence gaps and unresolved questions

- PyPI provenance/attestation not independently verified.
- Linux ELF analysis was a string-presence scan (readelf/objdump not available on this host) → `libgcc_s.so.1` confirmed present as a NEEDED-name string; a full `readelf -d` is still recommended for the canonical `DT_NEEDED` list.
- Windows PE import inventory: unavailable → **UNKNOWN**.
- Exact component-version provenance for each bundled third-party component was not re-derived; treated incomplete.

## Remaining Binary Evidence — 2026-11-10

### Linux ELF — canonical dynamic dependencies

Tool: stdlib-Python ELF64 parser (no `readelf`/`objdump` on host); parser maps vaddr→file offset via `PT_LOAD`. Exact command: `python elf_dyn3.py <extracted libpdfium.so>` (extracted from the hash-verified Linux wheel).

- Class/machine: ELF64, x86-64 (machine 62).
- `DT_NEEDED` (complete): `libpthread.so.0`, `libm.so.6`, `libgcc_s.so.1`, `libc.so.6`, `ld-linux-x86-64.so.2`.
- **`libgcc_s.so.1` is explicitly listed in `DT_NEEDED`** (actual dynamic dependency).
- `libstdc++.so.6` is **not** listed in `DT_NEEDED` (in this binary).
- `DT_RPATH`: none. `DT_RUNPATH`: none.
- Provided by OS/container: `libc`, `libm`, `ld-linux`, `libpthread` (glibc base). Bundled in wheel: PDFium `.so`. `libgcc_s` is dynamically required; its provider must be confirmed in the actual `python:3.13-slim` image. Static, that cannot be identified from dynamic list is not inferred.

### Windows PE — imported DLL inventory

Tool: stdlib-Python PE parser (no `dumpbin`/`objdump`). Exact command: inline PE import-directory scan over the extracted `pdfium.dll` from the hash-verified Windows wheel.

- PE machine: `0x8664` (x86-64), PE32+.
- Imported DLLs (complete from import directory): `KERNEL32.dll`, `ADVAPI32.dll`, `GDI32.dll`, `USER32.dll`.
- All four are OS-provided (Windows system DLLs); none are bundled in the wheel.

### PyPI provenance / attestation

- Artifact filenames + SHA-256 identity recorded in §3 and confirmed on redownload.
- Attestation/provenance: metadata **retrieved** (pip download from PyPI), but **cryptographic verification was NOT performed** in this environment (no verifier/trust roots available). Distinction recorded: attestation exists/available at PyPI; not independently verified here.

### Remaining limitations

- Linux `DT_NEEDED` was parsed with a stdlib parser (not `readelf`); results are canonical but a `readelf -d` re-run is recommended for independent confirmation.
- PyPI provenance/attestation signature not cryptographically verified.
- Component-version provenance for third-party notices still not independently re-derived.

## Independent Verification Review — 2026-11-10

### Wheel hash verification
- Linux `…manylinux2014_x86_64.whl` SHA-256 `dc31aea5…61e37` — verified ✓
- Windows `…win_amd64.whl` SHA-256 `74d1bace…c5acfbd` — verified ✓

### PyPI provenance / attestation
- Official PyPI release JSON (version 5.15.2) retrieved; the exact two wheel hashes appear in the release files.
- **PEP 740 attestations/provenance are NOT present** for this release: no `attestations` key and no provenance field on any of the 23 files. Therefore **cryptographic provenance verification is not possible** (no attestation exists to verify). Blocker recorded; result stays pending.

### Independent Linux ELF inspection
- Tool: `pyelftools 0.33` (readelf-equivalent), in an isolated venv; command: parse `DT_NEEDED` via `DynamicSegment.iter_tags()`.
- Result: ELF64 / `EM_X86_64` / `ET_DYN`; `DT_NEEDED = [libpthread.so.0, libm.so.6, libgcc_s.so.1, libc.so.6, ld-linux-x86-64.so.2]`; `DT_RPATH=None`, `DT_RUNPATH=None`.
- **Agrees exactly** with the prior custom parser. libgcc_s confirmed as a real dynamic dependency; libstdc++ absent from DT_NEEDED.

### Independent Windows PE inspection
- Tool: `pefile 2024.8.26`, isolated venv; command: parse import directory.
- Result: machine `0x8664` (x86-64); normal imports `[ADVAPI32.dll, GDI32.dll, KERNEL32.dll, USER32.dll]`; no delay-import directory.
- **Agrees exactly** with the prior custom result.

### Third-party component-version traceability
- Wheel ships `pdfium.txt` (PDFium BSD-style license, 2014 PDFium Authors) and `pdfium-binaries.txt` (MIT, 2014-2026 Benoit Blanchon), plus the full `BUILD_LICENSES/` tree.
- PDFium raw version `159.0.8149` is recorded in `pypdfium2_raw/version.json` (origin `sourcebuild-toolchained`).
- **Component-version → exact binary linkage is NOT independently proven** for each third-party component: the notices are shipped and match upstream build-license material, but mapping each notice to a specific compiled/linked component in this particular binary is inferred, not directly verified. Mark as `NOT_INDEPENDENTLY_VERIFIED` where not directly proven. OS-provided runtime libs (glibc, libgcc_s, etc.) are distinguished from bundled components.

### Remaining evidence gaps
- PyPI attestation cryptographic verification: unavailable (no attestation exists for 5.15.2).
- Component-version↔binary linkage: not independently proven.
- `readelf -d`/`objdump` re-run still recommended for ultimate confirmation (pyelftools/pefile are independent but not the canonical binutils).

## 12. Final technical verdict

**`INCOMPLETE — REQUIRED ARTIFACTS OR EVIDENCE MISSING`** — Linux ELF and Windows PE import evidence are now independently confirmed, but **PyPI attestation cryptographic verification is not possible** (no attestation exists for this release) and **material third-party component-version provenance remains not independently verified**. No `CLEARED`/`APPROVED`/`SAFE FOR PRODUCTION` language applies.
