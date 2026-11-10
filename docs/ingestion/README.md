# Darsyar Knowledge Ingestion — Design Documentation

## Purpose

This is the technical design specification for Darsyar's **Knowledge Ingestion** pipeline (Phase 4). It covers the full lifecycle from source registration through authorization, integrity, page inventory, extraction, chunking, indexing references, state, and observability — for the two verified pilot textbooks and for future official educational resources.

## Status

- Phase 4: **Planned / Gated** (not implemented).
- All documents here are **design proposals**, not implemented functionality.
- No PDF was processed in producing these documents; only the documented preflight results already in the repository were used.

## Scope

The design must:
- Respect `AGENTS.md` and accepted ADRs (especially ADR-024, ADR-037, ADR-038).
- Be compatible with R-150 through R-157.
- Be provider-agnostic, asynchronous, failure-safe, and testable.
- Handle Persian/RTL textbook content.
- Extend beyond the two pilot books to other grades/subjects/editions/formats.

## Document index

| Document | Purpose |
|---|---|
| `ARCHITECTURE.md` | High-level architecture, component boundaries, data flow, security boundaries |
| `PIPELINE_STAGES.md` | Stage-by-stage contracts, inputs/outputs, authorization checks, failure behavior |
| `EXTRACTION_STRATEGY.md` | Mathematics, Physics, and general extraction strategy |
| `CHUNKING_AND_PROVENANCE.md` | Chunk hierarchy, R-150 provenance propagation, citations |
| `AUTHORIZATION_GATE.md` | Resource/operation authorization matrix, pending states, reference 13529 |
| `STATE_MACHINE_AND_FAILURES.md` | R-156 state machine, error codes, retry/recovery |
| `ACCEPTANCE_CRITERIA.md` | Measurable acceptance criteria per stage/doc type |

## Implementation prerequisites

- Actual source-specific authorization evidence and scope review (ADR-024) — reference 13529 is pending.
- Legacy grade mappings where applicable (ADR-037, OQ-009 closed).
- Edition metadata policy (ADR-038).
- The ingestion pipeline is **not yet implemented**.

## Current governance blockers

- Governance design: documented and designed.
- Owner confirmation: received.
- Reference 13529: registered (pending evidence/scope).
- Documentary evidence: **pending**.
- Resource scope: **pending**.
- Operation scope: **pending**.
- Independent legal verification: **not performed**.
- The two pilot manifests remain `ingestion_status: needs_review`.
- Neither source may be marked `ready` until ADR-024 evidence/scope requirements are satisfied.
- The design is governance-aligned and fail-closed; it is **not** a claim that sources are verified/cleared/lawful.
