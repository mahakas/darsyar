# RAG Golden Evaluation Dataset — Not Yet Populated

R-171 requires at least 150 questions with reviewed reference answers and authorized evidence. This starter does not fabricate textbook questions, answers, page citations, or licenses. The dataset belongs here after the owner supplies/approves source material and the evaluation schema. Until the golden set and evaluator exist, `make eval` must remain BLOCKED and CI must not invent scores.

Suggested record fields: `case_id`, `language`, `selected_grade`, `subject`, `edition_year`, `question`, `reference_answer`, `allowed_evidence_ids`, `expected_abstention`, `reviewer`, `dataset_version`. Do not place personal student data in the dataset.
