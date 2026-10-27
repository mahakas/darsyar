# ADR-038: سال چاپ به‌عنوان metadata سند

- Status: proposed
- Context: نسخه‌های متفاوت یک کتاب ممکن است صفحه و محتوای متفاوت داشته باشند.
- Decision: `edition_year` در هر سند/manifest اجباری است. `ACTIVE_EDITION_YEAR` فقط در صورت وجود نسخهٔ مشخص استفاده می‌شود؛ ابهام باید خطا دهد.
- Rejected alternatives: فرض جهانی چاپ ۱۴۰۳.
- Consequences: retrieval/cache/citation باید edition را در فیلتر و کلیدها لحاظ کنند.
- Affected files: document schema, ingestion, retrieval cache, citations.
