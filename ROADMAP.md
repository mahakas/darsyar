# نقشهٔ راه درسیار — مبنا: AGENTS.md v4.0

وضعیت فاز با ایجاد فایل تغییر نمی‌کند؛ گزارش اجرا، تست‌ها و معیارهای پذیرش باید شاهد داشته باشند. «Prototype/Partial» به معنی پذیرش رسمی فاز نیست.

| فاز | سند مرجع | دامنه | پیش‌نیاز | وضعیت واقعی |
|---|---|---|---|---|
| 0 | `specs/phase-0.md` | Foundation: زیرساخت، تنظیمات، API shell، DB/Redis، Compose، lockfile و CI | قرارداد v4 | تکمیل‌شده (گزارش بستن: 2026-10-27) |
| 1 | `specs/phase-1.md` | OTP، هویت، نشست و امنیت JWT/refresh | فاز 0 | تکمیل‌شده (ADR-046 accepted؛ اصلاح امنیتی refresh اعمال شد — 2026-10-29) |
| 2 | `specs/phase-2.md` | کردیت، reservation، ledger، usage، طرح‌ها و پرداخت | فاز 1 + رفع تعارض‌های مالی | تکمیل‌شده با محدودیت‌های مستند (2026-11-07) |
| 3 | `specs/phase-3.md` | provider gateway، inference service/remote، گفتگو و استریم | فازهای 0/1 و ADRهای مربوط | تکمیل‌شده (2026-11-08؛ شواهد پذیرش Phase 3 ثبت‌شده) |
| 4 | `specs/phase-4.md` | منابع، manifest، مجوز، استخراج/OCR، chunking و worker | فازهای 0/3 | **Partial/Gated — synthetic ingestion pipeline (PR #13), durable job claim/lease/fencing/retry/cancellation (PR #21), fenced artifact staging/publish/cleanup (PR #22), low-cardinality observability metrics (PR #23), and PostgreSQL→Parent/Child→artifact end-to-end success/failure tests (PR #24) merged. PR #24 CI: 545 passed, 21 skipped, 1 warning; all five jobs passed.** فاز پذیرفته نشده است؛ intake/consumer عملیاتی، مجوز هر منبع، Gate A/B/C و آزمون روی منبع مجاز باقی است.
| 5 | `specs/phase-5.md` | RAG هیبرید، فیلتر پایه، RRF، rerank، evidence و وب | فاز 4 + دیتاست طلایی | **Partial prototype — registry-bound retrieval and honest synthetic retrieval/citation metadata metrics merged (PR #11)**؛ فاز پذیرفته نشده. ADR-043، دیتاست طلایی ۱۵۰ پرسشی، evidence snapshot و اتصال به پاسخ واقعی باقی است. |
| 6 | `specs/phase-6.md` | رابط چت، منبع‌ها، Markdown/KaTeX/Mermaid امن، تاریخچه و i18n | فازهای 1/3/5 | **Partial — authenticated session/profile, explicit grade, owner-scoped searchable/paginated history and durable idempotent SSE replay/status recovery merged (PRs #9/#14, 2026-11-12)**؛ live provider reattachment/event-offset resume، evidence SourceCard، safe Markdown/KaTeX/Mermaid، accessibility و responsive/theme acceptance باقی است. |
| 7 | `specs/phase-7.md` + `docs/ADMIN_CONSOLE_SPEC.md` | Admin Control Center | فازهای ۱–۶ و primitives حسابرسی | **Partial foundation (PR candidate)** — server-side `require_admin` seed guard/DB-role authorization و PostgreSQL append-only audit migration/testها CI-verified؛ هنوز هیچ Admin route/UI، seed operation یا acting session فعال نشده؛ ADR-051 همچنان Proposed است و MFA/step-up/recovery باید جداگانه تعیین تکلیف شود. |
| 8 | `specs/phase-8.md` | قابلیت‌های یادگیری آینده؛ خارج از MVP و غیرفعال | ADR جدید و تأیید مالک | تعویق‌شده؛ endpoint نساز. |
| 9 | `specs/phase-9.md` | سخت‌سازی تولید، امنیت، بکاپ/بازیابی، انطباق و عملیات | فازهای MVP | برنامه‌ریزی‌شده؛ هیچ Production release تأیید نشده است. |

## شواهد CI

آخرین اجرای CI روی `main` پس از ادغام PR #24، commit `385a3d1fdedb429250e478ed836c96e9e1422a9e`، در 2026-11-12 موفق شد: [Run 43254717321](https://github.com/mahakas/darsyar/actions/runs/43254717321).
- Backend: **545 passed, 21 skipped, 1 warning**.
- Ruff، mypy (132 source files)، Alembic migration smoke: PASS.
- Frontend lint/typecheck/build: PASS.
- Linux SIGTERM acceptance و Nginx config/header smoke: PASS.
- Trivy filesystem/base-image report-only scans: PASS؛ تولید گزارش به معنی صفر آسیب‌پذیری نیست.
- RAG evaluation به دلیل نبود golden dataset بازبینی‌شده اجرا نشد؛ sandbox/cgroup و real-model checks نیز در CI عمومی به‌دلیل نبود محیط/منابع اختصاصی Skip شدند.

Skipهای صریح را نباید Passed شمرد؛ سبز بودن CI به معنی تأیید Gateهای امنیتی PDF، مجوز منابع یا Production نیست.

## قواعد پیشروی
- هر فاز دقیقاً یک سند canonical در `specs/phase-N.md` دارد.
- فاز بعدی فقط پس از پذیرش خروجی‌های وابسته و گیت‌های آن آغاز/اعلام تکمیل می‌شود.
- قابلیت خارج از MVP صرفاً به دلیل وجود پوشه یا spec به API تبدیل نمی‌شود.
- `COMPLETE` فقط با شواهد واقعی اجرا و معیارهای پذیرش مجاز است.
- تعارض‌های `docs/OPEN_QUESTIONS.md` باید پیش از فاز مرتبط رفع شوند.
