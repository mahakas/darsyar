"""Gate C pilot: compare pypdf text extraction with pypdfium2 rendering.

Owner authorization: 2026-11-19, limited to the locally supplied, owner-owned
6-page sample. No score is invented: metrics are measured from the PDF bytes.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


def _tokens(text: str) -> Counter[str]:
    normalized = re.sub(r"[\s\u200c\u200d\u200e\u200f]+", " ", text)
    return Counter(token for token in normalized.split() if len(token) > 1)


def _jaccard(left: Counter[str], right: Counter[str]) -> float:
    union = set(left) | set(right)
    if not union:
        return 1.0
    intersection = sum(min(left[token], right[token]) for token in union)
    total = sum(max(left[token], right[token]) for token in union)
    return intersection / total if total else 1.0


def run(pdf_path: Path, scale: float = 0.5) -> dict[str, object]:
    import pypdfium2 as pdfium

    reader = PdfReader(pdf_path)
    document = pdfium.PdfDocument(str(pdf_path))
    if len(reader.pages) != len(document):
        raise ValueError("pdfium and pypdf disagree on page count")

    pages: list[dict[str, object]] = []
    for index, page in enumerate(document):
        pypdf_text = reader.pages[index].extract_text() or ""
        pdfium_text = page.get_textpage().get_text_range() or ""
        bitmap = page.render(scale=scale)
        pixels = bytes(bitmap.buffer)
        distinct = len(set(pixels[:: max(1, bitmap.stride // 64)]))
        pages.append(
            {
                "page": index + 1,
                "pypdf_chars": len(pypdf_text),
                "pdfium_chars": len(pdfium_text),
                "text_token_jaccard": round(
                    _jaccard(_tokens(pypdf_text), _tokens(pdfium_text)), 4
                ),
                "render_width": bitmap.width,
                "render_height": bitmap.height,
                "render_nonblank": bitmap.width > 0 and bitmap.height > 0 and distinct > 1,
            }
        )
        bitmap.close()
    document.close()

    return {
        "pdf": str(pdf_path),
        "page_count": len(pages),
        "all_pages_rendered_nonblank": all(bool(page["render_nonblank"]) for page in pages),
        "pages": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--scale", type=float, default=0.5)
    args = parser.parse_args()

    report = run(args.pdf, args.scale)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: report[key] for key in ("page_count", "all_pages_rendered_nonblank")}))
    return 0 if report["all_pages_rendered_nonblank"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
