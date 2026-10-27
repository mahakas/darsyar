# ADR-033: HMAC و pepper برای OTP

- Status: proposed
- Context: OTP شش‌رقمی فضای جست‌وجوی کم دارد؛ digest بدون secret برای حملهٔ آفلاین کافی نیست.
- Decision: digest با HMAC-SHA256 و pepper مستقل از DB و APP_SECRET_KEY ساخته شود؛ compare ثابت‌زمان و نسخه‌بندی pepper پشتیبانی شود.
- Rejected alternatives: ذخیرهٔ plaintext؛ Argon2id بدون pepper برای OTP.
- Consequences: مدیریت/چرخش secret و پاک‌سازی challenge تست می‌شود.
- Affected files: `backend/app/core/security.py`, auth service, settings, tests.
