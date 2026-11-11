# درسیار (Darsyar AI)

درسیار یک دستیار آموزشی فارسی‌محور برای دانش‌آموزان پایه‌های ۱ تا ۱۲، دانشجویان و معلمان است. هدف محصول، پاسخ‌گویی آموزشی مستند به منابع مجاز، رعایت سقف پایهٔ تحصیلی، صداقت دربارهٔ نبود شاهد و حفاظت از داده‌های کاربران است.

> **وضعیت انتشار:** پروژه در حال توسعه است و هنوز محصول کامل یا آمادهٔ استفادهٔ عمومی/Production نیست. وضعیت هر قابلیت فقط با کد، تست و شواهد پذیرش تعیین می‌شود؛ وجود یک spec یا ماژول اولیه به معنی تکمیل فاز نیست.

## وضعیت فعلی

- فازهای ۰ و ۱ تکمیل‌شده‌اند.
- فاز ۲ تکمیل‌شده با محدودیت‌های عملیاتی مستند است.
- فاز ۳ تکمیل‌شده و CI اصلی در 2026-11-11 موفق بوده است.
- فاز ۴ دارای اجزای synthetic برای manifest، chunking، embedding، indexing و retrieval است؛ اما مسیر عملیاتی کامل ingestion، مجوز هر منبع و گیت‌های PDF هنوز باز هستند.
- فاز ۵ یک نمونهٔ اولیهٔ retrieval و ارزیابی synthetic دارد؛ دیتاست طلایی و اتصال کامل evidence/citation به پاسخ چت هنوز تکمیل و پذیرفته نشده‌اند.
- فاز ۶ یک shell رابط و چت streaming اولیه دارد؛ تجربهٔ کامل تاریخچه، منابع، Markdown امن، دسترس‌پذیری و احراز هویت فرانت‌اند باقی است.
- فاز ۷ مشخصات پنل مدیریت را دارد؛ پیاده‌سازی پنل هنوز آغاز/پذیرفته نشده است.
- فاز ۸ عمداً Deferred و خارج از MVP است.
- فاز ۹ سخت‌سازی و آمادگی انتشار عمومی باقی مانده است.

جزئیات و گیت‌ها در [ROADMAP.md](ROADMAP.md)، [AGENTS.md](AGENTS.md) و [مشخصات فازها](specs/README.md) ثبت شده‌اند.

## قابلیت‌های پیاده‌سازی‌شده در کد

- Backend مبتنی بر FastAPI async، SQLAlchemy 2 و Alembic.
- احراز هویت OTP، نشست و refresh-token با کنترل‌های امنیتی.
- اعتبار، ledger تغییرناپذیر، reservation، usage، پلن‌ها و اجزای پرداخت.
- Model/provider gateway، inference service و چت SSE با چرخهٔ مالی و بازیابی.
- PostgreSQL با pgvector و pg_trgm، Redis و arq.
- جداول durable ingestion، outbox و reconciliation.
- اجزای synthetic برای اعتبارسنجی manifest، chunking دو سطحی، embedding، indexing و hybrid retrieval.
- رابط React/TypeScript اولیه با fa/en/ar و جهت RTL/LTR.

این فهرست، فهرست قابلیت‌های موجود در کد است و به معنی آماده‌بودن همهٔ آن‌ها برای کاربران نهایی نیست.

## مواردی که هنوز آماده نیستند

- هیچ PDF کتاب واقعی بدون شواهد مجوز و تأیید دامنهٔ استفاده پردازش نمی‌شود. مرجع 13529 هنوز از نظر سند، دامنه و عملیات مستقل تأیید نشده است.
- Gate A (انتخاب/مجوز renderer)، بخش‌هایی از Gate B (محدودیت‌های امنیتی پردازش) و Gate C (آزمون هم‌ارزی) باز هستند.
- consumer عملیاتی PDF در worker و endpoint کامل intake هنوز در مسیر پذیرش نهایی نیستند.
- RAG هنوز دیتاست طلایی حداقل ۱۵۰ پرسشی و ارزیابی منطبق با ADR-043 ندارد.
- پنل کامل Admin، تجربهٔ کامل کاربر، و گیت‌های انتشار Production آماده نیستند.

## فناوری‌ها

- **Backend:** Python 3.13، FastAPI، Pydantic v2، SQLAlchemy 2 async، Alembic.
- **Data/Queue:** PostgreSQL 18 + pgvector + pg_trgm، Redis 7، arq.
- **Frontend:** React، TypeScript، Vite، i18next.
- **AI:** providerهای OpenAI-compatible، سرویس inference جدا، embedding و reranking قابل‌تعویض.
- **Operations:** Docker Compose، Nginx و GitHub Actions.

قرارداد دقیق نسخه‌ها و قواعد توسعه در [AGENTS.md](AGENTS.md) و [docs/TECH_STACK.md](docs/TECH_STACK.md) است.

## راه‌اندازی محلی

پیش‌نیازها: Git، Docker Desktop/Compose، Python 3.13، uv، Node.js 24 و npm.

1. مخزن را clone کنید و وارد پوشهٔ پروژه شوید.
2. فایل نمونه را کپی کنید و secrets محلی مستقل بسازید:

```bash
cp .env.example .env
```

در Windows PowerShell:
```powershell
Copy-Item .env.example .env
```

مقادیر `CHANGE_ME` نمونه و غیرقابل‌استفاده‌اند. `APP_SECRET_KEY` و `OTP_PEPPER` باید تصادفی، مستقل از یکدیگر و فقط در فایل محلی `.env` باشند. هرگز `.env` یا راز واقعی را commit نکنید.

3. سرویس‌های توسعه را اجرا کنید:

```bash
make up
make health
```

- Frontend: http://127.0.0.1:5173
- API: http://127.0.0.1:8000
- Health: http://127.0.0.1:8000/health

برای مشاهدهٔ وضعیت:
```bash
make ps
make logs
```

## آزمون و کیفیت

فرمان‌های متداول:

```bash
make lint
make typecheck
make test
make test-db
```

تست‌های DB به PostgreSQL واقعی نیاز دارند؛ SQLite جایگزین معتبر این پروژه نیست. برخی تست‌های sandbox یا مدل واقعی فقط در محیط محدودشده/دارای منابع لازم اجرا می‌شوند و ممکن است در CI عمومی به‌صورت صریح skip شوند.

آخرین CI روی `main` در 2026-11-11: **Backend 463 passed, 21 skipped**؛ Frontend، migration smoke و Linux SIGTERM acceptance نیز موفق بودند. جزئیات: [GitHub Actions](https://github.com/mahakas/darsyar/actions).

## حاکمیت، امنیت و منابع

- `AGENTS.md` قرارداد مهندسی و `ROADMAP.md` مرجع وضعیت و ترتیب فازها هستند.
- اسناد canonical هر فاز در `specs/phase-N.md` قرار دارند.
- تصمیمات معماری در `docs/adr/` و `docs/DECISIONS.md` ثبت می‌شوند.
- منابع آموزشی باید مجوز، منشأ، ناشر و سال چاپ قابل‌ردیابی داشته باشند. `license_note` به‌تنهایی مجوز استفاده نیست.
- پوشهٔ `resources/` برای ساختار محلی منابع است؛ کتاب‌های واقعی و PDFهای آزمایشی مجاز نیستند به Git اضافه شوند.
- پیش از Production، سیاست حریم خصوصی/رضایت، بازپرداخت، بکاپ و بازیابی، امنیت، منابع مجاز و دسترسی‌های عملیاتی باید به‌طور مستقل تأیید شوند.

