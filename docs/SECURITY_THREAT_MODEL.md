# مدل تهدید امنیتی درسیار

## دارایی‌ها
شمارهٔ موبایل، نشست‌ها و JWT، پیام‌ها، منابع آموزشی و مجوزشان، کلیدهای provider، اعتبار و تراکنش‌ها، شواهد بازیابی‌شده و دادهٔ عملیاتی.

## مهاجم‌ها و مرز اعتماد
کاربر عادی یا مخرب، محتوا/پیوند تزریق‌شده در PDF یا وب، provider خراب/کند، callback تکراری، دسترسی غیرمجاز به endpoint ادمین، و افشای پایگاه داده یا لاگ.

## کنترل‌های لازم
- OTP با HMAC-SHA256 و pepper مستقل از DB؛ زمان کوتاه، یک‌بار مصرف، rate limit و ضد enumeration.
- Access token کوتاه‌عمر در حافظهٔ runtime؛ refresh token فقط در کوکی HttpOnly/Secure و hash در DB، همراه CSRF و تشخیص reuse.
- CORS دقیق، trusted proxy روشن، CSP، HSTS در production، `nosniff` و `Referrer-Policy`.
- query-level ownership و تست multi-user isolation.
- فایل upload در quarantine و بیرون web root؛ بررسی magic bytes، MIME، حجم، زمان؛ فایل هرگز اجرا/رندر مستقیم نشود.
- SSRF: مسدودکردن IP داخلی، loopback، link-local و cloud metadata؛ اتصال به IP تأییدشده و مقابله با DNS rebinding.
- prompt injection: محتوای بیرونی دادهٔ غیرقابل‌اعتماد است؛ دستور ابزار و مجوزها مستقل از محتوا کنترل شوند.
- مالی: reservation قبل provider، PostgreSQL transaction، idempotency DB، ledger append-only و reconcile.
- logging: redact در کلیدهای ساخت‌یافته و الگوهای رشته‌ای؛ prompt کاربر به‌صورت پیش‌فرض در trace ذخیره نشود.
- کاربران ممکن است زیر ۱۸ سال باشند؛ حداقل‌سازی، حذف، صادرسازی، retention و تأیید حقوقی لازم است.

## ریسک‌های نیازمند تصمیم
- وضعیت fail-open چت هنگام قطعی Redis باید با سقف هزینهٔ اضطراری تعیین تکلیف شود؛ چت هزینه‌زا بدون guard جایگزین فعال نشود.
- طراحی نهایی CSRF، refresh grace و بازاتصال stream در فاز ۱/۳ تست شود.
- هیچ مدعای انطباق حقوقی خودکار از این سند برداشت نشود؛ `R-211` لازم‌الاجرا است.
