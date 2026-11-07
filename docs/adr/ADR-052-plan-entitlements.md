# ADR-052: مدل Entitlement پلن‌ها و تخصیص اعتبار

- **وضعیت:** accepted (تصمیم مالک — 2026-11-07؛ تأیید کامل تصمیمات هشت‌گانه OQ-018..025)
- **تاریخ:** 2026-10-31
- **هم‌راستا با:** R-125..139، R-144؛ ADR-035/040/047/048/049/050

## زمینه

`credit_accounts.available_balance` موجودی تجمیعی است و برای سیاست‌های مصوب کافی نیست: استقلال Basic/Pro، انقضای مستقل هر خرید، حفظ اعتبارها حین Unlimited، ابطال قابل‌انتساب در refund/لغو، و خرید مجدد با تمدید روی `expires_at` فعلی، نیازمند رکوردهای مستقل entitlement و grant دارند.

## تصمیم تأییدشده

1. جدول `plan_entitlements`: هویت دورهٔ فعال هر پلن (user_id، product_id، status، activated_at، expires_at، granted_credits، remaining_credits، payment_id، snapshot کاتالوگ، metadata لغو).
2. جدول `credit_grants`: سبد/محفظهٔ اعتبار قابل‌انتساب (entitlement_id، user_id، kind=free_grant|plan_grant، original/remaining، expires_at، payment_id).
3. هر Reservation می‌تواند به grant خاص گره بخورد (`grant_id` اختیاری)؛ مصرف فقط از grants معتبر (remaining>0 و expires_at>now).
4. `credit_accounts` همچنان projection تجمیعی است و با ledger و مجموع grants/entitlements بازسازی می‌شود.
5. **ترتیب مصرف بین Free Grant/Basic/Pro طبق تصمیم مالک است** (OQ-026)؛ معماری به‌گونه‌ای است که پس از تصمیم، بدون بازنویسی ledger قابل اعمال باشد (انتخاب grant در تابع واحد).
6. Unlimited: بدون grant؛ حق دسترسی زمانی (status/expires_at). رزرو unlimited فقط با entitlement فعال مجاز است.
7. انقضای هر entitlement به‌صورت اتمیک اعتبارهای (grantهای) همان entitlement را باطل می‌کند (رویداد جبرانی ledger + projection)؛ سایر پلن‌ها دست‌نخورده.
8. Refund/Cancellation: رکوردهای مستقل (refund_records / cancellation_requests) با حالت‌ها و audit؛ فقط grantهای مربوط به همان خرید/پلن باطل می‌شوند.

## پیامدها
- مهاجرت 0012 (جدول‌ها + افزودن plan_type/duration_days به کاتالوگ + seed unlimited).
- تأثیر بر PaymentService.finalize_succeeded (ساخت entitlement + grant)، FairUse/Reservation (گیت unlimited)، jobهای دوره‌ای (expire entitlements).
- گزینهٔ ردشده: ادامه با فقط موجودی تجمیعی (انقضای هر پلن غیرقابل تشخیص).
