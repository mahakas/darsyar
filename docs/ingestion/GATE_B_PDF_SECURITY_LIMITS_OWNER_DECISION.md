# Gate B — PDF Ingestion Security and Resource Limits: Owner Decision Package

**Date:** 2026-11-11. **Read-only technical and security assessment.** This document
prepares owner decisions for Gate B; it does **not** approve any security limit. No code,
configuration, resource limit, schema, or runtime operation changed. No PDF was opened,
rendered, extracted, or inspected.

## Preserved governance baseline

```text
R-1: OWNER_DECIDED_OPTION_B
R1-IMPL: IMPLEMENTED
R-2: OWNER_APPROVED
R-3: OWNER_DECIDED_DEFER_ARCHIVAL

B1: OWNER_APPROVED_WITH_CONDITIONS
B2: OWNER_APPROVED_MANUAL_ONE_SHOT
B3: OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION

S-1: OWNER_APPROVED_WITH_CONDITIONS
S-2: OWNER_APPROVED_WITH_CONDITIONS

SLICE_1: IMPLEMENTED
SLICE_2: CLOSED
SLICE_3: CLOSED

APPLICATION_DB_REVISION: 0019_outbox_job_fk_restrict
APPLICATION_DB_FK: RESTRICT

GATE_A: OPEN
GATE_B: OPEN / OWNER_DECISION_REQUIRED
GATE_C: OWNER_APPROVAL_REQUIRED

PHASE_4: PLANNED / GATED
PHASE_5: NOT_STARTED

LICENSING_AND_AUTHORIZATION: PENDING
PRODUCTION: NOT_APPROVED
```

The existing Publisher decisions (B1/B2/B3) are unrelated to Gate B PDF resource limits
and remain unchanged.

---

## 1. Implementation basis — what actually exists (verified)

| Area | Path | State |
|---|---|---|
| Upload API endpoint | `backend/app/api/v1/documents.py` | **Placeholder** (1-line comment; no endpoint) |
| Storage backend | `backend/app/services/storage.py` | **Placeholder** (no storage implementation) |
| PDF render/extract child process | none in `backend/app` | **Does not exist** (no subprocess/pdfium code) |
| Ingestion services | `backend/app/services/ingestion/` | Empty (`__init__.py` + `.gitkeep` only) |
| Config fields (ingestion/upload limits) | `backend/app/core/config.py` | **No ingestion-specific field**; only `max_request_bytes=20971520`, `upload_dir="./uploads"`, `resources_dir="./resources"` |
| Rate limiting | `backend/app/core/ratelimit.py` | Generic Redis/Pg limiter (used by OTP/chat); no upload/ingestion rules |
| Auth/admin | `backend/app/api/deps.py` | `get_current_user` exists; **`require_admin` not implemented** (`admin/__init__.py` placeholder) |
| Audit log | `backend/app/models/admin_audit_log.py` | Model exists (append-only design) but no upload/ingestion audit wiring |
| Worker | `backend/app/services/worker.py` | `max_jobs=4`, `job_timeout=300`; no ingestion cron/consumer |
| nginx | `infra/nginx/nginx.conf` | `client_max_body_size 20m`; `proxy_read/send_timeout 360s` |
| Compose | `docker-compose.yml` | **No container memory/CPU/pids limits**; `stop_grace_period` api=90s, worker=30s; `security_opt: no-new-privileges` on all services |
| ADRs | `docs/adr/ADR-024-resource-licensing.md`, ADR-037/038/042/045 | Licensing/grade/edition/retention/index-meta requirements; no numeric processing limits |
| Requirements | `AGENTS.md` R-118, R-119 | File validation/MIME/magic, quarantine, safe storage, SSRF/domain guards, admin auth, no HTML execution |

**Key conclusion:** no upload endpoint, no file-validation/MIME/magic verification, no
PDF metadata/render/extraction interface, no child-process isolation, and no temporary-file
handling are implemented. Gate B limits are to be decided before such implementation;
current "enforced" values are limited to transport-level request body (20 MiB), nginx body
(20m) and proxy timeouts (360s), worker job timeout (300s), and absence of container
resource limits.

---

## 2. Gate B security matrix

