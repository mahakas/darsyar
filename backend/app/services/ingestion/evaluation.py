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
    ground_truth_chunk_keys: set[tuple[int, int]]  # (grade, chunk_index)
    review_status: str = "draft"


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


def load_golden(path: str) -> list[GoldItem]:
    """Load reviewed golden questions from JSONL; no questions are fabricated here."""
    import json
    from pathlib import Path

    items: list[GoldItem] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        items.append(
            GoldItem(
                query=str(row["query"]),
                grade=int(row["selected_grade"]),
                ground_truth_chunk_keys={
                    (int(grade), int(index)) for grade, index in row["ground_truth_chunk_keys"]
                },
                review_status=str(row.get("review_status", "draft")),
            )
        )
    return items


def load_retrieval_results(path: str) -> list[RetrievalResult]:
    """Load an explicit retrieval snapshot produced by a reviewed, real run."""
    import json
    from pathlib import Path

    results: list[RetrievalResult] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        chunks = [
            RetrievedChunk(
                chunk_id=str(item.get("chunk_id", uuid.uuid4())),
                document_id=str(item.get("document_id", uuid.uuid4())),
                chunk_index=int(item["chunk_index"]),
                is_parent=bool(item.get("is_parent", False)),
                grade_level=int(item["grade_level"]),
                subject=str(item.get("subject", "")),
                page_number=item.get("page_number"),
                title=item.get("title"),
                content=str(item.get("content", "")),
                dense_score=item.get("dense_score"),
                lexical_score=item.get("lexical_score"),
                rrf_score=float(item.get("rrf_score", 0.0)),
                rerank_score=item.get("rerank_score"),
            )
            for item in row["retrieved"]
        ]
        results.append(
            RetrievalResult(chunks=chunks, grade_ceiling_applied=True, k=float(row.get("k", 60.0)))
        )
    return results


async def capture_retrieval_results(golden_path: str, output_path: str) -> int:
    """Run a real retrieval once per reviewed question and persist the snapshot.

    No answers or scores are generated here. This exists so the owner can check in
    a reproducible retrieval snapshot after approving the golden dataset.
    """
    import json
    from pathlib import Path

    from app.core.config import get_settings
    from app.db.session import SessionFactory
    from app.inference.remote import RemoteInferenceBackend
    from app.services.ingestion.retrieval_service import RetrievalService

    settings = get_settings()
    backend = RemoteInferenceBackend(settings)
    await backend.startup()
    try:
        service = RetrievalService(
            embed=backend.embed,
            rerank=lambda query, docs: backend.rerank([(query, doc) for doc in docs]),
            embedding_model=settings.embedding_model,
            embedding_dim=settings.embedding_dim,
        )
        gold = load_golden(golden_path)
        lines: list[str] = []
        async with SessionFactory() as session:
            for item in gold:
                result = await service.retrieve(
                    session, query=item.query, selected_grade=item.grade
                )
                row = {
                    "query": item.query,
                    "k": result.k,
                    "retrieved": [chunk.__dict__ for chunk in result.chunks],
                }
                lines.append(json.dumps(row, ensure_ascii=False))
        import asyncio

        await asyncio.to_thread(
            Path(output_path).write_text, "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )
        return len(gold)
    finally:
        await backend.aclose()


def main(argv: list[str] | None = None) -> int:
    """Offline evaluator or snapshot capture from a reviewed golden dataset."""
    import argparse
    import asyncio
    import json

    parser = argparse.ArgumentParser(description="Evaluate or capture retrieval snapshots")
    parser.add_argument("--golden", required=True)
    parser.add_argument("--results")
    parser.add_argument("--capture", action="store_true", help="write a real retrieval snapshot")
    parser.add_argument("--output", help="destination for --capture")
    args = parser.parse_args(argv)

    if args.capture:
        if not args.output:
            parser.error("--capture requires --output")
        count = asyncio.run(capture_retrieval_results(args.golden, args.output))
        print(f"captured {count} retrieval results")
        return 0
    if not args.results:
        parser.error("--results is required unless --capture is used")

    gold = load_golden(args.golden)
    results = load_retrieval_results(args.results)
    if len(gold) != len(results):
        parser.error("golden/results length mismatch")
    report = evaluate_retrieval(gold, results)
    print(json.dumps(report.__dict__, ensure_ascii=False, indent=2))
    reasons: list[str] = []
    if report.sample_size < 150:
        reasons.append("golden dataset must contain at least 150 cases")
    unreviewed = [item for item in gold if item.review_status != "approved"]
    if unreviewed:
        reasons.append(f"{len(unreviewed)} cases are not owner-reviewed/approved")
    if reasons:
        print("EVAL NOT ACCEPTED: " + "; ".join(reasons))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
