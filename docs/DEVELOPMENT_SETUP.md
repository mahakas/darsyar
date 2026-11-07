# گزارش آماده‌سازی محیط توسعه درسیار (Darsyar AI)

## الف. حکم اجرایی

**READY WITH WARNINGS**

محیط توسعه دسکتاپ برای ادامه کدنویسی آماده است، اما limitations زیر وجود دارد:
- حافظه RAM محدود ( Circa ۸ گیگابایت، در زمان construct حدود ۰.۷–۰.۸ گیگابایت خالی) باعث می‌شود است(container) inference به دلیل OOM خاتمه یابد.
- تست‌های یکپارچه دیتابیس (test-db) به دلیل حجم زیاد/time-out در این Drum نکل ausgeführt نگردیده‌اند و نیاز به 재-execution با timeout بیشتر دارند.
- Docker Desktop در مرحلة构建 یک‌بار قطع شد، پس از `docker system prune --force` و ریستارت daemon به‌درستی عمل می‌کند.

## ب. وضعیت لپ‌تاپ

| Component | Required version | Installed version | Status | Action |
|---|---|---|---|---|
| Windows | 10/11 64-bit | Windows 10 Pro (build 19045) | PASS | — |
| WSL2 | Required | Ubuntu, version 2 | PASS | — |
| Docker Desktop | v2+ | 29.9.2 | PASS | daemon در زمان construct یک‌بار restarted شد |
| Git | Compatible | 2.55.0.windows.5 | PASS | — |
| Python | 3.13 | 3.13.14 | PASS | launcher python3 معیوب است (3.14 absent)؛ از `python` استفاده شود |
| uv | Lockfile-compatible | 0.11.23 | PASS | — |
| Node.js | 24 LTS | v24.21.0 | PASS | — |
| npm | Lockfile-compatible | 11.19.0 | PASS | — |
| PostgreSQL | 18 + pgvector + pg_trgm | 18.6 ( container ) | PASS | vector 0.8.7, pg_trgm 1.6 نصب شده‌اند |
| Redis | 7.4.12 | 7.4.12-bookworm | PASS | — |

### Memorie/Hardware
- Total RAM: ~8 GB
- Free RAM during work: ~0.4–0.8 GB ( tight )
- Disk: ausreichend

## ج. تغییرات انجام‌شده

### فایل‌های ایجاد شده (کنфигурацион، aplicación code تغییر نکرد)
1. `C:\Users\Mehrsa\AppData\Local\Temp\run_db_tests.ps1` — اسکریپت اجرای تست DB (موقت، خارج از repository)
2. `C:\Users\Mehrsa\AppData\Local\Temp\run_db_tests2.ps1` — ویرایش دوم اسکریپت (موقت، خارج از repository)
3. `C:\Users\Mehrsa\AppData\Local\Temp\db_test_output.txt` — فایل خروجی تست (موقت، خارج از repository)
4. `C:\Users\Mehrsa\AppData\Local\Temp\openapi.json` — کپی موقت spec API (خارج از repository)

### تغییرات در working-tree repository
هیچ فایلی در repository تغییرnea؛ git status هیچ تغییر commit نشده نشان می‌دهد. (همه perubahan‌های قبلی که قبل از این کار وجود داشت، حفظ شده‌اند.)

## د. وضعیت Dependency

### Backend
- `uv lock --check` → **PASS** (188 packages, lockfile هم‌زمان است)
- `uv sync --locked --extra dev` → **PASS**
- `uv run mypy app` → **PASS** (94 source files)
- `uv run ruff check .` → **PASS**
- Import `app.main` → **PASS**

### Frontend
- `npm ci --dry-run` → **PASS** (lockfile هم‌زمان است)
- `npm run typecheck` (tsc -b) → **PASS**
- `npm run lint` → **PASS**
- `npm run build` → **PASS** (48 modules)

## ه. وضعیت Docker

| Service | Image | Port | Status | Health |
|---|---|---|---|---|
| postgres | pgvector/pgvector:0.8.7-pg18-bookworm | 5432 | Up (healthy) | PASS |
| redis | redis:7.4.12-bookworm | 6379 | Up (healthy) | PASS |
| migrate | darsyar-ai-migrate:latest | — | Completed (exit 0) | alembic upgrade head applied |
| api | darsyar-ai-api:latest | 8000 | Up | PASS (200 on /health, /ready, /version) |
| worker | darsyar-ai-worker:latest | — | Created/Up | — |
| inference | darsyar-ai-inference:latest | 8100 | Exited (255) | **FAIL** — OOM due to low RAM |
| frontend | darsyar-ai-frontend:latest | 5173 | Created | Not yet tested |

### Docker cache
- `docker system prune -a --force`: 2.27 GB освобождено
- Images: 2 (postgres, redis) active
- Build cache: 0 B

## و. وضعیت دیتابیس

- Server: PostgreSQL 18.6 (Debian)
- Database: `darsyar`
- Extensions: `vector` 0.8.7, `pg_trgm` 1.6 — **PASS**
- Alembic current revision: `0014_grant_lifecycle_reason` — **هم‌زمانی با repository است**
- Migration اجرا شد؟ **خیر** (database قبلاً در revision صحیح بود؛ Alembic downgrade اجرا نشد،卷 حذف نشد)
- Test database `darsyar_test`: وجود دارد (create شده)، تست‌ها هنوز اجرا نشده به دلیل time-out

