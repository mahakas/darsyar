"""Phase 4: bounded two-level chunking (R-158/R-159).

Children are retrieval units and may overlap on sentence boundaries. Parents are
bounded context windows built from contiguous child ranges. Page metadata is
preserved on children; a parent spanning multiple pages has no single page number.
The module defaults are test/development defaults; production values must be
injected from validated settings after the golden dataset is available.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

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
    parts = re.split(r"\n\s*\n", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _split_sentences(paragraph: str, max_len: int, overlap: int) -> list[str]:
    """Pack sentences into bounded chunks, carrying a sentence-boundary overlap.

    A single sentence longer than max_len uses a bounded character-window fallback;
    all other overlap is kept on complete trailing sentences where possible.
    """
    sentences = [part.strip() for part in re.split(r"(?<=[.!؟?])\s+", paragraph.strip()) if part.strip()]
    out: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            out.append(" ".join(current))
            current.clear()

    for sentence in sentences:
        if len(sentence) > max_len:
            flush()
            stride = max_len - overlap
            start = 0
            while start < len(sentence):
                out.append(sentence[start : start + max_len])
                if start + max_len >= len(sentence):
                    break
                start += stride
            continue

        candidate = " ".join([*current, sentence])
        if len(candidate) <= max_len:
            current.append(sentence)
            continue

        flush()
        if overlap:
            carry: list[str] = []
            carry_len = 0
            # Keep the largest suffix made of complete sentences that fits overlap.
            for previous in reversed(sentences[: sentences.index(sentence)]):
                separator = 1 if carry else 0
                proposed = carry_len + separator + len(previous)
                if proposed > overlap:
                    break
                carry.append(previous)
                carry_len = proposed
            current.extend(reversed(carry))

        candidate = " ".join([*current, sentence])
        if len(candidate) <= max_len:
            current.append(sentence)
        else:
            current[:] = [sentence]

    flush()
    return out


def chunk_two_level(
    segments: Iterable[tuple[str, int | None]],
    *,
    child_chunk_size: int = CHILD_CHUNK_SIZE,
    child_chunk_overlap: int = CHILD_CHUNK_OVERLAP,
    parent_chunk_size: int = PARENT_CHUNK_SIZE,
) -> ChunkingResult:
    """Chunk page-scoped extracted text into bounded children and contiguous parents."""
    if child_chunk_size <= 0:
        raise ValueError("child_chunk_size must be positive")
    if child_chunk_overlap < 0 or child_chunk_overlap >= child_chunk_size:
        raise ValueError("child_chunk_overlap must be in [0, child_chunk_size)")
    if parent_chunk_size < child_chunk_size:
        raise ValueError("parent_chunk_size must be >= child_chunk_size")

    children: list[ChildChunk] = []
    for segment_text, page_number in segments:
        if not isinstance(segment_text, str):
            raise TypeError("segment text must be a string")
        if page_number is not None and page_number < 1:
            raise ValueError("page_number must be positive or None")
        for paragraph in _split_paragraphs(segment_text):
            for chunk_text in _split_sentences(paragraph, child_chunk_size, child_chunk_overlap):
                children.append(
                    ChildChunk(text=chunk_text, page_number=page_number, order_index=len(children))
                )

    parents: list[ParentChunk] = []
    child_cursor = 0
    while child_cursor < len(children):
        child_start = child_cursor
        parent_parts: list[str] = []
        page_numbers: set[int | None] = set()
        parent_chars = 0

        while child_cursor < len(children):
            child = children[child_cursor]
            extra = len(child.text) + (2 if parent_parts else 0)
            if parent_parts and parent_chars + extra > parent_chunk_size:
                break
            parent_parts.append(child.text)
            parent_chars += extra
            page_numbers.add(child.page_number)
            child_cursor += 1

        parents.append(
            ParentChunk(
                text="\n\n".join(parent_parts),
                page_number=next(iter(page_numbers)) if len(page_numbers) == 1 else None,
                child_start=child_start,
                child_end=child_cursor - 1,
            )
        )

    return ChunkingResult(children=children, parents=parents)
