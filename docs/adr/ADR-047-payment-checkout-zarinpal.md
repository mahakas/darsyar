# ADR-047: خرید یک‌بارهٔ Basic/Pro از طریق زرین‌پال — تأییدشده

- **وضعیت:** accepted (تصمیم صریح مالک — 2026-10-29؛ پذیرش تصمیم معماری، نه مجوز اجرای Slice B)
- **هم‌راستا با:** R-004، R-095/096، R-121..128، R-132..147؛ ADR-035/039 (accepted)
- **دامنه:** فقط خرید یک‌بارهٔ Basic/Pro. خارج از دامنه: اشتراک‌ها، fair-use، grant رایگان، UI فرانت/ادمین، بازپرداخت بانکی، streaming/partial billing.

## زمینه

فاز ۲ (Slice B) به مدل پرداخت پایدار، اعتبارسنجی سرور-محور و اعطای کردیت اتمیک/idempotent نیاز دارد. این ADR تصمیم‌های تأییدشدهٔ مالک را به‌صورت قرارداد اجرایی ثبت می‌کند.

## تصمیم‌های ثبت‌شده

1. **محصولات اولیه (کاتالوگ مورد اعتماد):** Basic = 500,000 تومان / 500 کردیت؛ Pro = 1,000,000 تومان / 1,200 کردیت (R-136).
2. **کاتالوگ سرور-محور:** جدول `product_catalog`؛ تغییر قیمت فقط از مسیر operator/CLI (`scripts/upsert_product.py`) با رویداد `catalog_price_change` در `admin_audit_log` (actor، reason، before/after، timestamp) — بدون UI ادمین. به‌روزرسانی کاتالوگ و رویداد audit همزمان/اتمیک.
3. **اسنپشات immutable:** هر خرید، محصول، مبلغ تومانی، مبلغ provider/واحد و مقدار کردیت را در `payment_transactions` تثبیت می‌کند؛ تغییر قیمت آتی روی خریدهای موجود اثر ندارد.
4. **API:** `POST /api/v1/billing/checkout`، `GET /api/v1/billing/callback`، `GET /api/v1/billing/payments/{id}` (با ایزولیشن مالک).
5. **Idempotency:** `UNIQUE(user_id, idempotency_key)` + `request_fingerprint` از فیلد معنایی نرمال‌شدهٔ `product_id` (کلید فقط scope جست‌وجو). Same key/same fingerprint → payment موجود؛ different → `idempotency_conflict` بدون اثر مالی.
6. **مدل `payment_transactions`:** id UUID؛ user_id FK→users **RESTRICT** (حفظ تاریخچهٔ مالی؛ بدون CASCADE محض)؛ product_id؛ amount_toman int؛ credit_grant int؛ provider؛ provider_currency؛ provider_amount؛ authority (**UNIQUE جزئی**)؛ ref_id؛ idempotency_key + UNIQUE(user_id, key)؛ status؛ failure_code/reason؛ request_id؛ زمان‌ها. مهاجرت `0006_payment_transactions` (downgrade صریح).
7. **ماشین حالت (تصمیم در مورد `created`/`requesting`):**
   - `created` (رکورد اولیه) → **claim اتمیک** `created→requesting` با `UPDATE … WHERE status='created'` و راستی‌آزمایی rowcount==1؛ **دقیقاً یک هندلر** اجازهٔ تماس خارجی با درگاه را می‌گیرد؛ retry هم‌زمان درخواست تکراری به درگاه نمی‌فرستد.
   - `requesting` **قبل از تماس HTTP خارجی** persist می‌شود؛ crash/timeout/پاسخ بدشکل → `unknown_outcome` (توسط reconcile محدود، بدون resend کور).
   - `pending` پس از ذخیرهٔ authority معتبر؛ `succeeded` | `failed` فقط از `pending`؛ ترمینال‌ها دارای trigger رد گذار؛ `Status=NOK` هرگز `failed` را نهایی نمی‌کند.
   - **پاسخ checkout برای پیامد نامعلوم (تصمیم B):** `redirect_url` فقط پس از ذخیرهٔ authority معتبر و gateway URL در `pending` بازگردانده می‌شود؛ برای payment موجود/جدید در `requesting` یا `unknown_outcome` پاسخ پایدار `202 {payment_id, status}` (بدون `redirect_url` ساختگی/گم‌شده) تعریف می‌شود؛ same-key/same-payload در این حالت payment دوم یا درخواست درگاه تکراری نمی‌سازد؛ same-key/different-payload → `idempotency_conflict` پایدار.
   - **چهار حالت پیامد نامعلوم (تصمیم نهایی):**
     - **A — پیامد درخواست نامعلوم، authority ثبت‌نشده** (crash/timeout/قطع اتصال/پاسخ بدشکل پس از پذیرش احتمالی): بدون grant؛ بدون `failed` قطعی بدون شاهد معتبر؛ بدون resend کور؛ ماندن در غیرنهایی `requesting`/`unknown_outcome`؛ حفظ audit trail با طبقه‌بندی امن؛ اگر authority هرگز ذخیره نشده و قرارداد رسمی نمی‌تواند درخواست خارجی را قابل‌اعتماد به payment محلی پیوند دهد، **بازیابی خودکار ممکن نیست**؛ مسیر عملیاتی/دستی: مجاز، auditable (`payment_manual_resolution`) و هرگز بدون شواهد کافی grant نمی‌سازد؛ retry همان کلید/همان payload درخواست دوم به درگاه صادر نمی‌کند.
     - **B — authority ثبت‌شده؛ نتیجهٔ verify نامعلوم:** حفظ authority و payment موجود؛ بدون ایجاد درخواست جدید؛ بدون grant؛ **retry کنترل‌شدهٔ verify** برای همان payment/authority با سقف (bounded retry) مجاز است؛ payment غیرنهایی می‌ماند تا شاهد قطعی؛ تلاش‌های verify هم‌زمان نمی‌توانند grant تکراری بسازند.
     - **C — ناسازگاری provider/local:** تطبیق نتیجه با دقیقاً همان payment و authority ذخیره‌شده؛ اعتبارسنجی مبلغ و همهٔ فیلدهای مرتبطی که قرارداد تأییدشدهٔ provider در دسترس می‌گذارد؛ بدون grant وقتی correlation امن برقرار نیست؛ ثبت مورد reconcile auditable؛ نهایی‌سازی فقط پس از برقراری شواهد معتبر و در همان عملیات فاینال اتمیک/idempotent.
     - **D — callback دیررس برای payment ترمینال:** `succeeded` هرگز grant دوم نمی‌گیرد؛ `failed` صرفاً با callback بی‌اعتماد باز نمی‌شود؛ شواهد متعارض فقط برای reconcile ثبت می‌شوند نه تغییر خاموش وضعیت ترمینال؛ حفاظت ترمینال DB و ناوردان‌های ADR-035 حفظ می‌شوند.
