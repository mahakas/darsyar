# ADR-037: نگاشت grade و محتوای نظام قدیم

- Status: proposed
- Context: شماره‌گذاری نظام آموزشی قدیم و جاری یکسان نیست و نگاشت خاموش می‌تواند grade ceiling را نقض کند.
- Decision: grades جاری ۱–۱۲ canonical هستند؛ legacy pre-university به صورت خودکار به ۱۲ نرود تا metadata/مالکیت نگاشت تأیید شود.
- Rejected alternatives: نسبت دادن هر مسیر legacy به ۱۲ بدون بررسی.
- Consequences: manifest و صف review برای اسناد مبهم لازم است.
- Affected files: `docs/GRADE_MAPPING.md`, ingestion metadata, tests.
