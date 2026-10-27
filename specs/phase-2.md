# Phase 2: Credits, Ledger & Billing

**Status:** Planned; gated by open financial questions  
**Dependencies:** Phase 1 and accepted ADR-035/039

## Goal

Create auditable credits and payment flows without double spending.

## In scope

- [ ] Append-only ledger, credit account projection and persistent reservations.
- [ ] Atomic Postgres reserve/settle/release/reconcile; idempotency DB constraints.
- [ ] Usage events; basic/pro/unlimited plan rules; fair-use counters.
- [ ] ZarinPal adapter, amount verification, unit conversion in one place and callback idempotency.
- [ ] Reconciliation and alerts.

## Out of scope

- Billing implementation before OQ-001/002/003/008 are resolved
- Real production payment credentials in repo

## Acceptance criteria

- [ ] Parallel reservation race tests prove no overspend.
- [ ] Ledger/projection/reconcile invariants hold.
- [ ] Duplicate callback does not duplicate payment or credit.
- [ ] Toman/rial conversion tests cover boundaries.
- [ ] Partial-stream behavior matches accepted ADR and refund draft approval.

## Required evidence

- Commands actually executed, exit code and important output.
- Files changed and references to applicable `R-NNN` rules.
- Risks, assumptions, and `NOT RUN` checks with exact blocker.
- New decisions in an ADR before code when required.
