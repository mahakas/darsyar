# Manifest بستهٔ شروع Darsyar AI — Version 4

## دامنه
این ZIP بر اساس `AGENTS.md` نسخهٔ ۴٫۰ شامل قرارداد مهندسی، اسناد مرجع، ADRها، مشخصات فازها، اسکلت Backend/Frontend/infra، تنظیمات نمونه و تست‌های محدود foundation است.

## محدودیت‌ها
- این بسته محصول کامل و آمادهٔ انتشار نیست؛ OTP، chat، payment، RAG و admin کامل نیستند.
- lockfileهای واقعی Python و npm در بسته تولید نشده‌اند؛ KiloCode باید در فاز صفر با registry واقعی بسازدشان.
- هیچ کتاب، secret، token، فایل `.env` یا دادهٔ شخصی در بسته وجود ندارد.
- ADRهای جدید نسخهٔ ۴ که وضعیت proposed دارند، به‌خودی‌خود accepted محسوب نمی‌شوند.

## شواهد ساخت بسته
ساختار و فایل‌ها در مرحلهٔ بسته‌بندی بررسی می‌شوند؛ این بررسی جای build یا تست runtime نیست. `docker compose config`, `make lock`, lint/typecheck/test، migration و `make health` باید در محیط واقعی اجرا و نتیجهٔ واقعی گزارش شوند. هر مورد اجرا نشده باید NOT RUN بماند.

## گزارش اعتبارسنجی محیط بسته‌بندی

- `AGENTS.md` با فایل نسخهٔ ۴ ارسالی تطبیق داده شد: **PASS**.
- `python -m compileall -q backend/app backend/alembic backend/tests scripts`: **PASS**.
- `pytest` روی تست‌های قابل‌جمع‌آوری به‌جز `backend/tests/test_health.py`: **13 passed**.
- اجرای مجموعهٔ کامل تست‌ها در محیط بسته‌بندی: **BLOCKED**؛ کتابخانهٔ runtime `redis` در Python سیستم نصب نیست. این وابستگی در `backend/pyproject.toml` تعریف شده است.
- parse فایل‌های `docker-compose.yml`، workflow CI و JSONهای frontend: **PASS**.
- تولید `uv.lock`: **BLOCKED**؛ تلاش برای دسترسی به PyPI با خطای DNS مواجه شد. lockfile جعلی یا دست‌ساز داخل بسته قرار داده نشده است.
- تولید `frontend/package-lock.json`، اجرای `npm ci` و build فرانت‌اند: **NOT RUN**؛ lockfile واقعی نیازمند registry است.
- اجرای Docker Compose، migration روی PostgreSQL واقعی و healthcheck همهٔ سرویس‌ها: **NOT RUN**؛ Docker در محیط بسته‌بندی نصب نیست.
- Node نصب‌شده در محیط بسته‌بندی نسخهٔ ۲۲ است، اما قرارداد نسخهٔ ۴ Node.js 24 LTS را هدف می‌گیرد؛ build رسمی باید با Node 24 انجام شود.
- `.env`، رمزها، کلیدهای API، کتاب‌های واقعی درسی و دادهٔ شخصی: **در بسته وجود ندارند**.

این نتایج فقط آزمون‌های بالا را توصیف می‌کند و به معنی تأیید آمادگی production نیست. در فاز صفر، KiloCode باید lockfileهای واقعی را بسازد و در محیط سازگار، lint/typecheck/test، migration، build و health را واقعاً اجرا و گزارش کند.

## گزارش اجرای فاز صفر توسط KiloCode (2026-10-27)

محیط اجرا: Windows + PowerShell، Docker Desktop (daemon 29.9.2)، uv 0.12.18، Python 3.13.14، Node v24.21.0. `make` در میزبان موجود نیست؛ همهٔ targetهای Makefile با فرمان معادل مستقیم اجرا شدند و Makefile به‌عنوان تعریف معتبر targetها حفظ شد (گزارش کامل در پاسخ پایانی فاز صفر).

