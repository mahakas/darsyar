# Development Environment — Historical Snapshot

This document records a development-environment check performed on 2026-11-06. It is a historical diagnostic, not a guarantee that the same machine, Docker daemon, RAM availability or dependency cache is available today.

## Environment baseline reported at the time

| Component | Required baseline | Reported value | Notes |
|---|---|---|---|
| Windows | 10/11 64-bit | Windows 10 Pro, build 19045 | WSL2 used |
| WSL2 | Version 2 | Ubuntu, WSL2 | PASS at the time |
| Docker Desktop | Compose v2 | 29.9.2 | Daemon restarted once |
| Git | Compatible | 2.55.0.windows.5 | PASS |
| Python | 3.13 | 3.13.14 | Use the `python` launcher where `python3` is unavailable |
| uv | Lock-compatible | 0.11.23 | PASS |
| Node.js | 24 LTS | 24.21.0 | PASS |
| npm | Lock-compatible | 11.19.0 | PASS |
| PostgreSQL | 18 + pgvector + pg_trgm | 18.6 container | vector 0.8.7, pg_trgm 1.6 |
| Redis | 7.4.12 | 7.4.12-bookworm | PASS |

The reported machine had approximately 8 GB RAM. Loading the local inference stack exceeded the available memory; the inference container exited with an OOM-related failure. A remote inference configuration or additional memory may be necessary on similarly constrained machines.

## Historical validation recorded

| Check | Historical result |
|---|---|
| `uv lock --check` | PASS at that time |
| Backend Ruff | PASS |
| Backend mypy | PASS (94 source files at that time) |
| Backend unit tests | 64 passed, 138 skipped |
| Frontend npm lock check | PASS |
| Frontend typecheck/lint/build | PASS |
| PostgreSQL integration suite | NOT RUN in that local diagnostic due to a timeout |
| Local API health/readiness/version | HTTP 200 at that time |
| Local inference service | FAIL due to memory pressure |

These results are historical and are superseded for current CI status by the linked GitHub Actions runs.

## Current commands

From the repository root:

```bash
make up
make health
make ps
make logs
make lint
make typecheck
make test
make test-db
```

On Windows PowerShell, GNU Make may not be installed by default. Use WSL2/GNU Make or run the equivalent `docker compose`, `uv` and `npm` commands directly.

## Public-repository privacy note

Machine-specific absolute paths, local usernames, temporary output filenames and local secrets are intentionally not included here. Do not commit `.env`, credentials, private PDFs, user data or raw operational logs.
