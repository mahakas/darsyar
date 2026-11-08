# دفتر تصمیم‌های معماری (ADR Register)

وضعیت‌های مجاز: `proposed`, `accepted`, `superseded`, `rejected`. AGENTS v4 و ADR پذیرفته‌شدهٔ جدیدتر مرجع‌اند؛ هر تعارض باید گزارش شود.

## خط پایهٔ آغازین

| ADR | موضوع | وضعیت | یادداشت |
|---|---|---|---|
| ADR-001 | محدوده MVP پایه‌های ۱–۱۲ | accepted | هم‌راستا با R-011/R-012 |
| ADR-002 | PostgreSQL منبع دادهٔ پایدار؛ Redis cache/rate limit/queue | accepted | هم‌راستا با R-028/R-124 |
| ADR-003 | امنیت OTP و نشست | accepted | جزئیات v4 و ADR-033/034 را دنبال کن؛ 033/034 جانشین مستقیم (supersede) نیستند، جزئیات‌بنداز پذیرفته‌نشده‌اند |
| ADR-004 | fetch streaming | accepted | reconnect به فاز ۳ موکول است |
| ADR-005 | citation سمت سرور از evidence | accepted | هم‌راستا با R-168/R-178 |
| ADR-006 | مدل سنگین خارج از process وب | accepted | جزئیات در ADR-036 |
| ADR-007 | ledger append-only و رزرو idempotent | accepted | مدل مالی با OQ-001..003 پیش از فاز ۲ روشن شود |
| ADR-008 | secrets جدا از تنظیمات محصول | accepted | هم‌راستا با R-069/R-077 |
| ADR-009 | lockfile و ارتقای تست‌شده | accepted | هم‌راستا با R-034/R-035 |
| ADR-010 | grade ceiling در SQL | accepted | هر دو شاخهٔ retrieval |
| ADR-011 | seed admin با CLI auditدار | accepted | هم‌راستا با R-117 |
| ADR-012 | وب fallback محدود و opt-in | accepted | SSRF و citation مستقل لازم است |
| ADR-024 | ثبت مجوز و منشأ منبع آموزشی | accepted | تصمیم مالک — 2026-11-09؛ سیاست strict و تأیید مجوز به‌ازای هر منبع/عملیات |

## ADRهای نسخهٔ ۴ (ثبت برای بررسی)

