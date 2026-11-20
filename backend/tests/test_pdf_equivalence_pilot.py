"""Gate C pilot evidence; skipped when the gitignored owner sample is unavailable."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PDF = Path(__file__).resolve().parents[2] / "resources" / "physics" / "grade12" / "samples" / "physics12.pdf"

pytestmark = pytest.mark.skipif(not PDF.exists(), reason="owner-supplied pilot PDF is gitignored")


def test_pilot_pdf_renders_all_pages_with_both_backends() -> None:
    pytest.importorskip("pypdfium2")
    from scripts.pdf_equivalence_pilot import run

    report = run(PDF, scale=0.25)

    assert report["page_count"] == 6
    assert report["all_pages_rendered_nonblank"] is True
    assert len(report["pages"]) == 6
    # Text order differs between RTL extractors; the measured overlap is reported,
    # not treated as an invented equivalence score.
    assert all(0.0 <= page["text_token_jaccard"] <= 1.0 for page in report["pages"])
