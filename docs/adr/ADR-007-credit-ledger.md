# ADR-007: ledger و چرخهٔ اعتبار

- Status: Accepted
- Decision: ledger در PostgreSQL append-only است. هر reserve، settle، release و refund یک شناسهٔ idempotency و ارتباط با رزرو/درخواست دارد. Redis موجودی مالی نهایی را تعیین نمی‌کند.
- Invariant: مجموع تغییرات ledger برابر موجودی محاسبه‌شده است؛ رزرو دوبار settle نمی‌شود؛ refund با رکورد جدید انجام می‌شود؛ اصلاح ledger با UPDATE/DELETE ممنوع است.
- Recovery: یک reconciler دوره‌ای رزروهای باز منقضی‌شده را بررسی و با وضعیت درخواست/usage سازگار می‌کند. TTL به‌تنهایی آزادسازی تضمین‌شده نیست.
- Required tests: parallel reserve، crash after provider call، stream disconnect، settlement retry و refund replay.
