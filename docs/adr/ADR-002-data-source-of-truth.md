# ADR-002: منبع حقیقت داده

- Status: Accepted
- Decision: PostgreSQL منبع حقیقت برای کاربران، پیام‌ها، تراکنش‌ها، ledger و رزروهای اعتبار است. Redis برای cache، rate-limit و هماهنگی کوتاه‌مدت است.
- Reason: عملیات مالی/اعتباری نباید به کلید cache یا انقضای Redis وابسته باشد.
- Consequences: عملیات ledger و تغییر وضعیت رزرو در تراکنش PostgreSQL و با قید یکتا/قفل مناسب انجام شود. Redis TTL صرفاً سیگنال زمان‌دار است و جایگزین reconciliation نیست.
- Required tests: retry، درخواست هم‌زمان، قطع شبکه پس از reserve، تکرار settle/refund و reconciliation.
