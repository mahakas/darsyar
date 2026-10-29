# قرارداد API — طرح مرجع

Base path مسیرهای محصول: `/api/v1`. سه endpoint عملیاتی root مطابق R-208 در ریشه‌اند (`/health`, `/ready`, `/version`). هر endpoint دارای schema ورودی/خروجی Pydantic است. این سند مسیرهای هدف را تعریف می‌کند؛ endpointی که در کد فعلی نیست نباید پیاده‌سازی‌شده فرض شود.

## پیاده‌سازی پایهٔ فاز صفر

| Method | Path | کاربرد | وضعیت بسته |
|---|---|---|---|
| GET | `/health` | زنده بودن process، بدون dependency | scaffold |
| GET | `/ready` | آمادگی dependencyهای لازم | scaffold |
| GET | `/version` | نسخهٔ برنامه | scaffold |
| GET | `/api/v1/health/live` | مسیر سازگاری برای مشاهدهٔ وضعیت در API v1 | scaffold |
| POST | `/api/v1/auth/otp/request` | درخواست کد؛ پاسخ یکسان ضد-enumeration | پیاده‌سازی‌شده (فاز ۱) |
| POST | `/api/v1/auth/otp/verify` | تأیید کد؛ صدور access + کوکی refresh HttpOnly | پیاده‌سازی‌شده (فاز ۱) |
| POST | `/api/v1/auth/refresh` | چرخش refresh با CSRF/Origin؛ تشخیص reuse | پیاده‌سازی‌شده (فاز ۱) |
| POST | `/api/v1/auth/logout` | ابطال خانواده | پیاده‌سازی‌شده (فاز ۱) |

## مسیرهای هدف فازهای بعدی

| Method | Path | فاز | هدف |
|---|---|---|---|
| POST/GET | `/conversations` | 3 | ساخت و فهرست مکالمه‌های خود کاربر |
| POST | `/conversations/{id}/messages` | 3/5 | پاسخ استریم‌شده با reservation پیش از provider |
| GET | `/conversations/{id}/messages` | 3 | پیام‌ها با cursor pagination و مالکیت query-level |
| POST | `/documents` | 4 | ایجاد ingestion job برای منبع مجاز |
| GET | `/documents/{id}` | 4/7 | وضعیت ingestion، فقط با مجوز |
| POST | `/billing/checkout` | 2 | ایجاد سفارش با مبلغ ذخیره‌شده در DB |
| POST | `/billing/callback` | 2 | verify provider و ثبت اتمیک/idempotent |
| GET | `/admin/*` | 7 | endpointهای مدیریتی با `require_admin` |

## خطا
فرمت یکتا: `{"code":"...","message":"پیام امن برای کاربر","request_id":"..."}`. جزئیات داخلی و stack trace در پاسخ عمومی ممنوع‌اند. validation error نیز جزئیات ورودی حساس را منعکس نمی‌کند.

## احراز هویت (فاز ۱)
- `POST /api/v1/auth/otp/request`: بدنهٔ `{phone}`؛ شماره به E.164 نرمال می‌شود؛ پاسخ همیشه `202 {status:"sent"}` است (ضد-enumeration). محدودیت: ۳/۵دقیقه per phone و ۱۰/دقیقه per IP؛ در نبود Redis 503 `rate_limit_unavailable`.
- `POST /api/v1/auth/otp/verify`: بدنهٔ `{phone, code}`؛ تلاش‌های ناموفق شمارش می‌شود (سقف `OTP_MAX_ATTEMPTS` → 429 `otp_attempts_exceeded`)؛ کد منقضی/مصرف‌شده → 401 `invalid_otp`. موفقیت → `{access_token, token_type:"bearer", expires_in, user}` و کوکی‌های `darsyar_refresh` (HttpOnly؛ path=/api/v1/auth) و `darsyar_csrf`.
- `POST /api/v1/auth/refresh`: کوکی refresh + `X-CSRF-Token` (برابر کوکی csrf) + Origin در فهرست CORS لازم است؛ ناموفق 403 `csrf_origin_rejected`/`csrf_token_mismatch`. چرخش با ابطال عضو قبلی؛ بازپخش والد در پنجرهٔ grace (۳۰ ثانیه) → **409 `refresh_conflict_retry`** بدون `Set-Cookie` و بدون ابطال خانواده (کلاینت نباید یک 409 مجرد را logout تعبیر کند؛ می‌تواند بعداً retry کند)؛ reuse پس از grace → 401 `refresh_reuse_detected` و ابطال خانواده.
- `POST /api/v1/auth/logout`: ابطال خانواده؛ کوکی‌ها حذف می‌شوند؛ 204.

## Streaming
از `fetch` + `ReadableStream` استفاده می‌شود؛ نه `EventSource` برای bearer-authenticated POST stream. قرارداد eventها باید `event`, `id`, `data` را مشخص کند، `Last-Event-ID` را برای resume امن تعریف کند و خروجی نیمه‌کاره را از پایان موفق جدا کند.

تغییر path/schema/status/code نیازمند ADR و به‌روزرسانی هم‌زمان این سند، کد و تست‌ها است.