| آیتم | نتیجه |
|---|---|
| سازگاری وابستگی | تعارض واقعی `redis>=6` با `arq` (نیازمند redis<6) کشف و با پین `redis[hiredis]>=5,<6` حل شد (ADR-044). |
| `backend/uv.lock` | تولیدشده با `uv lock` (188 پکیج)؛ `uv sync --locked` موفق. |
| `frontend/package-lock.json` | تولیدشده با `npm install --package-lock-only`؛ `npm ci` موفق (0 آسیب‌پذیری). |
| `ruff check .` | PASS |
| `mypy app` | PASS (52 فایل) |
| `pytest` (واحد) | 16 passed |
| `npm run lint` / `typecheck` / `build` | PASS (تولید dist) |
| `docker compose config` | PASS (exit 0) |
| `docker compose up --build` | PASS؛ همهٔ سرویس‌ها healthy، migrate یک‌بارمصرف exit 0 |
| `make health` (معادل) | PASS |
| `make test-db` (معادل) | PASS؛ migration 0001+0002 روی PostgreSQL واقعی + 19 passed |
| schema | `vector` و `pg_trgm` فعال؛ head=0002؛ جدول `index_meta` موجود |
| رازها | کلید API ظاهراً واقعی در `.env` محلی پاک‌سازی شد؛ `.env` در .gitignore؛ `.env.example` فقط placeholder |

## گزارش بازبینی بستن فاز صفر (Closure Review — 2026-10-27)

همهٔ آیتم‌های زیر در همین بازبینی از نو اجرا شدند (شاهد قبلی استفاده نشد):

| آیتم | نتیجه (exit code واقعی) |
|---|---|
| `uv lock --check` | PASS (exit 0) — lockfile هم‌گام است |
| `uv sync --locked --extra dev` | PASS (exit 0) |
| `uv run --locked ruff check .` | PASS (exit 0) |
| `uv run --locked mypy app` | PASS (exit 0) — 52 فایل |
| `uv run --locked pytest -q` | PASS (exit 0) — 20 passed, 3 skipped (schema):
 |
| `python scripts/run_test_db.py` (معادل `make test-db`) | PASS (exit 0) — migration 0001+0002 روی PostgreSQL واقعی + 23 passed |
| `npm ci` | PASS (exit 0) — 0 آسیب‌پذیری |
| `npm run lint` / `npm run typecheck` / `npm run build` | PASS (exit 0) |
| `docker compose config --quiet` | PASS (exit 0) |
| health gate (`check_compose_health.py`) | PASS (exit 0) — همهٔ سرویس‌ها در وضعیت مورد انتظار |
| `/health`, `/ready`, `/version`, فرانت `:5173` | 200 در همه |
| inference `/embed` (زنده در کانتینر) | 503 با بدنهٔ `{code, message, request_id}` و هدر `X-Request-ID` منطبق (R-054) |
| اسکن الگوی راز | صفر hit در درخت منبع؛ `.env` در `.gitignore` و `.dockerignore` (ریشه و backend) |
| Redis | **تصمیم مالک (ADR-044 accepted):** سرور 7.4.12 (`redis:7.4.12-bookworm`) + کلاینت redis-py 5.3.1 + arq 0.28.0؛ پشتیبان‌گیری و پاک‌سازی placeholderهای AOF خالی Redis 8 (RDB 15) پیش از شروع؛ volume حفظ شد |
| CI (GitHub Actions) | **NOT RUN** — مخزن git/remote وجود ندارد؛ workflow موجود است |
| پوشش ۷۰٪ (R-217) و آزمون بار (R-025) | **NOT RUN** — در دامنهٔ فاز ۱+ |

## اجرای تصمیم مالک ADR-044 (گزینهٔ ۲ — Redis 7.4.12)

