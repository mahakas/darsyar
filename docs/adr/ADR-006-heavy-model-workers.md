# ADR-006: جداسازی مدل‌های سنگین

- Status: Accepted
- Decision: embedding محلی، reranker، OCR و VLM محلی در worker/service اختصاصی اجرا می‌شوند، نه در web API process.
- Reason: جلوگیری از مصرف حافظه/CPU نامحدود، restartهای پرهزینه و تأخیر شروع درخواست.
- Consequences: queue، timeout، retry محدود، idempotency و health/readiness برای worker لازم است. مدل یک‌بار در startup worker بارگذاری و cache شود.
