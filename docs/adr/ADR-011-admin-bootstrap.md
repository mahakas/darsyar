# ADR-011: ایجاد ادمین اولیه

- Status: Accepted
- Decision: ایجاد admin اولیه از دستور مدیریتی صریح با تأیید اپراتور انجام می‌شود. startup عادی ادمین جدید نمی‌سازد.
- Reason: جلوگیری از ارتقای ناخواستهٔ حساب با تغییر env یا رفتار seed در هر restart.
- Required controls: Argon2id، audit log، least privilege، rate limit و روش rotation امن.
