# ADR-040: منطقهٔ زمانی دورهٔ اشتراک

- Status: proposed
- Context: اشتراک و fair-use باید در مرز ماه قابل‌پیش‌بینی صفر شوند.
- Decision: zone مرجع `Asia/Tehran` از `PLAN_PERIOD_TIMEZONE` تعریف می‌شود؛ پشتیبانی تقویم شمسی فقط پس از مشخص‌شدن تعریف دوره و edge caseها فعال می‌شود.
- Rejected alternatives: bucket ماهانه بر مبنای UTC خام.
- Consequences: rollover، زمان تغییر ساعت و بازسازی شمارنده تست می‌شوند.
- Affected files: plan service, usage reconciliation, settings, tests.