| ADR | موضوع | وضعیت |
|---|---|---|
| ADR-032 | دامنه MVP و defer قابلیت‌های یادگیری پیشرفته | proposed |
| ADR-033 | HMAC OTP + pepper مستقل و چرخش کلید | accepted (مشخص‌سازی ADR-003) |
| ADR-034 | access memory و refresh cookie + CSRF | accepted (مشخص‌سازی ADR-003) |
| ADR-035 | PostgreSQL reservation (مدل حسابداری، idempotency هیبرید، گذار اتمیک) | accepted (OQ-001/002/003 بسته) |
| ADR-036 | INFERENCE_MODE: service یا remote | proposed |
| ADR-037 | نگاشت پایه و سیاست legacy | accepted (تصمیم مالک — 2026-11-09؛ OQ-009 بسته؛ عدم نگاشت خودکار و ارجاع legacy به needs_review) |
| ADR-038 | edition_year و active edition | accepted (تصمیم مالک — 2026-11-09؛ edition_year اجباری برای هر سند) |
| ADR-039 | سیاست داخلی پاسخ نیمه‌کاره و billable threshold | accepted (OQ-008 بسته؛ مرز با REFUND_POLICY مشتری حفظ شد) |
| ADR-040 | دورهٔ ماهانهٔ Gregorian در Asia/Tehran (YYYY-MM؛ نیمه‌باز) | accepted |
| ADR-048 | گرانت رایگان ۵ اعتبار یک‌بار (free_grant + ایندکس جزئی) | accepted |
| ADR-049 | اشتراک Unlimited و حفظ اعتبار Basic/Pro؛ تصمیم‌های تجاری باز | accepted (با OQ باز) |
| ADR-050 | سیاست Fair-Use: سقف نرم 10,000 + abuse_flag (بدون بلاک) | accepted |
| ADR-049 | قواعد تجاری Unlimited: خرید دستی؛ بلوک ۳۰ روزه؛ تمدید روی انقضای موجود؛ بدون grace؛ لغو با پشتیبانی+ادمین (نتایج A/B)؛ غیرقابل‌بازپرداخت + استثنا + اختیار ادمین؛ استقلال پلن‌ها؛ حفظ اعتبار؛ هشدار پیش از خرید | accepted (OQ-013..016 بسته؛ OQ-017 جزئی؛ OQ-018..025 بسته) |
| D-01 | ترتیب مصرف اعتبار: Earliest Expiry First برای Free/Basic/Pro (expires_at ASC، سپس created_at ASC، سپس PK پایدار)؛ بدون اولویت نوع پلن | accepted (تصمیم مالک؛ OQ-026) |
| D-02 | حفظ grantهای Free/Basic/Pro حین Unlimited فعال (بدون مصرف/انتخاب)؛ ادامهٔ انقضای مستقل grant حین Unlimited؛ پس از پایان فقط grantهای معتبر واجد شرایط | accepted (تصمیم مالک؛ OQ-026) |
| ADR-053 | سیستم تخصیص grant→رزرو (reservation_credit_allocations) و حسابداری منبع‌محور | accepted (تصمیم مالک — 2026-11-07؛ هم‌راستا با D-03/D-04/D-05) |
| D-03 | OQ-027 گزینهٔ A: مهلت ثابت ۱۵ دقیقه برای رزروهای grant‌محور (created_at + 15min؛ تغییرناپذیر)؛ settle مجاز تا قبل از مهلت حتی پس از انقضای طبیعی grant؛ پس از مهلت فقط release منبع‌محور | accepted (تصمیم مالک) |
| D-04 | OQ-028 گزینهٔ A: لغو فوری/refund تأییدشده — رزروهای موجود تا مهلت اصلی ۱۵ دقیقه‌ای خود می‌توانند settle شوند؛ رزروهای جدید بلافاصله رد می‌شوند؛ پس از مهلت allocationها باطل می‌شوند (بدون بازگشت)؛ اعتبار غیررزروشده باطل؛ بررسی پایانی پس از terminal شدن همهٔ allocationها؛ پرداخت بیرونی جدا از تأیید ادمین | accepted (تصمیم مالک) |
| D-05 | admin_void: هیچ رزروی پس از ثبت reason=admin_void نمی‌تواند settle شود (حتی با allocation قبل از voided_at)؛ فقط مسیر release/انقضا؛ بدون بازگشت؛ تاریخچه حفظ | accepted (تصمیم مالک) |
| D-06 | OQ-029 گزینهٔ C: حفظ gating مسیر legacy به‌عنوان سیاست نهایی MVP؛ بدون backfill/reconcile خودکار برای رزروهای legacy؛ رزروهای legacy با منبع grant غیرقابل‌بازسازی ممکن است حل‌نشده بمانند | accepted (تصمیم مالک) |
| D-07 | OQ-030 گزینهٔ A: تکمیل پس از مهلت ۱۵ دقیقه‌ای از سیاست پذیرفته‌شدهٔ ADR-039 پیروی می‌کند؛ پیاده‌سازی (استریم/مهلت/مسابقه/runtime) به فاز ۳ موکول است و هنوز انجام نشده | accepted (تصمیم مالک) |
| D-08 | ADR-052 پذیرفته‌شده: مدل entitlement پلن‌ها و تخصیص اعتبار (تصمیمات هشت‌گانه OQ-018..025) با تأیید کامل مالک | accepted (تصمیم مالک — 2026-11-07؛ OQ-018..025 بسته) |
| D-09 | ADR-036 پذیرفته‌شده: انتخاب INFERENCE_MODE=service (سرویس داخلی) برای فاز ۳؛ remote حالت جایگزین پیکربندی‌پذیر است و fallback خاموش ندارد | accepted (تصمیم مالک — 2026-11-07) |
| D-10 | OQ-006 گزینهٔ انتخابی: چت هنگام ازکارافتادن Redis از شمارندهٔ fallback امن مبتنی بر PostgreSQL با سقف تنزل‌یافتهٔ قابل‌پیکربندی استفاده می‌کند (R-115 حفظ؛ بدون تبدیل Redis به منبع حقیقت مالی) | accepted (تصمیم مالک — 2026-11-07) |
| D-11 | ADR-054 پذیرفته‌شده: پشتیبانی رسمی Remote Embedding/Inference با جداسازی process و backend، بدون fallback خودکار؛ رابطه با ADR-036 به‌عنوان توسعه | accepted (تصمیم مالک — 2026-11-08) |
| ADR-051 | Admin Control Center، دسترسی user-facing برای Admin و acting context حسابرسی‌شده | proposed | جزئیات در docs/ADMIN_CONSOLE_SPEC.md؛ کنترل‌های MFA/step-up و مرزهای امنیتی پیش از اجرا ratify شوند |
| ADR-041 | ارتقای فناوری‌ها و سازگاری wheel | proposed |
| ADR-042 | retention و حذف دادهٔ دانش‌آموز | proposed |
| ADR-043 | dataset طلایی و RAG gates | proposed |
| ADR-044 | ترکیب Redis: سرور 7.4.12 (تصمیم مالک) + کلاینت 5.x + arq 0.28 | accepted |
| ADR-045 | ساخت جدول `index_meta` در فاز صفر (اجرای R-087) | accepted |
| ADR-046 | سیاست grace در چرخش refresh: 409 بدون چرخش در پنجره؛ ابطال خانواده پس از آن | accepted |
| ADR-047 | خرید یک‌بارهٔ Basic/Pro و زرین‌پال (قرارداد API + کاتالوگ + نهایی‌سازی اتمیک) | accepted |

شماره‌های تاریخی ADR-013 تا ADR-023 و ADR-025 تا ADR-031 در منابع این بسته در دسترس نیستند؛ محتوایشان جعل نشده است. اگر در مخزن اصلی موجودند، قبل از پذیرفتن ADR جدید با آن‌ها تطبیق داده شوند. ADRهای `proposed` به‌خودی‌خود accepted نیستند؛ در فاز صفر قواعد الزامی خود AGENTS اجرا می‌شوند.
