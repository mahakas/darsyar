# RAG Golden Evaluation Dataset — Not Yet Populated

R-171 requires at least 150 questions with reviewed reference answers and authorized evidence. This starter does not fabricate textbook questions, answers, page citations, or licenses. The dataset belongs here after the owner supplies/approves source material and the evaluation schema. Until the golden set and evaluator exist, `make eval` must remain BLOCKED and CI must not invent scores.

Suggested record fields: `case_id`, `language`, `selected_grade`, `subject`, `edition_year`, `question`, `reference_answer`, `allowed_evidence_ids`, `expected_abstention`, `reviewer`, `dataset_version`. Do not place personal student data in the dataset.


## Current evaluator boundary (2026-11-12)

The retrieval-only harness reports grade leakage, citation-metadata validity, recall@5 and retrieval precision@5. It does **not** claim answer groundedness/faithfulness; those remain unmeasured until generated answers and their exact evidence references are part of the reviewed evaluation input. Synthetic evaluation is not a real-textbook benchmark.


## Offline evaluator contract

`golden_set.draft.jsonl` is a 45-case **draft** extracted from the owner-attested 6-page pilot sample (`resources/physics/grade12/samples/physics12.pdf`, gitignored). It is not accepted by the evaluator until cases are reviewed and `review_status` becomes `approved`; a full 150-case reviewed set is still required.


`make eval` and CI run `python -m app.services.ingestion.evaluation` only when both
reviewed inputs exist. No score is synthesized.

- `golden_set.jsonl`: one reviewed case per line with `query`, `selected_grade`, and
  `ground_truth_chunk_keys` (a list of `[grade, chunk_index]` pairs).
- `retrieval_results.jsonl`: one real retrieval snapshot per golden case, in the same
  order, with `retrieved` entries containing at least `grade_level`, `chunk_index`,
  `title`, `page_number`, and `content`; optional `k` records the RRF constant.

The evaluator exits non-zero when fewer than 150 reviewed cases are present, so a
partial dataset cannot be mistaken for an accepted RAG benchmark.

## Capturing a real retrieval snapshot

After the golden dataset is reviewed and approved, generate the matching snapshot
from the running inference/index service; never write it by hand:

```bash
cd backend
uv run --locked python -m app.services.ingestion.evaluation \
  --golden tests/evaluation/golden_set.jsonl \
  --capture --output tests/evaluation/retrieval_results.jsonl
```

Then run `make eval`. The snapshot is a build input, evidence of a real run, not
a substitute for review.

## Reviewing draft cases

After a human reviews the draft questions and their `ground_truth_chunk_keys`:

```bash
python scripts/approve_golden.py --reviewer "<name>" --approve
```

This writes `golden_set.jsonl` with `review_status=approved`, `approved_by` and
`approved_at`. The tool refuses to run without both `--reviewer` and `--approve`.
