# Production readiness — remaining gates

This repository is **not production-approved**. The following artifacts reduce
operational risk but do not replace owner/legal/security sign-off.

## Operational scripts added

- `make backup-db` → `scripts/backup_db.sh` (custom-format `pg_dump` through Compose).
- `CONFIRM_RESTORE=yes make restore-db FILE=ops/backups/<dump>` → destructive restore, explicit confirmation required.
- `make load-test ARGS="--base-url https://host --requests 100 --concurrency 10"` → health-endpoint probe. This is **not** a chat/DB/SSE capacity certificate.
- `infra/nginx/nginx.prod.conf` → TLS/HSTS template. Replace domain and cert paths, verify renewal, then raise HSTS `max-age`; review CSP for the real frontend.

## Still required before release

| Gate | Evidence needed | Status |
|---|---|---|
| Real TLS/HSTS | certificate, renewal drill, domain-specific CSP | TEMPLATE ONLY |
| Load/capacity | chat + SSE + DB test against production-like data | NOT RUN |
| Backup restore | restore drill with checksum and recorded RPO/RTO | NOT RUN |
| Container resource limits | memory/CPU/pids in Compose/Kubernetes | CONFIGURATION_REQUIRED |
| Vulnerability enforcement | Trivy currently `exit-code: 0` (report-only) | REPORT ONLY |
| Privacy/legal | policy, consent, refund, retention approvals | PENDING |
| Full-book ingestion | owner uploads + reviewed golden set + snapshot | PENDING |
| Admin MFA/step-up | design and acceptance tests | NOT IMPLEMENTED |