8. **نهایی‌سازی اتمیک:** `pending→succeeded` (update شرطی + rowcount==1) + یک رکورد `credit_ledger` با `kind='plan_grant'` و کلید `payment:{id}:credit-grant` + افزایش `credit_accounts.available_balance` + ثبت `ref_id`/`succeeded_at`؛ بدون قفل ردیف در طول HTTP؛ retry فاینال idempotent.
9. **Duplicate/concurrency:** UNIQUE(authority) + گذار شرطی → یک grant؛ callback/verify تکراری و هم‌زمان → پیامد idempotent؛ `IntegrityError` → بازخوانی و پاسخ یکسان.
10. **Provider/local discrepancy:** 100 (موفق جدید) → grant فقط پس از تطبیق کامل؛ 101 (قبلاً verified): اگر local `succeeded` → idempotent بدون تغییر؛ اگر local `pending` → grant یک‌بار پس از تطبیق؛ دادهٔ متعارض/بی‌ارتباط → `unknown_outcome` + `payment_manual_resolution` در `admin_audit_log` بدون grant خودکار.
11. **روش پذیرش:** (الف) `رد` (ب) `verify 100` (ج) `verify 101` (د) callback تکراری/هم‌زمان (ه) عدم قطعیت/unknown_outcome (و) mismatch مبلغ/authority (ز) rollback اتمیک (ح) ایزولیشن کاربر (ط) حذف کاربر با حفظ تاریخچه.
12. **اعتبارسنجی sandbox** به‌عنوان گیت پذیرش نهایی انتگراسیون زرین‌پال (نه مجوز پرداخت واقعی).

## مراجع رسمی (دسترسی 2026-10-29)
- https://www.zarinpal.com/docs/sdk/nodejs/method/request
- https://www.zarinpal.com/docs/sdk/nodejs/method/verify
- https://www.zarinpal.com/docs/sdk/nodejs/method/inquiry
- https://www.zarinpal.com/docs/sdk/nodejs/method/unVerified
- https://github.com/ZarinPal/ZarinPal-node-SDK

صلاحیت: `merchant_id` (UUID) در بدنهٔ JSON؛ request: `POST {base}/pg/v4/payment/request.json {merchant_id, amount, callback_url, description, …}`؛ redirect: `{base}/pg/StartPay/{authority}`؛ verify: `POST {base}/pg/v4/payment/verify.json {merchant_id, amount, authority}`؛ inquiry: `POST {base}/pg/v4/payment/inquiry.json {authority}`؛ unverified: `POST {base}/pg/v4/payment/unVerified.json`. Base: prod `https://payment.zarinpal.com`، sandbox `https://sandbox.zarinpal.com`.

**اختلاف حداقل مبلغ — ثبت‌شده:** مستندات رسمی request «حداقل 10,000 ریال» را ذکر می‌کنند؛ `Validator` SDK مقدار 1,000 را اعمال می‌کند. **خط پایهٔ پیشنهادی: مستندات رسمی جاری (10,000)**؛ هر دو محصول بالای هر دو آستانه‌اند؛ تأیید نهایی با sandbox در گیت پذیرش انجام می‌شود.

## پیامدها
- فایل‌های متأثر: `0006_payment_transactions.py`, `0007_product_catalog.py`, `models/payment_transaction.py`, `models/product_catalog.py`, `repositories/payment_transactions.py`, `services/payment.py` (+`ZarinPalProvider`), `schemas/billing.py`, `api/v1/billing.py`, `core/config.py`, `.env.example`, تست‌ها، `docs/API_CONTRACT.md`.
- `docs/REFUND_POLICY.md` همچنان DRAFT است؛ ADR-039 تأیید شرایط مشتری‌محور نیست.

## محدودیت‌های باقی‌مانده (گیت‌های پذیرش زنده)
- محدودیت منطقه‌ای IP زین‌پال در محیط توسعه فعلی همچنان پابرجاست؛ **هیچ آزمون sandbox/زنده‌ای انجام نشده** و اتصال واقعی به provider تأیید نشده است.
- گیت پذیرش نهایی انتگراسیون زنده: اجرای end-to-end در sandbox از محیط مجاز (IP ایرانی واجد شرایط) + تأیید دسترسی runtime تولید به provider — قبل از اعلام تکمیل انتگراسیون زنده. "های mocked جایگزین آن نیستند.
