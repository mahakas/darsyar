# ADR-004: انتقال پاسخ استریم

- Status: Accepted
- Decision: برای استریم POST با Authorization از `fetch` و `ReadableStream` استفاده می‌شود. پروتکل event و معنای `delta`, `citation`, `usage`, `done`, `error` در API contract ثبت خواهد شد.
- Reason: مرورگر EventSource بومی امکان تنظیم Authorization header دلخواه را ندارد.
- Consequences: parser باید fragmentation، UTF-8 چندبایتی، disconnect، cancel و backpressure را پوشش دهد. کلاینت نباید به متن نیمه‌کاره به‌عنوان پاسخ نهایی اعتماد کند.
