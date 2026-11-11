# Gate B-S3 — Numeric Security Policy & Owner Decision Packet

**Date:** 2026-11-11. **Design and governance preparation only.** No owner decision is
recorded automatically; every numeric setting below remains `PENDING_OWNER_DECISION`.
No upload, PDF processing, rendering, OCR, extraction, or ingestion is implemented or
activated by this document.

Final state preserved:

```text
GATE_B_S0: IMPLEMENTED
GATE_B_S1: IMPLEMENTED
GATE_B_S2: IMPLEMENTED
GATE_B: OPEN / OWNER_DECISION_REQUIRED
UPLOAD_API: NOT_ACTIVATED
REAL_PDF_PROCESSING: NOT_AUTHORIZED
PHASE_4: PLANNED / GATED
PHASE_5: NOT_STARTED
PRODUCTION: NOT_APPROVED
```

---

## 1. Grounded evidence (verified)

| Evidence | Value | Source |
|---|---|---|
| Math pilot file size / pages | 37,478,046 B (~35.7 MiB) / 188 pages | `resources/math/grade2/manifest.yaml` |
| Physics pilot file size / pages | 12,821,822 B (~12.2 MiB) / 176 pages | `resources/physics/grade12/manifest.yaml` |
| Request-body limit | `max_request_bytes = 20971520` (20 MiB), config.py:64 | app config |
| Nginx body / proxy timeouts | `client_max_body_size 20m`; read/send 360s | nginx.conf:9,34-35 |
| Worker | `max_jobs=4`, `job_timeout=300` | worker.py:176-177 |
| pypdf 6.21.3 | per-filter/per-stream caps (default zlib output 75 MB); **not** a document-wide budget | pypdf Configuration |
| S2 container enforcement | `--memory 768m`, `--cpus 0.75`, `--pids-limit 96`, `--network none`, `--read-only`, non-root, cap-drop | Gate B-S2 doc |
| Deployment Compose | **no** container memory/CPU/pids limits | docker-compose.yml |

Pilot metadata is used **only** to check whether candidate limits would accommodate the
recorded sizes/page counts. It says nothing about rendering complexity, extraction
quality, or legal authorization. Accommodating these two files does not make a limit
suitable for all textbooks.

Evidence-classification used below:
- **Pilot-accommodating** — candidate large enough for the two recorded pilots.
- **Benchmark-needed** — requires synthetic/measured calibration before selection.
- **Owner choice** — policy decision independent of measurement.
- **NOT_PROVEN / NOT_TESTED** — no supporting evidence available.

---

## 1b. Owner decision record — `GATE_B_S3_PARTIAL_OWNER_DECISION`

`GATE_B_S3_PARTIAL_OWNER_DECISION = APPROVE_WITH_CONDITIONS` (2026-11-11).

The owner approved the following six policies **with conditions** (policy approval only;
no runtime configuration is authorized by this decision):

| ID | Approved policy | Conditions |
|---|---|---|
| GB-01 | Maximum file size: **40 MiB per document** | Document-size policy only. Existing HTTP/Nginx transport limits remain unchanged. Future multipart transport must account for request overhead; ~44 MiB is a planning estimate, not an approved transport setting. |
| GB-02 | Maximum PDF page count: **250** | Initial admission ceiling only; does not guarantee successful processing. |
| GB-03 | Maximum decompressed bytes per stream: **32 MiB** | Per-stream limit only; does not establish an aggregate document decompression budget. GB-04 remains pending. |
| GB-08 | Child wall-clock timeout: **120 seconds** | Candidate execution policy; no runtime configuration authorized. |
| GB-09 | Parent/Supervisor wall-clock timeout: **200 seconds** | Must exceed child timeout and leave time for termination, cleanup, and result handling. |
| GB-18 | Require `require_admin` permission and audit logging | Administrator access does not replace independent resource provenance and operation-specific authorization checks. |

**Clarification:** these are **owner-approved policies**, not implemented runtime
configuration, not a production acceptance result, and not a legal-clearance statement.
The technical evidence classifications in this document are unchanged. The remaining
twelve decisions stay `PENDING_OWNER_DECISION` and are not approved by implication.

---

## 2. Decisions

For each: Decision ID · policy question · recommended candidate (or alternatives) ·
rationale · compatibility · resource/security impact · enforcement layer · required
acceptance tests · failure behavior · scope (per-file/page/child/container/user/global)
· owner status.

