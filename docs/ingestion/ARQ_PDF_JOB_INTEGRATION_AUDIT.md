# ARQ ↔ PDF Job Integration Audit

**Updated:** 2026-11-12
**Scope:** Repository code and tests on main at 99a56c25327123957fdff7e4599cc0313bc75182.
**Verdict:** DURABLE_PERSISTENCE_AND_SYNTHETIC_PARENT_CHILD_EXIST; OPERATIONAL_CONSUMER_NOT_REGISTERED.

This is a current-state audit, not permission to activate ingestion, publish live outbox events, or process real PDFs.

## 1. Worker and queue architecture (verified)

- backend/app/services/worker.py currently registers only worker_probe in WorkerSettings.functions.
- WorkerSettings.cron_jobs contains reservation-deadline expiry and orphan chat-stream recovery. There is no ingestion cron and no process_ingestion_event handler.
- Worker settings remain max_jobs=4 and job_timeout=300; these are general worker values, not approved per-child PDF resource limits.
- backend/app/services/outbox_publisher.py declares INGESTION_EVENT_FUNCTION = process_ingestion_event and the dedicated queue arq:queue:ingestion. Publishing can enqueue an event, but no Darsyar consumer is registered to execute it.
- The publisher uses deterministic ARQ job IDs derived from the outbox dedup key. Delivery remains at least once; this does not establish exactly-once processing.

## 2. What is implemented now

### Durable persistence and creation

- IngestionDocument provides canonical identity uniqueness over checksum, edition year, subject, and grade.
- IngestionJob persists job type/schema, state, request idempotency key/hash, attempt count, lease/fencing metadata, retry time, and failure summary. `services/ingestion_jobs.py` now implements PostgreSQL `FOR UPDATE SKIP LOCKED` claim, lease renewal, fenced success/retry/failure, cancellation acknowledgement, and explicit expired-cancellation finalization (PR #21; 528 passed, 21 skipped, 1 warning in CI). These are callable primitives, not a running consumer.
- IngestionChunk persists parent/child chunk metadata and 1024-dimensional vector values.
- create_ingestion_job transactionally creates one job and its initial outbox event. Repeating the same (document, idempotency key, request hash) returns the prior job; a conflicting hash fails with an idempotency conflict.
- Outbox publication and manual reconciliation are implemented. Publisher batch size is an explicit required argument; owner-approved batch size 50 is limited to explicit manual one-shot invocation. Automatic scheduling and live application-event publication remain gated.

### Synthetic process isolation prototype

- backend/app/services/ingestion/parent_supervisor.py launches app.services.ingestion.pdf_child as a separate Python process with shell=False, a narrow environment allowlist, explicit working directory, and structured stdin/stdout IPC.
- The parent owns the process lifecycle and attempts terminate/kill plus wait on timeout; the child receives serialized document bytes and explicit test limits, not database/Redis handles or application credentials.
- Synthetic tests exercise successful parse/page count, explicit FlateDecode limits, malformed input, timeout, termination, parent recovery after child failure, and credential/environment separation.
- This is the Gate B-S1 synthetic prototype. It is not a PDFium renderer, not a worker-integrated supervisor, not an operational parser pipeline, and not real-textbook validation.

## 3. What is still missing

| Concern | Current state | Required before operational ingestion |
|---|---|---|
| Source authorization | Reference 13529 is pending evidence and scope review | Documentary evidence and approved scope per source and operation |
| Intake | No authenticated ingestion upload/intake route | Admin authorization, audit, quarantine, integrity and size controls |
| Consumer | No process_ingestion_event function in WorkerSettings | Registered consumer with bounded concurrency and safe lifecycle |
| Job claiming/recovery | Claim/lease/fencing/retry/cancellation primitives implemented and PostgreSQL-tested; no ARQ consumer invokes them | Integrate the primitives into an approved consumer, add heartbeat orchestration, parent/child cancellation and shutdown/reaping, retry policy/runtime limits, and end-to-end recovery tests |
| Parent/child integration | S1 subprocess prototype is test-only and invoked directly by tests | Async ARQ integration, cancellation propagation, child reaping on worker shutdown, bounded IPC/output and temp cleanup |
| Parser/renderer | pypdf S0/S1 checks and conditional renderer research exist | Gate A licensing/selection and Gate B parser/resource-security closure |
| Aggregate decompression | No complete aggregate document budget is proven/approved | Owner decision, complete parse-time/lazy-stream accounting, adversarial tests and resource backstop |
| OCR/layout quality | Not run on real authorized textbooks | Authorized Persian OCR, formula/diagram fidelity and pilot acceptance |
| Gate C | Not closed | Equivalence/quality evidence after Gate A/B and authorization prerequisites |

## 4. Failure and idempotency boundaries

- Duplicate request creation: database uniqueness plus request hash protects job creation.
- Duplicate queue enqueue: deterministic ARQ job ID reduces duplicate queue entries.
- Duplicate job execution: atomic claim and fencing primitives now protect concurrent attempts when explicitly called; no registered consumer calls them yet, so queue-to-worker duplicate-execution behavior remains unverified.
- Worker cancellation/shutdown: the standalone synchronous supervisor tests timeout termination, but there is no ARQ cancellation/shutdown integration proving child cleanup.
- Child crash/timeout: handled only by the standalone prototype tests; no operational job-state transition/retry is wired around it.
- Database/Redis split failure: outbox delivery is at-least-once; a crash after enqueue but before PostgreSQL commit may enqueue again. Downstream idempotency remains mandatory.
- Outbox retention: the application database FK was migrated to RESTRICT; deleting a job with retained outbox history is intentionally blocked.

## 5. Activation gates

Do not register or run a real consumer merely because persistence and the outbox publisher exist. Before activation:

1. Satisfy ADR-024 with reviewed source-specific evidence and operation scope.
2. Close Gate A and required Gate B numeric/security decisions; do not infer approval for pending GB-04 through GB-17.
3. Wire the already implemented claim/lease/fencing primitives into an explicitly approved ARQ consumer, then prove heartbeat, parent/child cancellation, shutdown/reaping and recovery. Consumer activation remains blocked by deployment/runtime and source authorization gates.
4. Keep publisher invocation manual and one-shot unless the owner separately approves scheduling and runtime parameters.
5. Complete Gate C and authorized real-document quality tests.
6. Obtain separate production approval before production deployment.

**Current phase status:** Phase 4 remains Partial / Gated and is not accepted. Phase 5 must not rely on real textbook retrieval until these gates pass.