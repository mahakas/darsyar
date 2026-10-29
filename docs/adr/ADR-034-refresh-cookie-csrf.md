# ADR-034: مدل ذخیره‌سازی و چرخش توکن

- Status: accepted (تأیید مالک — 2026-10-29؛ به‌عنوان مشخص‌سازی ADR-003، نه supersede)
- Context: نگهداری توکن در storage قابل‌دسترسی JavaScript خطر سرقت دارد؛ کوکی خودکار به سرور ارسال می‌شود و CSRF باید کنترل شود.
- Decision: access token در حافظهٔ runtime، refresh در cookie HttpOnly/Secure/SameSite و فقط hash در DB؛ محافظت CSRF و کنترل Origin اجباری. reuse موجب ابطال خانواده می‌شود.
- Rejected alternatives: refresh در localStorage؛ کوکی بدون CSRF.
- Consequences: grace همزمانی باید پس از تحلیل threat model مشخص و تست شود (به ADR-046 مراجعه شود).
- Affected files: auth API, frontend API client, `docs/SECURITY_THREAT_MODEL.md`.

## شواهد انطباق (2026-10-29)
- با R-105 تا R-109 و ADR-003 (accepted) هم‌خوان است؛ سیاست امنیتی جدیدی معرفی نمی‌کند و الزامی را تضعیف نمی‌کند.
- پیاده‌سازی: `api/v1/auth.py` (کوکی‌های `darsyar_refresh` HttpOnly/Secure/SameSite=Lax و `darsyar_csrf`؛ CSRF double-submit؛ بررسی Origin)؛ `core/security.py` (JWT و digest)؛ `repositories/refresh_tokens.py` (فقط hash، jti/خانواده).
- رفتار «reuse → ابطال خانواده» در `test_auth_db.py` اثبات شده و جزئیات grace تحت بررسی ADR-046 است.
