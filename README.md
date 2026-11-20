# درسیار (Darsyar AI)

درسیار یک دستیار آموزشی فارسی‌محور برای دانش‌آموزان پایه‌های ۱ تا ۱۲، دانشجویان و معلمان است. هدف محصول، پاسخ‌گویی آموزشی مستند به منابع مجاز، رعایت سقف پایهٔ تحصیلی، صداقت دربارهٔ نبود شاهد و حفاظت از داده‌های کاربران است.

> **وضعیت انتشار:** پروژه در حال توسعه است و هنوز محصول کامل یا آمادهٔ استفادهٔ عمومی/Production نیست. وضعیت هر قابلیت فقط با کد، تست و شواهد پذیرش تعیین می‌شود؛ وجود یک spec یا ماژول اولیه به معنی تکمیل فاز نیست.

## وضعیت فعلی

- فازهای ۰ و ۱ تکمیل‌شده‌اند.
- فاز ۲ تکمیل‌شده با محدودیت‌های عملیاتی مستند است.
- فاز ۳ تکمیل‌شده و شواهد CI/خاموشی کنترل‌شده ثبت شده‌اند.
- فاز ۴ علاوه بر اجزای synthetic مربوط به manifest، chunking، embedding، indexing و retrieval، چرخهٔ durable job (PR #21)، staging/publish امن Artifact (PR #22)، متریک‌های کم‌کاردینالیتی (PR #23) و تست انتهابه‌انتها PostgreSQL→Parent/Child→Artifact برای موفقیت و شکست (PR #24) را دارد؛ بااین‌حال ingestion عملیاتی کتاب کامل، مجوز مستقل منابع و تأیید production گیت‌های Gate A/B/C باز هستند (تصمیم آزمایشی نمونه در `docs/ingestion/OWNER_DECISIONS.md`).
- فاز ۵ نمونهٔ اولیهٔ retrieval و ارزیابی synthetic دارد؛ groundingservice با fail-closed، citationها و SourceCard در رابط متصل و replay SSE با Last-Event-ID همگام شد، ولی دیتاست طلایی حداقل ۱۵۰ پرسشی تأییدشده و evidence snapshot برای benchmark باقی است (۴۵ مورد پیشنویس از نمونهٔ ۶صفحهای متعلق به مالک `backend/tests/evaluation/golden_set.draft.jsonl` موجود است، اما هنوز تأیید نشدهاند).
- فاز ۶ احراز هویت نشست، پایهٔ تحصیلی صریح، تاریخچهٔ مالک‌محور، pagination/search و replay/status recovery پایدار SSE دارد؛ SourceCard، Markdown امن، دسترس‌پذیری و پذیرش کامل رابط باقی است.
- فاز ۷ زیرساخت محدود مجوز مدیر و audit تغییرناپذیر در PostgreSQL دارد؛ پنل مدیریت، routeهای مدیریتی، seed عملیاتی، MFA/step-up و acting session هنوز پیاده‌سازی/پذیرفته نشده‌اند. ADR-051 همچنان Proposed است.
- [فاز ۸](specs/phase-8.md) برنامهٔ ابزارهای یادگیری پس از MVP است؛ منطق مستقل مرور آزموده شده اما ابزار وب فعال نیست.
- فاز ۹ بخشی از hardening هدرها و no-store را دارد؛ TLS/HSTS واقعی، تست بار، backup/restore، vulnerability triage/enforcement، privacy/legal approvals و Production release باقی است.

جزئیات و گیت‌ها در [ROADMAP.md](ROADMAP.md)، [AGENTS.md](AGENTS.md) و [مشخصات فازها](specs/README.md) ثبت شده‌اند.

## قابلیت‌های پیاده‌سازی‌شده در کد

- Backend مبتنی بر FastAPI async، SQLAlchemy 2 و Alembic.
- احراز هویت OTP، نشست و refresh-token با کنترل‌های امنیتی.
- اعتبار، ledger تغییرناپذیر، reservation، usage، پلن‌ها و اجزای پرداخت.
- Model/provider gateway، inference service و چت SSE با چرخهٔ مالی و بازیابی.
- PostgreSQL با pgvector و pg_trgm، Redis و arq.
- جداول durable ingestion، outbox و reconciliation.
- اجزای synthetic برای اعتبارسنجی manifest، chunking دو سطحی، embedding، indexing و hybrid retrieval.
- رابط React/TypeScript با هستهٔ چت، تاریخچه و fa/en/ar با جهت RTL/LTR.

این فهرست، فهرست قابلیت‌های موجود در کد است و به معنی آماده‌بودن همهٔ آن‌ها برای کاربران نهایی نیست.

## مواردی که هنوز آماده نیستند

- هیچ PDF کتاب واقعی بدون شواهد مجوز و تأیید دامنهٔ استفاده پردازش نمی‌شود. مرجع 13529 هنوز از نظر سند، دامنه و عملیات مستقل تأیید نشده است.
- Gate A (مجوز/انتخاب نهایی renderer)، بخش‌هایی از Gate B (محدودیت‌های عددی و امنیت پردازش) و Gate C (آزمون هم‌ارزی) باز هستند.
- endpoint کامل intake و consumer عملیاتی PDF در worker هنوز پذیرفته نشده‌اند.
- RAG دارای مسیر groundشدهٔ fail-closed و منابع SSE است، ولی دیتاست طلایی حداقل ۱۵۰ پرسشی و اسناد مجوز منبع برای پردازش PDF واقعی باقی است.
- تجربهٔ کامل کاربر و پنل Admin هنوز آماده نیستند.
- Production هنوز تأیید نشده است.

## فناوری‌ها

- **Backend:** Python 3.13، FastAPI، Pydantic v2، SQLAlchemy 2 async، Alembic.
- **Data/Queue:** PostgreSQL 18 + pgvector + pg_trgm، Redis 7، arq.
- **Frontend:** React، TypeScript، Vite، i18next.
- **AI:** providerهای OpenAI-compatible، سرویس inference جدا، embedding و reranking قابل‌تعویض.
- **Operations:** Docker Compose، Nginx و GitHub Actions.

قرارداد دقیق نسخه‌ها و قواعد توسعه در [AGENTS.md](AGENTS.md) و [docs/TECH_STACK.md](docs/TECH_STACK.md) است.

## راهنمای راه‌اندازی برای مبتدی‌ها

راهنمای گام‌به‌گام ویندوز، WSL2، Docker Desktop، نصب ابزارها، clone پروژه، ساخت و تنظیم امن `.env`، پیکربندی LLM و Inference، اجرای سرویس‌ها، تست‌ها و رفع خطاها در این فایل قرار دارد:

**[راهنمای کامل راه‌اندازی درسیار در ویندوز — مخصوص مبتدی‌ها](docs/BEGINNER_SETUP_GUIDE_FA.md)**

این راهنما وضعیت واقعی سرویس‌ها و پیش‌نیازهای مدل‌ها را توضیح می‌دهد. به‌خصوص توجه کن که آدرس/کلید/نام مدل embedding در نمونه خالی است و چت واقعی نیز به اعتبارنامهٔ LLM نیاز دارد؛ بنابراین کپی‌کردن صرف `.env.example` برای راه‌اندازی کامل کافی نیست.

## راه‌اندازی سریع محلی

پیش‌نیازها: Git، Docker Desktop/Compose، Python 3.13، uv، Node.js 24 و npm.

1. مخزن را clone کنید و وارد پوشهٔ پروژه شوید.
2. فایل نمونه را کپی کنید:

```bash
cp .env.example .env
```

در Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

مقادیر `CHANGE_ME` نمونه و غیرقابل‌استفاده‌اند. `APP_SECRET_KEY` و `OTP_PEPPER` باید تصادفی، مستقل از یکدیگر و فقط در فایل محلی `.env` باشند. هرگز `.env` یا راز واقعی را commit نکنید.

3. پس از تکمیل تنظیمات ضروری LLM و embedding در `.env`، از ریشهٔ مخزن اجرا کنید:

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

وضعیت شواهد (محلی، روی شاخهٔ کاری جاری، 2026-11-19):

- `backend`: `ruff check .` و `mypy app` موفق (133 فایل)؛ coverage محلی بدون DB: **52%** (با ۳۳۰ تست skipشده قابل مقایسه با هدف ۷۰٪ نیست).
- `pytest -q` (بدون PostgreSQL و Redis محلی): **265 passed, 330 skipped**؛ تستهای `*_db` و sandbox/real-model صریحاً skip شدند و نتیجهٔ PASS تلقی نمیشوند.
- `frontend`: `npm test` (4 test)، `npm run typecheck` و `npm run lint` موفق.
- `.github/workflows/ci.yml` اکنون شامل backend/frontend test gate، RAG evaluator با مسیر درست و smoke یکپارچه reverse-proxy است؛ نتایج CI اخیر تأیید نشدهاند.
- آخرین CI موفق ثبتشده روی `main` مربوط به PR #24 و commit `385a3d1fdedb429250e478ed836c96e9e1422a9e`، 2026-11-12 است: [Run 43254717321](https://github.com/mahakas/darsyar/actions/runs/43254717321). این شاهد مربوط به کد قبل از تغییرات اخیر است و نباید بهعنوان نتیجهٔ CI شاخهٔ حاضر خوانده شود.
- Trivy تنها report-mode است و صفر بودن آسیبپذیریها را ثابت نمیکند.

## حاکمیت، امنیت و منابع

- `AGENTS.md` قرارداد مهندسی و `ROADMAP.md` مرجع وضعیت و ترتیب فازها هستند.
- اسناد canonical هر فاز در `specs/phase-N.md` قرار دارند.
- تصمیمات معماری در `docs/adr/` و `docs/DECISIONS.md` ثبت می‌شوند.
- منابع آموزشی باید مجوز، منشأ، ناشر و سال چاپ قابل‌ردیابی داشته باشند. `license_note` به‌تنهایی مجوز استفاده نیست.
- پوشهٔ `resources/` برای ساختار محلی منابع است؛ کتاب‌های واقعی و PDFهای آزمایشی مجاز نیستند به Git اضافه شوند.
- پیش از Production، سیاست حریم خصوصی/رضایت، بازپرداخت، بکاپ و بازیابی، امنیت، منابع مجاز و دسترسی‌های عملیاتی باید به‌طور مستقل تأیید شوند.
