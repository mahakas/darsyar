# Owner Decision Package — Ingestion Implementation Gates

Date: 2026-11-10. Read-only assessment. This document **prepares decisions**; it does not approve any dependency, security threshold, authorization scope, or implementation.

## 1. Executive summary

Three gates block ingestion implementation:

- **Gate A** — PDF rendering backend selection.
- **Gate B** — owner-approved numeric PDF processing/security limits.
- **Gate C** — authorization to execute a controlled PDF-backend equivalence test.

Each is presented with evidence and states. No owner decision is made on the owner's behalf.

## 2. Gate A — PDF renderer options

Current stack evidence:
- `pypdf>=6.0,<7.0` (locked 6.21.3) is in the `rag` extra; it provides parsing/text/geometry/image-resource/encryption/metadata, **not** page rendering.
- `Pillow>=12.0,<13.0` also in `rag` (image handling, not PDF rendering by itself).
- Temporary pilot profiling used PyMuPDF; PyMuPDF is **not** an approved production dependency.
- Dockerfile image is `python:3.13-slim`; no OS-level rendering lib is currently declared.

| Candidate | Status | Notes |
|---|---|---|
| `pypdf` (existing) | `ALREADY_APPROVED` (parse only) | cannot render pages |
| PyMuPDF (`pymupdf`) | `AVAILABLE_BUT_NOT_APPROVED` | used for preflight; needs approval, packaging, licensing review |
| OS renderer (e.g., poppler/mutool) | `REQUIRES_EXTERNAL_REVIEW` | separate binary; Docker+licensing impact; no repo evidence |
| Other (UNKNOWN) | `UNKNOWN` | no repository evidence to compare |
| Keep no renderer (block render-dependent stages) | `NOT_SUPPORTED_BY_CURRENT_STACK` | acceptable until a decision |

Decision matrix (recommended evaluation order, not a decision):
1. Confirm requirement: are original-page renders required for all pages, or only for `image_only`/`mixed`/formula/graph pages?
2. Evaluate `pymupdf` vs OS renderer against packaging (Docker slim), licensing, security isolation, and "render without modifying the original PDF".
3. Decide; record the choice and its operational/licensing implications.

Licensing: must be reviewed by owner/legal before approval; no license claim is made here.

## 3. Gate B — security/numeric limit inventory

Existing evidence (non-secret):

| Parameter | Existing value | Source | Confidence | Recommendation status |
|---|---|---|---|---|
| API request body limit | 20 MiB (`max_request_bytes=20971520`) | `backend/app/core/config.py` | High | Existing; aligns with nginx |
| Nginx client_max_body_size | 20m | `infra/nginx/nginx.conf` | High | Existing |
| Nginx proxy timeouts | read/send 360s | `infra/nginx/nginx.conf` | High | Existing |
| arq worker concurrency | `max_jobs = 4` | `backend/app/services/worker.py` | High | Existing |
| arq job timeout | `job_timeout = 300` (s) | `backend/app/services/worker.py` | High | Existing |
| Compose stop_grace | api=90s, worker=30s | `docker-compose.yml` | High | Existing |
| Container memory/CPU/pids | not documented | `docker-compose.yml` | — | `CONFIGURATION_REQUIRED` |
| Upload dir | `./uploads` | config.py `upload_dir` | High | convention; temp-quota N/A |

Ingestion-specific parameters (none exist yet; all require owner decision unless a source sets them):

| Parameter | Status |
|---|---|
| `MAX_INGEST_PDF_BYTES` | `OWNER_DECISION_REQUIRED` |
| `MAX_INGEST_PDF_PAGES` | `OWNER_DECISION_REQUIRED` |
| `INGEST_PAGE_PROCESS_TIMEOUT_SECONDS` | `OWNER_DECISION_REQUIRED` |
| `INGEST_DOCUMENT_TIMEOUT_SECONDS` | `OWNER_DECISION_REQUIRED` |
| `INGEST_WORKER_MEMORY_LIMIT_MB` | `CONFIGURATION_REQUIRED` (no container limit defined) |
| `INGEST_TEMP_STORAGE_QUOTA_BYTES` | `OWNER_DECISION_REQUIRED` |
| `INGEST_MAX_CONCURRENT_DOCUMENTS` | `OWNER_DECISION_REQUIRED` (worker max_jobs=4 is a ceiling, not an ingestion-specific limit) |

Observations:
- Suggested ranges are **suggestions only**, not approved: document byte limit should be ≤ current 20 MiB request body unless the upload path is separate; page count and timeouts should be sized to the pilot PDFs (188/176 pages) with headroom. No value is set here.
- Fail-closed: if any mandatory limit is unset, processing must be blocked (never unlimited).
- Conflicts to check when deciding: API body vs Nginx body; worker job_timeout vs document timeout vs proxy read timeout; container memory vs worker concurrency.

## 4. Gate C — PDF-backend equivalence test plan

Authorization state: **`OWNER_APPROVAL_REQUIRED`** (not executed).

Preconditions:
- A production PDF adapter is selected (Gate A) and its backend/version recorded.
- Owner authorizes running the test against the two pilot PDFs.

Exact inputs:
- `resources/math/grade2/C2051.pdf` (188 pages; 158 >80-char pages; 181 Method-B pages; 2,496 Method-B refs).
- `resources/physics/grade12/C112209.pdf` (176 pages; 176 >80-char pages; 103 Method-B pages; 415 Method-B refs).

