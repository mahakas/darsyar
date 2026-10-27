# قرارداد API — طرح مرجع

Base path مسیرهای محصول: `/api/v1`. سه endpoint عملیاتی root مطابق R-208 در ریشه‌اند (`/health`, `/ready`, `/version`). هر endpoint دارای schema ورودی/خروجی Pydantic است. این سند مسیرهای هدف را تعریف می‌کند؛ endpointی که در کد فعلی نیست نباید پیاده‌سازی‌شده فرض شود.

## پیاده‌سازی پایهٔ فاز صفر

| Method | Path | کاربرد | وضعیت بسته |
|---|---|---|---|
| GET | `/health` | زنده بودن process، بدون dependency | scaffold |
| GET | `/ready` | آمادگی dependencyهای لازم | scaffold |
| GET | `/version` | نسخهٔ برنامه | scaffold |
| GET | `/api/v1/health/live` | مسیر سازگاری برای مشاهدهٔ وضعیت در API v1 | scaffold |

## مسیرهای هدف فازهای بعدی

| Method | Path | فاز | هدف |
|---|---|---|---|
| POST | `/auth/otp/request` | 1 | درخواست OTP با پاسخ ضد-enumeration |
| POST | `/auth/otp/verify` | 1 | مصرف یک‌بارهٔ challenge و صدور نشست |
| POST | `/auth/refresh` | 1 | چرخش refresh، CSRF و تشخیص reuse |
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

## Streaming
از `fetch` + `ReadableStream` استفاده می‌شود؛ نه `EventSource` برای bearer-authenticated POST stream. قرارداد eventها باید `event`, `id`, `data` را مشخص کند، `Last-Event-ID` را برای resume امن تعریف کند و خروجی نیمه‌کاره را از پایان موفق جدا کند.

تغییر path/schema/status/code نیازمند ADR و به‌روزرسانی هم‌زمان این سند، کد و تست‌ها است.