Legend: **Enforced** = enforced in code/infra today; **Config** = config value exists;
**Documented req** = stated requirement (R-118/adr) not yet implemented; **Benchmark** =
measured evidence; **Missing** = no measurement; **Proposed (evidence)** = candidate range
only when supported; **Owner status** = PENDING_OWNER_DECISION unless noted.

### A. Upload limits

| Parameter | Enforced | Config | Documented req | Benchmark | Missing | Proposed | Owner status |
|---|---|---|---|---|---|---|---|
| Max request body size | Yes (20 MiB via `max_request_bytes=20971520`; nginx `20m`) | Yes | — | — | driver body vs nginx interplay | Do not raise unless separate upload path approved | PENDING_OWNER_DECISION |
| Max PDF file size | No (no upload path) | No | R-118 (size limit required) | — | Yes | ≤ current 20 MiB transport unless separate path; **conflict: math pilot 37,478,046 B > 20 MiB** | PENDING_OWNER_DECISION |
| Max page count | No | No | R-118 | — | Yes | pilot evidence: 188/176 pages; headroom needed | PENDING_OWNER_DECISION |
| Max files per request | No | No | — | — | Yes | — | PENDING_OWNER_DECISION |
| Max concurrent uploads | No | No | — | — | Yes | — | PENDING_OWNER_DECISION |
| Upload rate limits | No | No | R-113 (rate limits) | — | Yes | — | PENDING_OWNER_DECISION |
| Filename/path validation | No | No | R-118 | — | Yes | — | PENDING_OWNER_DECISION |
| MIME + magic-byte verification | No | No | R-118 | — | Yes | — | PENDING_OWNER_DECISION |
| Encrypted/password-protected PDF | No | No | R-118 (malformed/encrypted) | — | Yes | reject with explicit error | PENDING_OWNER_DECISION |
| Malformed-file rejection | No | No | R-118 | synthetic malformed rejection in Gate A preflight (pypdfium2) | — | — | PENDING_OWNER_DECISION |

### B. PDF expansion / resource exhaustion

| Control | Verifiable pre-render? | Requires isolated processing? | Owner status |
|---|---|---|---|
| Max decompressed/expanded content size | Partial (PDF object/xref pre-scan) | Yes (render-phase) | PENDING_OWNER_DECISION |
| Max image dimensions | Partial (image-resource metadata) | Yes | PENDING_OWNER_DECISION |
| Max embedded image count / aggregate image data | Partial | Yes | PENDING_OWNER_DECISION |
| Max PDF object/resource count | Partial (object count) | Yes | PENDING_OWNER_DECISION |
| Max rendering pixel count | No | Yes | PENDING_OWNER_DECISION |
| Max total rendered output size | No | Yes | PENDING_OWNER_DECISION |
| Decompression-bomb defense | Pre-scan limits + render-phase isolation | Yes | PENDING_OWNER_DECISION |

### C. Rendering controls

| Parameter | Existing | Evidence | Proposed | Owner status |
|---|---|---|---|---|
| Allowed DPI range | Gate A preflight used 72/150 DPI (synthetic only) | synthetic | needs benchmark | PENDING_OWNER_DECISION |
| Max page dimensions (px) | none | — | needs benchmark | PENDING_OWNER_DECISION |
| Max width/height (px) | none | — | needs benchmark | PENDING_OWNER_DECISION |
| Max total pixels per page | none | — | needs benchmark | PENDING_OWNER_DECISION |
| Max total rendered pixels per document | none | — | needs benchmark | PENDING_OWNER_DECISION |
| Max intermediate image size | none | — | needs benchmark | PENDING_OWNER_DECISION |
| Max output artifact size | none | — | needs benchmark | PENDING_OWNER_DECISION |

No renderer limits are selected.

### D. Execution limits

| Parameter | API process | Parent supervisor | PDF child process | Owner status |
|---|---|---|---|---|
| Timeout | nginx 360s exists; API none for ingestion | none | none | PENDING_OWNER_DECISION |
| Memory limit | none | none | none | PENDING_OWNER_DECISION |
| CPU quota | none (host) | none | none | PENDING_OWNER_DECISION |
| Max child-process count | n/a | none | none | PENDING_OWNER_DECISION |
| Process recycling threshold | n/a | none | none | PENDING_OWNER_DECISION |
| Cancellation propagation | none | none | none | PENDING_OWNER_DECISION |
| Orphan-process detection | n/a | none | none | PENDING_OWNER_DECISION |
| Unresponsive-child behavior | n/a | none | none | PENDING_OWNER_DECISION |
| Prevent stale processes publishing artifacts | n/a | none | none | PENDING_OWNER_DECISION |

