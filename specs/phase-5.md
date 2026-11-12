# Phase 5: Educational RAG & Evidence

**Status:** Partial synthetic prototype exists; Phase remains Planned and is not accepted. ADR-043 is still proposed and the required golden dataset/evidence gates are not met.  
**Dependencies:** Phase 4 and accepted ADR-043

## Implemented prototype (synthetic only)

- Dense pgvector + lexical pg_trgm query paths with SQL grade filtering in both branches.
- Persian normalization, deterministic RRF (k=60) and tie-breaking.
- Provider-callback reranking and a retrieval orchestration wrapper.
- Synthetic PostgreSQL tests for grade ceiling, document isolation and citation formatting.
- Fail-closed active `index_meta` registry check for query embedding model/dimension and hybrid retrieval; no active index means no query.
- Synthetic evaluator reports grade leakage, citation metadata validity, recall@5 and retrieval precision@5. Answer groundedness is explicitly `NOT MEASURED` by a retrieval-only harness.

This is not yet an accepted educational RAG implementation: synthetic tests do not establish textbook answer quality, and the evaluator is not a substitute for the required reviewed gold set. The active registry is not auto-provisioned; real retrieval remains fail-closed until an explicitly verified provider/model record exists.

## Remaining work

- [ ] Minimum 150-question versioned golden dataset with answer/evidence references, under the source-licensing rules.
- [ ] Accepted ADR-043 and measured retrieval/rerank thresholds; no threshold may be tuned from a handful of synthetic examples.
- [ ] Evidence snapshot per request and strict citation allowlist/removal.
- [ ] Context token budget and deterministic truncation.
- [ ] Cache implementation whose key includes model, normalized query, all filters, edition and grade ceiling.
- [ ] Bounded query rewrite and separately cited web fallback with SSRF defense.
- [ ] Connect retrieval/evidence into the real chat response lifecycle; prove no unsupported model-memory answers.

### Implementation CI evidence — 2026-11-12

The active-index enforcement branch ran [GitHub Actions Run 43129891289](https://github.com/mahakas/darsyar/actions/runs/43129891289) on HEAD `259b13916a4579d2e947da27209e504a71f94ea4`: Backend **492 passed, 21 skipped, 1 warning**; Ruff, Frontend and Linux SIGTERM all passed. The branch is still a PR candidate, not merged at this point.

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
