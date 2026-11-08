# نقشهٔ راه درسیار — مبنا: AGENTS.md v4.0

وضعیت فاز با ایجاد فایل تغییر نمی‌کند؛ گزارش اجرا، تست‌ها و معیارهای پذیرش باید شاهد داشته باشند.

| فاز | سند مرجع | دامنه | پیش‌نیاز | وضعیت |
|---|---|---|---|---|
| 0 | `specs/phase-0.md` | Foundation: زیرساخت، تنظیمات، API shell، DB/Redis، Compose، lockfile و CI | قرارداد v4 | تکمیل‌شده (گزارش بستن: 2026-10-27) |
| 1 | `specs/phase-1.md` | OTP، هویت، نشست و امنیت JWT/refresh | فاز 0 | تکمیل‌شده (ADR-046 accepted؛ اصلاح امنیتی refresh اعمال شد — 2026-10-29) |
| 2 | `specs/phase-2.md` | کردیت، reservation، ledger، usage، طرح‌ها و پرداخت | فاز 1 + رفع تعارض‌های مالی | تکمیل‌شده با محدودیت‌های مستند (2026-11-07): معیارهای رسمی پذیرش برآورده شده‌اند؛ ADR-052/053 پذیرفته و OQ-029/030 طبق تصمیم مالک بسته شده‌اند؛ محدودیت‌ها: OQ-029 (رزروهای legacy ممکن است حل‌نشده بمانند) و OQ-030 (اجرای runtime به فاز ۳ موکول است)؛ 171 تست محلی (غیر CI) گزارش شده است |
| 3 | `specs/phase-3.md` | provider gateway، inference service/remote، گفتگو و استریم | فازهای 0/1 و ADRهای مربوط | تکمیل‌شده (2026-11-08؛ GitHub Actions Run #33، commit ceacee4a026be5998e4683ede517520cd5df0511؛ Backend 320 passed/1 skipped، Frontend PASS، Alembic→0017 PASS، Linux SIGTERM A/B PASS) |
| 4 | `specs/phase-4.md` | منابع، manifest، مجوز، استخراج/OCR، chunking و worker | فازهای 0/3 | برنامه‌ریزی‌شده |
| 5 | `specs/phase-5.md` | RAG هیبرید، فیلتر پایه، RRF، rerank، evidence و وب | فاز 4 + دیتاست طلایی | برنامه‌ریزی‌شده |
| 6 | `specs/phase-6.md` | رابط چت، منبع‌ها، Markdown/KaTeX/Mermaid امن، تاریخچه و i18n | فازهای 1/3/5 | برنامه‌ریزی‌شده |
| 7 | `specs/phase-7.md` + `docs/ADMIN_CONSOLE_SPEC.md` | Admin Control Center: کاربران/User 360، پشتیبانی، مالی، AI/RAG، امنیت، تنظیمات، عملیات، حریم خصوصی، analytics و audit | فازهای ۱–۶ و primitives حسابرسی؛ هماهنگی عملیاتی با فاز ۹ | برنامه‌ریزی‌شده |
| 8 | `specs/phase-8.md` | قابلیت‌های یادگیری آینده؛ خارج از MVP و غیرفعال | ADR جدید و تأیید مالک | تعویق‌شده؛ endpoint نساز |
| 9 | `specs/phase-9.md` | سخت‌سازی تولید، امنیت، بکاپ/بازیابی، انطباق و عملیات | فازهای MVP | برنامه‌ریزی‌شده |

## قواعد پیشروی
- هر فاز دقیقاً یک سند canonical در `specs/phase-N.md` دارد.
- فاز بعدی فقط پس از پذیرش خروجی فاز قبلی آغاز می‌شود.
- قابلیت خارج از MVP صرفاً به دلیل وجود پوشه یا spec به API تبدیل نمی‌شود.
- `COMPLETE` فقط با شواهد واقعی اجرا اعلام می‌شود.
- تعارض‌های `docs/OPEN_QUESTIONS.md` باید پیش از فاز مرتبط رفع شوند.
