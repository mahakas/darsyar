# Phase 9: Production Hardening & Release

**Status:** Planned; before public launch  
**Dependencies:** All in-scope MVP phases

## Goal

Prove operational reliability, privacy, security and recoverability before exposure to real students.

## In scope

- [ ] Security review, dependency/image pinning and supply-chain checks.
- [ ] Load tests against R-025 targets; costs and provider failure drills.
- [ ] Encrypted off-host PostgreSQL backups and tested restore.
- [ ] Retention/delete/export, privacy consent and refund policy approval.
- [ ] HTTPS/CSP/headers, graceful shutdown, alerting and incident runbooks.
- [ ] Production transaction and SMS tests with authorized credentials.

## Out of scope

- Claiming legal compliance without owner/legal review

## Acceptance criteria

- [ ] All hard gates in AGENTS v4 Appendix C pass.
- [ ] No accepted high-severity unresolved risks.
- [ ] Backup restore demonstrated.
- [ ] Owner approves consent/privacy/refund and source licenses.

## Required evidence

- Commands actually executed, exit code and important output.
- Files changed and references to applicable `R-NNN` rules.
- Risks, assumptions, and `NOT RUN` checks with exact blocker.
- New decisions in an ADR before code when required.


## Implemented verification slice — 2026-11-12 (not phase acceptance)

- Nginx reverse-proxy template adds `X-Frame-Options: DENY` in addition to CSP `frame-ancestors 'none'`.
- API proxy responses use `Cache-Control: no-store`.
- Production static frontend marks `index.html` as `no-store`.
- New CI job validates both Nginx configurations with the same `nginx:1.28-alpine` image used by the frontend production image, then runs an HTTP response-header smoke test for the static frontend.

Still NOT RUN / not established: production HTTPS/TLS certificate/domain, HSTS at the real TLS terminator, full CSP report-only/violation validation across OAuth/payment flows, dependency/image vulnerability scan, load/provider failure drills, encrypted off-host backup and restore test, privacy/legal approvals, production SMS/payment tests and owner production approval. Phase 9 remains Planned.
