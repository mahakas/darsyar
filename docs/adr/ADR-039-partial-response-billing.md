# ADR-039: پاسخ ناقص و کردیت

- Status: proposed; gated by OQ-008
- Context: provider ممکن است پیش از نخستین token یا میان استریم شکست بخورد.
- Decision: پیش از فاز ۲ ماتریس دقیق حالات complete/cancel/provider-error/server-error و refund باید توسط مالک پذیرفته شود؛ تا آن زمان billing نهایی پیاده نشود.
- Rejected alternatives: یک try/finally کلی بدون state machine.
- Consequences: تست چت شامل قطع کلاینت، خطای میانی و MIN_BILLABLE_TOKENS خواهد بود.
- Affected files: quota service, streaming API, usage events, refund policy.
