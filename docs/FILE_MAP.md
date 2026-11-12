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
| `README.md` | وضعیت فعلی، فناوری‌ها، راه‌اندازی سریع و لینک راهنمای مبتدی. |
| `docs/BEGINNER_SETUP_GUIDE_FA.md` | راهنمای کامل فارسی راه‌اندازی ویندوز/WSL2، Docker، .env، ارائه‌دهندگان AI، اجرای سرویس‌ها، تست و عیب‌یابی مبتدی. |
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
| `backend/app/api/v1/health.py` | روتر/وابستگی API؛ برخی فایل‌ها placeholder فاز آینده‌اند. || `backend/app/api/v1/router.py` | تجمیع health + auth (فاز ۱). |
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
| `backend/app/services/citation.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. || `backend/app/services/embedding.py` | سرویس/adapter؛ placeholder تا فاز مربوطه مگر آنکه در کد توضیح داده شده باشد. |
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
| `backend/app/services/usage.py` | سرویس ثبت رویداد مصرف idempotent. || `backend/app/services/fair_use.py` | شمارش بازهٔ صریح (بدون قواعد تجاری). |
| `backend/app/services/reconcile.py` | تطبیق read-only ledger↔projection + هشدار. |
| `backend/tests/test_usage_reconcile_db.py` | تست‌های یکپارچهٔ Slice C-1 روی PostgreSQL واقعی. |
| `backend/alembic/versions/0010_free_grant_partial_unique.py` | ایندکس جزئی یک‌باربودن free_grant (ADR-048). |
| `backend/app/services/free_grant.py` | سرویس گرانت رایگان یک‌بار (ساخت کاربر+حساب+ledger یکجا). |
| `backend/tests/test_free_grant_db.py` | تست‌های یکپارچهٔ گرانت رایگان روی PostgreSQL واقعی. |
| `backend/alembic/versions/0011_abuse_flags.py` | مهاجرت جدول abuse_flags (ADR-050). |
| `backend/app/models/abuse_flag.py` | مدل پرچم Fair-Use. |
| `backend/app/repositories/abuse_flags.py` | دسترسی پرچم؛ درج اتمیک و حل شرطی. |
| `backend/tests/test_fair_use_period.py` | تست واحد محاسبهٔ دورهٔ ماهانه (ADR-040). |
| `backend/tests/test_fair_use_db.py` | تست‌های یکپارچهٔ Fair-Use روی PostgreSQL واقعی. |
| `backend/alembic/versions/0012_plan_entitlements.py` | مهاجرت پلن/entitlement + grants + cancellation/refund (ADR-052). |
| `backend/app/models/plan_entitlement.py` | مدل entitlement پلن. |
| `backend/app/models/credit_grant.py` | مدل سبد اعتبار. |
| `backend/app/models/cancellation_request.py` | مدل درخواست لغو. |
| `backend/app/models/refund_record.py` | مدل رکورد بازپرداخت. |
| `backend/app/repositories/entitlements.py` | دسترسی entitlement/grant/cancellation/refund. |
| `backend/app/services/plans.py` | سرویس پلن: فعال‌سازی/تمدید/انقضا/لغو/بازپرداخت. |
| `backend/tests/test_plans_db.py` | تست‌های یکپارچهٔ پلن روی PostgreSQL واقعی. |
| `docs/adr/ADR-052-plan-entitlements.md` | مدل entitlement و تخصیص اعتبار (accepted). |
| `backend/alembic/versions/0013_grant_allocation.py` | مهاجرت تخصیص grant→رزرو (reservation_credit_allocations؛ reserved_amount). |
| `backend/app/models/reservation_allocation.py` | مدل تخصیص grant→رزرو. |
| `backend/tests/test_grant_allocation_db.py` | تست‌های تخصیص/EFF/Unlimited/هم‌زمانی روی PostgreSQL واقعی. |
| `docs/adr/ADR-053-grant-allocation.md` | تخصیص grant→رزرو و حسابداری منبع‌محور (accepted). |
| `backend/tests/test_finance_db.py` | تست‌های یکپارچهٔ مالی روی PostgreSQL واقعی (Slice A). |
| `backend/tests/test_concurrency_hardening_db.py` | تست‌های هم‌زمانی مرزهای reserve/settle در برابر admin_void + گاردهای post-void + natural_expiry (عکس ۲). |
| `backend/tests/test_expiry_accounting_db.py` | تست‌های حسابداری انقضای طبیعی با رزروهای فعال: فقط بخش غیررزروشده باطل می‌شود (رفع نقص plans.py). |
| `backend/tests/test_cancel_refund_accounting_db.py` | تست‌های حسابداری لغو فوری/refund با رزروهای فعال: فقط بخش غیررزروشده باطل می‌شود (رفع نقص plans.py). |
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
| `backend/tests/test_config.py` | تست پایه یا placeholder برای تست‌های مرحله‌ای. || `backend/tests/test_errors.py` | تست پایه یا placeholder برای تست‌های مرحله‌ای. |
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
| `docs/adr/ADR-009-dependency-policy.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. || `docs/adr/ADR-010-grade-filter.md` | ثبت تصمیم معماری؛ وضعیت proposed/accepted در خود سند آمده است. |
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
| `docs/adr/ADR-047-payment-checkout-zarinpal.md` | خرید یک‌بارهٔ Basic/Pro و زرین‌پال (accepted). |
| `docs/adr/ADR-040-billing-period-timezone.md` | دورهٔ ماهانهٔ Gregorian در Asia/Tehran (accepted). |
| `docs/adr/ADR-048-free-credit-grant.md` | گرانت رایگان ۵ اعتبار یک‌بار (accepted). |
| `docs/adr/ADR-049-unlimited-subscription.md` | اشتراک Unlimited و حفظ اعتبار Basic/Pro (accepted؛ با OQ باز). |
| `docs/adr/ADR-050-fair-use-policy.md` | سیاست Fair-Use و abuse flag (accepted). |
| `docs/ADMIN_CONSOLE_SPEC.md` | مشخصات جامع پنل Admin و مرکز کنترل عملیات Darsyar (Phase 7). |
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
| `frontend/src/api/chat.ts` | API چت استریم (fetch-SSE؛ idempotent؛ access-token reader؛ history). |
| `frontend/src/components/ChatPanel.tsx` | پنل چت (استریم شده؛ انتخاب پایه؛ خطا/توقف؛ RTL). |
| `frontend/src/api/sse.ts` | لایهٔ یگانهٔ HTTP و fetch streaming. || `frontend/src/components/.gitkeep` | رابط React/TypeScript اولیه. |
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
| `backend/alembic/versions/0015_chat_and_rate_limit.py` | مهاجرت فاز ۳: conversations/messages + rate_limit_counters (fallback ریت‌لیمیت، جدا از ledger). |
| `backend/app/models/conversation.py` | مدل گفتگو (فاز ۳). |
| `backend/app/models/message.py` | مدل پیام و وضعیت‌های استریم (فاز ۳). |
| `backend/app/models/rate_limit_counter.py` | مدل شمارندهٔ fallback ریت‌لیمیت (OQ-006). |
| `backend/app/repositories/conversations.py` | دسترسی گفتگو/پیام با مالکیت در query. |
| `backend/app/schemas/conversation.py` | schemaهای گفتگو/پیام/استریم (فاز ۳). || `backend/app/services/llm.py` | درگاه provider سازگار OpenAI (NVIDIA/OpenAI) برای استریم چت (فاز ۳). |
| `backend/tests/test_llm_provider.py` | تست واحد درگاه LLM با respx. |
| `backend/tests/test_chat_persistence_db.py` | تست‌های یکپارچهٔ گفتگو/پیام روی PostgreSQL واقعی. |
| `backend/tests/test_rate_limit_fallback_db.py` | تست‌های fallback ریت‌لیمیت مبتنی بر PostgreSQL. |
| `backend/alembic/versions/0016_chat_reservation_link.py` | مهاجرت اتصال پیام assistant به رزرو (unique جزئی؛ گارد درج تکراری). |
| `backend/app/services/chat_service.py` | ارکستراسیون چت استریم + چرخه مالی reserve→stream→settle/release (ADR-039/OQ-030). |
| `backend/app/api/v1/chat.py` | endpoint استریم چت با fetch/SSE؛ مالکیت و ریت‌لیمیت چت (degraded). |
| `backend/tests/test_chat_stream_db.py` | تست‌های یکپارچهٔ چت استریم + چرخه مالی روی PostgreSQL واقعی. |
| `backend/app/inference/runtime.py` | کرنل واقعی inference (Slice E): لود BGE-M3 + Reranker، batch، اعتبارسنجی ابعاد/NaN، اجرای غیرمسدودکننده. |
| `backend/app/inference/remote.py` | backend دورستی inference (OpenAI-compatible embedding + generic rerank) با `EMBEDDING_BACKEND=remote`. |
| `backend/app/inference/main.py` | سرویس inference عملیاتی: /health، /ready واقعی، POST /embed، POST /rerank؛ انتخاب backend بر اساس تنظیمات (ADR-036). |
| `backend/tests/test_inference_shell.py` | تست قرارداد endpointهای inference با runtime جعلی. |
| `backend/tests/test_inference_remote.py` | تست backend دورستی با respx (بدون تماس واقعی). |
| `backend/tests/test_inference_backend_selection.py` | ماتریس انتخاب backend بر اساس EMBEDDING_BACKEND (ADR-054). |
| `backend/app/core/metrics.py` | متریک‌های سبک درون‌فرایندی (Slice F): Counter/Gauge/Histogram؛ low-cardinality و privacy-safe. |
| `backend/app/core/shutdown.py` | حالت خاموشی تدریجی درون‌فرایندی (draining + active_streams). |
| `backend/tests/test_slice_f_observability.py` | تست‌های متریک‌ها، drain و lifecycle خاموشی (Slice F). |
| `backend/tests/test_phase3_http_acceptance.py` | پذیرش یکپارچه فاز ۳: HTTP واقعی (Uvicorn subprocess) + PostgreSQL + Provider mock محلی. |
| `backend/scripts/phase3_sigterm_acceptance.py` | پذیرش process-level: SIGTERM واقعی در Linux/Docker برای چت استریم. |
| `backend/tests/test_deployment_hardening.py` | تست‌های سخت‌سازی Deployment: امنیت Metrics، Early Draining و زمان‌بندی بازیابی worker. |
| `backend/app/core/run_server.py` | Runner حداقلی Uvicorn با Early Draining (فعال‌سازی draining از لحظه SIGTERM). |
| `backend/scripts/phase3_sigterm_linux.py` | آزمون process-level Linux CI: Open SSE + SIGTERM واقعی + تأیید مالی PostgreSQL. |
| `resources/math/grade2/manifest.yaml` | manifest آزمایشی ریاضی دوم دبستان (کد 2051)؛ حالت needs_review. |
| `resources/physics/grade12/manifest.yaml` | manifest آزمایشی فیزیک ۳ دوازدهم (کد 112209)؛ حالت needs_review. |
| `docs/PHASE4_INGEST_PILOT.md` | معیارهای پذیرش pilot ingestion برای دو کتاب (مانifest/PDF/OCR/تصاویر/فرمول/chunking/state). |
| `docs/licenses/13529.md` | ثبت مرجع مجوز تأمینی توسط مالک (reference 13529؛ pending_evidence_and_scope_review). |
| `docs/ingestion/README.md` | فهرست/هدف طراحی ingestion Phase 4 (design). |
| `docs/ingestion/ARCHITECTURE.md` | معماری ingestion: مؤلفه‌ها، مرزها، جریان داده، امنیت (design). |
| `docs/ingestion/PIPELINE_STAGES.md` | قرارداد مرحله‌به‌مرحله pipeline (design). |
| `docs/ingestion/EXTRACTION_STRATEGY.md` | راهبرد استخراج ریاضی/فیزیک/عمومی (design). |
| `docs/ingestion/CHUNKING_AND_PROVENANCE.md` | سلسله‌مراتب chunk و حفظ R-150 (design). |
| `docs/ingestion/AUTHORIZATION_GATE.md` | گیت مجوز per-resource/per-operation و ارجاع 13529 (design). |
| `docs/ingestion/STATE_MACHINE_AND_FAILURES.md` | R-156 state machine، خطاها، retry/recovery (design). |
| `docs/ingestion/ACCEPTANCE_CRITERIA.md` | معیارهای پذیرش طراحی‌شده (غیراجرا) (design). |
| `docs/ingestion/DESIGN_REVIEW.md` | ممیزی مستقل طراحی ingestion (PASS WITH CONDITIONS؛ فهرست اصلاحات لازم). |
| `docs/ingestion/SECOND_AUDIT.md` | دومین ممیزی مستقل پس از remediation (PASS WITH CONDITIONS؛ گیت‌های خارجی باز). |
| `docs/ingestion/OWNER_DECISIONS.md` | بستهٔ تصمیم مالک برای سه گیت (renderer، محدودیت‌های امنیتی، آزمون هم‌ارزی) — آماده‌سازی، بدون تصمیم. |
| `.github/workflows/ingestion-pdfium-linux-preflight.yml` | workflow دستی (workflow_dispatch) برای preflight Linux pypdfium2+Pillow در `python:3.13-slim` (فقط دستی؛ بدون اجرا توسط KiloCode). |
| `scripts/ci/pdfium_linux_preflight.py` | هارنس CI-only برای تست Linux pypdfium2 5.15.2 + Pillow 12.3.0 (ماژول کاربردی نیست). |
| `docs/ingestion/PDFIUM_LINUX_PREFLIGHT.md` | ثبت شواهد Run #6 (PASS فنی؛ بدون تأیید Production؛ Gate A OPEN). || `docs/ingestion/GATE_A_RENDERER_DECISION.md` | ارزیابی نهایی Gate A؛ توصیه pypdfium2 به‌عنوان پیشنهاد تأیید مالک (نه Production). |
| `docs/ingestion/PDFIUM_LICENSE_INVENTORY.md` | موجودی فنی مجوز/notices برای pypdfium2 5.15.2 (ایعزلوله/Windows)؛ تأیید حقوقی نیست. |
| `docs/ingestion/PDFIUM_OWNER_LEGAL_REVIEW.md` | خلاصه یادمند مالک/حقوقی برای pypdfium2 5.15.2 (چک‌لیست تصمیم‌ها؛ بدون تصمیم‌گیری). |
| `docs/ingestion/PDFIUM_CONCURRENCY_DECISION.md` | ارزیابی فرایندهای isolated/هم‌زمانی برای pypdfium2 (پیشنهاد Option C؛ بدون تصمیم مالک). |
| `docs/ingestion/ARQ_PDF_JOB_INTEGRATION_AUDIT.md` | ممیزی یکپارچه‌سازی arq↔PDF (BLOCKED_BY_MISSING_IDEMPOTENCY_OR_RECOVERY؛ بدون تصمیم مالک). |
| `docs/ingestion/INGESTION_JOB_IDEMPOTENCY_DESIGN.md` | طراحی durable ingestion jobs/idempotency/outbox/fencing (READY_FOR_OWNER_DESIGN_REVIEW). |
| `docs/ingestion/INGESTION_ARCHITECTURE_OWNER_DECISION.md` | بستهٔ تصمیم یکپارچه مالک برای معماری ingestion (Group 1/2/3؛ Owner decision PENDING). |
| `docs/ingestion/DURABLE_INGESTION_JOB_IMPLEMENTATION_SPEC.md` | مشخصات پیاده‌سازی durable ingestion job/outbox/fencing (OWNER_APPROVED_WITH_CONDITIONS؛ Slice 1 IMPLEMENTED). |
| `backend/app/models/ingestion_document.py` | مدل هویت canonical سند (R-157). |
| `backend/app/models/ingestion_job.py` | مدل durable ingestion job (persistence only). |
| `backend/app/models/outbox_event.py` | مدل transactional outbox (publisher در Slice بعدی). |
| `backend/alembic/versions/0018_ingestion_persistence.py` | مهاجرت Slice 1 (ingestion_documents/jobs/outbox_events). |
| `backend/tests/test_ingestion_persistence.py` | تست ساختاری + PostgreSQL برای persistence ingestion. |
| `backend/tests/test_inference_real_models.py` | تست واقعی مدل‌ها (skip-gated؛ فقط وقتی هر دو مدل cache شده باشند). |
| `docs/adr/ADR-054-remote-inference-support.md` | تصمیم پذیرفته‌شده: پشتیبانی رسمی Remote Embedding/Inference (accepted؛ 2026-11-08). |

