"""Phase 5: retrieval-only evaluation over synthetic gold data (R-171/R-172).

This module measures retrieval properties, not generated-answer faithfulness. Answer
groundedness requires answer text and its evidence references plus human review; it is
reported as NOT MEASURED here rather than inferred from retrieval precision.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.services.ingestion.retrieval import RetrievalResult, RetrievedChunk


@dataclass(frozen=True)
class GoldItem:
    query: str
    grade: int
    ground_truth_chunk_keys: set[tuple[int, int]]  # (grade, chunk_index), synthetic keys for now


@dataclass(frozen=True)
class EvalResult:
    grade_leakage: float
    invalid_citation_rate: float
    recall_at_5: float
    retrieval_precision_at_5: float
    answer_groundedness: float | None = None
    sample_size: int = 0
    notes: list[str] = field(default_factory=list)


def _chunk_key(chunk: RetrievedChunk) -> tuple[int, int]:
    return (int(chunk.grade_level), int(chunk.chunk_index))


def _valid_citation_metadata(chunk: RetrievedChunk) -> bool:
    """Validate fields required to build a source citation from server metadata."""
    if not isinstance(chunk.title, str) or not chunk.title.strip():
        return False
    if not isinstance(chunk.subject, str) or not chunk.subject.strip():
        return False
    if not 1 <= int(chunk.grade_level) <= 12 or int(chunk.chunk_index) < 0:
        return False
    if chunk.page_number is not None and int(chunk.page_number) < 1:
        return False
    try:
        uuid.UUID(chunk.document_id)
        uuid.UUID(chunk.chunk_id)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def evaluate_retrieval(
    gold: list[GoldItem],
    results: list[RetrievalResult],
) -> EvalResult:
    if len(gold) != len(results):
        raise ValueError("gold/results length mismatch")

    leaked = 0
    retrieved_total = 0
    invalid_citations = 0
    citation_total = 0
    true_positives_at_5 = 0
    gold_total = 0
    retrieved_at_5_total = 0

    for item, res in zip(gold, results, strict=True):
        retrieved = list(res.chunks)
        retrieved_total += len(retrieved)
        leaked += sum(1 for chunk in retrieved if int(chunk.grade_level) > item.grade)

        top5 = retrieved[:5]
        retrieved_at_5_total += len(top5)
        gold_total += len(item.ground_truth_chunk_keys)
        true_positives_at_5 += sum(
            1 for chunk in top5 if _chunk_key(chunk) in item.ground_truth_chunk_keys
        )

        for chunk in top5:
            citation_total += 1
            if not _valid_citation_metadata(chunk):
                invalid_citations += 1

    return EvalResult(
        grade_leakage=leaked / max(retrieved_total, 1),
        invalid_citation_rate=invalid_citations / max(citation_total, 1),
        recall_at_5=true_positives_at_5 / max(gold_total, 1),
        retrieval_precision_at_5=true_positives_at_5 / max(retrieved_at_5_total, 1),
        answer_groundedness=None,
        sample_size=len(gold),
        notes=[
            "answer_groundedness_not_measured_by_retrieval_only_evaluation",
            "citation_validity_checks_server_metadata_not_generated_answer_text",
        ],
    )
