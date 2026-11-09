# ADR-024: منبع، مجوز و منشأ منابع آموزشی

- Status: accepted (owner approval 2026-11-09)
- Context: منابع درسی دارای حقوق و شرایط استفاده‌اند؛ OCR، embedding، ذخیره و نمایش می‌تواند محدودیت متفاوت داشته باشد.
- Decision: هر سند باید منشأ، ناشر، سال چاپ و `license_note` داشته باشد. ingestion production بدون ثبت مجوز مسدود است.
- Permission/evidence scope: هر منبع باید منشأ قابل ردیابی، ناشر، سال چاپ و شاهد مجوز داشته باشد؛ اجازه باید صریحاً عملیات مدنظر (کسب، ذخیره، استخراج/OCR، embedding/ایندکس، نمایش/نقل) را پوشش دهد؛ `license_note` متادیتای ارجاع به شاهد است و به‌تنهایی اثبات مجوز نیست؛ هرگز مجوز/اجازه/ناشر/منبع/استنتاج حقوقی نباید اختراع شود؛ مالک مسئول تأیید مجوزهای واقعی است.
- Rejected alternatives: ورود هر PDF بدون بررسی؛ فرض عمومی‌بودن تمام کتاب‌ها.
- Consequences: ثبت مجوز بخشی از ingestion است؛ مالک مسئول بررسی حقوقی و مستندسازی تأیید خواهد بود.
- Affected files: `docs/RESOURCE_LAYOUT.md`, `docs/licenses/`, manifest schema, ingestion service.
