# ADR-037: نگاشت grade و محتوای نظام قدیم

- Status: accepted (owner approval 2026-11-09)
- Context: شماره‌گذاری نظام آموزشی قدیم و جاری یکسان نیست و نگاشت خاموش می‌تواند grade ceiling را نقض کند.
- Decision: grades جاری ۱–۱۲ canonical هستند؛ legacy pre-university به صورت خودکار به ۱۲ نرود تا metadata/مالکیت نگاشت تأیید شود.
- Per-source rule: هر منبع legacy (`pre_university`/`grade_pre`) نیازمند بازبینی صریح سطح-منبع و نگاشت پایهٔ تأییدشده توسط مالک است؛ نگاشت تأییدشده باید صریحاً در metadata/manifest منبع باشد؛ منابع بازبینی‌نشده/مبهم باید `needs_review` شوند یا ingestion شکست بخورد؛ هرگز هم‌ارزی محتوایی/نظام آموزشی از نام پوشه استنتاج نشود.
- Rejected alternatives: نسبت دادن هر مسیر legacy به ۱۲ بدون بررسی.
- Consequences: manifest و صف review برای اسناد مبهم لازم است.
- Affected files: `docs/GRADE_MAPPING.md`, ingestion metadata, tests.
