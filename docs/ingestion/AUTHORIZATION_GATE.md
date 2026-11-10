# Authorization Gate

## Decision levels (distinct)

1. Owner confirmation.
2. Registered authorization reference.
3. Documentary evidence availability.
4. Evidence review.
5. Resource scope verification.
6. Operation scope verification.
7. Independent legal verification (if governance requires).

A resource with insufficient verified authorization never silently proceeds to an unauthorized processing stage.

## Resource/operation matrix

| Operation | Status concept |
|---|---|
| Acquisition/download | scope_pending |
| Local storage/backup | scope_pending |
| Text extraction | scope_pending |
| OCR | scope_pending (optional, separately authorized) |
| Image/page rendering | scope_pending |
| Embedding/indexing | scope_pending |
| Retrieval/AI processing | scope_pending |
| Display/quotation | scope_pending |

`scope_pending` means "not yet established from underlying evidence" — not granted.

## Reference 13529 (present status)

- Owner-provided reference id `13529`, registered at `docs/licenses/13529.md`.
- `record_status: pending_evidence_and_scope_review`; `verification_status: not_independently_verified`.
- The reference is **not** independently verified and does **not** auto-grant permission to books 2051/112209.

## Decision process

- Look up resource authorization record.
- Evaluate scope per operation.
- Allowed → proceed; Denied → block with code + reason; Pending → hold in `needs_review` with reason.
- Audit every decision (actor, resource, operation, decision, reason, timestamp).

## Failure codes (machine-readable)

| Code | Meaning |
|---|---|
| `authorization_pending` | evidence/scope review outstanding |
| `authorization_denied` | operation not covered |
| `authorization_no_reference` | no registered reference |
| `authorization_evidence_missing` | documentary evidence absent |
| `authorization_not_independently_verified` | independent verification not performed |

## Human review workflow

- Operator sees gated resource with classification + reason.
- Operator may add reviewed evidence/scope (does not by itself grant; must satisfy ADR-024).
- A blocked authorization decision is never represented as a successful empty extraction.

## ADR-024

- `license_note` references evidence; it is not proof by itself.
- Do not mark ADR-024 fully satisfied while evidence/scope are pending.
- Wording accuracy: the two textbooks are **not** described as verified/cleared/lawful. Only the following are asserted: owner confirmation received; reference 13529 registered; documentary evidence pending; resource scope pending; operation scope pending; independent legal verification not performed.
