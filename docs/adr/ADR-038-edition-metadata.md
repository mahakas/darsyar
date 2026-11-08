# ADR-038: سال چاپ به‌عنوان metadata سند

- Status: accepted
- Decision date: 2026-11-09 (تصمیم صریح مالک)

## Context

نسخه‌های متفاوت یک کتاب ممکن است متن، ترتیب و شمارهٔ صفحهٔ متفاوتی داشته باشند؛ استفاده از سال پیش‌فرض می‌تواند ارجاع نادرست تولید کند.

## Decision

- سیاست **per_document** پذیرفته شد: `edition_year` برای هر سند و در manifest اجباری است.
- سال ۱۴۰۳ فقط مقدار واقعی نسخه‌هایی است که چاپ ۱۴۰۳ بودنشان اثبات شده؛ مقدار پیش‌فرض یا fallback سراسری نیست.
- نبودن یا نامعتبر بودن `edition_year` باید به خطای اعتبارسنجی یا `needs_review` منجر شود؛ سال چاپ از نام فایل، مسیر یا مقدار تنظیمات حدس زده نمی‌شود.
- `ACTIVE_EDITION_YEAR` فقط برای انتخاب میان نسخه‌های مشخص و موجودِ یک `(subject, grade)` به‌کار می‌رود؛ این تنظیم هرگز metadata مفقود سند را تکمیل نمی‌کند.
- اگر چند نسخهٔ فعال وجود داشته باشد و انتخاب یکتا ممکن نباشد، ingestion با `ambiguous_edition` متوقف می‌شود و حدس نمی‌زند.
- edition باید در metadata سند، فیلترهای retrieval، کلیدهای cache و citation حفظ شود.

## Rejected alternatives

- فرض جهانی چاپ ۱۴۰۳: رد شد، چون نسخهٔ واقعی هر سند باید مستقل شناسایی شود.
- پرکردن edition مفقود با `ACTIVE_EDITION_YEAR`: رد شد، چون این تنظیم ابزار انتخاب نسخهٔ موجود است نه جایگزین metadata سند.

## Consequences

- `edition_year` در هر manifest اجباری است و برای idempotency، retrieval، cache و citation بخشی از هویت نسخه محسوب می‌شود.
- اسناد فاقد edition معتبر تا تعیین تکلیف آمادهٔ ingestion تولیدی نیستند.

## Affected files

`AGENTS.md`, `docs/DECISIONS.md`, `docs/RESOURCE_LAYOUT.md`, document schema، ingestion، retrieval cache و citations.
