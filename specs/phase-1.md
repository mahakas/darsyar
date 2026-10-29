# Phase 1: Identity, OTP & Sessions

**Status:** Completed (2026-10-29; evidence below)
**Dependencies:** Phase 0

## Goal

Implement mobile OTP login with a secure challenge lifecycle and refresh rotation.

## In scope

- [x] E.164 normalization; OTP HMAC-SHA256 with independent pepper and key id. — `test_phone.py`, `test_security_tokens.py`
- [x] Anti-enumeration responses, per-IP/per-phone limits, per-challenge attempt cap. — `test_anti_enumeration_existing_vs_unknown_phone_identical_response`, `test_ratelimit.py`, `test_auth_db.py::test_wrong_code_increments_attempts_and_locks`
- [x] Users, otp_challenges, refresh_tokens migrations and schemas. — migration `0003_users_otp_refresh_audit`; `test_schema_baseline.py`
- [x] Access JWT in memory; refresh HttpOnly cookie with CSRF/Origin policy. — `test_auth_api.py` (csrf/origin/cookie), `test_security_tokens.py`
- [x] Refresh reuse detection, family revocation, audit events and CLI seed-admin. — `test_refresh_rotation_reuse_detection_and_grace`, `test_concurrent_rotation_cas_keeps_single_active`, `test_admin_seed_requires_explicit_action_and_audits`

## Out of scope

- Password login unless approved ADR
- Credit/payment/chat/RAG

## Acceptance criteria

- [x] OTP is never stored/logged in plaintext. — `test_full_otp_flow_auto_registers_and_never_stores_plaintext`
- [x] Expired/consumed challenges and reuse are rejected. — `test_expired_challenge_rejected`, `test_consumed_challenge_rejected`, `test_refresh_garbage_token_rejected`
- [x] Multi-user and anti-enumeration tests pass. — `test_multi_user_isolation`, `test_anti_enumeration_existing_vs_unknown_phone_identical_response`
- [x] Refresh reuse revokes the session family; grace behavior is tested. — `test_grace_replay_conflict_does_not_rotate_or_create_child`, `test_grace_conflict_returns_409_without_set_cookie`, `test_reordered_responses_cannot_overwrite_newer_cookie` (ADR-046 accepted)
- [x] Admin bootstrap requires explicit CLI action and audit. — `test_admin_seed_requires_explicit_action_and_audits`; `app/scripts/seed_admin.py`

## Required evidence

- **Local (2026-10-29, Windows + Python 3.13):**
  - `uv run --locked ruff check .` → `All checks passed!` (exit 0)
  - `uv run --locked mypy app` → `Success: no issues found in 64 source files` (exit 0)
  - `make test-db` (`python scripts/run_test_db.py`, real PostgreSQL via Compose) → **64 passed** (exit 0); includes new anti-enumeration regression
  - `pytest --cov=app --cov-fail-under=70` → 82.69% (R-217)
  - `git diff --check` → clean
- **GitHub Actions (remote):** PR branch `ci/run-postgres-integration-tests` ran PostgreSQL-gated tests with test-only auth secrets (commit `ebef6f9`, 10 passed per repository report). No post-merge CI run has been executed after merge `b580f0d`; a fresh CI run on merged main is still pending.
- **NOT RUN (blocker):** real Kavenegar SMS send (requires production secret); real payment/chat flows (Phase 2+).
