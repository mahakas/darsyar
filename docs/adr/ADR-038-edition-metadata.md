# ADR-038: سال چاپ به‌عنوان metadata سند

- Status: accepted (owner approval 2026-11-09)
- Context: نسخه‌های متفاوت یک کتاب ممکن است صفحه و محتوای متفاوت داشته باشند.
- Decision: `edition_year` در هر سند/manifest اجباری است. `ACTIVE_EDITION_YEAR` فقط در صورت وجود نسخهٔ مشخص استفاده می‌شود؛ ابهام باید خطا دهد.
- Edition identity: هویت نسخه باید در کل زنجیره (ingestion و retrieval/cache/citation) قابل ردیابی بماند؛ هیچ سال چاپ سراسری hard-code نمی‌شود؛ اگر چند نسخهٔ فعال برای (subject،grade) باشد و `ACTIVE_EDITION_YEAR` معتبر نباشد، `ambiguous_edition`.
- Rejected alternatives: فرض جهانی چاپ ۱۴۰۳.
- Consequences: retrieval/cache/citation باید edition را در فیلتر و کلیدها لحاظ کنند.
- Affected files: document schema, ingestion, retrieval cache, citations.
