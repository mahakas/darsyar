# ADR-036: مسیر inference

- Status: proposed
- Context: مدل محلی سنگین نباید در process وب لود شود؛ مسیر چت نیز نباید برای embedding/rerank منتظر queue بماند.
- Decision: `INFERENCE_MODE=service` برای سرویس داخلی مجزا، یا `remote` برای adapter بیرونی. هر دو قرارداد embed/rerank و readiness روشن دارند.
- Rejected alternatives: مدل ML در API؛ صف worker synchronously در مسیر چت.
- Consequences: سرویس internal فقط در شبکه compose است و health/ready معنای متفاوت و آزموده دارد.
- Affected files: inference service, provider adapters, Compose, `docs/TECH_STACK.md`.
