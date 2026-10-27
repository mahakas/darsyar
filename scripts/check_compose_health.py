"""Parse docker compose JSON output and fail if a running service is not healthy."""
import json
import sys

REQUIRED = {"postgres", "redis", "migrate", "inference", "api", "worker", "frontend"}
raw = sys.stdin.read().strip()
if not raw:
    print("No docker compose status rows were received.", file=sys.stderr)
    raise SystemExit(2)
try:
    parsed = json.loads(raw)
    rows = parsed if isinstance(parsed, list) else [parsed]
except json.JSONDecodeError:
    rows = []
    for line in raw.splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"Invalid docker compose JSON row: {line}", file=sys.stderr)
            raise SystemExit(2)
by_service = {str(row.get("Service", row.get("Name", ""))): row for row in rows if isinstance(row, dict)}
failed = []
for service in sorted(REQUIRED):
    row = by_service.get(service)
    if row is None:
        failed.append(f"{service}: missing")
        continue
    state = str(row.get("State", "")).lower()
    health = str(row.get("Health", "")).lower()
    # One-shot migrate exits successfully and is not expected to remain running.
    if service == "migrate":
        if state != "exited" or str(row.get("ExitCode", "0")) != "0":
            failed.append(f"{service}: state={state} exit={row.get('ExitCode')}")
    elif state != "running" or health != "healthy":
        failed.append(f"{service}: state={state} health={health or 'not reported'}")
if failed:
    print("UNHEALTHY: " + "; ".join(failed), file=sys.stderr)
    raise SystemExit(1)
print("All required services have expected status.")
