# مدل دادهٔ هدف و قیود اصلی

این سند طرح مفهومی است؛ migration هر موجودیت در فاز مربوطه نوشته می‌شود. وجود نام جدول در این سند به معنی وجود جدول در schema اولیه نیست.

| موجودیت | نقش | قیود کلیدی |
|---|---|---|
| users | کاربر و grade منتخب | UUID، phone E.164 یکتا، soft delete |
| otp_challenges | چالش OTP | digest keyed، attempts، expires_at، consumed_at |
| refresh_tokens | نشست/زنجیره refresh | فقط hash توکن، jti، family/session id، revocation |
| conversations/messages | تاریخچه | owner predicate در query، وضعیت پاسخ جزئی |
| credit_accounts | projection مانده | قفل ردیف برای تغییر، سازگاری با ledger |
| credit_ledger | رویداد مالی append-only | INSERT/SELECT برای نقش اپ، idempotency یکتا، بدون UPDATE/DELETE |
| reservations | مصرف موقت | وضعیت، نوع credit/unlimited، idempotency، expiration/reconcile |
| payment_transactions | پرداخت | authority یکتا، مبلغ/واحد، وضعیت verify، idempotency |
| usage_events | مصرف/latency/هزینه | بدون متن پیام غیرضروری، مناسب بازسازی fair-use |
| documents/chunks | کتاب و evidence | grade، edition_year، subject، منشأ، checksum، validity |
| index_meta | مدل/ابعاد embedding | یک ایندکس فعال برای هر namespace/دامنهٔ سازگار |
| settings | تنظیمات محصول | JSONB typed، validation در write، audit actor/reason |
| admin_audit_log | عملیات ادمین | append-only با قبل/بعد و دلیل |
| traces | ردگیری کنترل‌شده | retention محدود، prompt storage به‌صورت پیش‌فرض خاموش |

## نکتهٔ باز مالی
جزئیات دقیق اثر reserve/release/settle روی available/reserved/ledger باید پیش از فاز ۲ در `docs/OPEN_QUESTIONS.md` حل و در ADR ثبت شود. `credit_accounts` به‌تنهایی منبع حقیقت نیست؛ ledger و قواعد محاسبه باید با هم سازگار تعریف شوند.

## کلیدها و حذف
UUID برای شناسه‌های عمومی. تمام FKها `ondelete` صریح دارند. حذف ابتدا soft delete و چرخهٔ حذف فیزیکی/بی‌نام‌سازی با سیاست retention انجام می‌شود.
