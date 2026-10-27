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
