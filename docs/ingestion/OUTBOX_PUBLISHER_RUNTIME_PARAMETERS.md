# Outbox Publisher Runtime Parameters — Owner Decision Preparation (B3)

**Date:** 2026-11-11. **Read-only technical assessment.** This document prepares owner
decision `B3`; it does **not** select, approve, or implement any runtime value, default,
or configuration field. No code, configuration, database, or runtime operation changed.

## Preserved owner decisions

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

---

## 1. Implementation basis (verified)

Inspected (actual code):

- `backend/app/services/outbox_publisher.py` — `run_outbox_publisher(session, redis, *, batch_size, source)`; `publish_pending_outbox_events(session, redis, *, batch_size)`.
- `backend/app/services/outbox_reconciliation.py` — `reconcile_pending_outbox_events(session, redis, *, batch_size)`.
- `backend/app/repositories/outbox_events.py` — `claim_eligible_events` (`FOR UPDATE SKIP LOCKED`, `ORDER BY available_at, id`, `LIMIT`), `mark_published`, `record_transient_failure`, `record_permanent_failure`.
- `backend/app/core/config.py` — `Settings` (pydantic-settings). **No Publisher-specific config field exists.**
- `backend/app/core/metrics.py` — in-process counters (outbox_*), Prometheus text renderer.
- `backend/app/services/worker.py` — `WorkerSettings`: `functions=[worker_probe]`, `cron_jobs` (two recovery crons), `max_jobs=4`, `job_timeout=300`, `RedisSettings.from_dsn(settings.redis_url)`. No ingestion cron; no ingestion consumer.

Key facts confirmed in code:

- `batch_size` is a **required keyword-only argument** on all three entry points; no default; no settings field; no env fallback.
- The publisher runs **one PostgreSQL transaction** per invocation: `claim_eligible_events` → per-event `enqueue_job` → `mark_published` → `session.commit()`. Row locks held across the bounded Redis calls until commit.
- Redis enqueue uses ARQ `enqueue_job(_job_id=..., _queue_name="arq:queue:ingestion", ...)`; deterministic `_job_id` from dedup key; duplicate enqueue returns `None` and is tolerated.
- **Transient** failures (`RedisError`, `OSError`, `TimeoutError`) are recorded to `pending` with `attempt_count+1` and `last_error_details` (i.e. deferred).
- **Permanent** failures (unsupported event contract) are recorded to `failed`.
- Commit failure after enqueue raises `OutboxPublishCommitError`; events remain pending and are recoverable via reconciliation.
- No retry loop, no backoff, no publisher timeout wrapper, no max-attempt enforcement inside the publisher.
- Reconciliation is a one-shot function with the same signature; it is **not** scheduled.

---

## 2. Parameter inventory

Legend — code location · exists? (Y/N) · mandatory/optional · required for Manual one-shot · required for Scheduled · requires Production benchmarking · risk if wrong · evidence to select · recommended decision · owner status.

| Parameter | Location | Exists | Man/Opt | Manual one-shot | Scheduled | Production bench | Risk if wrong | Evidence needed | Recommendation | Owner status |
|---|---|---|---|---|---|---|---|---|---|---|
| `batch_size` | publisher/reconciliation required kwarg | Y | Mandatory | Yes (approved 50) | Yes | Yes (re-validate) | lock/throughput | B1 benchmark (done) | Keep required input; value 50 approved (B1) | OWNER_APPROVED_WITH_CONDITIONS |
| Redis enqueue timeout | inherited from ARQ `RedisSettings` connection timeouts (`worker.py`/`create_pool`); no explicit override | N (no publisher override) | Optional | Not required (defaults apply) | Recommend explicit | Yes | enqueue hang / long lock hold | measured p95 enqueue latency (benchmark: 12–21 ms) | Defer; consider explicit setting only when scheduling/Production | PENDING_OWNER_DECISION |
| Publisher execution timeout (wall-clock) | none | N | — | Not required (manual caller bounds it) | Yes | Yes | runaway invocation | load/backlog test | Defer until scheduled/Production | PENDING_OWNER_DECISION |
| Database transaction timeout | none (session default; connection timeout exists in config) | N | — | Not required | Recommend | Yes | long lock hold / deadlock | lock-duration benchmark (B1: tx p95 0.74 s @50) | Defer; do not set now | PENDING_OWNER_DECISION |
| Claim/lock duration | derived from transaction (repo `FOR UPDATE SKIP LOCKED`) | Y (behavioral) | — | Bounded by batch_size | Bounded by batch_size | Yes | contention | B1 benchmark | No separate input; only batch_size governs | — |
| Publisher concurrency (parallel invocations) | none (caller-managed) | N | Optional | Single manual invocation at a time | Yes | Yes | duplicate/corruption risk | concurrency test (benchmark: 2×200 safe) | Single invocation for manual; defer concurrency policy to scheduling | PENDING_OWNER_DECISION |
| Retry limit (max attempts) | none (no retry loop) | N | — | Not required (manual re-run/reconcile) | Yes | Yes | infinite/stuck retry | failure analysis | Defer until scheduled/Production | PENDING_OWNER_DECISION |
| Retry/backoff strategy | none (transient → pending; no backoff) | N | — | Not required (reconcile is the retry) | Yes | Yes | thundering herd / unbounded | failure/load test | Defer until scheduled | PENDING_OWNER_DECISION |
| Error classification | publisher: transient (RedisError/OSError/TimeoutError) vs permanent (UnsupportedEventContractError) vs commit failure | Y | Built-in | Yes | Yes | Yes | mis-deferred/mis-failed | already validated | No change | — |
| Reconciliation invocation interval | none (one-shot function) | N | — | Not required (manual) | Yes | Yes | stale pending work | backlog/cadence test | Defer; no interval invented | PENDING_OWNER_DECISION |
| Scheduling cadence | none (`WorkerSettings.cron_jobs` unchanged) | N | — | No (B2 manual) | Yes | Yes | premature auto-publication | separate decision | Defer; B2 controls (NOT_AUTHORIZED) | PENDING_OWNER_DECISION |
| Logging/observability thresholds | metrics counters exist (`metrics.py`); no alert thresholds | Partial | — | Useful (logs/metrics present) | Yes | Yes | silent drift | monitoring review | Keep existing; defer alert thresholds | PENDING_OWNER_DECISION |
| Memory/CPU limits | none for publisher (worker `max_jobs=4`/`job_timeout=300` are worker-level) | N | — | Not required | Yes | Yes | resource exhaustion | RSS/container measurement | Defer until scheduled/Production | PENDING_OWNER_DECISION |

