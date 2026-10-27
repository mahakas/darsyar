# KiloCode — دستور شروع کنترل‌شدهٔ درسیار نسخهٔ ۴٫۰

این فایل را به‌طور کامل به KiloCode بده. مخزن تازه است؛ فرض نکن قابلیتی از قبل پیاده‌سازی شده است.

## مأموریت

تو مهندس ارشد پروژهٔ Darsyar AI هستی. قرارداد `AGENTS.md` نسخهٔ ۴٫۰، `ROADMAP.md`، `docs/DECISIONS.md` و ADRهای موجود را بخوان. برای این اجرا فقط `specs/phase-0.md` را اجرا کن.

## قوانین اجرا

1. ابتدا ۵ تا ۱۰ خط برنامهٔ فاز صفر را اعلام کن، سپس در همین اجرا کار را انجام بده؛ اگر `make` در محیط Windows موجود نیست، از WSL2/Git Bash یا فرمان معادل مستند استفاده کن و targetهای Makefile را همچنان بساز؛ دربارهٔ مواردی که اسناد روشن کرده‌اند سؤال تکراری نپرس.
2. هیچ قابلیت فاز ۱ به بعد را پیاده‌سازی نکن: OTP/JWT واقعی، کردیت، پرداخت، چت، RAG، ingestion واقعی و پنل ادمین خارج از فاز صفرند.
3. اگر تعارضی در مدل مالی، سیاست امنیتی، قرارداد API یا استک کشف شد، کارهای مستقل را ادامه بده ولی بخش متعارض را تغییر نده؛ تعارض، گزینه‌ها و پیامدها را گزارش کن.
4. نسخه‌ها را از مستندات و registry واقعی بررسی کن. `uv.lock` را با `uv lock` و `package-lock.json` را با npm بساز. lockfile جعلی یا دستی نساز.
5. هیچ مدل ML سنگینی را دانلود یا بارگذاری نکن. سرویس inference در این فاز فقط shell/health است و نباید ادعای embedding/reranking واقعی کند.
6. هیچ راز واقعی در مخزن قرار نده و `.env` را commit نکن. `.env.example` باید با `Settings` و Compose هماهنگ باشد.
7. تغییر DB فقط با Alembic. `create_all()` و auto-migration در startup ممنوع‌اند.
8. همهٔ خطاهای API مطابق `docs/API_CONTRACT.md` باشند. stack trace یا راز به کلاینت نرسد.
9. ساخت فایل کافی نیست: تست و فرمان را واقعاً اجرا کن. در نبود Docker/registry، `NOT RUN` همراه علت و دستور لازم برای اجرا گزارش شود.
10. تمام فایل‌های جدید/تغییریافته را در `docs/FILE_MAP.md` ثبت کن. تصمیم معماری جدید باید ADR داشته باشد.

## دامنهٔ فاز صفر

- هم‌ترازکردن Settings و `.env.example` با متغیرهایی که در فاز صفر خوانده می‌شوند.
- بررسی FastAPI، middleware درخواست، request ID، خطای مرکزی و JSON logging/redaction.
- بررسی PostgreSQL async، Redis، health/live، health/ready و version.
- migration اولیهٔ extensionها با نام revision توصیفی؛ migration در startup اجرا نشود.
- Docker Compose توسعه‌ای با PostgreSQL، Redis، سرویس migrate یک‌بارمصرف، API، worker، inference shell و frontend.
- shell رابط React و انتخاب fa/en/ar با RTL/LTR؛ چت همچنان غیرفعال بماند.
- ایجاد lockfile واقعی، lint/typecheck/test، CI و Makefile با هدف‌های معتبر.
- ثبت شواهد در `MANIFEST.md` و به‌روزرسانی `docs/FILE_MAP.md`.

## خارج از دامنه

OTP/JWT، کاربران/نشست‌ها، ledger/reservations، زرین‌پال، کاوه‌نگار، provider واقعی LLM، ذخیرهٔ پیام، ingestion/RAG، جست‌وجوی وب، مدل‌های محلی، پنل ادمین و قابلیت‌های یادگیری آینده.

## پذیرش فاز صفر

در صورت در دسترس بودن ابزارها، این موارد را اجرا کن:

```bash
docker compose config
make lock
make lint
make typecheck
make test
make test-db
make up
make health
```

اگر Docker یا registry در دسترس نیست، صرفاً با بررسی فایل‌ها PASS اعلام نکن. تغییرات schema باید با migration و تست مربوط همراه باشند.

## گزارش نهایی اجباری

از قالب ضمیمهٔ ب `AGENTS.md` استفاده کن. گزارش باید شامل وضعیت `COMPLETE | PARTIAL | BLOCKED | NOT RUN`، فایل‌های تغییرکرده، خروجی واقعی فرمان‌ها و exit code، قواعد R-NNN اعمال‌شده، ریسک‌ها و یک گام بعدی باشد. گام بعدی پیشنهادی `specs/phase-1.md` است؛ آن را در همین اجرا شروع نکن.