### GB-01 — Maximum upload file size (bytes)
- Question: largest accepted textbook/PDF upload in bytes.
- Candidate: **40 MiB (41,943,040 B)** document limit, with a separate upload path distinct
  from the current 20 MiB request body; alternatives: keep 20 MiB transport + server-storage
  registration for larger books, or 50 MiB.
- Rationale: accommodates both pilots (math 35.7 MiB) with headroom; does not raise the
  existing transport limit silently.
- Compatibility: needs a dedicated upload route or storage-registration path (hybrid intake);
  does not change `max_request_bytes`/nginx by itself.
- Impact: larger DoS surface; mitigated by rate limits + quarantine + magic-byte checks.
- Enforcement layer: request validation (nginx + API) → storage quarantine.
- Acceptance tests: oversized fixture rejected; boundary accepted; multipart overhead separated.
- Failure: reject (4xx) with explicit code; no staging write.
- Scope: **per-file**.
- Approved: `APPROVED_WITH_CONDITIONS` (2026-11-11).
- Condition: **document-size policy only**. Existing HTTP/Nginx transport limits remain
  unchanged. Future multipart transport capacity must account for request overhead;
  approximately 44 MiB is a planning estimate, not an approved transport setting.
- Note: owner-approved policy; **not** an implemented runtime configuration.

### GB-02 — Maximum PDF page count
- Question: max pages per PDF.
- Candidate: **250 pages**; alternative 300.
- Rationale: pilots are 188/176; headroom ~1.3–1.6×.
- Compatibility: enforced pre-render in the Child (no decode needed).
- Impact: bounds page-tree work; not a decompression control.
- Enforcement layer: Child (structural page count).
- Acceptance tests: multi-page synthetic fixture over limit rejected; boundary accepted.
- Failure: reject (unsupported/too-large) before processing.
- Scope: **per-file**.
- Approved: `APPROVED_WITH_CONDITIONS` (2026-11-11).
- Condition: **initial admission ceiling only**; it does not guarantee successful processing.
- Note: owner-approved policy; **not** an implemented runtime configuration.

### GB-03 — Maximum decompressed bytes per stream
- Question: per-stream decode output cap (zlib/FlateDecode etc.).
- Candidate: **32 MiB** per stream; alternative rely on pypdf default 75 MiB until measured.
- Rationale: pypdf 6.21.3 enforces per-filter/per-stream caps (default 75 MB); explicit
  smaller cap lowers per-stream risk. This is **not** a document-wide budget.
- Compatibility: passed via `ParentChildRequest.limits` → scoped `Configuration` in Child.
- Impact: bounds single-stream decode memory.
- Enforcement layer: Child (pypdf Configuration).
- Acceptance tests: S1-style decode under tiny cap → `RESOURCE_LIMIT`; boundary metadata.
- Failure: reject as `RESOURCE_LIMIT`.
- Scope: **per-stream**.
- Approved: `APPROVED_WITH_CONDITIONS` (2026-11-11).
- Condition: **per-stream limit only**; it does not establish an aggregate document
  decompression budget. **GB-04 remains pending.**
- Note: owner-approved policy; **not** an implemented runtime configuration.

### GB-04 — Maximum aggregate decompressed bytes per document
- Question: document-wide sum of decoded stream bytes.
- Candidate: **256 MiB** per document; alternative 512 MiB.
- Rationale: pypdf has **no** document-wide aggregate control; requires child-side
  accounting across decoded streams plus a container-memory backstop.
- Compatibility: custom child-side counter (new logic); container memory bound is the backstop.
- Impact: the real decompression-bomb defense; currently **NOT_PROVEN/absor**.
- Enforcement layer: Child (aggregation) + container memory.
- Acceptance tests: synthetic multi-stream budget overflow rejected; aggregate boundary.
- Failure: terminate child with `RESOURCE_LIMIT`; parent survives.
- Scope: **per-file**.
- Status: `PENDING_OWNER_DECISION` (requires implementation + benchmark).

