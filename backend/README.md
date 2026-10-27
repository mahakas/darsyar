# Backend درسیار

این پوشه اسکلت فاز صفر است. راه‌اندازی پس از ساخت lockfile واقعی انجام می‌شود:

```bash
uv lock
uv sync --locked --extra dev
uv run ruff check .
uv run mypy app
uv run pytest -q
```

مدل‌های سنگین، OTP واقعی، پرداخت، رزرو مالی و RAG هنوز پیاده‌سازی نشده‌اند. قبل از اجرای محیط production اسناد `AGENTS.md`، `docs/OPEN_QUESTIONS.md` و `docs/DEPLOYMENT.md` را بخوانید.
