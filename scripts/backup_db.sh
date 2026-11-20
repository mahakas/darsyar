#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then echo "missing .env" >&2; exit 2; fi
set -a; . ./.env; set +a
mkdir -p ops/backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="ops/backups/darsyar-${stamp}.dump"
docker compose exec -T postgres pg_dump -Fc -U "${POSTGRES_USER:?set POSTGRES_USER}" -d "${POSTGRES_DB:?set POSTGRES_DB}" > "$out"
echo "backup written: $out"
