# Darsyar Knowledge Ingestion — Phase 4

This directory contains the architecture, security, authorization, acceptance, and implementation records for the Darsyar knowledge-ingestion pipeline.

## Current status — 2026-11-12

**Phase 4 is PARTIAL and remains GATED; it is not accepted.** The repository contains synthetic implementation and PostgreSQL persistence slices. These are real code, but they do not constitute an operational textbook-ingestion service and do not authorize processing a real textbook.

### Implemented (synthetic or persistence-only)

- Manifest validation, metadata checks, Persian normalization, and bounded parent/child chunking.
- Embedding adapter, PostgreSQL/pgvector indexing primitives, retrieval primitives, and fail-closed active-index registry checks.
- Durable IngestionDocument, IngestionJob, and IngestionChunk models and transactional job-plus-outbox creation with request idempotency.
- Synthetic PostgreSQL job lifecycle primitives: atomic type-filtered claim, lease renewal, monotonic fencing, retry/terminal failure, cancellation acknowledgement, and explicit expired-cancellation finalization. CI evidence is recorded in the durable-job implementation spec; this does not register an ARQ consumer.
- Outbox publishing/reconciliation to the dedicated arq:queue:ingestion queue using deterministic ARQ job IDs. This is at-least-once delivery and is not a running consumer.
- Durable claim/lease/fencing/retry/cancellation primitives and synthetic attempt-scoped staging/publishing with explicit integrity checks and cleanup (PRs #21/#22). These helpers are not registered in ARQ.
- Low-cardinality process-local metrics for claims, lease renewals, fixed job transitions, and successful artifact operations are under review in PR #23. They do not label metrics with job/document/worker IDs, filenames, or checksums.
- Synthetic-only PDF validation, parent/child IPC and process-supervisor prototypes, and Linux sandbox probes. These are not an approved production parser/renderer or an operational PDF pipeline.

### Not implemented or not accepted

- Source-by-source documentary authorization and separate scope approval for acquisition, storage, extraction, rendering, OCR, embedding/indexing, retrieval, and display. Reference 13529 remains unverified and grants no automatic permission.
- An authenticated intake/upload API, quarantine lifecycle, and registered ingestion consumer in ARQ. WorkerSettings.functions still does not register process_ingestion_event; the dedicated queue has no Darsyar ingestion consumer.
- Operational PDF extraction, OCR, rendering, formula/image fidelity, and end-to-end processing of an authorized textbook.
- Closure of Gate A, all required Gate B security/resource controls, and Gate C equivalence/quality validation.
- Production runtime settings and an operational active index record.

### Authorization boundary

The two pilot manifests must remain needs_review until the documentary evidence and resource/operation scopes satisfy ADR-024. Owner confirmation and a registered reference are not equivalent to reviewed legal permission. Do not download, render, extract, OCR, embed, index, quote, or otherwise process a real pilot PDF until the relevant operation is explicitly cleared.

The Gate B numeric policies approved with conditions are policy decisions only; they do not configure runtime defaults. In particular, the aggregate decompression budget and several renderer/container/upload limits remain pending owner decision and/or measurement. Synthetic tests must continue to use explicit test-supplied limits.

## Document index

| Document | Purpose |
|---|---|
| ARCHITECTURE.md | System boundaries and data flow |
| PIPELINE_STAGES.md | Stage contracts and failure behavior |
| EXTRACTION_STRATEGY.md | Extraction/OCR strategy; not production approval |
| CHUNKING_AND_PROVENANCE.md | Chunk hierarchy and citation provenance |
| AUTHORIZATION_GATE.md | Source-by-source authorization matrix |
| STATE_MACHINE_AND_FAILURES.md | Resource/job lifecycle and recovery |
| ACCEPTANCE_CRITERIA.md | Measurable acceptance criteria |
| GATE_A_RENDERER_DECISION.md | Conditional renderer candidate assessment |
| GATE_B_S3_NUMERIC_POLICY_OWNER_DECISION.md | Owner decisions and pending numeric controls |
| GATE_B_S5_PDF_PARSER_DECODER_ARCHITECTURE_COMPARISON.md | Parser/decoder evidence and unresolved selection |
| ARQ_PDF_JOB_INTEGRATION_AUDIT.md | Current persistence, publisher, queue, and worker gaps |

## Phase closure

Phase 4 may be marked COMPLETE only after the canonical phase specification and acceptance criteria are satisfied with repeatable evidence, all relevant security gates are closed, the real source and each operation are authorized, end-to-end ingestion runs against an authorized source, and the resulting chunks/index/citations are validated. Synthetic CI success alone is insufficient.