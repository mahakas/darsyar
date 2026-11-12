# نقشهٔ راه درسیار — مبنا: AGENTS.md v4.0

وضعیت فاز با ایجاد فایل تغییر نمی‌کند؛ گزارش اجرا، تست‌ها و معیارهای پذیرش باید شاهد داشته باشند. «Prototype/Partial» به معنی پذیرش رسمی فاز نیست.

| فاز | سند مرجع | دامنه | پیش‌نیاز | وضعیت واقعی |
|---|---|---|---|---|
| 0 | `specs/phase-0.md` | Foundation: زیرساخت، تنظیمات، API shell، DB/Redis، Compose، lockfile و CI | قرارداد v4 | تکمیل‌شده (گزارش بستن: 2026-10-27) |
| 1 | `specs/phase-1.md` | OTP، هویت، نشست و امنیت JWT/refresh | فاز 0 | تکمیل‌شده (ADR-046 accepted؛ اصلاح امنیتی refresh اعمال شد — 2026-10-29) |
| 2 | `specs/phase-2.md` | کردیت، reservation، ledger، usage، طرح‌ها و پرداخت | فاز 1 + رفع تعارض‌های مالی | تکمیل‌شده با محدودیت‌های مستند (2026-11-07) |
| 3 | `specs/phase-3.md` | provider gateway، inference service/remote، گفتگو و استریم | فازهای 0/1 و ADRهای مربوط | تکمیل‌شده (2026-11-08؛ شواهد پذیرش Phase 3 ثبت‌شده) |
| 4 | `specs/phase-4.md` | منابع، manifest، مجوز، استخراج/OCR، chunking و worker | فازهای 0/3 | **Partial — synthetic pipeline primitives + bounded overlap/parent chunks + fail-closed active index registry enforcement implemented (CI run 43129891289)**؛ فاز هنوز Gated و پذیرفته‌نشده است. intake/worker عملیاتی، Gate A/B/C و مجوز منابع باقی است. |
| 5 | `specs/phase-5.md` | RAG هیبرید، فیلتر پایه، RRF، rerank، evidence و وب | فاز 4 + دیتاست طلایی | **Partial prototype — retrieval fail-closed on active index registry; honest retrieval/citation metadata metrics in synthetic evaluator**؛ فاز پذیرفته نشده. ADR-043، دیتاست طلایی ۱۵۰ پرسشی، evidence snapshot و اتصال به پاسخ واقعی باقی است. |
| 6 | `specs/phase-6.md` | رابط چت، منبع‌ها، Markdown/KaTeX/Mermaid امن، تاریخچه و i18n | فازهای 1/3/5 | **Partial — authenticated session/profile + explicit grade + owner-scoped searchable/paginated conversation and message history merged 2026-11-12**؛ robust SSE reconnect/resume، evidence SourceCard، safe Markdown/KaTeX/Mermaid، accessibility، responsive/theme acceptance باقی است. |
| 7 | `specs/phase-7.md` + `docs/ADMIN_CONSOLE_SPEC.md` | Admin Control Center | فازهای ۱–۶ و primitives حسابرسی | **Specification only**؛ ADR-051 Proposed و پیاده‌سازی پنل/endpointها تکمیل نشده است. |
| 8 | `specs/phase-8.md` | قابلیت‌های یادگیری آینده؛ خارج از MVP و غیرفعال | ADR جدید و تأیید مالک | تعویق‌شده؛ endpoint نساز. |
| 9 | `specs/phase-9.md` | سخت‌سازی تولید، امنیت، بکاپ/بازیابی، انطباق و عملیات | فازهای MVP | برنامه‌ریزی‌شده؛ هیچ Production release تأیید نشده است. |

## شواهد CI

آخرین اجرای CI روی `main` پس از ادغام Phase 4 chunking، commit `3860a16fac7ed1c973a6afb13fd5db87106c5793`، در 2026-11-12 موفق شد:
- Backend: 483 passed, 21 skipped, 1 warning.
- Frontend: lint، typecheck و build موفق.
- Linux SIGTERM acceptance: موفق.
- Migration smoke و Ruff: موفق.
- اجرا: [Run 43128633013](https://github.com/mahakas/darsyar/actions/runs/43128633013).

شاخهٔ PR فعال-index-registry نیز روی HEAD `259b13916a4579d2e947da27209e504a71f94ea4`، اجرای CI کامل را گذرانده است: Backend **492 passed, 21 skipped, 1 warning**؛ Ruff، Frontend و Linux SIGTERM همگی موفق. این شاخه هنوز در main ادغام نشده است.

Skipهای صریح شامل برخی تست‌های sandbox/cgroup و مدل‌های واقعی به‌دلیل نیاز به محیط محدودشده/منابع اضافی هستند؛ بنابراین سبز بودن CI به معنی تأیید Gateهای امنیتی PDF یا Production نیست.

## قواعد پیشروی
- هر فاز دقیقاً یک سند canonical در `specs/phase-N.md` دارد.
- فاز بعدی فقط پس از پذیرش خروجی‌های وابسته و گیت‌های آن آغاز/اعلام تکمیل می‌شود.
- قابلیت خارج از MVP صرفاً به دلیل وجود پوشه یا spec به API تبدیل نمی‌شود.
- `COMPLETE` فقط با شواهد واقعی اجرا و معیارهای پذیرش مجاز است.
- تعارض‌های `docs/OPEN_QUESTIONS.md` باید پیش از فاز مرتبط رفع شوند.
