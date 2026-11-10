# PDFium Linux Preflight — Run #6 Evidence

**Date:** 2026-11-10 (recorded from GitHub Actions Run #6 result).

## Environment & versions (exact)

| Item | Value |
|---|---|
| Workflow | Ingestion PDFium Linux Preflight |
| Run ID | `42771524378` |
| Run number | 6 |
| Commit | `fffd51bc59dd220152532f7a1f4be34aed659723` |
| Artifact ID | `13742495529` |
| Artifact SHA-256 | `9a390d270248de0e65ce82c975fb9b4e10103127b2697ea8817a7396a547a6b3` |
| Docker image ID | `sha256:c0e8df9380519cf514d5fbb5aeaa7aa5de5f32c50330badcadc05cdabaae5566` |
| Architecture | x86_64 |
| Python | 3.13.18 |
| pypdfium2 | 5.15.2 |
| Pillow | 12.3.0 |

Link: https://github.com/mahakas/darsyar/actions/runs/42771524378

## Test summary

- **Outcome: PASS**.
- Rendering: 3 pages × 2 DPI = 6 successful PNG outputs.
- Lifecycle: 30/30 successful cycles.
- Malformed PDF: controlled rejection (no crash).
- Native library: `ldd` reported no missing dependency.
- Artifact contains 15 output files.

## Native library

- PDFium native shared library loaded; no missing dependency reported by `ldd`.
- Architecture x86_64 (Linux).

## Limitations of the synthetic test

- Uses a small synthetic 3-page PDF (stdlib-generated); it does **not** validate Persian fonts, real Iranian textbooks, scientific formulas, embedded-image extraction, or textbook layout fidelity.
- Result is an isolated Linux runtime compatibility check, not a production benchmark.

## Governance boundary

- **Technical compatibility: PASS** (this run).
- **Production approval: NOT APPROVED.** Gate A remains **OPEN**; pypdfium2 is not a selected production dependency.
- Phase 4 remains **Planned / Gated**; Phase 5 not started; both pilot resources remain `needs_review`; license reference 13529 remains pending evidence/scope review.
- No legal or production-readiness clearance is claimed.

## Next stage

- Real textbook processing is a separate next stage and remains gated on the Authorization Gate (ADR-024 evidence/scope) before any production ingestion.