### GB-05 — Maximum rendered DPI (future rendering, separately authorized)
- Question: DPI ceiling if rendering is later authorized.
- Candidate: **150 DPI**; alternative 72 DPI (archival) or 200 DPI.
- Rationale: Gate A preflight used 72/150 DPI (synthetic only).
- Compatibility: depends on Gate A renderer selection; not implementable now.
- Impact: drives pixel/artifact size and memory.
- Enforcement layer: future renderer config (Child).
- Acceptance tests: renderer benchmark only after Gate A.
- Failure: reject/limit request outside allowed DPI.
- Scope: **per-file** (document-global setting).
- Status: `PENDING_OWNER_DECISION` (Gate A prerequisite).

### GB-06 — Maximum page width / height / total pixels
- Question: per-page dimension and pixel caps.
- Candidate: **5,000 × 5,000 px** (25 MP) per page; alternative 8,192 × 8,192.
- Rationale: no current evidence; benchmark-needed.
- Compatibility: future render path only.
- Impact: bounds per-page image buffer (`image_maximum_buffer_size` analog).
- Enforcement layer: future renderer (Child).
- Acceptance tests: synthetic large-page fixture rejected at pixel cap.
- Failure: reject/terminate render of that page.
- Scope: **per-page**.
- Status: `PENDING_OWNER_DECISION` (benchmark-needed).

### GB-07 — Maximum aggregate pixel budget per document
- Question: total rendered pixels across a document.
- Candidate: **500 MP** per document; alternative 1,000 MP.
- Rationale: correlates with memory/temp/CPU; benchmark-needed.
- Compatibility: future render pipeline accounting.
- Impact: caps aggregate render work.
- Enforcement layer: future renderer (Child).
- Acceptance tests: aggregate pixel overflow aborts document render.
- Failure: terminate child; parent reports resource limit.
- Scope: **per-file**.
- Status: `PENDING_OWNER_DECISION` (benchmark-needed).

### GB-08 — Child processing wall-clock timeout
- Question: per-child processing timeout.
- Candidate: **120 s**; alternatives 60 s / 300 s (worker `job_timeout=300`).
- Rationale: prototype used 20 s for normal work; 1 s to force hang. Needs benchmark.
- Compatibility: enforced in Parent Supervisor (`subprocess` timeout), not worker job timeout.
- Impact: bounds child hang; needs margin under nginx proxy 360 s.
- Enforcement layer: Parent (subprocess timeout) → terminate → kill.
- Acceptance tests: normal completion < timeout; hang triggers terminate then kill; no orphan.
- Failure: terminate child, typed `TIMEOUT`; parent remains usable.
- Scope: **per-child**.
- Approved: `APPROVED_WITH_CONDITIONS` (2026-11-11).
- Condition: **candidate execution policy only**; no runtime configuration is authorized.
- Note: owner-approved policy; **not** an implemented runtime configuration.

### GB-09 — Parent/Supervisor wall-clock timeout
- Question: total parent wait per request.
- Candidate: **200 s** (child timeout + margin); alternative 300 s.
- Rationale: must exceed child timeout and remain under nginx proxy (360 s).
- Compatibility: Parent supervisor-level; distinct from child timeout.
- Impact: bounds request-holding; cleanup guarantee.
- Enforcement layer: Parent supervisor.
- Acceptance tests: parent aborts a stuck child burst and frees the slot.
- Failure: abort request, cleanup, report; subsequent request succeeds.
- Scope: **per-request** (global constant).
- Approved: `APPROVED_WITH_CONDITIONS` (2026-11-11).
- Condition: must exceed the child timeout and leave time for termination, cleanup, and
  result handling.
- Note: owner-approved policy; **not** an implemented runtime configuration.

### GB-10 — Child/container memory limit
- Question: memory ceiling for the PDF child container.
- Candidate: **1 GiB** container `mem_limit` (matches `WORKER_MEMORY_LIMIT=1g` documentation but
  currently unenforced); alternative 768 MiB (S2 value).
- Rationale: S2 demonstrated container-level `--memory 768m`; deployment compose has no limits.
- Compatibility: deployment container resource; per-child cgroup is **NOT_ENFORCED**.
- Impact: OOM containment; protects host.
- Enforcement layer: container runtime (`mem_limit`); per-child cgroup unresolved.
- Acceptance tests: memory-exhaustion probe killed; parent survives.
- Failure: child OOM-killed; parent reports, retries/cleanup.
- Scope: **per-container** (goal: per-child if cgroup added).
- Status: `PENDING_OWNER_DECISION` (benchmark-needed).

