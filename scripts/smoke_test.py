"""Smoke test سبک؛ سرویس باید از قبل اجرا شده باشد."""

import asyncio
import os
import sys

import httpx


async def main() -> int:
    """سه endpoint عملیاتی را به‌شکل async بررسی می‌کند."""
    base = os.environ.get("DARSYAR_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    async with httpx.AsyncClient(base_url=base, timeout=5.0) as client:
        for path in ("/health", "/ready", "/version"):
            try:
                response = await client.get(path)
                if response.status_code != 200:
                    print(f"FAIL {path}: HTTP {response.status_code}")
                    return 1
                print(f"PASS {path}: HTTP {response.status_code}")
            except httpx.HTTPError as exc:
                print(f"FAIL {path}: {type(exc).__name__}")
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
