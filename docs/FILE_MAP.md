# نقشهٔ کامل فایل‌ها — Darsyar AI v4

این فهرست برای قرارداد `R-008` و `R-231` نگهداری می‌شود. فایل `docs/FILE_MAP.md` خود این فهرست را نگه می‌دارد. فایل‌هایی که به‌عنوان placeholder ثبت شده‌اند، قابلیت فعال یا پیاده‌سازی‌شده محسوب نمی‌شوند. فایل‌های `backend/uv.lock` و `frontend/package-lock.json` در اجرای فاز صفر (2026-10-27) از registry واقعی تولید شده‌اند.

| مسیر | مسئولیت |
|---|---|
| `.dockerignore` | محدودکردن محتوای ارسالی به build context. |
| `.env.example` | الگوی تنظیمات؛ فقط placeholder، بدون راز واقعی. |
| `.github/workflows/ci.yml` | خط CI برای lock، migration، lint و تست. |
| `.gitignore` | جلوگیری از ثبت اسرار، cacheها و خروجی ساخت. |
| `AGENTS.md` | قرارداد مهندسی نسخهٔ ۴؛ مرجع قواعد R-NNN. |
| `KILOCODE_START_HERE.md` | پرامپت کنترل‌شده؛ فقط فاز صفر را اجرا می‌کند. |
| `MANIFEST.md` | دامنهٔ بسته و محدودیت‌های اعتبارسنجی. |
| `Makefile` | دستورهای توسعه، تست، migration، سلامت و lint. |
| `README.md` | راهنمای شروع و محدودیت‌های بسته. |
| `ROADMAP.md` | فازبندی رسمی و ترتیب وابستگی‌ها. |
| `backend/.dockerignore` | پیکربندی و اسکلت اجرایی backend. |
| `backend/.python-version` | پیکربندی و اسکلت اجرایی backend. |
| `backend/Dockerfile` | پیکربندی و اسکلت اجرایی backend. |
| `backend/README.md` | پیکربندی و اسکلت اجرایی backend. |
| `backend/alembic/env.py` | پیکربندی و migration صریح دیتابیس. |
| `backend/alembic/script.py.mako` | پیکربندی و migration صریح دیتابیس. |
| `backend/alembic/versions/0001_enable_vector_and_trgm.py` | پیکربندی و migration صریح دیتابیس. |
| `backend/alembic/versions/0002_index_meta_registry.py` | مهاجرت جدول `index_meta` (R-087)؛ ایجادشده در فاز صفر. |
| `backend/alembic/versions/0003_users_otp_refresh_audit.py` | مهاجرت users/otp_challenges/refresh_tokens/admin_audit_log (فاز ۱). |
| `backend/alembic.ini` | پیکربندی و اسکلت اجرایی backend. |
| `backend/app/__init__.py` | پیکربندی و اسکلت اجرایی backend. |
| `backend/app/agent/__init__.py` | محل orchestration و nodeهای آینده. |
| `backend/app/agent/nodes/.gitkeep` | محل orchestration و nodeهای آینده. |
| `backend/app/agent/nodes/__init__.py` | محل orchestration و nodeهای آینده. |
| `backend/app/api/__init__.py` | روتر/وابستگی API؛ برخی فایل‌ها placeholder فاز آینده‌اند. |
| `backend/app/api/deps.py` | وابستگی‌ها: get_db، Redis، rate-limit و IP. |
| `backend/app/api/v1/__init__.py` | روتر/وابستگی API؛ برخی فایل‌ها placeholder فاز آینده‌اند. |
| `backend/app/api/v1/admin/.gitkeep` | روتر/وابستگی API؛ برخی فایل‌ها placeholder فاز آینده‌اند. |
| `backend/app/api/v1/admin/__init__.py` | روتر/وابستگی API؛ برخی فایل‌ها placeholder فاز آینده‌اند. |
| `backend/app/api/v1/auth.py` | مسیرهای OTP/verify/refresh/logout با CSRF و rate-limit (فاز ۱). |
| `backend/app/api/v1/billing.py` | روتر/وابستگی API؛ برخی فایل‌ها placeholder فاز آینده‌اند. |
| `backend/app/api/v1/chat.py` | روتر/وابستگی API؛ برخی فایل‌ها placeholder فاز آینده‌اند. |
| `backend/app/api/v1/documents.py` | روتر/وابستگی API؛ برخی فایل‌ها placeholder فاز آینده‌اند. |
| `backend/app/api/v1/health.py` | روتر/وابستگی API؛ برخی فایل‌ها placeholder فاز آینده‌اند. |
| `backend/app/api/v1/router.py` | تجمیع health + auth (فاز ۱). |
| `backend/app/api/v1/router.py` | روتر/وابستگی API؛ برخی فایل‌ها placeholder فاز آینده‌اند. |
| `backend/app/api/v1/sessions.py` | روتر/وابستگی API؛ برخی فایل‌ها placeholder فاز آینده‌اند. |
| `backend/app/core/__init__.py` | تنظیمات، امنیت پایه، لاگ، خطا یا عملیات مرکزی. |
| `backend/app/core/config.py` | تنظیمات، امنیت پایه، لاگ، خطا یا عملیات مرکزی. |
| `backend/app/core/errors.py` | تنظیمات، امنیت پایه، لاگ، خطا یا عملیات مرکزی. |
| `backend/app/core/logging.py` | تنظیمات، امنیت پایه، لاگ، خطا یا عملیات مرکزی. |
| `backend/app/core/operations.py` | تنظیمات، امنیت پایه، لاگ، خطا یا عملیات مرکزی. |
| `backend/app/core/phone.py` | نرمال‌سازی E.164 (فاز ۱). |
| `backend/app/core/ratelimit.py` | قرارداد و RedisRateLimiter (فاز ۱). |
| `backend/app/core/security.py` | OTP HMAC/pepper، JWT، digest و تولید توکن (فاز ۱). |
| `backend/app/core/time.py` | تنظیمات، امنیت پایه، لاگ، خطا یا عملیات مرکزی. |
| `backend/app/db/__init__.py` | اتصال پایگاه داده، Base و بررسی schema. |
| `backend/app/db/base.py` | اتصال پایگاه داده، Base و بررسی schema. |
| `backend/app/db/session.py` | اتصال پایگاه داده، Base و بررسی schema. |
| `backend/app/guard.py` | پیکربندی و اسکلت اجرایی backend. |
| `backend/app/inference/__init__.py` | پوستهٔ inference؛ مدل سنگین در فاز صفر لود نمی‌شود. |
| `backend/app/inference/main.py` | پوستهٔ inference؛ مدل سنگین در فاز صفر لود نمی‌شود. |
| `backend/app/inference/models.py` | پوستهٔ inference؛ مدل سنگین در فاز صفر لود نمی‌شود. |
| `backend/app/main.py` | پیکربندی و اسکلت اجرایی backend. |
| `backend/app/models/.gitkeep` | محل مدل‌های SQLAlchemy؛ فعلاً اسکلت. |
| `backend/app/models/__init__.py` | رجیستری مدل‌های SQLAlchemy؛ `IndexMeta`, `User`, `OtpChallenge`, `RefreshToken`, `AdminAuditLog`. |
| `backend/app/models/admin_audit_log.py` | مدل لاگ حسابرسی ادمین append-only (فاز ۱). |
| `backend/app/models/index_meta.py` | مدل جدول `index_meta` با سبک `Mapped[]` (R-042/R-087). |
| `backend/app/models/otp_challenge.py` | مدل چالش OTP؛ فقط digest+pepper_id (فاز ۱). |
| `backend/app/models/refresh_token.py` | مدل توکن refresh؛ hash، family و ابطال (فاز ۱). |
| `backend/app/models/user.py` | مدل کاربر/ادمین با phone E.164 و soft delete (فاز ۱). |
| `backend/app/repositories/__init__.py` | لایهٔ دسترسی داده و مالکیت. |
| `backend/app/repositories/admin_audit_log.py` | درج لاگ حسابرسی (فاز ۱). |
| `backend/app/repositories/otp_challenges.py` | دسترسی چالش‌های OTP (فاز ۱). |
| `backend/app/repositories/refresh_tokens.py` | دسترسی و ابطال خانوادهٔ refresh (فاز ۱). |
| `backend/app/repositories/users.py` | دسترسی کاربران با مالکیت/soft delete (فاز ۱). |
| `backend/app/schemas/.gitkeep` | محل schemaهای Pydantic. |
| `backend/app/schemas/__init__.py` | محل schemaهای Pydantic. |
| `backend/app/schemas/auth.py` | schemaهای OTP/nشست (فاز ۱). |
| `backend/app/scripts/__init__.py` | پیکربندی و اسکلت اجرایی backend. |
| `backend/app/scripts/seed_admin.py` | CLI ادمین اولیه با تأیید و حسابرسی (فاز ۱). |
| `backend/app/services/__init__.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/auth.py` | سرویس دامنهٔ OTP و چرخش/ابطال refresh (فاز ۱). |
| `backend/app/services/citation.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/embedding.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/ingestion/.gitkeep` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/ingestion/__init__.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/learning/.gitkeep` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/learning/__init__.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/payment.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/provider.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/quiz/.gitkeep` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/quiz/__init__.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/quota.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/rerank.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/reservation.py` | سرویس دامنهٔ مالی Slice A: reserve/settle/release/reconcile (ADR-035). |
| `backend/app/models/credit_account.py` | مدل projection اعتبار (Slice A فاز ۲). |
| `backend/app/models/credit_ledger.py` | مدل ledger append-only (Slice A فاز ۲). |
| `backend/app/models/reservation.py` | مدل رزرو پایدار (Slice A فاز ۲). |
| `backend/app/repositories/credit_accounts.py` | دسترسی projection با قفل ردیف (Slice A). |
| `backend/app/repositories/credit_ledger.py` | دسترسی ledger فقط-درج (Slice A). |
| `backend/app/repositories/reservations.py` | دسترسی رزروها و گذار شرطی (Slice A). |
| `backend/alembic/versions/0004_financial_core.py` | مهاجرت هستهٔ مالی: accounts/ledger/reservations + trigger (Slice A). |
| `backend/alembic/versions/0005_ledger_immutability_trigger.py` | مهاجرت سخت‌سازی: trigger رد UPDATE/DELETE روی credit_ledger. |
| `backend/alembic/versions/0006_payment_transactions.py` | مهاجرت تراکنش‌های پرداخت + trigger ترمینال (Slice B). |
| `backend/alembic/versions/0007_product_catalog.py` | مهاجرت کاتالوگ محصولات + seed Basic/Pro (Slice B). |
| `backend/app/models/payment_transaction.py` | مدل payment_transactions (ADR-047). |
| `backend/app/models/product_catalog.py` | مدل کاتالوگ محصولات. |
| `backend/app/repositories/payment_transactions.py` | دسترسی پرداخت‌ها و گذارهای شرطی. |
| `backend/app/repositories/product_catalog.py` | دسترسی کاتالوگ و به‌روزرسانی مع audit. |
| `backend/app/services/payment.py` | سرویس پرداخت: checkout/verify/finalize/reconcile/resolution. |
| `backend/app/services/payment_provider.py` | adapter زرین‌پال v4 (تبدیل تومان/ریال فقط اینجا). |
| `backend/app/schemas/billing.py` | schemaهای checkout/payment status. |
| `backend/app/api/v1/billing.py` | مسیرهای checkout/callback/payments. |
| `backend/app/scripts/upsert_product.py` | CLI operator برای تغییر کاتالوگ با audit. |
| `backend/tests/test_zarinpal_provider.py` | تست واحد adapter با respx. |
| `backend/tests/test_billing_db.py` | تست‌های یکپارچهٔ پرداخت روی PostgreSQL واقعی. |
| `backend/alembic/versions/0008_usage_events.py` | مهاجرت usage_events append-only + trigger (Slice C-1). |
| `backend/alembic/versions/0009_reconciliation_alerts.py` | مهاجرت هشدارهای تطبیق با قید جزئی فعال (Slice C-1). |
| `backend/app/models/usage_event.py` | مدل رویداد مصرف. |
| `backend/app/models/reconciliation_alert.py` | مدل هشدار تطبیق. |
| `backend/app/repositories/usage_events.py` | دسترسی usage؛ فقط درج/شمارش بازه. |
| `backend/app/repositories/reconciliation_alerts.py` | دسترسی هشدار؛ upsert فعال + resolve. |
| `backend/app/services/usage.py` | سرویس ثبت رویداد مصرف idempotent. |
| `backend/app/services/fair_use.py` | شمارش بازهٔ صریح (بدون قواعد تجاری). |
| `backend/app/services/reconcile.py` | تطبیق read-only ledger↔projection + هشدار. |
| `backend/tests/test_usage_reconcile_db.py` | تست‌های یکپارچهٔ Slice C-1 روی PostgreSQL واقعی. |
| `backend/tests/test_finance_db.py` | تست‌های یکپارچهٔ مالی روی PostgreSQL واقعی (Slice A). |
| `backend/app/services/retrieval/.gitkeep` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/retrieval/__init__.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/settings_store.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/sms.py` | adapter پیامک Kavenegar (فاز ۱). |
| `backend/app/services/storage.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/websearch.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/app/services/worker.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
| `backend/pyproject.toml` | پیکربندی و اسکلت اجرایی backend. |
| `backend/tests/conftest.py` | تست پایه یا placeholder برای تست‌های مرحله‌ای. |
| `backend/tests/integration/.gitkeep` | تست پایه یا placeholder برای تست‌های مرحله‌ای. |
| `backend/tests/security/.gitkeep` | تست پایه یا placeholder برای تست‌های مرحله‌ای. |
| `backend/tests/test_config.py` | تست پایه یا placeholder برای تست‌های مرحله‌ای. |
| `backend/tests/test_errors.py` | تست پایه یا placeholder برای تست‌های مرحله‌ای. |
| `backend/tests/test_health.py` | تست پایه یا placeholder برای تست‌های مرحله‌ای. |
| `backend/tests/test_inference_shell.py` | تست شکل خطای استاندارد و صداقت shell سرویس inference. |
| `backend/tests/test_logging.py` | تست پایه یا placeholder برای تست‌های مرحله‌ای. |
| `backend/tests/test_phone.py` | تست نرمال‌سازی E.164 (فاز ۱). |
| `backend/tests/test_ratelimit.py` | تست RedisRateLimiter (فاز ۱). |
| `backend/tests/test_schema_baseline.py` | تست schema روی PostgreSQL واقعی (فقط `make test-db`). |
| `backend/tests/test_security_primitives.py` | تست پایه یا placeholder برای تست‌های مرحله‌ای. |
| `backend/tests/test_security_tokens.py` | تست JWT/OTP/token (فاز ۱). |
| `backend/tests/test_auth_api.py` | تست مسیرهای auth با سرویس جایگزین؛ بدون DB/شبکه. |
| `backend/tests/test_auth_db.py` | تست یکپارچهٔ auth روی PostgreSQL واقعی (DARSYAR_TEST_DB). |
| `backend/tests/test_sms_provider.py` | تست adapter Kavenegar با respx (R-216). |
| `docker-compose.yml` | سرویس‌های توسعه‌ای؛ migrate یک‌بارمصرف و inference داخلی. |
| `docs/API_CONTRACT.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/ARCHITECTURE.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/CITATION_FORMAT.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/CONSENT_AND_PRIVACY_DRAFT.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/DATA_MODEL.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/DECISIONS.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/DEPLOYMENT.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/GRADE_MAPPING.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/INCIDENTS.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/OPEN_QUESTIONS.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/PRODUCT_SPEC.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/RAG_EVALUATION_PLAN.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/REFUND_POLICY.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/RESOURCE_LAYOUT.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/SECURITY_THREAT_MODEL.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/TECH_STACK.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/TEST_STRATEGY.md` | سند مرجع طراحی، امنیت، عملیات یا ریسک. |
| `docs/adr/.gitkeep` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-001-mvp-scope.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-002-data-source-of-truth.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-003-authentication-security.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-004-streaming-transport.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-005-server-validated-citations.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-006-heavy-model-workers.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-007-credit-ledger.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-008-configuration-secrets.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-009-dependency-policy.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-010-grade-filter.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-011-admin-bootstrap.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-012-web-fallback.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-024-resource-licensing.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-032-mvp-scope.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-033-otp-hmac-pepper.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-034-refresh-cookie-csrf.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-035-postgres-reservation.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-036-inference-mode.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-037-grade-mapping.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-038-edition-metadata.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-039-partial-response-billing.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-040-billing-period-timezone.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-041-stack-baseline.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-042-data-retention.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-043-rag-golden-dataset.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
| `docs/adr/ADR-044-redis-client-pin.md` | تصمیم تأییدشدهٔ مالک: سرور Redis 7.4.12 + کلاینت 5.x + arq (accepted). |
| `docs/adr/ADR-045-baseline-index-meta.md` | تصمیم تأییدشدهٔ مالک: جدول `index_meta` در خط پایه (accepted). |
| `docs/adr/ADR-046-refresh-grace-semantics.md` | سیاست تأییدشدهٔ grace: 409 بدون چرخش؛ ابطال خانواده پس از پنجره (accepted). |
| `docs/adr/ADR-047-payment-checkout-zarinpal.md` | پیشنهاد خرید یک‌بارهٔ Basic/Pro و زرین‌پال (proposed). |
| `docs/licenses/README.md` | سیاست ثبت مجوز و منشأ منبع آموزشی. |
| `frontend/.dockerignore` | ساخت/پیکربندی فرانت‌اند. |
| `frontend/.npmrc` | ساخت/پیکربندی فرانت‌اند. |
| `frontend/Dockerfile` | ساخت/پیکربندی فرانت‌اند. |
| `frontend/eslint.config.js` | ساخت/پیکربندی فرانت‌اند. |
| `frontend/index.html` | ساخت/پیکربندی فرانت‌اند. |
| `frontend/nginx.conf` | ساخت/پیکربندی فرانت‌اند. |
| `frontend/package.json` | ساخت/پیکربندی فرانت‌اند. |
| `frontend/public/.gitkeep` | ساخت/پیکربندی فرانت‌اند. |
| `frontend/src/App.tsx` | رابط React/TypeScript اولیه. |
| `frontend/src/api/.gitkeep` | لایهٔ یگانهٔ HTTP و fetch streaming. |
| `frontend/src/api/client.ts` | لایهٔ یگانهٔ HTTP و fetch streaming. |
| `frontend/src/api/sse.ts` | لایهٔ یگانهٔ HTTP و fetch streaming. |
| `frontend/src/components/.gitkeep` | رابط React/TypeScript اولیه. |
| `frontend/src/context/.gitkeep` | رابط React/TypeScript اولیه. |
| `frontend/src/i18n/ar.ts` | رشته‌های رابط برای fa/en/ar. |
| `frontend/src/i18n/en.ts` | رشته‌های رابط برای fa/en/ar. |
| `frontend/src/i18n/fa.ts` | رشته‌های رابط برای fa/en/ar. |
| `frontend/src/i18n.ts` | رابط React/TypeScript اولیه. |
| `frontend/src/index.css` | رابط React/TypeScript اولیه. |
| `frontend/src/main.tsx` | رابط React/TypeScript اولیه. |
| `frontend/src/pages/.gitkeep` | رابط React/TypeScript اولیه. |
| `frontend/src/styles/.gitkeep` | رابط React/TypeScript اولیه. |
| `frontend/src/vite-env.d.ts` | رابط React/TypeScript اولیه. |
| `frontend/tsconfig.app.json` | ساخت/پیکربندی فرانت‌اند. |
| `frontend/tsconfig.json` | ساخت/پیکربندی فرانت‌اند. |
| `frontend/tsconfig.node.json` | ساخت/پیکربندی فرانت‌اند. |
| `frontend/vite.config.ts` | ساخت/پیکربندی فرانت‌اند. |
| `infra/.gitkeep` | پیکربندی زیرساخت نمونه؛ انتشار عمومی بدون بازبینی ممنوع. |
| `infra/nginx/nginx.conf` | پیکربندی زیرساخت نمونه؛ انتشار عمومی بدون بازبینی ممنوع. |
| `resources/.gitkeep` | محل منابع دارای مجوز؛ کتاب‌ها در این بسته وجود ندارند. |
| `resources/README.md` | محل منابع دارای مجوز؛ کتاب‌ها در این بسته وجود ندارند. |
| `scripts/check_compose_health.py` | اسکریپت smoke، بررسی سلامت یا اجرای تست DB. |
| `scripts/run_test_db.py` | اسکریپت smoke، بررسی سلامت یا اجرای تست DB. |
| `scripts/smoke_test.py` | اسکریپت smoke، بررسی سلامت یا اجرای تست DB. |
| `specs/README.md` | راهنمای ساختار specهای اجرایی. |
| `specs/phase-0.md` | مشخصات اجرایی فاز؛ دامنه، خارج از دامنه و معیار پذیرش. |
| `specs/phase-1.md` | مشخصات اجرایی فاز؛ دامنه، خارج از دامنه و معیار پذیرش. |
| `specs/phase-2.md` | مشخصات اجرایی فاز؛ دامنه، خارج از دامنه و معیار پذیرش. |
| `specs/phase-3.md` | مشخصات اجرایی فاز؛ دامنه، خارج از دامنه و معیار پذیرش. |
| `specs/phase-4.md` | مشخصات اجرایی فاز؛ دامنه، خارج از دامنه و معیار پذیرش. |
| `specs/phase-5.md` | مشخصات اجرایی فاز؛ دامنه، خارج از دامنه و معیار پذیرش. |
| `specs/phase-6.md` | مشخصات اجرایی فاز؛ دامنه، خارج از دامنه و معیار پذیرش. |
| `specs/phase-7.md` | مشخصات اجرایی فاز؛ دامنه، خارج از دامنه و معیار پذیرش. |
| `specs/phase-8.md` | مشخصات اجرایی فاز؛ دامنه، خارج از دامنه و معیار پذیرش. |
| `specs/phase-9.md` | مشخصات اجرایی فاز؛ دامنه، خارج از دامنه و معیار پذیرش. |
| `uploads/.gitkeep` | محل توسعه‌ای فایل‌ها؛ محتوای واقعی در Git قرار نگیرد. |

## مسیرهای تولیدشده در فاز صفر (2026-10-27)

| مسیر | مسئولیت |
|---|---|
| `backend/uv.lock` | lockfile دقیق پایتون؛ تولیدشده با `uv lock` از PyPI واقعی. |
| `frontend/package-lock.json` | lockfile دقیق npm؛ تولیدشده با `npm install --package-lock-only` از registry واقعی. |