Metrics (kept distinct):
- Method A: displayed image occurrences.
- Method B: referenced image resources (historical reference).
- Method C: structured-text image blocks.
- Method D: image placement rectangles.

Comparison rules:
- Compare page count, native text counts, image-resource counts, occurrence counts, page-level inventory, vector support.
- If a capability is unsupported or not comparable on the selected backend, record `UNSUPPORTED`/`NOT_COMPARABLE`; do not fabricate equivalence.
- Only demonstrated-equivalent metrics may be treated as equivalent.

Outputs:
- Temporary outputs only (outside repository): comparison CSV/JSON per metric; no repository writes.
- No modifications to original PDFs; no repository dependency changes; no OCR/ingestion/embedding/chunking/indexing.

Failure criteria:
- Any metric that cannot be reproduced is reported as unresolved, not silently accepted.

Constraints:
- Test must not run in this task; it waits for owner approval and Gate A selection.

## 5. Unknowns / unsupported assumptions

- Renderer licensing and operational details: `UNKNOWN` pending owner/legal review.
- Container memory/CPU limits: not documented → `CONFIGURATION_REQUIRED`.
- PyMuPDF production equivalence: unproven until Gate C runs.
- No numeric ingestion limit is pre-approved.

## 6. Recommended decision order

1. **Gate A**: decide renderer (or explicitly defer render-dependent stages).
2. **Gate B**: approve numeric security limits (informed by Gate A and existing 20 MiB/360s boundaries).
3. **Gate C**: authorize and run the equivalence test against the chosen backend.

## 7. Consequences of approving/deferring

- Defer Gate A: render-dependent stages remain blocked; native-text-only pipeline can still be specified/developed for text-dominant pages.
- Approve a renderer without licensing review: legal/operational risk.
- Approve limits too low: pilot PDFs or legitimate resources fail; too high: DoS/abuse risk.
- Defer Gate C: PDF-metric equivalence remains unverified; retrieval/index quality assumptions rest on unverified backend parity.

## 8. Explicit owner decision fields (to be filled by owner)

- [ ] Gate A: selected renderer (or explicit defer).
- [ ] Gate B: approved values for the seven ingestion parameters.
- [ ] Gate C: authorization to run the equivalence test.

## 9. Owner-confirmed decision — Hybrid textbook intake

```yaml
decision_id: hybrid_textbook_intake
decision_status: owner_confirmed
recorded_on: "2026-11-10"
supported_intake_methods:
  - controlled_server_storage_registration
  - authenticated_admin_panel_upload
architecture_rule: unified_intake_pipeline
```

Meaning: both intake methods are required product capabilities and converge on **one shared intake, validation, authorization and ingestion pipeline**. This decision does **not** approve any rendering library, dependency, numeric security limit, authorization scope, the equivalence test, or production ingestion. Gates A, B and C remain unresolved unless independently approved.

## 10. Temporary PDFium Feasibility Evidence — 2026-11-10

Preliminary, isolated Windows experiment for `pypdfium2`. This is **evidence only**, not production approval.

### Environment
- Windows 10; CPython 3.13.14; x86_64.
- Isolated temporary environment: `%TEMP%\darsyar-pdfium-preflight\`.
- `pypdfium2==5.15.2`; bundled PDFium version `159.0.8149`.
- Native Windows binary loads successfully. No project dependency modified.

### Synthetic test
- Three-page synthetic PDF (stdlib-generated): portrait, landscape, and 90°-rotated page; dimensions and rotation detected.
- SHA-256: `3b467358e751db62c691dc34ba4606ee5e035fb0c5a0ba3d662e5a9d8e8c3017`.

### Rendering
- Rendering at 72 and 150 DPI succeeded for portrait, landscape, and rotated pages.
- Bitmap output available as raw BGR bytes.
- PNG export **NOT RUN** (Pillow intentionally not installed).
- 30 sequential open/render/close cycles completed without reported exception.
- Python tracemalloc peak: 2.91 MB (does **not** prove absence of native PDFium memory leaks).

### Linux packaging
- Linux manylinux x86_64 wheel downloaded to temp only: `pypdfium2-5.15.2-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`.
- **NOT RUN** inside the Darsyar Linux/Docker runtime; download availability ≠ runtime compatibility.

### Licensing / thread safety
- Package and bundled third-party notices inventoried; legal/distribution review **pending**; no production license clearance claimed.
- Concurrent rendering **NOT RUN**; treat PDFium resources as unsafe for concurrent same-process access until a supported concurrency model is independently established.

### Gate A status
```text
Windows basic rendering feasibility: PASS
Linux production runtime compatibility: NOT VERIFIED
PNG serialization compatibility: NOT VERIFIED
Persian/textbook visual fidelity: NOT VERIFIED
Production dependency approval: NOT APPROVED
Licensing review: PENDING
Gate A: OPEN
```

Classification: **`PREFERRED_CANDIDATE_FOR_FURTHER_EVALUATION`** (not an approved production dependency).

Preserved: `pypdf` remains the approved existing parsing dependency; `pypdfium2` is an additional candidate; PyMuPDF is not automatically selected; no dependency/lockfile/Gate B/Gate C/implementation approval.