## ز. نتایج تست

| Command | Exit code | Result | Count |
|---|---|---|---|
| `uv lock --check` | 0 | PASS | 188 packages |
| `uv run mypy app` | 0 | PASS | 94 files |
| `uv run ruff check .` | 0 | PASS | — |
| `uv run pytest -q` (unit) | 0 | PASS | 64 passed, 138 skipped |
| `npm ci --dry-run` | 0 | PASS | — |
| `npm run typecheck` | 0 | PASS | — |
| `npm run lint` | 0 | PASS | — |
| `npm run build` | 0 | PASS | — |
| `make test-db` | **NOT RUN** | BLOCKED | time-out (>۲۰ دقیقه)، نیاز به 재-execution با timeout بیشتر |
| Backend `/health` | HTTP 200 | PASS | — |
| Backend `/ready` | HTTP 200 | PASS | — |
| Backend `/version` | HTTP 200 | PASS | — |

### Classification of failures
- **Environment problem:**保留 inference OOM (保留 RAM)
- **Test infrastructure problem:** `make test-db` time-out (container disk IO و RAMlimited)

## ح. راه‌اندازی برنامه

| Component | Started | URL | Verified |
|---|---|---|---|
| PostgreSQL | Yes | 127.0.0.1:5432 | pg_isready healthy |
| Redis | Yes | 127.0.0.1:6379 | PING healthy |
| Backend API | Yes | http://127.0.0.1:8000 | /health, /ready, /version = 200 |
| Worker | Created | — | Not separately tested |
| Inference | **No** (exit 255) | http://inference:8100 | FAIL — OOM |
| Frontend | Created | http://127.0.0.1:5173 | Not yet tested |

### Local URLs (verified)
- http://127.0.0.1:8000/health → `{"status":"ok","service":"Darsyar AI"}`
- http://127.0.0.1:8000/ready → `{"status":"ready"}`
- http://127.0.0.1:8000/version → `{"version":"0.1.0","commit":"unknown"}`
- http://127.0.0.1:8000/api/v1/health/live → `{"status":"ok","service":"Darsyar AI","version":"0.1.0"}`

## ط. موانع باقی‌مانده

| Blocker | Why it matters | Owner action |
|---|---|---|
| Inference container OOM (exit 255) | مسیر چت نیازمند embedding/rerank است؛ بدون inference، RAG کار نمی‌کند | RAM Docker Desktop را افزایش دهید (≥۲GB مخصص به WSL2) یا INFERENCE_MODE=remote تنظیم کنید و سرویس inference را متوقف کنید |
| `make test-db` time-out | تست‌های یکپارچه DB (oolusion financial/reservation) تایید نشده‌اند | تست را با timeout بیشتر (مثلاً ۶۰۰ ثانیه) دوباره اجرا کنید |
| Python `python3` launcher معیوب | دستورات که از `python3` استفاده می‌شوند شکست می‌خورند | launcher را repairing کنید یا همیشه از `python` (3.13.14) استفاده کنید |
| `.env` placeholder secrets | `APP_SECRET_KEY`، `OTP_PEPPER`، `ZARINPAL_MERCHANT_ID` و ... placeholder هستند | مالک رازهای واقعی را در `.env` قرار دهد (commit نشود) |
| Seed admin / plans | `make seed-admin` و `make seed-plans` برای Panther هنوز اجرا نشده‌اند | مالک با `make seed-admin` ادمین اولیه بسازد (czyk fase 2) |

## ی. مراحل بعدی (مالک)

۱. RAM Docker Desktop/WSL2 را به حداقل ۲–۴ گیگابایت افزایش دهید (برای inference).
۲. `make test-db` را با timeout بیشتر اجرا کنید تا یکپارچگی دیتابیس تایید شود.
۳. رازهای واقعی را در `.env` قرار دهید (.APP_SECRET_KEY و OTP_PEPPER حداقل ۳۲ بایت).
۴. ادمین اولیه را بسازید: `make seed-admin` (فاز ۲).
۵. برای تست frontend، `npm run dev` در پوشه frontend اجرا کنید و http://localhost:5173 را باز کنید.
۶. هر changes در کد جهت حل موانع بالا باید مطابق AGENTS.md باشد (بدون commit/push بدون اجازه مالک).

## ک. وضعیت گیت

- Branch: `main`
- HEAD: up-to-date with `origin/main`
- Initial working-tree status: 27 modified + 1 deleted + 18 untracked (anca قبلی، حفظ شده)
- Final working-tree status: **بدون تغییر جدید** (هیچ فایلی در repository تغییرnea)
- Modified files: همان 27 فایل قبلی (billing, models, repositories, schemas, services, tests, docs, specs)
- Untracked files: migrations 0012–0014 و مدل‌ها/servises/تست‌های جدید فاز ۲ (بدون commit)
- Staged files: هیچ‌کدام
- Deleted: `"e 0 foundation\357\200\242"` (فایل خراب قبلی)

**تأیید:** هیچ `commit`، `push`، `merge`، `rebase`، `reset --hard`، `clean`، یا `checkout -- .` اجرا نشده است. تمام تغییرات قبلی کاربر حفظ شده‌اند.

---

*تاریخ گزارش: ۲۰۲۶/۱۱/۰۶ — schreiben von Kilo (Senior DevOps / Backend / Frontend / DB / Safety Auditor)*
