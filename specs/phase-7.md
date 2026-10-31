# Phase 7: Admin Console & Operations

**Status:** Planned — مشخصات تفصیلی در `docs/ADMIN_CONSOLE_SPEC.md`  
**Dependencies:** Phases 1–6 برای ماژول‌های وابسته، primitives حسابرسی، settings و عملیات worker؛ قابلیت‌های production backup/recovery و hardening با Phase 9 هماهنگ می‌شوند.  
**Architecture decision:** ADR-051 (Proposed) — دسترسی سراسری Admin و Admin Control Center.

## Goal

ساخت یک مرکز کنترل مدیریتی امن، یکپارچه و قابل توسعه که مدیر واحد Darsyar بتواند از طریق آن تمام قابلیت‌های عادی کاربر و تمام عملیات مدیریتی محصول را مدیریت کند؛ بدون نیاز به ویرایش مستقیم کد برای تنظیمات و عملیات قابل‌پیکربندی.

این فاز باید عملیات مدیریتی را از serviceهای دامنه استفاده دهد و نباید منطق مالی، چت، RAG یا worker را داخل router پنل بازنویسی کند.

## Product and access decisions

- نقش‌های محصول در این محدوده فقط `user` و `admin` هستند؛ نقش‌های مدیریتی میانی/RBAC قابل‌پیکربندی اضافه نمی‌شوند.
- Admin علاوه بر Admin Console به همهٔ قابلیت‌های عادی پنل کاربری دسترسی دارد.
- دسترسی تمام endpointهای مدیریتی در سمت سرور با `require_admin` کنترل می‌شود.
- عملیات به نمایندگی از کاربر باید actor (Admin واقعی) و subject (کاربر هدف) را جدا نگه دارد؛ token یا credential کاربر هدف ساخته نمی‌شود.
- عملیات حساس مالی، امنیتی و privacy از جریان مدیریتی مستقل، با reason و تأیید مجدد اجرا می‌شوند.
- ledger append-only، مرز secrets، ownership، grade ceiling، citation integrity و قیود دیتابیس با اختیار Admin قابل دورزدن نیستند.

## In scope

### Admin shell and dashboard
- [ ] رابط responsive و fa/en/ar با RTL/LTR؛ ناوبری گروه‌بندی‌شده، جست‌وجوی ماژول و وضعیت موارد اقدام‌خواه.
- [ ] داشبورد مدیریتی با کاربران فعال، پلن/درآمد، هزینه AI، متریک‌های کیفیت، سلامت سرویس‌ها، صف‌ها، هشدارها و تیکت‌های باز.
- [ ] نمایش freshness و منبع متریک؛ دادهٔ stale/unknown به‌عنوان healthy نمایش داده نشود.

### User management and support
- [ ] جست‌وجو، فیلتر و cursor pagination کاربران.
- [ ] User 360: حساب، پلن/پرداخت، ledger read-only، مصرف، گفتگوها، فایل‌ها، نشست‌ها، تیکت‌ها، privacy requests و تاریخچه Audit.
- [ ] پشتیبانی داخلی: ticket، public reply، private note، priority/status/labels، پیوست امن و timeline.
- [ ] تعلیق/رفع تعلیق و مدیریت نشست کاربر از مسیرهای audited.
- [ ] Admin acting session: context سمت سرور، زمان‌دار، reason اجباری، actor/subject مجزا، نشان UI دائمی، exit فوری، audit کامل و بدون ساخت credential کاربر.
- [ ] عملیات حساس در حالت acting از طریق جریان مدیریتی مستقل و step-up انجام شوند.

### Plans, billing and credits
- [ ] مدیریت کاتالوگ Basic/Pro/Unlimited، قیمت، مدت، مقدار کردیت و وضعیت فروش با validation و audit.
- [ ] تغییر duration/credit با انتخاب دامنهٔ «فقط خرید جدید» یا «خریدهای فعال قبلی هم شامل شود» و impact preview.
- [ ] پیاده‌سازی قوانین تأییدشدهٔ مالک دربارهٔ انقضا، تمدید دستی Unlimited، تمدید زودهنگام، خرید مجدد، استقلال پلن‌ها، لغو، درخواست پس‌گرفتن لغو و refund؛ جزئیات در ADMIN_CONSOLE_SPEC.md.
- [ ] پرداخت‌ها، verify/callback، refund/cancellation review و reconciliation.
- [ ] Ledger فقط read-only؛ refund/adjust از service مالی و رویداد جبرانی append-only.
- [ ] مدیریت Fair-Use threshold و abuse flags، با audit و بدون auto-block خارج از سیاست پذیرفته‌شده.

### AI and prompt operations
- [ ] مدیریت provider/model role، fallback، timeout، token limit، health و usage/cost.
- [ ] مدیریت نسخه‌بندی‌شدهٔ prompt و personality، preview، evaluation، staged rollout و rollback.
- [ ] AI Quality/Safety: traces پالایش‌شده، evidence/citation inspection، report review، guard events و Golden Dataset metrics.
- [ ] Kill switch برای provider/model با fallback امن و audit.

