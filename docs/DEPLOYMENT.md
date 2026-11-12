# راهنمای استقرار

## Development
- Docker Compose v2 و `.env` محلی لازم است.
- `make lock` lockfileهای واقعی را می‌سازد.
- `make up` سرویس‌ها را بالا می‌آورد؛ migration در سرویس یک‌بارمصرف `migrate` انجام می‌شود.
- هیچ model download در فاز صفر انجام نمی‌شود.

## Production baseline
- imageها با tag دقیق و ترجیحاً digest pin شوند.
- `.env` روی host با permission محدود یا secret store؛ هیچ secret داخل image یا Git نیست.
- TLS و domain، trusted proxy و CORS دقیق، HSTS/CSP و محدودیت body/time فعال شوند.
- PostgreSQL backup رمزگذاری‌شده بیرون از host، restore دوره‌ای آزمایش‌شده.
- log/trace retention و دادهٔ کودکان مطابق سیاست تأییدشده.
- قبل از deploy: migrate صریح، readiness schema، smoke، امنیت، backup restore و بار.

## نکتهٔ اولیه
پورت‌های localhost در Compose صرفاً توسعه‌اند. فایل Nginx نمونه، بدون TLS گواهی واقعی یا دامنهٔ تولید، آمادهٔ public exposure نیست.


## Reverse-proxy verification

CI job `nginx-config` runs `nginx -t` against both templates using the pinned-by-project release `nginx:1.28-alpine`, then requests the static frontend container and checks `nosniff`, `X-Frame-Options`, `Referrer-Policy`, CSP and `Cache-Control: no-store`.

The API proxy marks `/api/` responses as `no-store`. The static frontend marks the SPA `index.html` as `no-store`. This does not configure HTTPS or HSTS: the actual public TLS terminator must set and verify those headers for the real domain. The repository template listens on HTTP 8080 and is not a public TLS endpoint.
