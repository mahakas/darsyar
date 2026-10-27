# ADR-003: OTP و نشست امن

- Status: Accepted
- Decision: OTP کوتاه‌عمر و یک‌بارمصرف؛ ذخیره‌سازی HMAC-SHA256 با pepper محرمانه و مقایسه constant-time؛ Argon2id برای رمز عبور در صورت افزودن ورود رمزی. Refresh tokens در سمت سرور قابل ابطال و چرخشی باشند.
- Access tokens کوتاه‌عمرند. Refresh token ترجیحاً در کوکی HttpOnly, Secure, SameSite با CSRF mitigation مناسب نگهداری شود؛ access token در حافظهٔ فرانت‌اند.
- تشخیص استفادهٔ مجدد refresh token باید نشست/خانوادهٔ مرتبط را باطل کند.
- SMS و OTP هرگز در log ثبت نمی‌شوند. شماره تلفن در لاگ‌ها redact یا pseudonymize می‌شود.
- Required tests: brute-force throttling، replay، reuse، expiry، clock skew، invalidation و عدم افشای secrets.
