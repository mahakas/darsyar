# راه‌اندازی محلی روی Windows

## مسیر توصیه‌شده

1. Git، VS Code و KiloCode را نصب کن.
2. Docker Desktop را با backend مبتنی بر WSL2 راه‌اندازی کن.
3. Python 3.13، `uv` سازگار با `docs/TECH_STACK.md`، Node.js 24 LTS و npm را نصب کن.
4. ترجیحاً پروژه را داخل filesystem توزیع WSL2 نگه دار تا رفتار فایل‌ها و ابزارهای لینوکس با CI هم‌راستا باشد.
5. در ریشهٔ پروژه `.env.example` را به `.env` کپی کن و فقط رازهای محلی خودت را در `.env` وارد کن. این فایل هرگز commit نمی‌شود. رمز PostgreSQL در نمونه باید با رمز واقعی محلی و سازگار با URL جایگزین شود.
6. در ترمینالی که GNU Make در دسترس دارد `make lock` را اجرا کن؛ سپس فاز صفر طبق `KILOCODE_START_HERE.md` اجرا شود.

## اگر Make در PowerShell در دسترس نیست

معادل بخش lock (پس از آماده‌بودن اتصال registry):

```powershell
Set-Location backend
uv lock
uv sync --locked --extra dev
Set-Location ../frontend
npm install --package-lock-only
npm ci
Set-Location ..
```

سایر فرمان‌ها با `docker compose`، `uv run` و `npm run` اجرا شوند. اگر هر فرمان اجرا نشد، گزارش باید `NOT RUN` یا `BLOCKED` و علت واقعی را ثبت کند؛ نبود ابزار نباید به PASS تبدیل شود.

## نکات امنیتی

- در production، placeholderهای `CHANGE_ME_...` غیرمجازند. برای `APP_SECRET_KEY` و `OTP_PEPPER` از دو راز مستقل و تصادفی استفاده کن.
- منابع درسی واقعی را فقط پس از بررسی مجوز پردازش اضافه کن.
- این بسته شامل محتوای کتاب، راز واقعی یا دادهٔ واقعی کاربر نیست.
