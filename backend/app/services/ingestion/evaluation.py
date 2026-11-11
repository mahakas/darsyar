"""Phase 5: RAG evaluation harness over synthetic data (R-171/R-172).

Evaluates the retrieval pipeline against a small synthetic gold dataset:
- grade leakage must be 0
- invalid citation rate must be 0 on the reviewed sample
- recall@k and answer groundedness are computed from the synthetic ground truth
This is a synthetic-only evaluation; it is not a real-textbook benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.ingestion.retrieval import RetrievalResult, RetrievedChunk


@dataclass(frozen=True)
class GoldItem:
    query: str
    grade: int
    ground_truth_chunk_keys: set[tuple[int, int]]  # (grade, chunk_index) that must be retrieved


@dataclass(frozen=True)
class EvalResult:
    grade_leakage: float
    invalid_citation_rate: float
    recall_at_5: float
    groundedness: float
    sample_size: int = 0
    notes: list[str] = field(default_factory=list)


def _chunk_key(chunk: RetrievedChunk) -> tuple[int, int]:
    return (int(chunk.grade_level), int(chunk.chunk_index))


def evaluate_retrieval(
    gold: list[GoldItem],
    results: list[RetrievalResult],
) -> EvalResult:
    if len(gold) != len(results):
        raise ValueError("gold/results length mismatch")

    total = 0
    leaked = 0
    invalid_cites = 0
    recall_sum = 0.0
    grounded = 0.0

    for item, res in zip(gold, results, strict=True):
        total += 1
        retrieved = [c for c in res.chunks]
        # grade leakage: retrieved chunk grade must be <= the query grade
        for c in retrieved:
            if int(c.grade_level) > item.grade:
                leaked += 1
        # ground truth keys present in top-5
        top5 = retrieved[:5]
        tp = sum(1 for c in top5 if _chunk_key(c) in item.ground_truth_chunk_keys)
        recall_sum += tp / max(len(item.ground_truth_chunk_keys), 1)
        # groundedness proxy: fraction of retrieved chunks that are ground truth (top-5)
        grounded += tp / max(len(top5), 1)
        # citation validity: citations built from real chunk metadata (title/present)
        for c in top5:
            if c.title is None and c.document_id == "":
                invalid_cites += 1

    n = max(total, 1)
    return EvalResult(
        grade_leakage=leaked / n,
        invalid_citation_rate=invalid_cites / n,
        recall_at_5=recall_sum / n,
        groundedness=grounded / n,
        sample_size=total,
    )
