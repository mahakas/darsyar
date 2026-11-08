# Phase 3: Model Gateway, Inference & Streaming Chat

**Status:** Completed — accepted 2026-11-08 (GitHub Actions Run #33, commit ceacee4a026be5998e4683ede517520cd5df0511)  
**Dependencies:** Phase 1, accepted ADR-036 and accepted financial policy  
**Acceptance evidence:** Backend `uv run --locked pytest -q` → 320 passed, 1 skipped, 1 warning; Frontend install/lint/build PASS; Alembic migration 0016→0017 PASS; Linux SIGTERM Scenario A/B PASS (released/settled; exit -15 per Uvicorn 0.54.0 signal restoration; no fallback kill).

## Goal

Provider-agnostic chat with cancellable, authenticated streaming and inference routing.

## In scope

- [x] OpenAI-compatible LLM provider adapter; timeout/retry/idempotency policy.
- [x] Conversation/message persistence and ownership query.
- [x] Fetch streaming protocol with request IDs, event IDs, Last-Event-ID and cancellation.
- [x] Inference service or remote embedding/rerank path; /health and /ready semantics.
- [x] Graceful shutdown and partial response status.

> Note: the real model-weights test (`test_inference_real_models.py:64`) was **skipped** in CI due to insufficient model cache/disk capacity. No claim is made that BGE-M3 / BGE-Reranker weights were loaded or tested in CI. The inference service is implemented and contract/remote-tested, but live local model loading is not verified by CI.

## Out of scope

- RAG evidence policy before phase 5
- Any model vendor SDK in domain layer

## Acceptance criteria

- [x] Provider failure before first meaningful token releases reservation.
- [x] Mid-stream provider failure and user cancellation follow the accepted billing ADR (ADR-039): correct settlement/release, no duplicate billing, and race/idempotency protection.
- [x] Late completion after the 15-minute reservation deadline follows the accepted OQ-030 / D-07 decision (settlement per the ADR-039 partial-stream policy).
- [x] No ML model loaded in API process.
- [x] SSE reconnection cannot duplicate billing or messages.

## Required evidence

- Commands actually executed, exit code and important output.
- Files changed and references to applicable `R-NNN` rules.
- Risks, assumptions, and `NOT RUN` checks with exact blocker.
- New decisions in an ADR before code when required.