### GB-11 — CPU quota
- Question: CPU ceiling for the child container.
- Candidate: **1.0 vCPU** per container; alternative 0.75 (S2 value).
- Rationale: S2 `--cpus 0.75` observed; completion-time evidence only.
- Compatibility: deployment container resource.
- Impact: bounds CPU saturation.
- Enforcement layer: container runtime (`--cpus`).
- Acceptance tests: CPU-bound probe completes; host not starved.
- Failure: throttled (not killed); monitor via counters.
- Scope: **per-container**.
- Status: `PENDING_OWNER_DECISION` (benchmark-needed).

### GB-12 — PID/process limit
- Question: max live processes in the child container.
- Candidate: **128** PIDs; alternative 96 (S2 value).
- Rationale: S2 `--pids-limit 96` observed (105/200 spawns failed).
- Compatibility: container runtime.
- Impact: prevents fork bombs.
- Enforcement layer: container runtime (`--pids-limit`).
- Acceptance tests: excessive concurrent spawns fail; parent unaffected.
- Failure: spawn rejected (EAGAIN); typed resource error.
- Scope: **per-container**.
- Status: `PENDING_OWNER_DECISION`.

### GB-13 — Temporary filesystem capacity / per-document temp budget
- Question: staging/tmp capacity and per-document budget.
- Candidate: **512 MiB per document**, **5 GiB total staging**; alternative 1 GiB/10 GiB.
- Rationale: S2 test tmpfs was 64 MiB; production needs headroom for artifacts.
- Compatibility: storage layer quota (R-199/upload_dir) + container tmpfs.
- Impact: bounds disk exhaustion.
- Enforcement layer: storage/worker quota (+ container tmpfs).
- Acceptance tests: per-document quota overflow rejected; total quota enforced.
- Failure: reject/terminate; cleanup incomplete staging.
- Scope: per-document quota **per-file**; total **global**.
- Status: `PENDING_OWNER_DECISION` (benchmark-needed).

### GB-14 — Temporary-file retention / cleanup policy
- Question: how long staging artifacts are retained and how cleanup runs.
- Candidate: delete on success/failure; orphan sweep daily; user uploads ≤ 7 days (R-199).
- Rationale: R-199 requires 7-day upload retention; R-042 retention obligations.
- Compatibility: separate cleanup job (not in S0/S1/S2); requires a new scheduled task.
- Impact: storage hygiene; no data loss beyond policy.
- Enforcement layer: worker/storage cron (separate decision; not yet registered).
- Acceptance tests: orphan detection, abnormal-termination cleanup, retention expiry.
- Failure: cleanup is idempotent; no deletion of authorized records.
- Scope: **global** (sweep) + per-upload retention.
- Status: `PENDING_OWNER_DECISION`.

### GB-15 — Maximum active child count / concurrency
- Question: how many PDF children may run concurrently.
- Candidate: **4** (match worker `max_jobs=4`); alternative 2 or 8.
- Rationale: worker max_jobs=4 is the existing ceiling; ingestion cap should be ≤ it.
- Compatibility: Parent supervisor concurrency gate + worker.
- Impact: bounds aggregate memory/CPU.
- Enforcement layer: queue/Parent supervisor gate.
- Acceptance tests: 5th concurrent request waits/rejected; bounded resource use.
- Failure: queue/backpressure, not silent overflow.
- Scope: **global** (concurrency).
- Status: `PENDING_OWNER_DECISION`.

### GB-16 — Upload request concurrency & backpressure
- Question: max in-flight uploads and behavior under load.
- Candidate: **8 concurrent uploads**; excess → 429/503 backpressure.
- Rationale: bounded queue avoids memory spikes.
- Compatibility: API request layer.
- Impact: overload protection.
- Enforcement layer: request validation (semaphore/rate limit).
- Acceptance tests: concurrent upload limiter; backpressure responses.
- Failure: reject with 429/503; queued requests not lost.
- Scope: **global** (per-API instance).
- Status: `PENDING_OWNER_DECISION`.

### GB-17 — Upload rate limits
- Question: per-user and per-IP upload rate.
- Candidate: per-user **60/hour**, per-IP **120/hour** (owner choice; tune after load test); use
  existing Redis limiter (R-113 pattern).
