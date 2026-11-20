"""Convert reviewed draft cases into the evaluator's accepted golden set.

This tool never marks a case approved automatically: the reviewer must pass
`--approve` and supply an identity recorded in the output file.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, default=Path("backend/tests/evaluation/golden_set.draft.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("backend/tests/evaluation/golden_set.jsonl"))
    parser.add_argument("--reviewer", required=True, help="name of the person approving the cases")
    parser.add_argument("--approve", action="store_true", help="required explicit approval flag")
    parser.add_argument("--max-cases", type=int, default=0, help="optional review batch limit")
    args = parser.parse_args()
    if not args.approve:
        parser.error("explicit --approve is required")
    if not args.reviewer.strip():
        parser.error("reviewer must not be empty")

    rows = [json.loads(line) for line in args.draft.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.max_cases > 0:
        rows = rows[: args.max_cases]
    for row in rows:
        row["review_status"] = "approved"
        row["approved_by"] = args.reviewer
        row["approved_at"] = datetime.now(UTC).isoformat()
    args.output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    print(f"approved {len(rows)} cases for reviewer {args.reviewer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
