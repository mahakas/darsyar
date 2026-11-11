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
## مدل‌های پیاده‌سازی‌شدهٔ پلن/اعتبار (ADR-052 — وضعیت واقعی schema)

### plan_entitlements
- `id` UUID PK؛ `user_id` FK→users (RESTRICT)؛ `payment_id` FK→payment_transactions (RESTRICT؛ یکتا)؛ `product_id`/`plan_type` (credit|unlimited)؛ `status` (active|expired|cancelled)؛ `activated_at`/`expires_at` (UTC)؛ `granted_credits`/`remaining_credits` (برای unlimited صفر)؛ `snapshot` JSON (اسنپشات خرید)؛ `cancelled_at/cancelled_by/cancellation_reason`.
- قیدها: status معتبر؛ granted/remaining ≥ 0؛ سازگاری credit/unlimited؛ `UNIQUE(payment_id)`؛ ایندکس `(user_id, product_id, status)` و `expires_at`.

### credit_grants
- `id`؛ `user_id`؛ `entitlement_id` (nullable)؛ `kind` (free_grant|plan_grant)؛ `original_amount`/`remaining_amount` (>0 / ≥0 / ≤original)؛ `expires_at` (nullable)؛ `payment_id` (nullable). ایندکس `(user_id, expires_at)`.
- **ناوردان:** مجموع remainingهای معتبر + مصرف‌شده‌ها قابل بازسازی است؛ انقضای entitlement تمام grants همان entitlement را باطل می‌کند (رویداد جبرانی `adjust` در ledger + کاهش projection).

### payment_transactions (ستون‌های جدید 0012)
- `plan_type` (credit|unlimited)؛ `duration_days` int>0 — Snapshot خرید با catalog در لحظهٔ checkout؛ تغییر کاتالوگ خریدهای قبلی را تغییر نمی‌دهد.

### product_catalog (ستون‌های جدید 0012)
- `plan_type` (credit|unlimited)؛ `duration_days`>0؛ `credit_grant`=0 برای unlimited؛ محصولات اولیه: basic (500000/500/30)، pro (1000000/1200/30)، unlimited (1500000/0/30).

### cancellation_requests / refund_records
- لغو: `status` (pending|withdrawn|approved|rejected)، `mode` (preserve_until_expiry|immediate)، actor/timestamp/reason. بازپرداخت: `status` (requested|approved|rejected|completed)، `requested_amount/approved_amount/credit_voided`، `provider_settlement_ref` (فقط با تأیید خارجی تکمیل می‌شود).

### رابطهٔ رزرو با grantها — وضعیت فعلی
- **پیاده‌سازی‌نشده:** رزروها هنوز `grant_id`/allocation ندارند (C-02؛ OQ-026). مدل پیشنهادی تخصیص چند-grant (reservation_id، grant_id، allocated/consumed/released، state، idempotency) **پیشنهادی است، نه پیاده‌سازی‌شده**.


## User grade selection (R-019 — implemented schema)

- `users.selected_grade` is nullable and constrained to 1..12 when set.
- New/legacy users remain `NULL`; no default or inferred grade is written.
- The authenticated user profile endpoint is the only supported self-service writer. Chat reads the persisted value from the authenticated user record and rejects missing/invalid grade before any credit reservation.
- Client-supplied grade values are not authoritative.
