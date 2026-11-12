"""Unit tests for retrieval-evaluation metric denominators and citation metadata."""

from uuid import uuid4

from app.services.ingestion.evaluation import GoldItem, evaluate_retrieval
from app.services.ingestion.retrieval import RetrievalResult, RetrievedChunk


def _chunk(
    *, grade: int, index: int, title: str | None = "ریاضی آزمایشی",
    document_id: str | None = None, chunk_id: str | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id or str(uuid4()),
        document_id=document_id or str(uuid4()),
        chunk_index=index,
        grade_level=grade,
        subject="math",
        page_number=1,
        title=title,
        content="synthetic content",
        dense_score=0.8,
        lexical_score=0.7,
        rrf_score=0.03,
        rerank_score=0.9,
    )


def test_citation_rate_counts_each_candidate_and_rejects_missing_metadata() -> None:
    chunks = [
        _chunk(grade=5, index=0),
        _chunk(grade=5, index=1, title="  "),
        _chunk(grade=5, index=2, document_id="not-a-uuid"),
    ]
    gold = [GoldItem(query="synthetic", grade=5, ground_truth_chunk_keys={(5, 0), (5, 1), (5, 2)})]
    result = evaluate_retrieval(
        gold,
        [RetrievalResult(chunks=chunks, grade_ceiling_applied=True, k=60.0)],
    )

    assert result.invalid_citation_rate == 2 / 3
    assert result.recall_at_5 == 1.0
    assert result.retrieval_precision_at_5 == 1.0
    assert result.answer_groundedness is None
    assert "answer_groundedness_not_measured_by_retrieval_only_evaluation" in result.notes


def test_grade_leakage_is_normalized_by_retrieved_chunks_not_queries() -> None:
    chunks = [
        _chunk(grade=5, index=0),
        _chunk(grade=5, index=1),
        _chunk(grade=5, index=2),
        _chunk(grade=8, index=3),
    ]
    gold = [GoldItem(query="synthetic", grade=5, ground_truth_chunk_keys={(5, 0), (5, 1), (5, 2)})]
    result = evaluate_retrieval(
        gold,
        [RetrievalResult(chunks=chunks, grade_ceiling_applied=True, k=60.0)],
    )

    assert result.grade_leakage == 0.25
    assert result.retrieval_precision_at_5 == 0.75


def test_evaluation_rejects_mismatched_gold_and_result_counts() -> None:
    try:
        evaluate_retrieval([], [RetrievalResult(chunks=[], grade_ceiling_applied=True, k=60.0)])
    except ValueError as exc:
        assert str(exc) == "gold/results length mismatch"
    else:
        raise AssertionError("expected mismatched input lengths to fail")
