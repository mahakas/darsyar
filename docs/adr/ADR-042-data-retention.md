# ADR-042: نگهداشت و حذف داده

- Status: proposed
- Context: بخشی از کاربران زیر ۱۸ سال‌اند و نگهداشت نامحدود داده لازم نیست.
- Decision: retention دوره‌ای برای OTP، upload، logs، traces و soft/hard delete تعریف می‌شود؛ حذف قانونی مالی و بی‌نام‌سازی از محتویات قابل حذف جداست.
- Rejected alternatives: نگهداشت دائمی همهٔ پیام‌ها/traceها بدون نیاز.
- Consequences: پاک‌سازی idempotent، export/delete endpoints و backup retention تست می‌شوند.
- Affected files: retention jobs, privacy UX, `docs/CONSENT_AND_PRIVACY_DRAFT.md`.
