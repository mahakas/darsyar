"""Phase 4: two-level chunking (R-158/R-159).

Parent/child: small children for retrieval; parents for model context. Splits on
paragraph/sentence boundaries with a size-based fallback, preserving page numbers.
Input is a sequence of (text, page_number) segments (e.g., one per page).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

# Test-only defaults (owner-approved values come from settings at the pipeline layer).
CHILD_CHUNK_SIZE = 400
CHILD_CHUNK_OVERLAP = 60
PARENT_CHUNK_SIZE = 2000


@dataclass(frozen=True)
class ChildChunk:
    text: str
    page_number: int | None
    order_index: int


@dataclass(frozen=True)
class ParentChunk:
    text: str
    page_number: int | None
    child_start: int
    child_end: int


@dataclass(frozen=True)
class ChunkingResult:
    children: list[ChildChunk] = field(default_factory=list)
    parents: list[ParentChunk] = field(default_factory=list)


def _split_paragraphs(text: str) -> list[str]:
    import re

    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_sentences(paragraph: str, max_len: int) -> list[str]:
    import re

    sentences = re.split(r"(?<=[.!؟?])\s+", paragraph.strip())
    out: list[str] = []
    buf = ""
    for s in sentences:
        if len(buf) + len(s) + 1 <= max_len:
            buf = (buf + " " + s).strip() if buf else s
        else:
            if buf:
                out.append(buf)
            # fallback: hard-split long sentences
            while len(s) > max_len:
                out.append(s[:max_len])
                s = s[max_len:]
            buf = s
    if buf:
        out.append(buf)
    return out


def chunk_two_level(segments: Iterable[tuple[str, int | None]]) -> ChunkingResult:
    """Chunk per-page segments into child + parent chunks."""
    children: list[ChildChunk] = []
    parents: list[ParentChunk] = []
    order = 0
    parent_buf = ""
    parent_page: int | None = None
    parent_start = 0

    for text, page in segments:
        for paragraph in _split_paragraphs(text):
            for sentence in _split_sentences(paragraph, CHILD_CHUNK_SIZE):
                children.append(ChildChunk(text=sentence, page_number=page, order_index=order))
                order += 1

        # parent accumulation (page-scoped)
        if parent_buf and len(parent_buf) + len(text) > PARENT_CHUNK_SIZE:
            parents.append(ParentChunk(text=parent_buf.strip(), page_number=parent_page,
                                       child_start=parent_start, child_end=len(children) - 1))
            parent_buf = ""
            parent_start = len(children)
        parent_buf = (parent_buf + "\n\n" + text).strip()
        parent_page = page

    if parent_buf:
        parents.append(ParentChunk(text=parent_buf.strip(), page_number=parent_page,
                                   child_start=parent_start, child_end=len(children) - 1))

    return ChunkingResult(children=children, parents=parents)
