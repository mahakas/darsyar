# Acceptance Criteria

All criteria are **designed**; none are implemented/tested/passed. Statuses used: Designed / Implemented / Tested / Manually reviewed / Pending approval.

## Registration & manifest (R-154, R-151, R-152, R-038)

- Required fields present/valid; subject in R-151 allowlist; grade canonical 1–12; edition_year = printing year; no auto legacy mapping; ambiguous → `needs_review`/`failed`.
- **Status:** Designed.

### Manifest field tests (DESIGNED — NOT EXECUTED)

- Each mandatory field present and typed correctly (string/integer); integer fields reject booleans; `sha256` hex-format validated; `book_code` treated as string.
- Subject ∈ R-151 allowlist; grade ∈ 1–12; edition_year is integer printing year.
- Cross-field: `academic_year` never substitutes for `edition_year`; path resolves safely within resource root (traversal rejected).
- Duplicate source identity detected (no duplicate documents).
- Valid and invalid manifest examples (above) produce the documented state transitions.

### PDF-backend equivalence test (DESIGNED — NOT RUN)

- Compare production PDF adapter vs historical PyMuPDF method across both pilot PDFs: page count, native text counts, image-resource counts, occurrence counts, page-level inventory, vector support. Report `UNSUPPORTED`/`NOT_COMPARABLE` for any unreproducible metric.

## Authorization gate (ADR-024)

- Per-resource/per-operation decisions; pending/denied block progression; reason recorded; reference 13529 registered but pending; no auto-grant.
- **Status:** Designed.

## Integrity

- File size + SHA-256 match; opens unencrypted; page count matches; original PDF preserved.
- **Status:** Designed.

## Page inventory & extraction

- Per-page text/image/vector/dimension records; blank never inferred from empty text; original text distinct from normalized; Method B canonical for reference comparison.
- **Status:** Designed.

## Chunking & provenance (R-150)

- All R-150 fields present; no essential semantic unit split; multi-page context kept; citation reconstructible; PDF index/one-based/printed page never conflated.
- **Status:** Designed.

## State machine & idempotency (R-156/R-157)

- `pending → processing → ready|failed|needs_review`; idempotent identity `checksum+edition_year+subject+grade`; atomic chunk replacement; duplicate prevention; recovery after interruption.
- **Status:** Designed.

## Pilot manual-review evidence (recorded, not acceptance-passed)

- Math: pages 36/37/182/184/186/188 manually reviewed (recorded in `docs/PHASE4_INGEST_PILOT.md`).
- Physics: pages 16/54/92 manually reviewed.
- These are recorded observations, not pipeline acceptance passes.

## Hybrid intake acceptance criteria (all `DESIGNED — NOT IMPLEMENTED — NOT EXECUTED`)

### Server-side registration
- Valid controlled path accepted.
- Path traversal rejected.
- Symlink escape rejected.
- Missing/unreadable file rejected.
- File hash verified.
- Repeated registration is idempotent.

### Admin upload
- Unauthenticated upload rejected.
- Unauthorized admin rejected.
- Incorrect file signature rejected.
- Oversized file rejected safely.
- Interrupted upload can be safely retried.
- Temporary files are cleaned up.
- Duplicate upload does not create duplicate documents.
- Original uploaded bytes remain unchanged.

### Unified intake
- Both methods produce the same normalized registration contract.
- Both methods invoke the same manifest validator.
- Both methods invoke the same authorization gate.
- Neither method bypasses ADR-024.
- Both paths preserve provenance and audit information.

## Gate

- Neither pilot source is `ready`; both manifests remain `needs_review`. Phase 4 remains Planned / Gated.
