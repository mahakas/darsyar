# Phase 5: Educational RAG & Evidence

**Status:** Partial synthetic prototype exists; Phase remains Planned and is not accepted. ADR-043 is still proposed and the required golden dataset/evidence gates are not met.  
**Dependencies:** Phase 4 and accepted ADR-043

## Implemented prototype (synthetic only)

- Dense pgvector + lexical pg_trgm query paths with SQL grade filtering in both branches.
- Persian normalization, deterministic RRF (k=60) and tie-breaking.
- Provider-callback reranking and a retrieval orchestration wrapper.
- Synthetic PostgreSQL tests for grade ceiling, document isolation and citation formatting.
- A synthetic evaluation helper reporting leakage/recall/grounding proxies.

This is not yet an accepted educational RAG implementation: synthetic tests do not establish textbook answer quality, and the evaluator is not a substitute for the required reviewed gold set.

## Remaining work

- [ ] Minimum 150-question versioned golden dataset with answer/evidence references, under the source-licensing rules.
- [ ] Accepted ADR-043 and measured retrieval/rerank thresholds; no threshold may be tuned from a handful of synthetic examples.
- [ ] Evidence snapshot per request and strict citation allowlist/removal.
- [ ] Context token budget and deterministic truncation.
- [ ] Cache implementation whose key includes model, normalized query, all filters, edition and grade ceiling.
- [ ] Bounded query rewrite and separately cited web fallback with SSRF defense.
- [ ] Connect retrieval/evidence into the real chat response lifecycle; prove no unsupported model-memory answers.

## Goal

Hybrid retrieval with strict grade ceiling, stable ranking and server-built citations.

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
