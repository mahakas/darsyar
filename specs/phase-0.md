# Phase 0: Foundation & Repository Baseline

**Status:** Active starting phase  
**Dependencies:** None

## Goal

A reproducible, secure development skeleton with config, API shell, health, DB/Redis, explicit migration service, frontend shell, CI and real lockfiles.

## In scope

- [x] Align Settings and .env.example for settings actually read by phase 0.
- [x] Request ID middleware, JSON logging/redaction and standard error shape.
- [x] PostgreSQL async session, Redis lifecycle and health/live/ready/version.
- [x] Alembic extension migration; a dedicated one-shot migrate service; no migration in app startup.
- [x] Compose services for PostgreSQL, Redis, migrate, API, worker, inference shell and frontend.
- [x] React shell with fa/en/ar and correct dir; chat submission stays disabled.
- [x] Real uv.lock and package-lock.json, Make targets, lint/typecheck/tests and CI.

## Out of scope

- Real OTP/JWT/session flows
- Credit reservation, payment, LLM chat, message persistence
- Real model loading, OCR, ingestion or RAG
- Admin endpoints and learning tools

## Acceptance criteria

- [x] docker compose config exits 0.
- [x] uv sync --locked and npm ci work with generated lockfiles.
- [x] lint/typecheck/unit tests pass.
- [x] Postgres/Redis health and Alembic migrate pass when Docker is available.
- [x] No create_all or automatic migration in app startup.
- [x] No secrets committed; frontend chat does not imply real AI.
- [x] Every changed file is listed in docs/FILE_MAP.md.

## Required evidence

- Commands actually executed, exit code and important output.
- Files changed and references to applicable `R-NNN` rules.
- Risks, assumptions, and `NOT RUN` checks with exact blocker.
- New decisions in an ADR before code when required.
