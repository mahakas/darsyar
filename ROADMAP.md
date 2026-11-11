# نقشهٔ راه درسیار — مبنا: AGENTS.md v4.0

وضعیت فاز با ایجاد فایل تغییر نمی‌کند؛ گزارش اجرا، تست‌ها و معیارهای پذیرش باید شاهد داشته باشند. «Prototype/Partial» به معنی پذیرش رسمی فاز نیست.

| فاز | سند مرجع | دامنه | پیش‌نیاز | وضعیت واقعی |
|---|---|---|---|---|
| 0 | `specs/phase-0.md` | Foundation: زیرساخت، تنظیمات، API shell، DB/Redis، Compose، lockfile و CI | قرارداد v4 | تکمیل‌شده (گزارش بستن: 2026-10-27) |
| 1 | `specs/phase-1.md` | OTP، هویت، نشست و امنیت JWT/refresh | فاز 0 | تکمیل‌شده (ADR-046 accepted؛ اصلاح امنیتی refresh اعمال شد — 2026-10-29) |
| 2 | `specs/phase-2.md` | کردیت، reservation، ledger، usage، طرح‌ها و پرداخت | فاز 1 + رفع تعارض‌های مالی | تکمیل‌شده با محدودیت‌های مستند (2026-11-07) |
| 3 | `specs/phase-3.md` | provider gateway، inference service/remote، گفتگو و استریم | فازهای 0/1 و ADRهای مربوط | تکمیل‌شده (2026-11-08؛ شواهد پذیرش Phase 3 ثبت‌شده) |
| 4 | `specs/phase-4.md` | منابع، manifest، مجوز، استخراج/OCR، chunking و worker | فازهای 0/3 | **Partial — synthetic building blocks موجود؛ فاز هنوز Planned/Gated و پذیرفته‌نشده**. مسیر کامل intake/worker، Gate A/B/C و مجوز واقعی منابع باقی است. |
| 5 | `specs/phase-5.md` | RAG هیبرید، فیلتر پایه، RRF، rerank، evidence و وب | فاز 4 + دیتاست طلایی | **Partial prototype — retrieval و ارزیابی synthetic موجود؛ فاز پذیرفته نشده**. ADR-043 و دیتاست طلایی حداقل ۱۵۰ پرسشی، evidence snapshot و اتصال به پاسخ واقعی باقی است. |
| 6 | `specs/phase-6.md` | رابط چت، منبع‌ها، Markdown/KaTeX/Mermaid امن، تاریخچه و i18n | فازهای 1/3/5 | **Partial prototype — shell و چت streaming اولیه موجود**؛ تجربهٔ کامل، تاریخچه، citation/source cards، Markdown امن، accessibility و احراز هویت فرانت‌اند باقی است. |
| 7 | `specs/phase-7.md` + `docs/ADMIN_CONSOLE_SPEC.md` | Admin Control Center | فازهای ۱–۶ و primitives حسابرسی | **Specification only**؛ ADR-051 Proposed و پیاده‌سازی پنل/endpointها تکمیل نشده است. |
| 8 | `specs/phase-8.md` | قابلیت‌های یادگیری آینده؛ خارج از MVP و غیرفعال | ADR جدید و تأیید مالک | تعویق‌شده؛ endpoint نساز. |
| 9 | `specs/phase-9.md` | سخت‌سازی تولید، امنیت، بکاپ/بازیابی، انطباق و عملیات | فازهای MVP | برنامه‌ریزی‌شده؛ هیچ Production release تأیید نشده است. |

## شواهد CI

آخرین اجرای CI روی commit `571fc2e09f31e361e9773ecf794601930e21349b` در 2026-11-11 موفق شد:
- Backend: 463 passed, 21 skipped.
- Frontend: lint و build موفق.
- Linux SIGTERM acceptance: موفق.
- Migration smoke: موفق.

Skipهای صریح شامل برخی تست‌های sandbox/cgroup و مدل‌های واقعی به‌دلیل نیاز به محیط محدودشده/منابع اضافی هستند؛ بنابراین سبز بودن CI به معنی تأیید Gateهای امنیتی PDF یا Production نیست.

## قواعد پیشروی
- هر فاز دقیقاً یک سند canonical در `specs/phase-N.md` دارد.
- فاز بعدی فقط پس از پذیرش خروجی‌های وابسته و گیت‌های آن آغاز/اعلام تکمیل می‌شود.
- قابلیت خارج از MVP صرفاً به دلیل وجود پوشه یا spec به API تبدیل نمی‌شود.
- `COMPLETE` فقط با شواهد واقعی اجرا و معیارهای پذیرش مجاز است.
- تعارض‌های `docs/OPEN_QUESTIONS.md` باید پیش از فاز مرتبط رفع شوند.
