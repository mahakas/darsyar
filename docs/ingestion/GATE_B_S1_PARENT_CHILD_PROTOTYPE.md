# Gate B-S1 — Isolated Parent/Child Prototype (Implementation)

**Date:** 2026-11-11. Owner decision `GATE_B-S1 = APPROVE_WITH_CONDITIONS`.
Isolated engineering prototype only — not a production pipeline, not Gate B
closure.

## Scope implemented

- **Parent Supervisor** (`backend/app/services/ingestion/parent_supervisor.py`) — spawns
  the child as a separate OS process, sends a minimal versioned request, enforces a
  test-supplied timeout, validates the structured result, and terminates/escalates.
- **Spawned PDF Child** (`backend/app/services/ingestion/pdf_child.py`) — runs as
  `python -m app.services.ingestion.pdf_child`; applies a scoped pypdf Configuration,
  parses synthetic PDF bytes, optionally decodes a selected FlateDecode content
  stream, and returns a structured JSON result.
- **Versioned IPC contract** (`parent_child_contract.py`) — `PARENT_CHILD_CONTRACT_VERSION = 1`;
  `ParentChildRequest`/`ParentChildResult` now have JSON serde helpers.
- Synthetic tests: `backend/tests/test_gate_b_parent_child.py`.

## pypdf version

- **pypdf 6.21.3** (exact lockfile version), verified in the isolated test environment
  (`pypdf.__version__ == "6.21.3"`). No dependency upgraded; `uv.lock` untouched.

## Architecture / IPC

```
Parent Supervisor
   |  ParentChildRequest (JSON on stdin): contract_version, attempt_id,
   |    document_bytes (base64), limits (explicit test-supplied), mode
   v
Spawned Isolated Child (python -m ...pdf_child)
   |  scoped Configuration(zlib_maximum_output_length=...)
   |  parse synthetic PDF; optional explicit content-stream decode
   v
ParentChildResult (JSON on stdout): outcome, error_category, page_count,
   |  decoded_stream_length, pypdf_version, memory_bytes, artifact_metadata
   v
Parent validates schema, contract version, exit code; returns typed result
```

- The Parent is the only component that may own database/application-infrastructure
  access. This prototype connects to neither PostgreSQL nor Redis.
- The Child receives only synthetic bytes + explicit limits; no credentials, secrets,
  session objects, or clients.

## Parent Supervisor behavior (verified)

- Spawn via `subprocess.Popen([sys.executable, "-m", CHILD_MODULE], ...)` — no shell.
- Allowlisted child environment (`_allowlisted_env`): PATH, PYTHONPATH, SYSTEMROOT,
  SystemRoot, WINDIR, COMSPEC, PATHEXT, TEMP, TMP, LANG, LC_ALL. Parent env is not
  inherited wholesale.
- Explicit working directory (backend cwd).
- Controlled stdio (piped); request written to stdin, result read from stdout.
- Timeout handling: `communicate(timeout=...)`; on expiry → terminate() → wait(5s) →
  if still alive kill() → wait(5s). Confirms exit.
- Validates result schema + contract version; maps abnormal exit / timeout / unparsable
  output to typed `ChildRunResult`.
- Parent remains usable after child crash or timeout (verified by follow-up requests).

## Child behavior (verified)

- Applies `apply_configuration(Configuration(zlib_maximum_output_length=...))` — scoped,
  restored after context exit.
- Parses synthetic PDF; counts pages (no text extraction, no rendering).
- In `decode_stream` mode, explicitly accesses the page `/Contents` FlateDecode stream
  and calls `get_data()` — this exercises the configured zlib limit.
- Catches `LimitReachedError` (→ `RESOURCE_LIMIT`), `PyPdfError` (→ `MALFORMED`/
  `TRUNCATED`), other (→ `INTERNAL`). Never crashes the parent.
- Records `pypdf_version` and best-effort `memory_bytes`.

## Memory / CPU

- **Memory:** `_memory_bytes()` uses POSIX `resource.getrusage().ru_maxrss` (KB→bytes).
  On the Windows host (no `resource` module) it returns `None` → memory is
  **NOT_ENFORCED / unmeasured** here; a POSIX path exists. `tracemalloc` is not used
  as an RSS proxy.
- **CPU:** no OS CPU quota is configured in this prototype → **NOT_ENFORCED** on this
  host. Explicit test-only CPU/s`resource`/cgroup enforcement is deferred to a platform
  mechanism and owner review.

## Filesystem / network isolation (status)

- Dedicated temporary working directory is used for the test cwd; no persistent
  staging; no path to app DB/storage is passed.
- The Child code opens no network connections and receives no DB/Redis credentials.
- **Explicit boundary:** a sanitized environment + separate process does **not**
  provide OS-level filesystem/network isolation. If the same OS user can reach app
  files or the network, that boundary is NOT enforced here. No container/OS sandbox is
  claimed; no Docker/Compose change was made.

## Synthetic tests (17) — results (pypdf 6.21.3)

```
tests/test_gate_b_parent_child.py -> 17 passed, 0 failed
```

Coverage: valid request + exact 6.21.3; scoped config applied; decode exercises the
configured limit; oversized synthetic stream rejected safely (`RESOURCE_LIMIT`); parent
validates structured output; sentinel secret env does not reach child; no DB/Redis
credential/client fields in IPC; malformed PDF → safe error; parser exception → typed
result; child timeout detected; graceful termination attempted; forced termination
escalation; no orphan process remains; parent functional after child failure; memory
recorded where available; CPU enforcement reported; temp working data cleaned; no pilot
PDF; no text extraction/rendering.

## Joint suite

```
pytest tests/test_gate_b_pdf_validation.py tests/test_gate_b_parent_child.py -q
-> 39 passed, 0 failed
```

`ruff check app tests` → all passed; `mypy app` → no issues.

## Security classification

| Aspect | Status |
|---|---|
| Implemented process separation | Yes (OS subprocess) |
| Verified secret/environment isolation | Yes (allowlist; sentinel test) |
| Verified timeout + process termination | Yes |
| Measured vs enforced memory | Measured on POSIX; **NOT_ENFORCED** on this host |
| Measured vs enforced CPU | **NOT_ENFORCED** on this host |
| Filesystem isolation | Not OS-enforced (same user caveat) |
| Network isolation | Not OS-enforced (child code opens none) |
| Missing OS-level sandbox controls | Filesystem/network/CPU cgroup isolation absent |
| Missing production numerical limits | All Gate B numeric decisions remain open |

Gate B is NOT passed because the prototype succeeds.

## Statuses

```text
GATE_B_S0: IMPLEMENTED
GATE_B_S1: IMPLEMENTED
GATE_B_S1_SYNTHETIC_VALIDATION: PASSED

GATE_B: OPEN / OWNER_DECISION_REQUIRED
UPLOAD_API: NOT_ACTIVATED
REAL_PDF_PROCESSING: NOT_AUTHORIZED
PILOT_MANIFESTS: needs_review

GATE_A: OPEN
GATE_C: OWNER_APPROVAL_REQUIRED

PHASE_4: PLANNED / GATED
PHASE_5: NOT_STARTED
PRODUCTION: NOT_APPROVED
```
