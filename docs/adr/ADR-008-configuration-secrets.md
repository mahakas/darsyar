# ADR-008: تنظیمات و اسرار

- Status: Accepted
- Decision: تنظیمات زیرساختی و اسرار از env/secret manager خوانده می‌شوند؛ تنظیمات محصول که ادمین مجاز به تغییر آن است در DB با audit trail ذخیره می‌شود.
- Secret rotation باید پشتیبانی شود. مقدار secret هرگز در API پنل، خطا یا log بازگردانده نمی‌شود.
- تغییرات حساس مثل provider، مدل و محدودیت مصرف باید schema validation و تاریخچهٔ تغییر داشته باشند.
