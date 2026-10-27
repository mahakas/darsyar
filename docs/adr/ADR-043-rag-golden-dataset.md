# ADR-043: دیتاست طلایی و gates ارزیابی RAG

- Status: proposed
- Context: آستانه‌های retrieval و ادعاهای groundedness با حدس قابل پذیرش نیستند.
- Decision: حداقل ۱۵۰ پرسش با پاسخ مرجع/evidence مجاز و نسخه‌بندی دیتاست لازم است؛ grade leakage و citation خارج از evidence باید صفر باشند.
- Rejected alternatives: threshold tuning براساس چند مثال دستی.
- Consequences: دسترسی/مجوز dataset کنترل می‌شود؛ تغییر chunk/embedding/rerank با evaluation می‌آید.
- Affected files: `backend/tests/evaluation/`, `docs/RAG_EVALUATION_PLAN.md`, CI.
