# Outbox Publisher Batch-Size Benchmark — Evidence for Owner Decision B1

**Date:** 2026-11-11. **Benchmark/evidence record.** Owner decision `B1 = OWNER_APPROVED_WITH_CONDITIONS` (2026-11-11) selected `batch_size=50` for explicit manual one-shot invocation; this document records the synthetic measurements that supported that decision.

## Test targets (verified)

- PostgreSQL: `darsyar_test`, version `18.6 (Debian 18.6-1.pgdg12+2)`, Alembic revision `0019_outbox_job_fk_restrict`.
- Redis: isolated logical DB **15**, dedicated queue `arq:queue:ingestion`; baseline depth 0 before and after.
- Application database `darsyar` was **not** touched; general ARQ queue `arq:queue` was **not** used; no application Worker consumed messages; no real ingestion consumer registered.

## Methodology

- Synthetic pending Outbox events created with consistent payload size/distribution (identical `ingestion_create` seed-1 payloads) and `available_at=now()`.
- Publisher invoked explicitly (`publish_pending_outbox_events`) with the candidate batch size; one invocation per workload.
- **5 repetitions per candidate** (10/50/100); each repetition used a fresh isolated workload of exactly `batch` events, then cleaned up.
- Transaction duration captured via SQLAlchemy session listeners (`after_begin`/`after_commit`). **Row-lock duration is reported as transaction duration** because `FOR UPDATE SKIP LOCKED` rows are held until commit (single-transaction publisher).
- Redis enqueue latency captured by wrapping `ArqRedis.enqueue_job` in-process (no code change).
- Memory measured with `tracemalloc` peak over each run (process-local Python allocation).
- Concurrency: two independent publisher invocations over 200 synthetic events.
- Failure tests: Redis unavailable (BrokenRedis stub), PostgreSQL commit failure after enqueue (recovered via reconciliation on a fresh session), repeated reconciliation idempotency, duplicate delivery tolerance.

## Results

| Metric | Batch 10 | Batch 50 | Batch 100 |
|---|---:|---:|---:|
| p50 transaction duration (s) | 0.208 | 0.596 | 1.457 |
| p95 transaction duration / row-lock (s) | 0.345 | 0.737 | 1.893 |
| Redis enqueue p95 (s) | 0.0212 | 0.0121 | 0.0155 |
| Events/second (mean) | 24.1 | 44.5 | 41.5 |
| Total execution time (mean, s) | 0.483 | 1.144 | 2.419 |
| Peak memory (tracemalloc, MiB) | 0.6 | 0.6 | 1.0 |
| Published / deferred / failed (sum over 5 reps) | 50/0/0 | 250/0/0 | 500/0/0 |

All events were published successfully; zero deferred and zero failed in every run.

### Concurrency outcome
- Two concurrent publishers over 200 events: **sum_published = 200** (expected 200); final DB state `{published: 200}`; queue depth consistent (no loss, no corruption, no event returned to pending).

### Failure outcomes
| Scenario | Result |
|---|---|
| Redis temporarily unavailable | deferred=10, published=0, events remain `pending` |
| PostgreSQL commit failure after enqueue | `OutboxPublishCommitError` caught; reconciliation on a fresh session published all 10; final state all `published` |
| Repeated reconciliation | first run published 20; second run republished 0 (idempotent) |
| Duplicate publication (same dedup) | published 1; queue contains exactly 1 instance of the dedup job id (tolerated) |

## Analysis (throughput vs lock trade-off)

- Throughput rises from batch 10 (24.1 ev/s) to batch 50 (44.5 ev/s) and then plateaus at batch 100 (41.5 ev/s). No meaningful throughput gain beyond ~50.
- Transaction/row-lock duration scales roughly linearly with batch size: p95 ≈ 0.35s (10), 0.74s (50), 1.89s (100). Larger batches hold `FOR UPDATE` row locks longer, increasing contention surface under concurrent publishers.
- Redis enqueue p95 is small and roughly flat (12–21 ms), so Redis is not the bottleneck; the DB transaction (claim→commit) dominates execution time.
- Memory footprint is modest and only slightly higher at batch 100 (1.0 MiB vs 0.6 MiB).

**Recommended initial operating range (for owner consideration):** evidence supports a
batch size in the vicinity of **50** — near-peak throughput (~44.5 ev/s) with a
materially shorter lock window (p95 ≈ 0.74s) than batch 100 (p95 ≈ 1.89s), while
still being substantially higher-throughput than batch 10. This is a recommendation
for review, **not** a decision; `B1` remains `PENDING_OWNER_DECISION`.

## Measurement uncertainty / limitations

- Synthetic workload only; real pending application events were not published. Results do not establish a Production-safe value.
- `tracemalloc` reflects process-local Python allocation, not native/container RSS; treat memory as indicative.
- Environment: disposable Docker runner on the `darsyar-ai_default` network (co-located PG/Redis). Cross-host or production latency would differ.
- Transaction-duration measurement is per-invocation (one transaction per invocation); row-lock duration equals transaction duration by design of the single-transaction publisher.
- 5 repetitions per candidate; percentiles from small samples carry inherent variance.

## Cleanup verification

- All synthetic benchmark rows removed from `darsyar_test` (outbox/jobs/documents created by this benchmark); leftover counts (3/3/3) are pre-existing rows from earlier Slice tests, not benchmark data.
- Redis DB 15 returned to baseline: queue depth `0`, `dbsize 0`; only test-owned keys were removed (no `FLUSHDB`/`FLUSHALL`; no unrelated keys touched).

## Statuses

```text
B1: OWNER_APPROVED_WITH_CONDITIONS
B2: OWNER_APPROVED_MANUAL_ONE_SHOT
B3: OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION

APPROVED_MANUAL_BATCH_SIZE: 50
AUTOMATIC_PUBLISHER_SCHEDULING: NOT_AUTHORIZED
LIVE_APPLICATION_OUTBOX_PUBLICATION: NOT_AUTHORIZED
REAL_INGESTION_CONSUMER: NOT_REGISTERED
PRODUCTION: NOT_APPROVED
```

## Owner decision record — B1 (2026-11-11)

- **`B1 = OWNER_APPROVED_WITH_CONDITIONS`** — owner selected **`batch_size=50`**.
- Scope: **exclusively for explicit manual, one-shot Outbox Publisher invocations**.
- `batch_size=50` remains an explicit invocation argument: no default argument, no implicit configuration fallback, no automatic value injection, no change to the Publisher's required-input contract.
- Evidence basis (synthetic): Batch 50 = 44.5 events/sec and p95 transaction/lock 0.737s — best measured throughput/lock-duration balance vs Batch 10 (24.1 ev/s, 0.345s) and Batch 100 (41.5 ev/s, 1.893s). 5 repetitions per candidate.
- **Limitations:** synthetic, not Production validation; `tracemalloc` does not represent full process RSS.
- **Not granted:** no standing authorization to publish pending application events; any actual invocation against live application Outbox events requires its own explicit authorization; synthetic benchmark publication is not equivalent to real ingestion execution; B1 does not authorize automatic scheduling or Production.
- B3 and all remaining runtime parameters remain pending.

No numerical value other than the approved manual batch size 50 is selected or applied.
