# نگاشت پایهٔ آموزشی

پایه‌های جاری ۱ تا ۱۲ تنها gradeهای canonical در MVP هستند. هیچ مسیر legacy نباید بدون شواهد و تأیید صریح به یک پایهٔ جاری تبدیل شود (ADR-037).

| دستهٔ مسیر | پایهٔ canonical | وضعیت |
|---|---:|---|
| `grade1` … `grade6` | ۱ … ۶ | نظام جاری؛ metadata سند باید بررسی شود |
| `grade7` … `grade9` | ۷ … ۹ | نظام جاری؛ metadata سند باید بررسی شود |
| `grade10` … `grade12` | ۱۰ … ۱۲ | نظام جاری؛ metadata سند باید بررسی شود |
| `pre_university` / `grade_pre` | تعیین‌نشده | بدون نگاشت خودکار؛ `needs_review` تا تأیید صریح |

## سیاست مسیرهای legacy

- `pre_university` و `grade_pre` alias پایهٔ ۱۲ نیستند.
- نام مسیر، نام فایل یا فرض نظام آموزشی برای تعیین grade کافی نیست.
- سند تا بررسی انسانی و تأیید صریح مالک در `needs_review` می‌ماند.
- خروج از `needs_review` فقط با ثبت grade canonical صریح در manifest همان سند و حفظ شواهد تصمیم مجاز است.
- تا آن زمان سند وارد corpus آمادهٔ retrieval یا ingestion تولیدی نمی‌شود.
- هر تغییر در این سیاست به ADR و تأیید مالک نیاز دارد.

`selected_grade` برای هر درخواست الزامی است؛ هر دو شاخهٔ dense و lexical باید `chunk.grade_level <= selected_grade` را در SQL اعمال کنند.