### E. Temporary storage

| Parameter | Existing | Owner status |
|---|---|---|
| Temporary directory boundaries | `upload_dir="./uploads"` convention (no isolation/quota) | PENDING_OWNER_DECISION |
| Per-document storage quota | none | PENDING_OWNER_DECISION |
| Total staging quota | none | PENDING_OWNER_DECISION |
| Max intermediate artifact size | none | PENDING_OWNER_DECISION |
| Retention period | R-199: user uploads 7 days (requirement, not implemented) | PENDING_OWNER_DECISION |
| Cleanup eligibility / orphan detection | none | PENDING_OWNER_DECISION |
| Crash recovery / safe cleanup of incomplete output | none | PENDING_OWNER_DECISION |

No storage cleanup is implemented.

### F. Abuse prevention & authorization

| Control | Existing | Owner status |
|---|---|---|
| Authentication | `get_current_user` exists | PENDING_OWNER_DECISION |
| Admin authorization | `require_admin` **not** implemented | PENDING_OWNER_DECISION |
| Rate limits | OTP/chat only; none for upload | PENDING_OWNER_DECISION |
| Concurrent upload controls | none | PENDING_OWNER_DECISION |
| Per-user quotas | none | PENDING_OWNER_DECISION |
| Per-organization limits | n/a (no org model in MVP) | PENDING_OWNER_DECISION |
| Audit logging | `admin_audit_log` model exists; no upload wiring | PENDING_OWNER_DECISION |
| Error response safety | R-054 uniform `{code,message,request_id}` applies | — |
| Prevention of unauthorized resource access | R-121 owner-scoped queries | PENDING_OWNER_DECISION |
| Repeated failed processing behavior | none | PENDING_OWNER_DECISION |

API responses remain free of `organizationReference`, consistent with governance.

---

## 3. Existing vs proposed values — explicit distinction

- **Enforced today (transport):** request body 20 MiB (`max_request_bytes=20971520`, config.py:64); nginx `client_max_body_size 20m` (nginx.conf:9); nginx proxy read/send timeout 360s (nginx.conf:34-35); worker `job_timeout=300` (worker.py:177); worker `max_jobs=4` (worker.py:176); compose `stop_grace_period` api=90s / worker=30s (docker-compose.yml:99,129).
- **Configuration values:** `max_request_bytes`, `upload_dir="./uploads"`, `resources_dir="./resources"`, `page_size_max=100` (config.py:63,125-126). `WORKER_MEMORY_LIMIT: 1g` appears in compose env but is **not** a container `mem_limit` and is not consumed by the ingestion pipeline; treat as documentation, not an enforced limit.
- **Documented requirements (not implemented):** R-118 (size, page count, MIME/magic, quarantine, safe storage, random filename, no HTML execution, attachment download headers), R-119 (SSRF/domain guards for outbound fetches), R-199 (upload retention 7 days), R-113 (rate limits), R-097/R-117 (`require_admin`, seeded admin).
- **Benchmark-derived evidence:** only the synthetic Gate A preflight (pypdfium2, 72/150 DPI, synthetic 3-page PDF, malformed rejection). No upload/rendering resource benchmark exists.
- **Missing measurements:** everything in the matrix marked "Missing".
- **Proposed candidate ranges:** none selected; only evidence-grounded constraints noted (e.g., document limit tied to the 20 MiB transport boundary unless a separate upload path is approved; page-count headroom over 188/176).
- **Owner status:** all ingestion-specific numeric decisions are `PENDING_OWNER_DECISION`.

### Explicit conflict — file-size policy vs pilot manifests

- Math pilot `resources/math/grade2/C2051.pdf` = **37,478,046 bytes (~35.7 MiB)** (`manifest.yaml` file_size_bytes); physical pages 188.
- Physics pilot `resources/physics/grade12/C112209.pdf` = **12,821,822 bytes (~12.2 MiB)**; physical pages 176.
- **Conflict:** the math pilot exceeds the current enforced 20 MiB request-body/nginx limit. If a 20 MiB upload limit were applied, the math pilot could not be uploaded through the current path. The owner must decide a document/upload limit or a separate server-storage-registration path (per the confirmed `hybrid_textbook_intake` decision) for the larger book. **The limit is not raised automatically**; the conflict is documented for decision.

