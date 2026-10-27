# ADR-034: مدل ذخیره‌سازی و چرخش توکن

- Status: proposed
- Context: نگهداری توکن در storage قابل‌دسترسی JavaScript خطر سرقت دارد؛ کوکی خودکار به سرور ارسال می‌شود و CSRF باید کنترل شود.
- Decision: access token در حافظهٔ runtime، refresh در cookie HttpOnly/Secure/SameSite و فقط hash در DB؛ محافظت CSRF و کنترل Origin اجباری. reuse موجب ابطال خانواده می‌شود.
- Rejected alternatives: refresh در localStorage؛ کوکی بدون CSRF.
- Consequences: grace همزمانی باید پس از تحلیل threat model مشخص و تست شود.
- Affected files: auth API, frontend API client, `docs/SECURITY_THREAT_MODEL.md`.
