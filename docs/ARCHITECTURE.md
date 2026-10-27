# معماری مرجع

## اجزای اصلی

```text
Browser (React/TypeScript; access token memory; fetch streaming)
        |
      Nginx (TLS, CSP, body/time limits, SSE no-buffer)
        |
        +--> API: FastAPI (validation, authz, services; no ML imports)
        |       +--> PostgreSQL: durable data, ledger, reservations, evidence
        |       +--> Redis: cache, rate-limit and queue coordination only
        |       +--> provider adapters: LLM/SMS/payment/web search
        |       +--> inference HTTP client (only when INFERENCE_MODE=service)
        +--> frontend

Worker (arq): ingestion/OCR/chunking/reconciliation/cleanup
Inference service (same backend image, separate process): heavy models loaded once
Migrate one-shot service: alembic upgrade head; never run in API startup
```

## درخواست چت (هدف فازهای بعد)
1. اعتبارسنجی نشست و `selected_grade`.
2. ایجاد reservation پایدار در PostgreSQL و ثبت idempotency.
3. اجرای retrieval با سقف پایه در هر شاخه.
4. اگر شاهد کافی نبود: query rewrite محدود؛ سپس در صورت فعال بودن، وب مستقل با کنترل SSRF.
5. تولید پاسخ با schema ساخت‌یافته؛ مدل فقط evidence IDs را ارجاع می‌دهد.
6. سرور evidence_set را اعتبارسنجی و citation نهایی را می‌سازد.
7. سیاست پاسخ ناقص و settle/release طبق ADR مالی پذیرفته‌شده اعمال می‌شود.

## اصول مرزی
- Router: احراز هویت، validation و delegation.
- Repository: query و مالکیت در WHERE.
- Service: منطق دامنه و تراکنش‌ها.
- Adapter: APIهای بیرونی.
- Worker/inference: CPU-heavy و ML، جدا از event loop وب.
- PostgreSQL: منبع حقیقت مالی/پایدار؛ Redis منبع حقیقت موجودی یا پرداخت نیست.

## نکتهٔ فاز صفر
inference فقط shell سلامت است و مدل سنگین دانلود نمی‌شود. در حالت `service`، فاز inference باید مدل واقعی و readiness را پیاده کند؛ تا آن زمان این سرویس قابلیت embedding/rerank واقعی ندارد.


## Readiness mode
The root `/ready` checks PostgreSQL and Redis. It checks the internal inference `/ready` endpoint when `INFERENCE_MODE=service`; remote providers are checked by their adapter-specific health behavior when that phase is implemented. Root `/health` is liveness-only and never depends on PostgreSQL.
