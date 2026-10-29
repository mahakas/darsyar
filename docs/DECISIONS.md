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
| ADR-024 | ثبت مجوز و منشأ منبع آموزشی | proposed | قبل از ingestion تولیدی accepted شود |

## ADRهای نسخهٔ ۴ (ثبت برای بررسی)

| ADR | موضوع | وضعیت |
|---|---|---|
| ADR-032 | دامنه MVP و defer قابلیت‌های یادگیری پیشرفته | proposed |
| ADR-033 | HMAC OTP + pepper مستقل و چرخش کلید | accepted (مشخص‌سازی ADR-003) |
| ADR-034 | access memory و refresh cookie + CSRF | accepted (مشخص‌سازی ADR-003) |
| ADR-035 | PostgreSQL reservation (مدل حسابداری، idempotency هیبرید، گذار اتمیک) | accepted (OQ-001/002/003 بسته) |
| ADR-036 | INFERENCE_MODE: service یا remote | proposed |
| ADR-037 | نگاشت پایه و سیاست legacy | proposed؛ OQ-009 باید حل شود |
| ADR-038 | edition_year و active edition | proposed |
| ADR-039 | سیاست داخلی پاسخ نیمه‌کاره و billable threshold | accepted (OQ-008 بسته؛ مرز با REFUND_POLICY مشتری حفظ شد) |
| ADR-040 | timezone/duration دورهٔ ماه | proposed |
| ADR-041 | ارتقای فناوری‌ها و سازگاری wheel | proposed |
| ADR-042 | retention و حذف دادهٔ دانش‌آموز | proposed |
| ADR-043 | dataset طلایی و RAG gates | proposed |
| ADR-044 | ترکیب Redis: سرور 7.4.12 (تصمیم مالک) + کلاینت 5.x + arq 0.28 | accepted |
| ADR-045 | ساخت جدول `index_meta` در فاز صفر (اجرای R-087) | accepted |
| ADR-046 | سیاست grace در چرخش refresh: 409 بدون چرخش در پنجره؛ ابطال خانواده پس از آن | accepted |

شماره‌های تاریخی ADR-013 تا ADR-023 و ADR-025 تا ADR-031 در منابع این بسته در دسترس نیستند؛ محتوایشان جعل نشده است. اگر در مخزن اصلی موجودند، قبل از پذیرفتن ADR جدید با آن‌ها تطبیق داده شوند. ADRهای `proposed` به‌خودی‌خود accepted نیستند؛ در فاز صفر قواعد الزامی خود AGENTS اجرا می‌شوند.