### Knowledge and RAG operations
- [ ] مدیریت منابع، manifest، edition، licensing، ingestion states، OCR failures و manual review.
- [ ] اجرای مجدد jobهای مجاز و idempotent، مشاهدهٔ progress و error.
- [ ] مدیریت index/version و inspection مسیر dense/lexical/RRF/rerank/evidence.
- [ ] اجرای Golden Dataset و گیت grade leakage=0 و invalid citation=0؛ بدون دستکاری آستانه برای سبزکردن مصنوعی.

### Security and operational control
- [ ] Security Center: auth events، sessions، refresh reuse، suspicious activity و access review.
- [ ] MFA/step-up برای Admin؛ انتخاب factor و recovery با ADR امنیتی پیش از implementation.
- [ ] Health/observability برای API، DB، Redis، worker، inference، storage و providers.
- [ ] Job/Queue Manager: queued/running/completed/failed/dead، retry policy و status guard.
- [ ] Alert/Incident Center با severity، deduplication، acknowledgement، timeline، root cause و runbook.
- [ ] Backup monitoring و restore-drill evidence؛ restore production از UI عمومی انجام نشود.
- [ ] Privacy & Data Lifecycle: export/delete/consent/retention و audit.
- [ ] Audit Log Explorer با cursor pagination، before/after redacted و export کنترل‌شده.

### Settings, feature flags and content
- [ ] Settings UI با typed validation، default/current، reason، history، rollback و cache invalidation.
- [ ] تفکیک Product Settings، runtime environment و secrets؛ secrets در DB ذخیره و در UI خوانده نمی‌شوند.
- [ ] Feature flags، targeting، rollout، schedule و kill switches؛ flag جای authorization را نگیرد.
- [ ] مدیریت FAQ/help, notices, maintenance messages, SMS templates و fa/en/ar content.
- [ ] Product analytics تجمیعی برای activation, retention, revenue, cost, usage و quality.

## Out of scope / safeguards

- ویرایش یا حذف مستقیم Ledger.
- نمایش یا ثبت Secretها، OTP، token و prompt/PII خام در UI یا Audit.
- ساخت نقش مدیریتی دیگر، permission editor یا RBAC عمومی.
- جعل نشست/توکن کاربر برای impersonation.
- اجرای financial actions صرفاً به دلیل فعال‌بودن acting context.
- عملیات restore تولید از UI عمومی.
- پیاده‌سازی مستقیم قابلیت‌های فازهای دیگر قبل از آماده‌شدن service و contract مالک آن‌ها.
- auto-refund، auto-suspension یا تصمیم مالی/امنیتی توسط LLM.

## Acceptance criteria

- [ ] تمام admin endpoints بدون Admin معتبر 401/403 می‌دهند؛ فرانت تنها سطح نمایش است.
- [ ] Admin قابلیت‌های user-facing را بدون تغییر role و بدون جعل user session اجرا می‌کند.
- [ ] acting context دلیل، TTL، actor/subject، شروع/پایان و audit دارد و credential کاربر ایجاد نمی‌کند.
- [ ] عملیات حساس step-up، reason، idempotency و outcome audit دارند.
- [ ] آزمون redaction ثابت می‌کند secrets/OTP/token/متن خصوصی در Audit و logs نشت نمی‌کنند.
- [ ] ledger endpoint فقط read-only است؛ refund/adjust فقط از service مالی قابل اجراست.
- [ ] تغییر تنظیمات پلن، دامنهٔ اثر و impact preview دارد و خریدهای خارج از scope را تغییر نمی‌دهد.
- [ ] retry job فقط با policy/status/idempotency معتبر ممکن است.
- [ ] metricهای stale/unknown به‌عنوان healthy گزارش نمی‌شوند.
- [ ] multi-user isolation، pagination، audit isolation، RBAC boundary (فقط user/admin) و RTL/LTR تست شده‌اند.
- [ ] migrationها با Alembic و تست‌ها روی PostgreSQL واقعی اجرا می‌شوند.
- [ ] lint، typecheck، test-db، migration test و UI smoke با خروجی واقعی گزارش می‌شوند.

## Required evidence

- فرمان‌های واقعی و exit code: `make lint`, `make typecheck`, `make test-db`، تست migration و UI smoke.
- تست security برای admin authz، acting-session, redaction و multi-user isolation.
- تست‌های race/idempotency برای billing، bulk operations و job retry.
- فایل‌های تغییرکرده، شناسهٔ قواعد AGENTS و وضعیت checks NOT RUN همراه blocker دقیق.
- موارد باقیماندهٔ Phase 9 و تصمیم‌های ADR ثبت‌شده.

## Delivery sequence

1. foundation: Admin shell, authz, audit, pagination, dashboard.
2. users: User 360, security overview, acting sessions.
3. support/finance: tickets, plans, billing, credits, Fair Use.
4. settings/flags: settings validation, revision/rollback, feature flags.
5. AI operations: providers/models, prompt versions, evaluation and trace review.
6. knowledge/RAG operations: ingestion, index and evidence inspection.
7. operations: health, jobs, alerts/incidents and backup evidence.
8. privacy/analytics/content.
9. production hardening in coordination with Phase 9.

Phase 7 remains Planned until the acceptance criteria have been implemented and proven.