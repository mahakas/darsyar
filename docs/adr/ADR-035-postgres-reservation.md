# ADR-035: رزرو اعتبار پایدار در PostgreSQL

- Status: proposed; gated by OQ-001–OQ-003
- Context: رزرو مالی نباید فقط در Redis باشد و نباید با crash یا retry دوباره اعمال شود.
- Decision: reservations و credit projection در PostgreSQL transaction و با row lock/idempotency نگهداری شوند؛ Redis فقط cache/rate-limit/queue است.
- Rejected alternatives: Redis-only balance؛ GET+DECR؛ آزادسازی متکی به TTL.
- Consequences: پیش از فاز ۲ باید semantics available/reserved/ledger و event idempotency بدون تناقض تعریف شوند.
- Affected files: credit service, reservation model, ledger, reconciliation jobs, tests.
