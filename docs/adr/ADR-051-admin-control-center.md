# ADR-051: Admin Control Center و دسترسی مدیریتی سراسری

- **Status:** Proposed
- **Date:** 2026-10-31
- **Owners:** Product owner / Architecture
- **Related:** AGENTS.md R-097, R-117, R-122; ADR-011; specs/phase-7.md; docs/ADMIN_CONSOLE_SPEC.md

## Context

Darsyar به یک پنل مدیریتی یکپارچه نیاز دارد که علاوه بر ادارهٔ کاربران و مالی، عملیات هوش مصنوعی، دانش آموزشی، امنیت، تنظیمات و سلامت زیرساخت را پوشش دهد. مالک محصول تأیید کرده است که فقط یک نقش مدیریتی به نام admin وجود داشته باشد و این نقش علاوه بر پنل مدیریت، تمام قابلیت‌های عادی پنل کاربر را نیز در اختیار داشته باشد.

دسترسی مدیریتی گسترده، به‌ویژه مشاهده یا اقدام به نمایندگی از کاربر، ریسک افشای داده، عملیات اشتباه مالی و دشواری انتساب اقدامات را افزایش می‌دهد. بنابراین اختیار گسترده باید با هویت actor/subject جدا، audit و کنترل‌های عملیات حساس همراه باشد.

## Decision proposed

1. نقش‌های محصول در این دامنه فقط user و admin باقی می‌مانند؛ نقش مدیریتی میانی یا RBAC قابل‌پیکربندی ساخته نمی‌شود.
2. Admin به همهٔ قابلیت‌های user-facing و همهٔ ماژول‌های مدیریتی محصول دسترسی دارد.
3. Admin Console مرکز کنترل عملیات است و مدیریت تنظیمات محصولی باید از UI ممکن باشد؛ secrets و تنظیمات زیرساختی همچنان تابع مرزهای AGENTS R-070/R-073 هستند.
4. عملیات به نمایندگی از کاربر از طریق acting context زمان‌دار و server-side انجام می‌شود؛ token یا credential کاربر هدف جعل یا صادر نمی‌شود.
5. در هر عملیات delegated، شناسهٔ Admin (actor) و کاربر هدف (subject) جداگانه ثبت می‌شوند.
6. عملیات حساس مالی، امنیتی، privacy و حذف، حتی در acting context، از جریان مدیریتی اختصاصی و step-up استفاده می‌کنند.
7. Ledger، Secretها، grade ceiling، citation validation، ownership و قیود integrity با اختیار Admin قابل دورزدن نیستند.
8. Audit مدیریتی append-only و مستقل از ledger و application logs باقی می‌ماند.

## Security controls proposed for ratification

- MFA برای حساب Admin؛ اولویت با WebAuthn/Passkey مقاوم به phishing و عامل جایگزین امن.
- Re-authentication/step-up برای refund، adjustment، تغییر پلن‌های فعال، حذف/export حساس، مدیریت نشست و تغییر Provider/Secret.
- reason اجباری برای acting session و عملیات حساس.
- زمان انقضای کوتاه و پایان صریح acting session.
- redaction در audit و trace؛ هیچ token، OTP یا secret ثبت نشود.
- dry-run و impact preview برای عملیات bulk.

## Consequences

### Positive
- مدیر برای استفاده از قابلیت‌های کاربری به حساب جدا نیاز ندارد.
- عملیات سیستم از یک مرکز واحد قابل مشاهده و مدیریت می‌شود.
- اقدامات نمایندگی از کاربر قابل انتساب و بازبینی باقی می‌مانند.
- معماری فعلی two-role حفظ می‌شود.

### Trade-offs
- Admin account به یک هدف با ارزش بالا تبدیل می‌شود و MFA/step-up ضروری است.
- acting context، audit و UI حالت نمایندگی پیچیدگی بیشتری دارند.
- برخی تنظیمات secrets و زیرساخت نمی‌توانند در جدول settings ذخیره یا در UI خوانده شوند؛ مدیریت آن‌ها به secret manager/ops نیاز دارد.

## Implementation boundaries

- جزئیات UI، ماژول‌ها، معیارهای پذیرش و ترتیب اجرا در docs/ADMIN_CONSOLE_SPEC.md است.
- اجرای این تصمیم در specs/phase-7.md انجام می‌شود.
- هر تغییر schema با Alembic و تست PostgreSQL واقعی است.
- قرارداد route/schema پیش از پیاده‌سازی در docs/API_CONTRACT.md ثبت می‌شود.
- هیچ وضعیت Roadmap با ایجاد این ADR یا Spec به COMPLETE تغییر نمی‌کند.

## Open items before implementation

1. انتخاب عامل MFA، روش recovery و timeoutهای Admin.
2. TTL و سیاست لغو acting session.
3. سیاست دقیق نمایش و دسترسی مدیر به محتوای گفتگوها.
4. اثر مالی مجاز/ممنوع در chat impersonation.
5. اتصال secret manager و اینکه آیا عملیات write-only از UI مجاز است.
6. نهایی‌شدن REFUND_POLICY و سیاست حریم خصوصی برای data access/export/delete.