---

## 4. Synthetic-only test plan (per security category)

For each test: fixture, method, expected invariant, failure condition, renderer required?, separate security approval required?

| # | Test | Fixture | Method | Expected invariant | Failure condition | Renderer run? | Security approval? |
|---|---|---|---|---|---|---|---|
| 1 | Oversized synthetic PDF rejection | PDF > configured limit | upload/ingest path | rejected with explicit error | accepted | No | Yes (limit must be approved first) |
| 2 | Excessive page-count rejection | synthetic PDF > page limit | pre-ingest page-count check | rejected | accepted | No | Yes |
| 3 | Malformed PDF rejection | corrupted/garbage PDF | parse/validation | rejected; no artifact | crash/accept | No | No (Gate A already rejects) |
| 4 | Encrypted PDF behavior | password-protected synthetic PDF | encryption detection | explicit reject (or documented policy) | silent/accept | No | Yes |
| 5 | Large-image/pixel-limit rejection | PDF with oversized embedded image | image-resource / render-pixel check | rejected | accept/OOM | Yes | Yes |
| 6 | Decompression-bomb defense | synthetic bomb PDF | pre-scan + isolated render | containment; no OOM | resource exhaustion | Yes | Yes |
| 7 | Rendering timeout | slow/looping synthetic PDF | child timeout | child terminated; no artifact | hang | Yes | Yes |
| 8 | Child-process memory exhaustion | memory-spike PDF | memory limit enforcement | child killed; supervisor healthy | OOM kill of parent | Yes | Yes |
| 9 | Child-process CPU exhaustion | CPU-bound PDF | CPU quota | child throttled/terminated | host starvation | Yes | Yes |
| 10 | Parent cancellation | in-flight render | cancel propagation | child terminated; no stale artifact | orphan persists | Yes | Yes |
| 11 | Child termination | kill child mid-render | orphan detection | orphan reaped/reported; no publication | stale process publishes | Yes | Yes |
| 12 | Orphan process recovery | leftover child | sweep/reconcile | cleaned; safe | accumulation | Yes | Yes |
| 13 | Temporary storage quota enforcement | multi-doc staging | quota check | blocked at quota | overrun | No | Yes |
| 14 | Cleanup after abnormal termination | crash mid-write | cleanup job | staging cleared | leftover files | No | Yes |
| 15 | Concurrent upload/load tests | N simultaneous synthetic uploads | concurrency + rate limit | bounded; no corruption | resource exhaustion | No | Yes |
| 16 | Rate-limit & authorization tests | unauthenticated/over-limit | route-level | 401/429 | allowed | No | Yes |

All fixtures are synthetic. No pilot PDF is opened, rendered, extracted, or inspected.

---

## 5. Process-isolation assessment

Proposed architecture:

```
Parent Supervisor → Spawned PDFium Child → Validated Staging Artifact → Parent-controlled publication
```

| Property | Current state |
|---|---|
| OS-process isolation | **Design proposal only** — no child-process code exists |
| Database credential isolation | Not implemented (parent-only DB access is proposed, not present) |
| Child IPC restrictions | None (no child) |
| Filesystem access restrictions | None |
| Network access restrictions | None (server-119 governs outbound fetches; not implemented for child) |
| CPU/memory enforcement | None (no container limits; no child cgroups) |
| Child timeout and termination | None |
| Crash recovery | None |
| Parent-only database access | None |
| Fencing before consequential commits | None (outbox publisher exists, but PDF child art process is not built) |

No process isolation is implemented or modified in this task.

---

## 6. Owner decision register (Gate B)

