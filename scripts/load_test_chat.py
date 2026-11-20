"""Small, deterministic HTTP smoke/load probe; not a capacity certification.

Usage:
    python scripts/load_test_chat.py --base-url http://127.0.0.1:8080 --requests 100
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def probe(base_url: str, requests: int, concurrency: int, token: str | None) -> dict[str, object]:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    failures = 0

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        async def one(index: int) -> None:
            nonlocal failures
            async with semaphore:
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                started = time.perf_counter()
                try:
                    response = await client.get("/api/v1/health/live", headers=headers)
                    if response.status_code != 200:
                        failures += 1
                except httpx.HTTPError:
                    failures += 1
                finally:
                    latencies.append(time.perf_counter() - started)

        await asyncio.gather(*(one(index) for index in range(requests)))

    ordered = sorted(latencies)
    def percentile(value: float) -> float:
        if not ordered:
            return 0.0
        return ordered[min(len(ordered) - 1, int(len(ordered) * value))]

    return {
        "requests": requests,
        "concurrency": concurrency,
        "failures": failures,
        "p50_ms": round(percentile(0.50) * 1000, 2),
        "p95_ms": round(percentile(0.95) * 1000, 2),
        "mean_ms": round(statistics.fmean(latencies) * 1000, 2) if latencies else 0.0,
        "note": "health endpoint probe only; chat/DB/SSE capacity is NOT certified by this result",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--token", default=None, help="optional bearer token (do not log it)")
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests and concurrency must be positive")
    report = asyncio.run(probe(args.base_url, args.requests, args.concurrency, args.token))
    import json
    print(json.dumps(report, indent=2))
    return 0 if report["failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
