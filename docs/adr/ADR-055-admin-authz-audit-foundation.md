# ADR-055: Admin authorization and immutable audit foundation

- **Status:** Implemented — limited technical foundation; full Admin Control Center approval is not implied.
- **Date:** 2026-11-12
- **Related:** AGENTS.md R-097, R-117, R-122; ADR-011; ADR-051; `specs/phase-7.md`.

## Context

The two-role product model uses only `user` and `admin`. Every administrative route must be authorized on the server; a frontend-only check or a JWT role claim is not sufficient. An installation without an active admin must fail closed with the canonical `503 no_admin_seeded`. Administrative audit history must not be silently rewritten by ordinary database operations, and deleting an actor must not mutate the audit record.

ADR-051 remains Proposed because MFA/recovery, step-up, acting-session and privacy boundaries are not fully ratified. This ADR deliberately addresses only the underlying authorization and database-audit primitives.

## Decision / implementation

1. **Server-side authorization dependency.** `require_admin` is a FastAPI dependency. It first counts non-deleted users whose persisted role is `admin`. If the count is zero, it raises `AppError(no_admin_seeded, 503)`. Otherwise it calls the existing access-token authentication path and checks the role loaded from the database. The JWT role claim is never used to grant admin authorization.
2. **Two-role boundary.** No extra product role, permission editor or generic RBAC system is introduced.
3. **Append-only audit barrier.** Alembic migration `0023_admin_audit_append_only` changes `admin_audit_log.actor_user_id` to `ON DELETE RESTRICT` and installs PostgreSQL triggers rejecting row `UPDATE`, row `DELETE` and table `TRUNCATE`.
4. **No route activation.** This implementation exports the dependency but does not register an admin router, endpoint or UI. It does not run the seed-admin CLI or expose sensitive administrative operations.
5. **Forward-only caution.** Normal user removal remains soft-delete. Removing or bypassing database triggers is an infrastructure-level privileged action and is outside ordinary application authority.

## Security boundaries and limitations

- The database role remains authoritative; changing a role claim in a signed JWT cannot elevate a regular user.
- The no-admin state returns 503 before user authentication as required by R-117. Once an admin exists, missing/invalid authentication is handled by the normal 401 path and a non-admin account receives 403.
- Triggers enforce append-only semantics for ordinary SQL DML. A PostgreSQL table owner or superuser may alter/disable triggers; this is not cryptographic tamper-proof storage. Production must use separated, least-privilege DB roles and protected backup/restore procedures.
- This ADR does not define the MFA factor, recovery process, step-up timeout, acting-session TTL/revocation, delegated data visibility, refund authority or secret-manager integration. Those remain under ADR-051 and must be decided before admin routes/actions are enabled.

## Verification evidence

Branch `feat/phase7-admin-authz-audit-foundation`, exact HEAD `879f302f837889ffe1cdd6486ca113abbc385e2a`, standard GitHub Actions Run [43138628126](https://github.com/mahakas/darsyar/actions/runs/43138628126):
- Alembic upgrade through `0023_admin_audit_append_only`: passed.
- Backend: **495 passed, 21 skipped, 1 warning** (real PostgreSQL CI).
- Ruff: passed.
- Frontend lint/typecheck/build: passed.
- Linux SIGTERM acceptance: passed.

The 21 skipped cases require restricted Linux sandbox/cgroup or real-model resources; they are not counted as successful controls. This branch was CI-verified but not yet merged when this ADR text was authored.
