#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ${CONFIRM_RESTORE:-} != "yes" ]]; then
  echo "refusing to restore without CONFIRM_RESTORE=yes" >&2
  exit 2
fi
if [[ $# -ne 1 || ! -f "$1" ]]; then
  echo "usage: CONFIRM_RESTORE=yes scripts/restore_db.sh ops/backups/<dump>" >&2
  exit 2
fi
if [[ ! -f .env ]]; then echo "missing .env" >&2; exit 2; fi
set -a; . ./.env; set +a
docker compose exec -T postgres pg_restore --clean --if-exists -U "${POSTGRES_USER:?set POSTGRES_USER}" -d "${POSTGRES_DB:?set POSTGRES_DB}" < "$1"
echo "restore completed from: $1"
