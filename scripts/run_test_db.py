"""ایجاد دیتابیس تست و اجرای migration/test با TEST_DATABASE_URL واقعی از .env."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def parse_env_file(path: Path) -> dict[str, str]:
    """زیرمجموعهٔ سادهٔ KEY=value را بدون اجرای فایل تنظیمات می‌خواند."""
    values: dict[str, str] = {}
    if not path.exists():
        raise RuntimeError(".env not found; copy .env.example to .env first")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"").strip("'")
    return values


def run(args: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main() -> int:
    values = parse_env_file(ROOT / ".env")
    user = values.get("POSTGRES_USER", "darsyar")
    test_url = values.get("TEST_DATABASE_URL", "")
    if not test_url or "CHANGE_ME" in test_url:
        raise RuntimeError("Set a valid TEST_DATABASE_URL in the root .env")
    # Local URL is expected to use localhost:5432; Compose publishes DB only on loopback.
    sql = "SELECT 1 FROM pg_database WHERE datname = 'darsyar_test'"
    check = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-U", user, "-d", "postgres", "-tAc", sql], cwd=ROOT, text=True, capture_output=True)
    if check.returncode != 0:
        print(check.stderr, flush=True)
        return check.returncode
    if check.stdout.strip() != "1":
        run(["docker", "compose", "exec", "-T", "postgres", "createdb", "-U", user, "darsyar_test"])
    env = os.environ.copy()
    env["DATABASE_URL"] = test_url
    env["DARSYAR_TEST_DB"] = "1"
    run(["uv", "run", "--locked", "alembic", "upgrade", "head"], cwd=BACKEND, env=env)
    run(["uv", "run", "--locked", "--extra", "dev", "pytest", "-q"], cwd=BACKEND, env=env)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))
