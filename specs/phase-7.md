# Phase 7: Admin Console & Operations

**Status:** Planned  
**Dependencies:** Phases 1–5 and audit primitives

## Goal

Provide permissioned operations for users, documents, plans, settings and traces.

## In scope

- [ ] Admin-only server-authorized endpoints and responsive UI.
- [ ] User/document/ingestion controls, settings overrides with validation/audit.
- [ ] Plans, ledger read-only audit, payment status, usage/cost and abuse flags.
- [ ] Trace/error overview with redacted data and retention controls.

## Out of scope

- Editing/deleting ledger records
- Exposing secrets or full private prompts by default

## Acceptance criteria

- [ ] Every admin endpoint requires require_admin server-side.
- [ ] Sensitive admin operations log actor, before/after and reason.
- [ ] Ledger endpoints are read-only.
- [ ] Pagination and audit isolation tests pass.

## Required evidence

- Commands actually executed, exit code and important output.
- Files changed and references to applicable `R-NNN` rules.
- Risks, assumptions, and `NOT RUN` checks with exact blocker.
- New decisions in an ADR before code when required.
