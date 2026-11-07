# ADR-053: تخصیص grant→رزرو (reservation_credit_allocations)

- **وضعیت:** accepted (تصمیم مالک — 2026-11-07؛ هم‌راستا با D-01/D-02 (OQ-026)، D-03 (OQ-027)، D-04 (OQ-028)، D-05 و ADR-035/048/052)
- **هم‌راستا با:** D-01/D-02 (OQ-026)، D-03 (OQ-027)، D-04 (OQ-028)، D-05، ADR-035/048/052، R-125/126

## زمینه
رزروهای فعلی منبع grant را ثبت نمی‌کنند (فقط `available_balance` تجمیعی)؛ انقضای مستقل grant و EFF بدون رکورد تخصیص قابل اثبات نیست.

## تصمیم تأییدشده
1. جدول `reservation_credit_allocations`: (reservation_id، grant_id، allocated، consumed، released، voided، status، timestamps) با `UNIQUE(reservation_id, grant_id)` و CHECK `consumed+released+voided <= allocated`.
2. اضافه‌شدن `credit_grants.reserved_amount` (claimهای در جریان)؛ واجد شرایط بودن = `remaining_amount - reserved_amount > 0` و معتبر بودن grant (منقضی نشده/باطل نشده) و نبود Unlimited فعال (D-02).
3. ترتیب EFF در انتخاب: `expires_at ASC NULLS LAST, created_at ASC, id ASC`.
4. رزرو: قفل grantها + ثبت allocations + افزایش reserved؛ ناکافی → بدون هیچ اثر جزئی.
5. Settle: فقط allocations همان رزرو، یک‌بار؛ reserved→consumed؛ remaining کاهش.
6. Release: بازگرداندن فقط به grantهای معتبر (expired/voided → allocation voided بدون بازگشت؛ settle در جریان پس از انقضا طبق D-03).
7. Unlimited: مسیر جدا؛ بدون allocation.

## پیامدها
- مهاجرت‌های 0013 و 0014 (هم‌سبک 0012: forward-only؛ downgrade پیش از DDL رد می‌شود)؛ 0013 جدول تخصیص + `reserved_amount` و 0014 `lifecycle_reason`/`voided_at`.
- سازگاری با رزروهای تاریخی: بدون بازسازی retroactive؛ مسیر legacy فقط با فقدان کامل grant فعال می‌شود (OQ-029).
- مهلت رزرو: ثابت ۱۵ دقیقه از created_at (D-03/OQ-027)؛ settle پیش از مهلت حتی با انقضای طبیعی grant؛ پس از آن فقط release منبع‌محور.
- مهر غیرمخرب grant غیرفعال: `remaining = reserved` (حفظ ناوردان؛ بدون تصمیم‌گیری برای OQ-028).
- **مجوز settle دلیل‌محور:** NULL/natural_expiry → OQ-027؛ immediate_cancellation/approved_refund → گرندفادر OQ-028 (pre-void allocation)؛ `admin_void` → هرگز settle (D-05)؛ رزرو جدید فقط با `lifecycle_reason IS NULL` و پس از قفل+بازاعتبارسنجی grant.