| آیتم | نتیجه (exit code واقعی) |
|---|---|
| `docker compose config --quiet` | PASS (exit 0) |
| دریافت `redis:7.4.12-bookworm` | PASS — digest `sha256:bd28fff4b665fdf1b73e8b5b73ec05d2f858f4fa3c8ea0d7c9bc09f7f6bf7039` |
| بازسازی امن Redis بدون حذف volume | PASS — `docker compose up -d redis`؛ volume حفظ شد؛ placeholderهای AOF خالی Redis 8 (RDB 15) پیش از شروع پشتیبان‌گیری و پاک شدند |
| `redis_version` واقعی از `INFO server` | `7.4.12` |
| اتصال از backend | `API_REDIS_PING= True` (exit 0) |
| اتصال از worker | `WORKER_REDIS_PING= True` (exit 0) |
| اجرای job واقعی arq | `ARQ_JOB_RESULT= {'status': 'ok'}` از `worker_probe` (exit 0) |
| rate limit | **NOT RUN** — در فاز صفر پیاده‌سازی نشده (فقط قرارداد `core/ratelimit.py`) |
| سلامت سرویس‌ها و لاگ | PASS — همهٔ سرویس‌ها healthy؛ لاگ Redis: `Redis version=7.4.12` |
| `uv lock --check` / `uv sync --locked --extra dev` | PASS (exit 0) |
| `ruff` / `mypy` / `pytest` (واحد) | PASS (exit 0) — 20 passed, 3 skipped |
| `make test-db` (معادل) | PASS (exit 0) — 23 passed روی PostgreSQL واقعی |
| فرانت‌اند lint/typecheck | PASS (exit 0) |
| تغییر schema/مهاجرت مخرب | انجام نشد — فقط `alembic upgrade head` روی دیتابیس تست در جریان `test-db` |

## وضعیت نهایی فاز صفر (2026-10-27)

- ADR-044: **accepted** (سرور Redis 7.4.12، کلاینت redis-py 5.3.1، arq 0.28.0) — OQ-012 بسته.
- ADR-045: **accepted** (جدول `index_meta`؛ تأیید مدل/migration/schema + قید یکتای جزئی + تست رد دو رکورد فعال).
- تمام معیارهای پذیرش `specs/phase-0.md` رعایت شدند؛ همهٔ فرمان‌های فوق در این بازبینی نهایی از نو اجرا و سبز شدند.
- شواهد نهایی: `redis_version=7.4.12`؛ `alembic_version=0002_index_meta_registry`؛ ستون‌های `index_meta` و ایندکس `uq_index_meta_active` تأیید شد؛ `/health`,`/ready`,`/version` = 200؛ همهٔ سرویس‌های Compose healthy؛ اتصال API/worker به Redis = PASS.
- **NOT RUN:** GitHub Actions (بدون مخزن git/remote)؛ پوشش ۷۰٪ (R-217) و آزمون بار (R-025) در دامنهٔ فازهای بعدی.
- فاز ۱ (`specs/phase-1.md`) شروع نشده و منتظر دستور مالک است.

## گزارش فاز ۱: هویت، OTP و نشست‌ها (2026-10-27)