| Decision | Exact question | Available evidence | Required benchmark/security test | Technical recommendation | Consequences | Dependencies | Status |
|---|---|---|---|---|---|---|---|
| Upload-size limit | Max PDF/upload size for ingestion | transport 20 MiB enforced; pilot conflict (37.5MB) | test #1 | separate upload path or explicit document limit; do not auto-raise | DoS vs pilot acceptance | R-118, hybrid intake | PENDING_OWNER_DECISION |
| Page-count limit | Max pages per PDF | pilot 188/176 | test #2 | headroom over pilot max | resource bounds | R-118 | PENDING_OWNER_DECISION |
| Decompressed-size limit | Max expanded content | none | test #6 | pre-scan + isolated render | bomb defense | — | PENDING_OWNER_DECISION |
| Rendering DPI/pixel limits | DPI, px width/height/total | Gate A preflight (72/150 DPI) only | tests #5 | benchmark-driven | artifact size/CPU | Gate A | PENDING_OWNER_DECISION |
| PDF execution timeout | Child render timeout | worker job_timeout=300 exists (worker-level) | test #7 | ≤ worker job_timeout; separate child value | hang prevention | — | PENDING_OWNER_DECISION |
| Parent timeout | Supervisor/wall-clock timeout | nginx 360s only | test #10 | > child timeout + margin | cleanup guarantee | — | PENDING_OWNER_DECISION |
| Memory/CPU limits | Child + container limits | none (WORKER_MEMORY_LIMIT env not enforced) | tests #8-9 | container `mem_limit`/cpus + child limit under memory cleanup configuration | OOM containment | Compose | PENDING_OWNER_DECISION |
| Child-process capacity | Max concurrent children | worker max_jobs=4 (exists, worker-level) | test #15 | ingestion-specific cap ≤ max_jobs | resource bounds | — | PENDING_OWNER_DECISION |
| Temporary storage quota | Per-doc + total staging quota | `upload_dir` convention only | tests #13-14 | explicit quotas | disk exhaustion | R-199 | PENDING_OWNER_DECISION |
| Temporary retention/cleanup | Retention period + orphan cleanup | R-199 (7 days, req) | tests #14 | approved retention + sweep | storage hygiene | R-199, R-42 | PENDING_OWNER_DECISION |
| Upload concurrency | Max concurrent uploads | none | test #15 | bounded concurrency | overload | — | PENDING_OWNER_DECISION |
| Rate limits | Upload rate limit per user/IP | OTP/chat limits exist (ratelimit.py) | test #16 | apply existing limiter pattern | abuse | R-113 | PENDING_OWNER_DECISION |
| Administrative authorization | require_admin for upload/admin | not implemented | test #16 | implement require_admin + audit | unauthorized access | R-097/R-117 | PENDING_OWNER_DECISION |

No decision is made on the owner's behalf.

---

## 7. Gate boundaries

- **Gate B:** upload, resource limits, processing security (this document).
- **Gate A:** renderer suitability, fidelity, licensing, provenance (separate; OPEN).
- **Gate C:** explicit approval for controlled PDF-backend equivalence testing (OWNER_APPROVAL_REQUIRED).

No gate is marked passed. Completion of a synthetic security benchmark does not authorize processing real textbooks.

---

## 8. Authorization reference 13529 (preserved)

```yaml
reference_id: "13529"
record_status: pending_evidence_and_scope_review
verification_status: not_independently_verified
```

Both pilot manifests remain `needs_review`. No legal-clearance claim is made. No pilot
PDF is downloaded, opened, rendered, extracted, OCR'd, embedded, indexed, retrieved, or
displayed/quoted.

---

## 8b. Gate B-S0 — Synthetic PDF Validation Foundation (implemented)

Owner decision `GATE_B-S0 = APPROVE_WITH_CONDITIONS` (2026-11-11). Implemented:

- Common PDF Validation Layer (`backend/app/services/ingestion/pdf_validation.py`), pypdf 6.21.4.
- Versioned Parent/Child contract (type-level; design only): `backend/app/services/ingestion/parent_child_contract.py`.
- Synthetic fixtures + tests `backend/tests/test_gate_b_pdf_validation.py` → **22 passed** (incl. pypdf resource-limit audit; verified under both locked 6.21.3 and installed 6.21.4).
- Explicit `PdfValidationPolicy(max_file_bytes, max_pages)`; no defaults; no config fields; not wired to any route.
- No pilot PDF, no upload API, no rendering/extraction, no PDFium.

