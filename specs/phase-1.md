# Phase 1: Identity, OTP & Sessions

**Status:** Planned  
**Dependencies:** Phase 0

## Goal

Implement mobile OTP login with a secure challenge lifecycle and refresh rotation.

## In scope

- [ ] E.164 normalization; OTP HMAC-SHA256 with independent pepper and key id.
- [ ] Anti-enumeration responses, per-IP/per-phone limits, per-challenge attempt cap.
- [ ] Users, otp_challenges, refresh_tokens migrations and schemas.
- [ ] Access JWT in memory; refresh HttpOnly cookie with CSRF/Origin policy.
- [ ] Refresh reuse detection, family revocation, audit events and CLI seed-admin.

## Out of scope

- Password login unless approved ADR
- Credit/payment/chat/RAG

## Acceptance criteria

- [ ] OTP is never stored/logged in plaintext.
- [ ] Expired/consumed challenges and reuse are rejected.
- [ ] Multi-user and anti-enumeration tests pass.
- [ ] Refresh reuse revokes the session family; grace behavior is tested.
- [ ] Admin bootstrap requires explicit CLI action and audit.

## Required evidence

- Commands actually executed, exit code and important output.
- Files changed and references to applicable `R-NNN` rules.
- Risks, assumptions, and `NOT RUN` checks with exact blocker.
- New decisions in an ADR before code when required.
