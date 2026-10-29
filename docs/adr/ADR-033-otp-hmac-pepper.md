# ADR-033: HMAC و pepper برای OTP

- Status: accepted (تأیید مالک — 2026-10-29؛ به‌عنوان مشخص‌سازی ADR-003، نه supersede)
- Context: OTP شش‌رقمی فضای جست‌وجوی کم دارد؛ digest بدون secret برای حملهٔ آفلاین کافی نیست.
- Decision: digest با HMAC-SHA256 و pepper مستقل از DB و APP_SECRET_KEY ساخته شود؛ compare ثابت‌زمان و نسخه‌بندی pepper پشتیبانی شود.
- Rejected alternatives: ذخیرهٔ plaintext؛ Argon2id بدون pepper برای OTP.
- Consequences: مدیریت/چرخش secret و پاک‌سازی challenge تست می‌شود.
- Affected files: `backend/app/core/security.py`, auth service, settings, tests.

## شواهد انطباق (2026-10-29)
- با R-100/R-101 و ADR-003 (accepted) هم‌خوان است؛ سیاست امنیتی جدیدی معرفی نمی‌کند و الزامی را تضعیف نمی‌کند.
- پیاده‌سازی: `core/security.py` (`otp_digest`, `otp_matches`, `resolve_pepper_for`)؛ تنظیمات `OTP_PEPPER`, `OTP_PEPPER_ID`, `OTP_PREVIOUS_PEPPER`؛ تست‌ها در `test_security_tokens.py` و `test_auth_db.py`.