## مسیرهای تولیدشده در فاز صفر (2026-10-27)

| مسیر | مسئولیت |
|---|---|
| `backend/uv.lock` | lockfile دقیق پایتون؛ تولیدشده با `uv lock` از PyPI واقعی. |
| `frontend/package-lock.json` | lockfile دقیق npm؛ تولیدشده با `npm install --package-lock-only` از registry واقعی. |
| ackend/app/services/ingestion_creation.py | سرویس Slice 2: ایجاد اتمیک job+outbox با idempotency درخواست. |
| ackend/tests/test_ingestion_creation_db.py | تست PostgreSQL Slice 2 (ایجاد اتمیک، idempotency، هم‌زمانی). |
| docs/ingestion/INGESTION_PROGRESS_AND_OPEN_DECISIONS.md | گزارش یکپارچه پیشرفت و تصمیم‌های باز مالک (snapshot 2026-11-10). |
| docs/ingestion/OUTBOX_RETENTION_AND_SLICE_3_OWNER_DECISION.md | بستهٔ تصمیم مالک برای retention outbox و دامنهٔ Slice 3 (سنتزیک). |
| docs/ingestion/SLICE_3_OUTBOX_PUBLISHER_IMPLEMENTATION.md | مشخصات پیاده‌سازی Slice 3: outbox publisher/reconciliation (S-1/S-2 APPROVED_WITH_CONDITIONS؛ CLOSED). |
| backend/app/repositories/outbox_events.py | دسترسی outbox: claim FOR UPDATE SKIP LOCKED + گذارهای publish/fail (Slice 3). |
| backend/app/services/outbox_publisher.py | سرویس انتشار outbox به صف ARQ اختصاصی (synthetic)؛ at-least-once (Slice 3). |
| backend/app/services/outbox_reconciliation.py | سرویس یک‌بارمصرف تطبیق/بازانتشار outbox (Slice 3). |
| backend/tests/test_outbox_publisher_db.py | تست یکپارچهٔ PostgreSQL + Redis/ARQ انتشار outbox و تطبیق (Slice 3؛ 13 تست). |
| docs/ingestion/NEXT_INGESTION_READINESS_OWNER_DECISIONS.md | بستهٔ تصمیم یکپارچه مالک برای مرحلهٔ بعد ingestion (R-1، Publisher runtime، Gate A/B/C، 13529؛ صرفاً اسنادی/ارزیابی). |
| docs/ingestion/OUTBOX_PUBLISHER_BATCH_BENCHMARK.md | شواهد benchmark سنتزی batch-size Publisher (B1؛ 10/50/100) روی darsyar_test + Redis DB15؛ B1=OWNER_APPROVED_WITH_CONDITIONS با batch_size=50 برای manual one-shot. |
| docs/ingestion/OUTBOX_PUBLISHER_RUNTIME_PARAMETERS.md | ارزیابی فنی read-only پارامترهای runtime Publisher (B3): فهرست پارامترها، پروفایل‌های manual/scheduled/Production، جدول تصمیم مالک؛ B3=OWNER_DECIDED_DEFER_UNTIL_SCHEDULING_OR_PRODUCTION؛ بدون انتخاب مقدار. |
| docs/ingestion/GATE_B_PDF_SECURITY_LIMITS_OWNER_DECISION.md | بستهٔ تصمیم مالک Gate B: ماتریس امنیت/محدودیت منابع PDF (آپلود/گسترش/رندر/اجرا/ذخیره موقت/سوءاستفاده)، مغایرت pilot-37.5MB با سقف 20MiB، تست‌های synthetic-only، جدول تصمیم مالک؛ بدون تأیید هیچ محدودیتی. |
| docs/ingestion/GATE_B_PDF_VALIDATION_IMPLEMENTATION.md | پیاده‌سازی Gate B-S0 (Approve_With_Conditions): Common PDF Validation Layer (pypdf 6.21.4/6.21.3)، Parent/Child contract (طراحی)، تست‌های synthetic-only (22 passed)؛ بدون pilot/آپلود/رندر. |
| docs/ingestion/GATE_B_S1_PARENT_CHILD_PROTOTYPE.md | پیاده‌سازی Gate B-S1 (Approve_With_Conditions): Parent Supervisor + PDF Child ایزوله (IPC v1، pypdf 6.21.3، timeout/خاتمه/بازیابی، ایزوله‌سازی env)؛ تست‌های synthetic-only (17 passed)؛ بدون pilot/آپلود/رندر/Production. |
| docs/ingestion/GATE_B_S2_LINUX_SANDBOX_PROTOTYPE.md | پیاده‌سازی Gate B-S2 (Approve_With_Conditions): sandbox ایزولهٔ Linux (network none، read-only rootfs، memory/CPU/PID limits، cap-drop، non-root) با شواهد probe؛ 52 passed در کانتینر؛ غیر از Deployment Dockerfile/Compose. |
| docs/ingestion/GATE_B_S3_NUMERIC_POLICY_OWNER_DECISION.md | بستهٔ تصمیم مالک Gate B-S3: 18 تصمیم عددی/امنیتی؛ `GATE_B_S3_PARTIAL_OWNER_DECISION=APPROVE_WITH_CONDITIONS` (6 تأییدشده: GB-01/02/03/08/09/18؛ 12 PENDING)؛ بدون پیاده‌سازی/فعال‌سازی. |
| docs/ingestion/GATE_B_S4_AGGREGATE_DECOMPRESSION_AND_CGROUP_EVIDENCE.md | آزمایش آزمایشگاهی Gate B-S4 (Approve_With_Conditions): بودجه decompression کل سند (256 MiB candidate: قابل‌اجرا، بدون تأیید) + شواهد شمارنده cgroup v2 مستقیم (memory OOM/CPU throttling/PID). || docs/ingestion/GATE_B_S4_1_AGGREGATE_DECOMPRESSION_COVERAGE.md | آزمایش Gate B-S4.1 (Approve_With_Conditions): پوشش/کشف جریان‌ها، حسابداری شکست‌ها، ایزوله‌سازی هم‌زمانی؛ Q1=PARTIALLY؛ بدون تأیید GB-04. |
| docs/ingestion/GATE_B_S4_2_PARSE_TIME_DECOMPRESSION_AND_PYPDF_SECURITY_REVIEW.md | آزمایش Gate B-S4.2 (Approve_With_Conditions): decompression ضمنی هنگام parse، ایزوله‌سازی فرایند per-document، بازبینی نسخه/مشاوره pypdf (4 نسخه)؛ قفل 6.21.3 بدون تغییر؛ **LAB_VALIDATION_PARTIAL** (شکاف‌های شواهد ثبت‌شده). |
| docs/ingestion/GATE_B_S5_PDF_PARSER_DECODER_ARCHITECTURE_COMPARISON.md | مقایسه معماری/امنیت پارسر-دیکودر Gate B-S5 (Approve_With_Conditions): 4 نامزد (pypdf 6.21.3/7.0.1، pypdfium2/PDFium، PyMuPDF/MuPDF، orchestration مستقل)؛ بازبینی رسمی pypdf (8 advisory scope) + pypdfium2/PyMuPDF/qpdf؛ بدون انتخاب/ارتقا؛ **ARCHITECTURE_REVIEW_COMPLETE**. |
| docs/reports/AUTONOMOUS_PROJECT_COMPLETION_REPORT.md | گزارش تحویل نهایی خودگردان: وضعیت واقعی، فازها (0–3 کامل؛ 4–9 گیت‌شده)، شواهد تست/استاتیک/build، گیت‌ها، تصمیمات در انتظار مالک. |
| docs/reports/AUTONOMOUS_EXECUTION_STATE.md | چک‌پوینت وضعیت اجرای خودگردان (directive §9): وضعیت فازها/گیت‌ها، ارزیابی ایزوله pypdf 7.0.1 (57 passed؛ 2 delta مورد انتظار)، ثبت تصمیمات تفویض‌شده، بلاک‌کننده 13529، اقدام بعدی دقیق. |
| docs/ingestion/PYPDF_RESOURCE_LIMITS_AUDIT.md | ممیزی منابع pypdf (per-filter/stream caps؛ نه بودجهٔ کلی) و رفتار validator (شمارش صفحه بدون decode جریان)؛ یکسانی رفتاری 6.21.3 و 6.21.4 تأییدشده (22 تست در هر دو). |
| backend/app/services/ingestion/pdf_validation.py | لایهٔ اعتبارسنجی مشترک PDF (Gate B-S0): امضا/ساختار/صفحه/رمزنگاری/محدودیت‌های صریح؛ بدون استخراج متن/رندر. |
| backend/app/services/ingestion/parent_child_contract.py | قرارداد نسخه‌دار Parent/Child (IPC v1؛ Gate B-S0/S1). |
| backend/app/services/ingestion/parent_supervisor.py | سرپرست Parent (Gate B-S1): spawn فرایند ایزوله، allowlist محیط، timeout/خاتمه/بازیابی، اعتبارسنجی نتیجه. |
| backend/app/services/ingestion/pdf_child.py | فرایند فرزند PDF (Gate B-S1): `python -m ...pdf_child`؛ scoped Configuration pypdf؛ decode جریان؛ نتیجهٔ ساخت‌یافته. |
| backend/app/services/ingestion/linux_sandbox.py | پروب/رانر sandbox Linux (Gate B-S2): اندازه‌گیری و تأیید enforcement (network/fs/memory/CPU/PID) و run_sandboxed_child. |
| backend/tests/test_gate_b_pdf_validation.py | تست‌های synthetic-only اعتبارسنجی PDF (Gate B-S0؛ 22 تست). |
| backend/tests/test_gate_b_parent_child.py | تست‌های synthetic-only Parent/Child (Gate B-S1؛ 17 تست). |
| backend/tests/test_gate_b_linux_sandbox.py | تست‌های synthetic-only sandbox Linux (Gate B-S2؛ 13 تست enforcement). |
| backend/tests/sandbox/Dockerfile.sandbox | ایمیج مستقل آزمایشی sandbox Linux (Gate B-S2؛ pypdf 6.21.3؛ نه بخش Deployment). |
| backend/tests/test_gate_b_s4_aggregate_decompression.py | آزمایش A (Gate B-S4): بودجه decompression کل/جریان با pypdf 6.21.3 (8 تست). |
| backend/tests/test_gate_b_s4_cgroup_evidence.py | آزمایش B (Gate B-S4): شواهد شمارنده cgroup v2 (memory/CPU/PID) (7 تست). |
| backend/tests/sandbox/s4_cgroup_lib.py | کتابخانهٔ probeهای cgroup (test-only). |
| backend/tests/sandbox/s4_cgroup_probe.py | درایور چاپ شواهد cgroup (test-only). |
| backend/tests/sandbox/s4_1_lib.py | کتابخانهٔ test-only S4.1 (builders/Orchestratorها). |
| backend/app/models/ingestion_chunk.py | مدل chunk سند (R-150؛ parent/child، Vector(1024)، متادیتا). |
| backend/app/services/ingestion/manifest.py | اعتبارسنجی manifest (R-153/154). |
| backend/app/services/ingestion/chunking.py | chunking دو سطحی (R-158/159). |
| backend/app/services/ingestion/normalize.py | نرمال‌سازی فارسی (R-164). |
| backend/app/services/ingestion/embedding_service.py | سرویس embedding (batch/timeout/retry/dim). |
| backend/app/services/ingestion/indexing.py | ایندکس idempotent اتمیک chunk+embedding. |
| backend/app/services/ingestion/retrieval.py | بازیابی هیبرید (pgvector+pg_trgm، RRF k=60، فیلتر grade در SQL، rerank top-20). |
| backend/alembic/versions/0020_ingestion_chunks.py | مهاجرت جدول ingestion_chunks (فاز 4). |
| backend/alembic/versions/0021_ingestion_chunks_indexes.py | مهاجرت ایندکس‌های سنگین HNSW/GIN (فاز 4). |
| backend/tests/test_phase4_ingestion_pipeline_db.py | تست‌های یکپارچه فاز 4 (10 تست؛ PostgreSQL واقعی). |
| backend/app/services/ingestion/retrieval_service.py | سرویس orchestration بازیابی فاز 5 (provider wiring + citation guard). |
| backend/app/services/ingestion/evaluation.py | ارزیابی gold مصنوعی RAG (فاز 5؛ grade leakage/citation). |
| backend/tests/test_phase5_rag_evaluation_db.py | تست‌های فاز 5 (گیت‌های RAG روی دادهٔ مصنوعی). |
| backend/tests/test_gate_b_s4_1_stream_coverage.py | آزمایش A S4.1: پوشش/کشف جریان‌ها. |
| backend/tests/test_gate_b_s4_1_failure_accounting.py | آزمایش B S4.1: حسابداری شکست/partial. |
| backend/tests/test_gate_b_s4_1_concurrency_isolation.py | آزمایش C S4.1: ایزوله‌سازی هم‌زمانی (threads/async). |
| backend/tests/sandbox/s4_2_lib.py | کتابخانهٔ test-only S4.2 (فرایند فرزند per-document). |
| backend/tests/sandbox/pypdf_version_probe.py | درایور مستقل version-matrix (S4.2). |
| backend/tests/test_gate_b_s4_2_parse_time_decompression.py | آزمایش A S4.2: decompression ضمنی هنگام parse. |
| backend/tests/test_gate_b_s4_2_process_isolation.py | آزمایش B S4.2: فرایند فرزند per-document. || backend/tests/test_gate_b_s4_2_security_regressions.py | آزمایش C/D S4.2: مشاوره/فیلترها (6.21.3). |
| backend/alembic/versions/0019_outbox_job_fk_restrict.py | مهاجرت R-1: تغییر FK `fk_outbox_events_job` از CASCADE به RESTRICT (برگشت‌پذیر؛ R1-IMPL؛ روی `darsyar` اعمال شد 2026-11-11). |
| backend/tests/test_ingestion_restrict_db.py | تست PostgreSQL R-1: metadata/catalog/RESTRICT، رد حذف SQL و ORM، حفظ والد/فرزند، حذف job بی‌outbox، head 0019 (7 تست). |