- Rationale: reuse `ratelimit.py` pattern; current OTP/chat limits exist.
- Compatibility: request layer `rate_limit_dependency`.
- Impact: abuse mitigation.
- Enforcement layer: request layer (Redis/Pg limiter).
- Acceptance tests: over-limit → 429; per-key isolation.
- Failure: 429 with `rate_limited`.
- Scope: **per-user / per-IP**.
- Status: `PENDING_OWNER_DECISION`.

### GB-18 — Required administrator permission / authorization
- Question: who may upload/register resources and how is it enforced.
- Candidate: `require_admin` on all intake routes + `admin_audit_log` (R-097/R-117/R-122).
- Rationale: `require_admin` is not yet implemented (S0 audit); admin seed + audit exist.
- Compatibility: `deps.py` + admin router; `admin_audit_log` model exists.
- Impact: prevents unauthorized intake.
- Enforcement layer: authorization (API).
- Acceptance tests: non-admin → 403; admin → audit row written.
- Failure: reject (403) before validation.
- Scope: **global** (role).
- Approved: `APPROVED_WITH_CONDITIONS` (2026-11-11).
- Condition: administrator access does **not** replace independent resource provenance and
  operation-specific authorization checks.
- Note: owner-approved policy; **not** an implemented runtime configuration.

---

## 3. Consolidated policy proposal

| Policy | Recommended candidate | Alternative | Enforcement location | Evidence strength | Owner decision |
|---|---|---|---|---|---|
| Upload file size | 40 MiB (document) | 20 MiB transport + storage-registration / 50 MiB | request validation → storage | pilot-accommodating; no benchmark reached | APPROVED_WITH_CONDITIONS |
| Page count | 250 | 300 | Child (pre-render) | pilot-accommodating | APPROVED_WITH_CONDITIONS |
| Decompressed per stream | 32 MiB | pypdf default 75 MiB | Child (pypdf Configuration) | synthetic (S1) only | APPROVED_WITH_CONDITIONS |
| Aggregate decompressed/document | 256 MiB | 512 MiB | Child + container memory | **NOT_PROVEN** | REQUIRED |
| DPI | 150 | 72 / 200 | future renderer | synthetic (Gate A) only | REQUIRED |
| Page width/height/pixels | 5000×5000 (25 MP) | 8192² | future renderer | **NOT_TESTED** | REQUIRED |
| Aggregate pixel budget | 500 MP | 1000 MP | future renderer | **NOT_TESTED** | REQUIRED |
| Child timeout | 120 s | 60 / 300 s | Parent (subprocess) | synthetic (S1) | APPROVED_WITH_CONDITIONS |
| Parent timeout | 200 s | 300 s | Parent supervisor | derived from child | APPROVED_WITH_CONDITIONS |
| Memory limit | 1 GiB | 768 MiB | container runtime | S2 container-level | REQUIRED |
| CPU quota | 1.0 vCPU | 0.75 | container runtime | S2 completion-time only | REQUIRED |
| PID limit | 128 | 96 | container runtime | S2 observed | REQUIRED |
| Temp capacity | 512 MiB/doc, 5 GiB total | 1 GiB/10 GiB | storage/worker + tmpfs | **NOT_TESTED** | REQUIRED |
| Temp retention/cleanup | delete on done; 7-day upload (R-199); daily sweep | — | worker/storage cron | documented requirement (R-199) | REQUIRED |
| Active children | 4 | 2 / 8 | Parent gate + worker | worker max_jobs=4 | REQUIRED |
| Upload concurrency | 8 | — | API request layer | design | REQUIRED |
| Upload rate | 60/hr user, 120/hr IP | — | request layer (Redis limiter) | pattern reuse (R-113) | REQUIRED |
| Admin authorization | require_admin + audit | — | authorization | R-097/R-117/R-122 | APPROVED_WITH_CONDITIONS |

Every number above is a **recommendation**, not an approved setting. `Evidence strength`
reflects only what is documented/measured; "NOT_TESTED" entries require benchmarking before
selection.

## 4. Dependencies

- **GB-05/06/07 (DPI, pixels, aggregate pixels)** are tightly coupled with GB-10/11/13
  (memory, CPU, temp) and GB-08/09 (timeouts): rendering budget must be considered as one
  package, after Gate A picks a renderer.
- **GB-04 (aggregate decompressed)** must be implemented with GB-10 (container memory) as a
  backstop before it can be enforced.