| آیتم | نتیجه |
|---|---|
| Settings و `.env.example` | متغیرهای OTP/JWT/cookie/SMS/ADMIN افزوده و هماهنگ شدند |
| نرمال‌سازی E.164 | `core/phone.py` + تست |
| OTP | فقط digest با HMAC-SHA256 + pepper مستقل + `pepper_id` (پشتیبانی چرخش با `OTP_PREVIOUS_PEPPER`)؛ انقضا، مصرف یک‌باره، سقف تلاش |
| ضد-enumeration | پاسخ 202 یکسان در request؛ ثبت‌نام/ورود یک مسیر |
| کش‌ها | users، otp_challenges (expires_at ایندکس‌شده)، refresh_tokens (jti/token_hash یکتا، family)، admin_audit_log |
| migration | `0003_users_otp_refresh_audit` (Alembic؛ upgrade/downgrade) |
| Access/Refresh | JWT کوتاه‌عمر؛ refresh در کوکی HttpOnly/Secure/SameSite با فقط hash در DB؛ CSRF double-submit + بررسی Origin |
| Rotation/Reuse | چرخش با ابطال عضو قبلی؛ پنجرهٔ grace ۳۰ ثانیه؛ reuse پس از grace ← ابطال خانواده (ADR-046 پیشنهادی) |
| Rate limit | RedisRateLimiter (پنجرهٔ ثابت)؛ OTP fail-closed روی Redis |
| SMS | adapter Kavenegar با timeout صریح؛ mock در تست‌ها |
| seed-admin | CLI `python -m app.scripts.seed_admin` با تأیید تعاملی + `admin_audit_log` |
| تست‌ها | `uv run --locked pytest -q` → 42 passed + 11 skipped (schema)؛ `make test-db` → 53 passed |
| lint/typecheck | ruff PASS؛ mypy PASS (64 فایل) |
| Docker | استک بالا و healthy؛ `/health` `/ready` `/version` = 200 |
| NOT RUN | GitHub Actions (بدون مخزن/remote)؛ ارسال SMS واقعی Kavenegar (نیازمند راز production)؛ آزمون بار R-025 |

## ممیزی بستن فاز ۱ (Closure Audit — 2026-10-27)

- **ADRها:** ADR-003 accepted (پایه)؛ ADR-033/034 proposed (جزئیات‌بنداز، بدون supersede رسمی)؛ ADR-046 proposed و برای تایید مالک ارجاع شد (خودسرانه accepted نشد).
- **رقابت هم‌زمان refresh:** آسیب‌پذیری read-modify-write در چرخش کشف و با **compare-and-swap اتمیک** (`try_mark_revoked` با `UPDATE … WHERE revoked_at IS NULL`) رفع شد؛ تست `test_concurrent_rotation_cas_keeps_single_active` تضمین می‌کند فقط یک عضو فعال در هر خانواده می‌ماند.
- **تست‌های امنیتی موجود:** CSRF (miss/mismatch)، Origin نامجاز، توکن refresh نامعتبر، OTP منقضی و مصرف‌شده، سقف تلاش، multi-user isolation، reuse+grace (۱۵ در پنجره و پس از آن)، ابطال خانواده، logout.
- **پوشش R-217:** `pytest --cov=app --cov-fail-under=70` با تست‌های DB → **60 passed؛ Total 82.76%** (core/security 90%، phone 100%، ratelimit 92%، auth service 87%، sms 100%).
- **شکاف‌های پوشش:** `core/time.py` 0% (ابزار وقت؛ در فازهای بعدی استفاده می‌شود)، `scripts/seed_admin.py` 33% (مسیر تعاملی CLI)، `core/operations.py` 57% (مسیر خطای /ready)، placeholderهای فازهای بعدی (guard/inference/worker) خارج از دامنه.
- **NOT RUN (بدون تغییر):** ارسال SMS واقعی Kavenegar؛ GitHub Actions؛ آزمون بار R-025.

## اصلاح امنیتی refresh (ADR-046 — 2026-10-29)

- سیاست تأییدشدهٔ مالک پیاده‌سازی شد: بازپخش والدِ باطل در پنجرهٔ grace → **409 `refresh_conflict_retry`** بدون `Set-Cookie` و بدون چرخش/فرزند جدید؛ پس از پنجره → 401 `refresh_reuse_detected` + ابطال خانواده + لاگ.
- ذخیره‌سازی hash-only (R-106) بدون تغییر؛ بدون مهاجرت؛ محدودیت «گم‌شدن پاسخ برنده» مستند شد (بازیابی همان متن خام تضمین‌نشده).
- تست‌ها: هم‌زمانی (حداکثر یک چرخش)، 409 بدون Set-Cookie، عدم چرخش در بازپخش‌های تکراری، بازترتیب پاسخ‌ها، ابطال پس از grace.
- خروجی: `make test-db` → 63 passed؛ coverage → 82.69%؛ ruff/mypy PASS.

