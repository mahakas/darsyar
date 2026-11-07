# Phase 3: Model Gateway, Inference & Streaming Chat

**Status:** Planned  
**Dependencies:** Phase 1, accepted ADR-036 and accepted financial policy

## Goal

Provider-agnostic chat with cancellable, authenticated streaming and inference routing.

## In scope

- [ ] OpenAI-compatible LLM provider adapter; timeout/retry/idempotency policy.
- [ ] Conversation/message persistence and ownership query.
- [ ] Fetch streaming protocol with request IDs, event IDs, Last-Event-ID and cancellation.
- [ ] Inference service or remote embedding/rerank path; /health and /ready semantics.
- [ ] Graceful shutdown and partial response status.

## Out of scope

- RAG evidence policy before phase 5
- Any model vendor SDK in domain layer

## Acceptance criteria

- [ ] Provider failure before first meaningful token releases reservation.
- [ ] Mid-stream provider failure and user cancellation follow the accepted billing ADR (ADR-039): correct settlement/release, no duplicate billing, and race/idempotency protection.
- [ ] Late completion after the 15-minute reservation deadline follows the accepted OQ-030 / D-07 decision (settlement per the ADR-039 partial-stream policy).
- [ ] No ML model loaded in API process.
- [ ] SSE reconnection cannot duplicate billing or messages.

## Required evidence

- Commands actually executed, exit code and important output.
- Files changed and references to applicable `R-NNN` rules.
- Risks, assumptions, and `NOT RUN` checks with exact blocker.
- New decisions in an ADR before code when required.
