# ADR-024: منبع، مجوز و منشأ منابع آموزشی

- Status: proposed
- Context: منابع درسی دارای حقوق و شرایط استفاده‌اند؛ OCR، embedding، ذخیره و نمایش می‌تواند محدودیت متفاوت داشته باشد.
- Decision: هر سند باید منشأ، ناشر، سال چاپ و `license_note` داشته باشد. ingestion production بدون ثبت مجوز مسدود است.
- Rejected alternatives: ورود هر PDF بدون بررسی؛ فرض عمومی‌بودن تمام کتاب‌ها.
- Consequences: ثبت مجوز بخشی از ingestion است؛ مالک مسئول بررسی حقوقی و مستندسازی تأیید خواهد بود.
- Affected files: `docs/RESOURCE_LAYOUT.md`, `docs/licenses/`, manifest schema, ingestion service.
