"""Docs must not advertise routes the application no longer registers."""

import re
from pathlib import Path

from app.main import app


def test_api_contract_paths_are_registered() -> None:
    doc = (Path(__file__).resolve().parents[2] / "docs" / "API_CONTRACT.md").read_text(
        encoding="utf-8"
    )
    documented = set(re.findall(r"`/(api/v1/[^`]+)`", doc))
    registered = set(app.openapi()["paths"])
    missing = sorted(p for p in documented if ("/" + p.split("?")[0]) not in registered)
    assert not missing, f"documented but unregistered: {missing}"