---

## 3. Operating-mode profiles

### Profile A — Manual one-shot (approved, current)
- Required inputs: an `AsyncSession`, an ARQ/Redis client, and **`batch_size=50`** supplied explicitly.
- No automatic polling, no periodic scheduling, no ARQ cron, no worker change.
- No live application Outbox publication without separate authorization (B2/B1 do not grant it).
- **Minimum additional inputs to safely invoke manually:** none beyond the existing contract. The caller provides the session and Redis pool; `batch_size=50` is the approved explicit value. No timeout/retry/concurrency parameters are required for a single manual invocation.

### Profile B — Scheduled operation (future, not authorized)
- Additional parameters would be needed: scheduling cadence, an execution timeout, a reconciliation interval, a retry/backoff policy, a max-attempt limit, and a concurrency policy (how many parallel invocations, if any).
- Explicitly **not** registered: no cron, no interval value, no cadence. `AUTOMATIC_PUBLISHER_SCHEDULING: NOT_AUTHORIZED`.

### Profile C — Production (future, not approved)
- Requires capacity/timeout/resource/monitoring evidence: Redis enqueue timeout under production load, DB transaction/lock limits, publisher wall-clock timeout, container memory/CPU limits, alert thresholds on deferred/failed/commit-failure/backlog, and a recovery/concurrency SLA.
- No Production-ready values are declared. `PRODUCTION: NOT_APPROVED`.

---

## 4. Recommendations

- **Need an owner decision now:** none beyond what is already decided (B1/B2). The approved manual-only operation has no additional required numeric parameter.
- **Can remain explicit required function inputs:** `batch_size` (approved value 50), and, for scheduled/future operation, any eventual timeout/retry values — they should stay explicit arguments or await an approved config field.
- **Irrelevant to the approved manual-only operation:** scheduling cadence, reconciliation interval, retry/backoff, worker concurrency, publisher timeout, memory/CPU limits.
- **Defer until scheduling or Production is considered:** all parameters in the "Scheduled"/"Production bench" columns above, specifically Redis enqueue timeout override, publisher execution timeout, DB transaction timeout, retry limit/backoff, reconciliation interval, cadence, concurrency policy, memory/CPU limits, and monitoring thresholds.

No numeric value is invented; no default and no config field is added.

---

## 5. Owner decision table (B3)

| Parameter group | Candidate decision | Recommendation | Owner status |
|---|---|---|---|
| Manual one-shot (current) | No additional numeric parameter | Reaffirm B1/B2; keep `batch_size=50` explicit | OWNER_APPROVED_WITH_CONDITIONS / OWNER_APPROVED_MANUAL_ONE_SHOT |
| Redis enqueue timeout | Approve measured value / defer | Defer until scheduling/Production; benchmark exists (p95 12–21 ms) | OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11) |
| Publisher execution timeout | Approve measured value / defer | Defer until scheduling/Production | OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11) |
| Database transaction timeout | Approve / defer | Defer; batch_size already bounds lock duration | OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11) |
| Publisher concurrency | Approve policy / defer | Defer until scheduling (manual = single invocation) | OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11) |
| Retry limit / backoff | Approve measured / defer | Defer until scheduled/Production | OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11) |
| Reconciliation interval | Approve / defer | Defer; no interval invented | OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11) |
| Scheduling cadence | Approve / defer | Defer; B2 keeps NOT_AUTHORIZED | OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11) |
| Observability thresholds | Approve / defer | Defer until scheduled/Production; existing metrics remain | OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11) |
| Memory/CPU limits | Approve / defer | Defer until Production consideration | OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION (2026-11-11) |

---

## 6. Statuses

```text
B1: OWNER_APPROVED_WITH_CONDITIONS
B2: OWNER_APPROVED_MANUAL_ONE_SHOT
B3: OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION

AUTOMATIC_PUBLISHER_SCHEDULING: NOT_AUTHORIZED
LIVE_APPLICATION_OUTBOX_PUBLICATION: NOT_AUTHORIZED
REAL_INGESTION_CONSUMER: NOT_REGISTERED
PRODUCTION: NOT_APPROVED
```

**Owner decision B3 (2026-11-11):** `OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION` —
the owner deferred the remaining Publisher runtime parameters (publisher execution timeout,
database transaction timeout, Redis enqueue timeout override, retry/backoff controls,
concurrency policy, reconciliation cadence, resource limits, monitoring thresholds) until
periodic scheduling or Production is considered. This deferral does not approve live
application Outbox publication. No values are selected, and B3 remains deferred until the
owner explicitly decides otherwise when scheduling/Production is considered.