- **GB-08 → GB-09** (parent timeout depends on child timeout).
- **GB-10/11/12** are deployment-container resource settings that must be coordinated with
  the (unchanged) deployment Compose to be enforced.
- **GB-14** depends on a separately scheduled cleanup job (not yet registered).
- **GB-18** is a prerequisite for any intake activation (GB-16/17 gate the same surface).

## 5. S2 evidence qualification (accuracy note)

- **Memory `rc=-9`**: evidence of the probe process being **SIGKILL**ed; this is **not**
  confirmed as a verified cgroup OOM event (no `memory.events`/oom_kill counter captured).
  Classify as **NOT_PROVEN** for "cgroup OOM confirmed"; the kill itself was observed.
- **CPU completion time (1.214 s)**: an observed completion time under `--cpus`; this is
  **not** proof of throttling without `cpu.stat`/`cpuacct` counters. Classify throttling as
  **NOT_PROVEN**; only "ran under --cpus" is observed.
- **PID spawn failures (105/200)**: observed `OSError`/fork failures; **not** verified
  against a `pids.events` limit counter. Classify as observed behavior; the counter-level
  event is **NOT_TESTED**.
- **`/etc/shadow` unreadable**: demonstrates a read-only rootfs and non-root execution; on
  its own it does **not** prove host-secret isolation. Host-secret isolation requires the
  combination of mount review (no secrets volume), Docker-socket absence (verified), and
  environment allowlisting (verified) — not the shadow file alone.
- **Per-child cgroup** and **seccomp/LSM**: remain **NOT_ENFORCED** / **NOT_TESTED**; the
  S2 limits are container-level, not per-child (no separate cgroup for each child). Container
  limits must not be represented as per-child guarantees.
- **pypdf 6.21.3** caps are per-filter/per-stream; they are not a document-wide aggregate
  decompression budget (GB-03 vs GB-04 are separate controls).

## 6. Explicit non-implementation statement

This packet performs **no** implementation or activation: no upload endpoints changed or
activated; no PDF ingestion; no rendering/OCR/extraction/embedding/indexing/retrieval; no
PDFium/renderer added; no production Dockerfiles/Compose/nginx/runtime/env changes; no
schema/migration/Redis/queue/publisher/scheduler/worker registration changes; no production
defaults set for any pending numeric limit; no Gate A/C change; Phase 4/5 not opened; no Git
operations. All existing local changes preserved.

## 7. Statuses

```text
GATE_B_S0: IMPLEMENTED
GATE_B_S1: IMPLEMENTED
GATE_B_S2: IMPLEMENTED
GATE_B_S3: DECISION_PACKET_COMPLETE
GATE_B_S3_PARTIAL_OWNER_DECISION: APPROVED_WITH_CONDITIONS

GB_01: APPROVED_WITH_CONDITIONS
GB_02: APPROVED_WITH_CONDITIONS
GB_03: APPROVED_WITH_CONDITIONS
GB_08: APPROVED_WITH_CONDITIONS
GB_09: APPROVED_WITH_CONDITIONS
GB_18: APPROVED_WITH_CONDITIONS

GB_04: PENDING_OWNER_DECISION
GB_05: PENDING_OWNER_DECISION
GB_06: PENDING_OWNER_DECISION
GB_07: PENDING_OWNER_DECISION
GB_10: PENDING_OWNER_DECISION
GB_11: PENDING_OWNER_DECISION
GB_12: PENDING_OWNER_DECISION
GB_13: PENDING_OWNER_DECISION
GB_14: PENDING_OWNER_DECISION
GB_15: PENDING_OWNER_DECISION
GB_16: PENDING_OWNER_DECISION
GB_17: PENDING_OWNER_DECISION

GATE_B: OPEN / OWNER_DECISION_REQUIRED
UPLOAD_API: NOT_ACTIVATED
REAL_PDF_PROCESSING: NOT_AUTHORIZED
PHASE_4: PLANNED / GATED
PHASE_5: NOT_STARTED
PRODUCTION: NOT_APPROVED
```

Six decisions were approved with conditions (`GATE_B_S3_PARTIAL_OWNER_DECISION =
APPROVE_WITH_CONDITIONS`, 2026-11-11). Twelve decisions remain
`PENDING_OWNER_DECISION` and were not approved by implication. No owner decision was
recorded automatically for the pending twelve.
