# Backend درسیار

Backend پروژه دیگر صرفاً اسکلت فاز صفر نیست. در مخزن فعلی، مسیرهای احراز هویت، مالی/اعتبار، استریم چت، provider/inference، ingestion persistence/outbox و نمونه‌های اولیهٔ synthetic برای chunking، embedding، indexing و hybrid retrieval وجود دارند.

**این وضعیت معادل تکمیل محصول نیست.** endpointهای ingestion و consumer عملیاتی PDF هنوز در گیت پذیرش نهایی نیستند؛ RAG به دیتاست طلایی و اتصال کامل evidence نیاز دارد؛ و پردازش کتاب واقعی تا تأیید مجوز و Gateهای PDF مسدود است.

## نصب وابستگی‌ها

```bash
uv sync --locked --extra dev
```

مدل‌های سنگین inference/RAG جدا از فرایند API اجرا می‌شوند. برای build سرویس‌ها از Dockerfile و Compose ریشه استفاده کنید.

## فرمان‌های اصلی

```bash
uv run --locked ruff check .
uv run --locked mypy app
uv run --locked pytest -q
```

برای تست‌های PostgreSQL از ریشهٔ repository:

```bash
make test-db
```

تست DB باید روی PostgreSQL واقعی با extensionهای موردنیاز اجرا شود؛ SQLite پشتیبانی نمی‌شود.

قبل از هر تغییر، `../AGENTS.md`، `../ROADMAP.md` و ADR مرتبط را بخوانید. migration فقط با Alembic انجام می‌شود. هرگز secrets، فایل .env یا PDF کتاب واقعی را وارد Git نکنید.
