# راهبرد آزمون

## سطوح
1. Unit: قواعد pure، config/boot guard، redaction، نرمال‌سازی و parsing. شبکهٔ واقعی ممنوع؛ `respx` یا `MockTransport`.
2. Integration: FastAPI با `httpx.ASGITransport`، PostgreSQL واقعی با pgvector و pg_trgm، Redis واقعی یا container.
3. Security: ownership، rate limit، anti-enumeration، refresh reuse/CSRF، SSRF، XSS، upload quarantine و prompt injection.
4. Financial concurrency: رزرو موازی، idempotency، settlement/release، reconciliation و webhook تکراری.
5. RAG evaluation: grade leakage صفر، invalid citation صفر در ارزیابی، recall@k، groundedness و نسخهٔ dataset.
6. Runtime: Compose health، migration، backup restore، graceful shutdown و بار.

## قواعد کیفیت
- حداقل یک happy path و edge/error برای منطق جدید.
- SQLite در تست DB ممنوع.
- core/security/credits/retrieval/agent حداقل ۷۰٪ پوشش هدف؛ coverage جایگزین صحت نیست.
- هر اجرای تست باید نتیجه، تعداد، فرمان و exit code واقعی را گزارش کند.
- تست‌هایی که نیاز به Docker یا registry دارند در نبود ابزار `NOT RUN` هستند، نه PASS.

## فاز صفر
فقط تست‌های config, errors, logging, health و smoke پایگاه داده/Redis در دامنه‌اند. قابلیت‌های بعدی نباید به صرف داشتن پوشه تست «تست‌شده» اعلام شوند.