Details: `GATE_B_PDF_VALIDATION_IMPLEMENTATION.md`; resource-limited audit: `PYPDF_RESOURCE_LIMITS_AUDIT.md`. Recorded: pypdf's built-in limits are **per-filter/per-stream** (75 MB output per filter etc.), not a document-wide budget; the validator's page-count path does not decode streams, so those caps are not exercised; no global decompression-bomb protection and no OS-level isolation exist. No numeric limit approved by S0.

**Gate B-S1 implemented** (`GATE_B-S1 = APPROVE_WITH_CONDITIONS`, 2026-11-11): Parent Supervisor + spawned PDF Child prototype (`parent_supervisor.py`, `pdf_child.py`), versioned IPC contract v1, scoped pypdf 6.21.3 Configuration, explicit synthetic content-stream decode under test-only limits, timeout/termination/escalation, secret-env isolation (allowlist), and synthetic tests (17). Parent is sole DB/infrastructure owner; no PG/Redis connection; no upload route; no production limits. See `GATE_B_S1_PARENT_CHILD_PROTOTYPE.md`.

**Gate B-S2 implemented** (`GATE_B-S2 = APPROVE_WITH_CONDITIONS`, 2026-11-11): Linux OS-level sandbox prototype around the Parent/Child architecture. Enforced (in a restricted Linux container) and verified by probes: network isolation (`--network none`, only `lo`, outbound connect blocked), read-only rootfs (`--read-only` + writable `/tmp` tmpfs), Docker socket absent, host secrets unreadable (/etc/shadow), memory limit (cgroup, allocation killed rc=-9), CPU quota (`--cpus` throttling), PID limit (`--pids-limit 96`, 105/200 spawns failed), capabilities dropped, no-new-privileges, non-root child. `pypdf==6.21.3` locked. Standalone experimental image `backend/tests/sandbox/Dockerfile.sandbox` (deployment Dockerfile/Compose untouched). Results: 52 passed in the sandbox container; host regression 39 passed / 13 enforcement tests skipped. See `GATE_B_S2_LINUX_SANDBOX_PROTOTYPE.md`. NOT_ENFORCED: OS-level fs sandbox (seccomp/LSM), separate per-child cgroup, production numeric limits.

---

## 9. Statuses

```text
GATE_A: OPEN
GATE_B: OPEN / OWNER_DECISION_REQUIRED
GATE_B_S0: IMPLEMENTED
GATE_B_SYNTHETIC_VALIDATION: PASSED
GATE_B_S1: IMPLEMENTED
GATE_B_S1_SYNTHETIC_VALIDATION: PASSED
GATE_B_S2: IMPLEMENTED
GATE_B_S2_LINUX_SANDBOX_VALIDATION: PASSED
GATE_C: OWNER_APPROVAL_REQUIRED

AUTHORIZATION_13529: PENDING_EVIDENCE_AND_SCOPE_REVIEW
PILOT_MANIFESTS: needs_review

B1: OWNER_APPROVED_WITH_CONDITIONS
B2: OWNER_APPROVED_MANUAL_ONE_SHOT
B3: OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION

PHASE_4: PLANNED / GATED
PHASE_5: NOT_STARTED

PRODUCTION: NOT_APPROVED
```

Gate B is not passed by this document.

## Sources inspected

- `backend/app/api/v1/documents.py` (placeholder), `backend/app/services/storage.py` (placeholder), `backend/app/services/ingestion/pdf_validation.py` + `parent_child_contract.py` (Gate B-S0), `backend/app/core/config.py`, `backend/app/core/ratelimit.py`, `backend/app/api/deps.py`, `backend/app/api/v1/admin/__init__.py`, `backend/app/models/admin_audit_log.py`, `backend/app/services/worker.py`
- `infra/nginx/nginx.conf`, `docker-compose.yml`
- `docs/ingestion/OWNER_DECISIONS.md`, `docs/ingestion/GATE_A_RENDERER_DECISION.md`, `docs/ingestion/PDFIUM_LICENSE_INVENTORY.md`, `docs/ingestion/PDFIUM_LINUX_PREFLIGHT.md`
- `docs/adr/ADR-024-resource-licensing.md`, ADR-037, ADR-038, ADR-042, ADR-045
- `AGENTS.md` (R-097, R-113, R-117, R-118, R-119, R-199), `docs/licenses/13529.md`, `resources/math/grade2/manifest.yaml`, `resources/physics/grade12/manifest.yaml`
