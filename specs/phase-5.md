# Phase 5: Educational RAG & Evidence

**Status:** Planned; gated by gold dataset  
**Dependencies:** Phase 4 and accepted ADR-043

## Goal

Hybrid retrieval with strict grade ceiling, stable ranking and server-built citations.

## In scope

- [ ] Dense pgvector + lexical pg_trgm retrieval; SQL grade filter in both branches.
- [ ] Persian normalization, deterministic RRF and tie-breaking.
- [ ] Reranking, configurable thresholds and budgeted context.
- [ ] Evidence snapshot; server-side citation builder; invalid-citation removal.
- [ ] Bounded rewrite and optional separately cited web fallback with SSRF defense.
- [ ] Golden dataset and evaluation output.

## Out of scope

- Using model memory to fill absent evidence
- Citation formatting as the only proof of groundedness

## Acceptance criteria

- [ ] grade leakage=0 on both retrieval branches.
- [ ] No displayed citation outside request evidence_set.
- [ ] RAG evaluation reports dataset/model/config versions.
- [ ] Cache key includes model, normalized query, filters, edition and grade ceiling.

## Required evidence

- Commands actually executed, exit code and important output.
- Files changed and references to applicable `R-NNN` rules.
- Risks, assumptions, and `NOT RUN` checks with exact blocker.
- New decisions in an ADR before code when required.
