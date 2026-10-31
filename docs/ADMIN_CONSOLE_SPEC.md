# مشخصات جامع پنل مدیریت و مرکز کنترل درسیار (Admin Console Specification)

- **وضعیت:** Draft — دامنهٔ محصول با مالک بررسی شده؛ جزئیات امنیتی و قراردادهای اجرایی باید پیش از پیاده‌سازی در ADRهای مربوط تصویب شوند.
- **نسخه:** 1.0-draft
- **دامنه:** Phase 7 و قابلیت‌های مدیریتی زیربنایی وابسته به فازهای دیگر
- **مرجع محصول:** AGENTS.md v4.0، ROADMAP.md، docs/PRODUCT_SPEC.md و تصمیم‌های ثبت‌شدهٔ مالک
- **اصل راهنما:** پنل Admin مرکز کنترل عملیاتی کل Darsyar است؛ نه صرفاً CRUD کاربران.

> این سند مشخصات هدف است، نه گزارش قابلیت‌های پیاده‌سازی‌شده. وجود هر قابلیت در این سند به معنی وجود endpoint، جدول یا UI آن در نسخهٔ فعلی نیست. وضعیت اجرایی فقط با شواهد تست و گزارش فاز اعلام می‌شود.

---

## 1. هدف و اصول محصول

پنل مدیریت باید به مدیر واحد سامانه امکان دهد بدون ویرایش مستقیم کد، رفتارهای قابل‌پیکربندی محصول، عملیات روزمره، پشتیبانی، سلامت زیرساخت و کنترل کیفیت هوش مصنوعی را از یک محیط امن مدیریت کند.

### 1.1 اصول قطعی نقش و دسترسی

1. نقش‌های MVP فقط user و admin هستند؛ نقش مدیریتی میانی یا نقش‌های قابل‌ساخت توسط مدیر به این محدوده افزوده نمی‌شود.
2. Admin به تمام قابلیت‌های عادی پنل کاربر نیز دسترسی دارد؛ یعنی لازم نیست برای استفاده از امکانات محصول حساب دیگری بسازد.
3. Admin به تمام ماژول‌های مدیریتی مجاز در این سند دسترسی دارد.
4. همهٔ مجوزها در سمت سرور اعمال می‌شوند. پنهان‌کردن کنترل در رابط کاربری، کنترل امنیتی محسوب نمی‌شود.
5. دسترسی کامل Admin به معنی مجازبودن دورزدن قیود پایگاه داده، حذف سوابق مالی، افشای رازها، دورزدن امنیت یا بی‌اثرکردن audit نیست.
6. عملیات انجام‌شده به نمایندگی از کاربر باید هویت واقعی Admin و کاربر هدف را جداگانه حفظ کند.
7. عملیات حساس، مالی، امنیتی، مخرب یا برگشت‌ناپذیر باید دلیل، نتیجه و سابقهٔ قابل حسابرسی داشته باشند.

### 1.2 اصول طراحی

- **Control without code changes:** تنظیمات محصولی و عملیات پشتیبانی باید از UI کنترل شوند؛ تنظیمات صرفاً زیرساختی که ذاتاً به محیط اجرا وابسته‌اند می‌توانند به ابزار امن عملیات/secret manager نیاز داشته باشند.
- **Server authority:** UI فقط درخواست می‌دهد؛ اعتبارسنجی، مجوز و اثر نهایی در backend است.
- **Audit by design:** ثبت رخداد بخشی از همان عملیات حساس و نه یک قابلیت جانبی است.
- **Provider agnostic:** پنل نباید دامنهٔ محصول را به یک vendor هوش مصنوعی، SMS، پرداخت، مانیتورینگ یا Feature Flag قفل کند.
- **Safe failure:** خرابی پنل یا ابزار عملیات نباید باعث اعطای اعتبار، تغییر پرداخت، عبور از grade ceiling یا از دست‌رفتن شواهد مالی شود.
- **Privacy minimization:** مدیر ابزار لازم برای پشتیبانی و عملیات را دارد، اما نمایش دادهٔ شخصی باید هدفمند، ثبت‌شده و محدود به نیاز عملیات باشد.
- **Progressive delivery:** تغییرات prompt، مدل، تنظیمات و قابلیت‌ها باید امکان آزمون، انتشار تدریجی و بازگشت امن داشته باشند.

## 2. مرزهای سند و ارتباط با Roadmap

این سند مرجع تفصیلی طراحی Phase 7 است. قابلیت‌ها از نظر وابستگی به سه گروه تقسیم می‌شوند:

- **Phase 7 core:** UI و API مدیریتی، User 360، پلن‌ها، تنظیمات، Audit، پشتیبانی، عملیات مدیریتی و داشبوردهای پایه.
- **Cross-phase integration:** پنل تنها زمانی داده یا عملیاتی را ارائه می‌کند که فاز مالک آن قابلیت، قرارداد و منبع داده را فراهم کرده باشد؛ برای مثال AI Gateway، RAG، پیام‌ها، payment، abuse flags و worker jobs.
- **Phase 9 / production operations:** سخت‌سازی، نگهداری backup، بازیابی، مدیریت رخداد تولیدی و کنترل‌های استقرار. Phase 7 می‌تواند وضعیت و عملیات کنترل‌شده را نمایش دهد، اما جایگزین فاز سخت‌سازی نیست.

Phase 7 نباید منطق گفت‌وگو، retrieval، محاسبهٔ مالی یا اجرای مدل را در router مدیریتی بازنویسی کند؛ پنل از serviceها و قراردادهای همان دامنه استفاده می‌کند.

## 3. ساختار ناوبری Admin

منوی پیشنهادی دسکتاپ و موبایل:

1. داشبورد مدیریتی
2. مدیریت کاربران
3. پشتیبانی و تیکت‌ها
4. پلن‌ها، اشتراک‌ها و پرداخت‌ها
5. اعتبار، Ledger و Fair Use
6. مرکز کنترل هوش مصنوعی و Providerها
7. Promptها و شخصیت‌های پاسخ‌گو
8. منابع آموزشی و Knowledge Base
9. RAG، ارزیابی و کیفیت پاسخ
10. امنیت و نشست‌ها
11. سلامت سیستم و عملیات
12. Jobها و صف‌ها
13. هشدارها و رخدادها
14. تنظیمات پیشرفته و Feature Flags
15. پشتیبان‌گیری و بازیابی
16. حریم خصوصی و چرخهٔ عمر داده
17. Audit Log
18. آمار و تحلیل محصول
19. محتوا و ارتباطات
20. تاریخچهٔ تغییرات و نسخهٔ سیستم

منو باید responsive، قابل جست‌وجو و دارای وضعیت/شمارنده برای موارد اقدام‌خواه (تیکت باز، alert فعال، job مرده، سند نیازمند بازبینی) باشد. دسترسی منو فقط یک affordance است؛ هر endpoint دوباره مجوز را سمت سرور بررسی می‌کند.

## 4. مشخصات ماژول‌ها

### 4.1 داشبورد مدیریتی

نمای واحدی از وضعیت فعلی سامانه با بازهٔ زمانی قابل انتخاب:

- کاربران ثبت‌نام‌شده و کاربران فعال روزانه/هفتگی/ماهانه
- خریدها و درآمد تجمیعی، تفکیک‌شده بر اساس پلن و بازه
- هزینه و مصرف LLM به تفکیک provider/model
- تعداد گفتگوها و پاسخ‌های تکمیل‌شده/ناقص/ناموفق
- کیفیت retrieval و citation در حد متریک‌های معتبر موجود
- وضعیت API، PostgreSQL، Redis، worker و inference
- عمق صف، jobهای شکست‌خورده و ingestionهای نیازمند اقدام
- هشدارهای فعال، Abuse Flagها و اختلاف‌های reconciliation
- تیکت‌های باز و درخواست‌های حریم خصوصی در انتظار رسیدگی

هر کارت باید زمان آخرین به‌روزرسانی، منبع داده و معنای متریک را نشان دهد. دادهٔ ناقص یا stale نباید به‌عنوان مقدار زنده نمایش داده شود. نمودار درآمد/هزینه باید رویدادهای مالی و usage را از projectionهای معتبر بخواند و با Ledger جایگزین نشود.

### 4.2 مدیریت کاربران و User 360

فهرست کاربران باید cursor pagination، جست‌وجو و فیلترهای محدود و ایندکس‌پذیر داشته باشد: شناسه، شمارهٔ نرمال‌شده (با نمایش ماسک‌شده در فهرست)، وضعیت حساب، تاریخ ثبت‌نام، پلن فعال و وضعیت رسیدگی.

پروندهٔ User 360 شامل تب‌های زیر باشد:

- نمای کلی حساب و وضعیت دسترسی
- پلن‌ها، خریدها، پرداخت‌ها و کردیت‌ها
- تاریخچهٔ ledger به‌صورت read-only و رزرو/مصرف
- گفتگوها و فعالیت‌های محصول، با رعایت retention و ثبت دسترسی مدیریتی
- فایل‌ها، اسناد کاربر و وضعیت پردازش
- نشست‌ها و رخدادهای امنیتی
- تیکت‌ها، بازخوردها و گزارش‌های کاربر
- تاریخچهٔ عملیات Admin مرتبط با همان کاربر
- درخواست‌های export/delete و وضعیت اجرای آن‌ها

عملیات قابل انجام: مشاهده، تعلیق/رفع تعلیق طبق سیاست مصوب، ابطال نشست، مدیریت درخواست پشتیبانی، و اعمال تنظیمات مجاز حساب. تغییر مالی فقط از جریان‌های اختصاصی و ledger-safe انجام می‌شود؛ ویرایش مستقیم رکوردهای مالی ممنوع است.

### 4.3 ورود نمایندگی Admin به پنل کاربر (Impersonation)

دو حالت باید از هم جدا باشند:

- **Admin as self:** مدیر با حساب Admin از قابلیت‌های عادی محصول استفاده می‌کند.
- **Admin acting for user:** مدیر با انتخاب کاربر هدف وارد context نمایندگی می‌شود تا تجربه یا مشکل او را بررسی کند.

الزامات حالت نمایندگی:

1. شروع نشست نمایندگی مستلزم انتخاب کاربر و واردکردن دلیل غیرخالی است.
2. backend یک Admin Acting Context مستقل و مدت‌دار ایجاد می‌کند؛ هرگز refresh/access token یا رمز عبور کاربر را جعل، کپی یا صادر نمی‌کند.
3. شناسهٔ Admin واقعی (actor) و شناسهٔ کاربر هدف (subject) در تمام درخواست‌ها از هم جدا باقی می‌مانند.
4. رابط کاربری نوار/نشان برجستهٔ «در حال فعالیت به نمایندگی از کاربر» و امکان پایان فوری نشست را نشان می‌دهد.
5. مدت نشست، شروع، پایان، دلیل، IP/اطلاعات دستگاه مجاز و عملیات انجام‌شده ثبت می‌شوند؛ داده‌های حساس مطابق سیاست logging ماسک می‌شوند.
6. خروج از context نمایندگی باید به محیط Admin برگردد و هیچ کوکی یا نشست متعلق به کاربر هدف ایجاد نکند.
7. عملیات حساس مانند refund، تغییر پلن، adjustment مالی، حذف داده، تغییر شماره یا تغییر وضعیت امنیتی از جریان مدیریتی مستقل با تأیید مجدد انجام می‌شوند؛ فقط حضور در context نمایندگی برای این عملیات کافی نیست.
8. عملیات چت/مصرف در context نمایندگی نباید ناخواسته از کردیت یا اشتراک کاربر هزینه کند. حالت آزمایشی بدون اثر مالی باید پیش‌فرض باشد؛ هر استثنای دارای اثر مالی نیازمند تصمیم تجاری/ADR و تأیید صریح پیش از اجراست.
9. شروع، پایان، تلاش ناموفق و هر عملیات تغییردهنده در Audit ثبت می‌شوند.

### 4.4 پشتیبانی و تیکت

- ایجاد تیکت از پنل کاربر و ثبت آن در پروندهٔ User 360
- دسته‌بندی: حساب، OTP، پرداخت، پلن، کردیت، چت/کیفیت AI، منابع آموزشی، فایل، حریم خصوصی و سایر
- اولویت، وضعیت، برچسب و مسئول رسیدگی
- پاسخ عمومی به کاربر و یادداشت خصوصی داخلی با تمایز بصری و API مجزا
- پیوست امن با محدودیت نوع/حجم و retention
- تاریخچهٔ کامل پاسخ‌ها و تغییر وضعیت
- اتصال تیکت به payment_id، reservation_id، conversation_id یا document_id در صورت وجود
- امکان بستن، بازگشایی و ارجاع تیکت
- جلوگیری از نمایش یادداشت داخلی به کاربر
- گزارش زمان پاسخ و زمان حل؛ این آمار برای پایش است و بدون تعریف SLA تجاری، تعهد زمانی نمی‌سازد.

### 4.5 پلن‌ها، اشتراک‌ها و پرداخت‌ها

پنل باید کاتالوگ پلن را از دادهٔ معتبر دامنه بخواند و امکان مدیریت موارد قابل‌پیکربندی را فراهم کند: نام، توضیح، قیمت تومان، مقدار کردیت، مدت، وضعیت فروش و قواعد فعال‌سازی.

تصمیم‌های تجاری تأییدشدهٔ مالک که طراحی باید منعکس کند:

- Basic و Pro هرکدام ۳۰ روز از زمان فعال‌سازی اعتبار دارند و دارای مقدار کردیت مشخص‌اند.
- با پایان هرکدام از دو شرط «مدت» یا «کردیت»، هرکدام زودتر رخ دهد، دسترسی همان پلن پایان می‌یابد.
- با پایان مدت، کردیت مصرف‌نشدهٔ همان خرید منقضی می‌شود و منتقل نمی‌شود.
- اگر کردیت زودتر تمام شود، دسترسی همان زمان پایان می‌یابد.
- خرید مجدد همان پلن در زمان فعال‌بودن: کردیت جدید به کردیت باقی‌مانده اضافه و ۳۰ روز به تاریخ انقضای فعلی افزوده می‌شود.
- خریدهای هم‌زمان و callbackهای تکراری باید idempotent باشند و هر پرداخت موفق دقیقاً یک بار مزایا را اعمال کند.
- Unlimited خرید دستی/تمدید دستی دارد؛ دورهٔ آن ۳۰ روز است. خرید زودهنگام ۳۰ روز به انقضای فعلی می‌افزاید؛ بعد از انقضا دورهٔ تازه از زمان فعال‌سازی شروع می‌شود؛ grace period وجود ندارد.
- کردیت‌های Basic/Pro هنگام فعال‌بودن Unlimited حفظ می‌شوند و مصرف نمی‌شوند؛ پس از پایان Unlimited دوباره قابل مصرف‌اند، البته فقط تا پایان اعتبار مستقل خودشان.
- پلن‌ها lifecycle مستقل دارند. خرید یک پلن دیگر، پلن یا کردیت قبلی را حذف یا منتقل نمی‌کند. پیش از خرید جدید، هشدار اطلاعاتی دربارهٔ مزایای باقی‌ماندهٔ پلن‌های فعال/معتبر نشان داده شود.
- لغو self-service نیست؛ کاربر درخواست پشتیبانی می‌دهد و Admin تصمیم می‌گیرد. تصمیم لغو Unlimited می‌تواند «عدم تمدید و حفظ دسترسی تا انقضا» یا «قطع فوری» باشد.
- کاربر تا پیش از تصمیم نهایی Admin می‌تواند درخواست لغو را پس بگیرد؛ پس از تصمیم، درخواست جدید لازم است.
- لغو فوری Basic/Pro، کردیت باقی‌ماندهٔ همان خرید را باطل می‌کند و به خرید بعدی منتقل نمی‌کند. سایر پلن‌ها مستقل می‌مانند.
- اصل کلی، عدم بازپرداخت خرید موفق Unlimited است؛ درخواست‌های فنی مانند پرداخت موفق بدون فعال‌سازی و سایر استثناها با اختیار بررسی/تصمیم Admin رسیدگی می‌شوند. درخواست بازپرداخت تضمین پذیرش نیست.
- بازپرداخت و لغو دو عملیات مستقل‌اند مگر اینکه Admin هر دو را صریحاً تأیید کند.
- در بازپرداخت تأییدشدهٔ Basic/Pro، کردیت استفاده‌نشده با رویداد جبرانی ledger باطل می‌شود؛ سوابق قبلی حذف/ویرایش نمی‌شوند و کردیت مصرف‌شده در سوابق باقی می‌ماند.

اختیارات پنل:

- ساخت/ویرایش/فعال‌سازی/غیرفعال‌سازی محصول برای فروش
- تغییر قیمت، مقدار کردیت و مدت
- هنگام تغییر مقدار/مدت انتخاب صریح دامنه: فقط خریدهای جدید یا خریدهای فعال قبلی نیز
- نمایش پیش‌نمایش تعداد کاربران/خریدهای تحت تأثیر قبل از اعمال تغییر سراسری
- ثبت مقدار قبل/بعد، دامنهٔ اثر، actor، زمان و دلیل
- مشاهدهٔ وضعیت پرداخت، verify، callback و reconciliation
- بررسی درخواست لغو و refund و ثبت تصمیم، مبلغ، نتیجه و دلیل
- محدودیت و تأیید مجدد برای عملیات bulk
- هیچ تغییر تنظیمی نباید سابقهٔ خرید/پرداخت یا ledger را بازنویسی کند.

**گیت:** سیاست مشتری‌محور REFUND_POLICY.md باید پیش از انتشار توسط مالک نهایی و تأیید شود؛ این سند مشخصات پنل جایگزین تأیید سیاست حقوقی نیست.

### 4.6 اعتبار، Ledger و Fair Use

- نمایش حساب کردیت، رزروهای pending، مصرف، grant، refund و adjustment
- ledger فقط خواندنی؛ اصلاح موجودی از service مالی و رویداد append-only
- عملیات adjustment نیازمند دلیل، مبلغ، جهت، مرجع و تأیید مجدد
- تطبیق projection با ledger و نمایش اختلاف و reconciliation alert
- مدیریت abuse flags و ثبت resolution توسط Admin
- پیکربندی آستانه‌های Fair Use فقط از تنظیمات معتبر، با توضیح دامنه و زمان اثر
- تفکیک اعتبار خریداری‌شده، free grant، unlimited usage و refund
- هیچ دکمه‌ای برای حذف یا UPDATE مستقیم ledger وجود ندارد.

### 4.7 AI Model Control Center

مدیریت از طریق adapter و catalog پیکربندی‌شده، بدون import منطق vendor در domain:

- ثبت/ویرایش/غیرفعال‌سازی provider و endpoint غیرمحرمانه
- انتخاب مدل برای وظایف مشخص: fast chat، reasoning، vision، embedding، reranker، OCR/VLM و در صورت افزودن voice، STT/TTS
- مدل اصلی و fallback برای هر وظیفه
- timeout، سقف token، retry، concurrency و limitهای مجاز
- وضعیت health/readiness، نرخ خطا، latency، token usage و برآورد هزینه
- تست اتصال و اجرای smoke test با دادهٔ غیرحساس
- فعال/غیرفعال‌سازی اضطراری provider/model
- تاریخچهٔ تغییرات، نسخهٔ پیکربندی، rollout و rollback
- جلوگیری از اعمال مدلی که با ابعاد index فعال ناسازگار است؛ تغییر embedding باید از مسیر backfill/evaluation/atomic switch پیروی کند.

کلید API و Secret:
- هرگز در جدول settings یا Audit before/after ذخیره نشود.
- هرگز در پاسخ API، trace یا UI به شکل قابل‌خواندن برنگردد.
- در صورت فراهم‌بودن Secret Manager، عملیات set/rotate به‌شکل write-only و با نمایش فقط metadata/fingerprint مجاز است؛ read-back ممنوع.
- اگر محیط استقرار Secret Manager امن ندارد، مدیریت Secret خارج از پنل محصول و از مسیر ops مستند انجام می‌شود؛ نباید با ذخیرهٔ Secret در DB دور زده شود.

### 4.8 Prompt & Behavior Management

- فهرست promptهای سیستمی و دامنه‌ای با شناسه و purpose
- نسخه‌بندی immutable؛ ویرایش نسخهٔ منتشرشده ممنوع، نسخهٔ جدید ساخته شود
- مقایسهٔ diff، توضیح تغییر، author و تاریخچه
- آزمایش روی مجموعهٔ نمونهٔ ثابت و Golden Dataset مناسب
- ارزیابی امنیت، کیفیت، grade leakage، invalid citation و groundedness پیش از انتشار
- انتشار staged/canary در صورت پشتیبانی
- امکان rollback به آخرین نسخهٔ سالم
- Secret، متن خصوصی کاربران و دادهٔ شخصی نباید وارد prompt template یا نسخهٔ قابل مشاهدهٔ عمومی شوند.

### 4.9 AI Quality, Safety & Trace Review

- trace با request_id و شناسهٔ نسخهٔ model/prompt/index
- بررسی evidence_set واقعی استفاده‌شده در پاسخ، بدون ساختن شاهد جدید
- دسته‌بندی پاسخ‌های گزارش‌شده، insufficient evidence، invalid citation و grade-leak blocked
- رویدادهای prompt injection و guard blocked
- نمایش وضعیت redacted و حداقل داده؛ prompt کامل کاربر فقط با policy و مجوز مناسب
- ثبت برچسب بازبینی انسانی و نتیجهٔ رسیدگی، بدون تغییر خاموش پاسخ تاریخی
- ارزیابی batch و مقایسهٔ نسخه‌ها
- شاخص‌های مصرف کنترل‌نشده و رفتار غیرعادی

### 4.10 Knowledge Base & RAG Operations

- مدیریت کتاب، پایه، درس، edition، manifest و مجوز منبع
- صف pending/processing/ready/failed/needs_review
- جزئیات خطای استخراج، OCR، chunking، embedding و indexing
- پیشرفت و مرحلهٔ جاری هر job
- retry دستی فقط برای jobهای idempotent و قابل‌تکرار
- نسخهٔ منابع و checksum
- مشاهدهٔ صفحات/قطعات و متادیتا
- مدیریت index namespace، embedding model/dimension و وضعیت فعال
- فرایند ساخت index جدید، backfill، evaluation و switch اتمیک؛ تغییر درجا ممنوع
- ابزار بررسی retrieval: query، filters، dense/lexical candidates، RRF، reranker و evidence نهایی
- اجرای Golden Dataset و نمایش گیت‌های grade leakage=0 و invalid citation=0
- منابع فاقد مجوز یا با metadata مبهم نباید از پنل به production منتشر شوند.

### 4.11 Security Center

- رخدادهای ورود موفق/ناموفق، OTP، refresh reuse و authorization failures
- نشست‌های فعال و ابطال کنترل‌شده
- IP/device metadata در حد مجاز و retention مصوب
- هشدار ورود غیرعادی، نرخ شکست OTP و رفتار مشکوک
- بررسی حساب‌های محدودشده و Abuse Flag
- ثبت عملیات مدیریتی و دسترسی به دادهٔ حساس
- MFA/step-up status حساب Admin
- مدیریت امن break-glass و بازیابی اضطراری با ثبت کامل
- تست دوره‌ای کنترل‌های admin authorization و multi-user isolation

حساب Admin به دلیل سطح اثر بسیار بالا باید عامل دوم داشته باشد. اولویت طراحی با عامل مقاوم به phishing مانند WebAuthn/Passkey است؛ OTP پیامکی به‌تنهایی عامل phishing-resistant محسوب نمی‌شود. جزئیات factor، recovery و session timeout باید در ADR امنیتی قبل از پیاده‌سازی نهایی شوند.

### 4.12 System Health & Observability

- سلامت API، DB، Redis، worker، inference، storage و providerها
- readiness مجزا از liveness
- نرخ خطا، p50/p95 latency، throughput و saturation
- عمق صف و زمان انتظار job
- مصرف CPU/RAM/Disk و فضای آزاد
- هزینه و نرخ خطای providerها
- version/commit/build information
- وضعیت migration و schema head
- نشان‌دادن زمان آخرین نمونه و stale state
- لینک از metric/alert به runbook یا رخداد مرتبط

این ماژول باید فقط از health/metrics معتبر استفاده کند و عملیات نوشتن مستقیم روی زیرساخت را به ابزارهای کنترل‌شدهٔ ops بسپارد.

### 4.13 Job & Queue Manager

- فهرست jobهای queued/running/completed/failed/dead
- نوع، شناسه، زمان ایجاد/شروع/پایان، مدت، تعداد retry و پیشرفت
- خطای redacted و علت شکست
- retry دستی فقط برای jobهایی که idempotency و policy retry آن‌ها اجازه می‌دهد
- لغو jobهای cancellable
- نمایش jobهای stale و dead-letter
- ثبت actor و reason برای retry/cancel
- جلوگیری از اجرای هم‌زمان job انحصاری و اجرای مالی تکراری
- کنترل concurrency و سقف‌ها فقط در محدودهٔ تنظیمات معتبر

### 4.14 Alert & Incident Center

- alert با severity، منبع، fingerprint، first_seen، last_seen، occurrence count و status
- deduplication و suppression کنترل‌شده
- وضعیت‌های open/acknowledged/investigating/resolved
- اتصال alert به metric، job، user یا provider
- incident timeline، اثر بر کاربر، root cause، mitigation و follow-up
- ثبت مدیر رسیدگی‌کننده و اقدام انجام‌شده
- runbook برای رخدادهای پرتکرار
- اعلان بیرونی فقط از integrationهای مصوب و با تنظیمات حریم خصوصی
- جلوگیری از alert fatigue با threshold، grouping و آزمایش alert

### 4.15 Settings & Feature Flags

تنظیمات سه دسته‌اند:

1. **Product settings:** در جدول settings با نوع، schema، بازه، مقدار پیش‌فرض، actor، reason و updated_at؛ اعتبارسنجی در زمان نوشتن.
2. **Runtime/infrastructure settings:** فقط از environment یا ابزار مدیریت زیرساخت؛ هرگز با تنظیمات محصولی مخلوط نشود.
3. **Secrets:** فقط در environment/secret manager؛ نه DB settings و نه UI read-back.

ویژگی‌های پنل:
- دسته‌بندی، جست‌وجو و توضیح هر setting
- نمایش current/default، نوع، محدوده و اثر
- تغییر با validation و reason
- تاریخچه، compare و rollback
- cache invalidation پس از update
- انتخاب scope برای تغییرات پلن روی خریدهای جدید یا خریدهای فعال
- زمان‌بندی تغییر در صورت پشتیبانی دامنه
- preview و dry-run برای bulk impact
- ثبت نسخهٔ پیکربندی

Feature Flags:
- enabled/disabled، محیط، مخاطب/targeting و زمان شروع/پایان
- rollout درصدی یا گروه آزمایشی فقط با قواعد deterministic و قابل‌ممیزی
- kill switch اضطراری برای provider/قابلیت مشخص
- fallback امن و مقدار پیش‌فرض مشخص
- ثبت نتیجهٔ ارزیابی flag و خطاها، بدون ذخیرهٔ PII غیرضروری
- flags جای authorization یا شرط امنیتی را نمی‌گیرند.

### 4.16 Backup & Recovery

- وضعیت آخرین backup و archive/WAL
- timestamp، نوع، حجم، مقصد و نتیجه
- retention و encryption metadata
- هشدار backup ناموفق یا stale
- زمان و نتیجهٔ آخرین restore drill
- ثبت RPO/RTO هدف و مقدار واقعی مشاهده‌شده
- runbook و مراحل restore
- عملیات restore production از UI عمومی انجام نمی‌شود؛ باید فرایند جدا، تأیید چندمرحله‌ای، مقصد ایزوله، preflight و تست پس از بازیابی داشته باشد.
- backup شامل secrets یا اطلاعاتی بیش از نیاز نباشد و دسترسی آن محدود باشد.

### 4.17 Privacy & Data Lifecycle

- درخواست export، حذف، اصلاح یا محدودسازی داده
- وضعیت پردازش، مهلت، خطا و بخش‌های تکمیل‌نشده
- سوابق consent و نسخهٔ terms/privacy
- retention policy برای upload، logs، traces و session data
- تفکیک داده‌هایی که باید به دلیل حسابرسی مالی نگهداری شوند
- اجرای deletion/soft-delete/anonymization از سرویس چرخهٔ عمر داده
- ثبت دسترسی مدیر به گفتگوها و دادهٔ حساس
- export فقط با دسترسی کنترل‌شده، لینک مدت‌دار و audit
- گزارش خطاهای deletion؛ حذف ناقص نباید موفق گزارش شود.

### 4.18 Audit Log Explorer

منابع مختلف رخداد نباید بی‌دلیل در یک جدول یا مفهوم ادغام شوند: admin_audit_log برای اقدامات مدیریتی، security events برای امنیت، application logs/traces برای عملیات، و ledger برای حقیقت مالی.

فیلدهای حداقلی رخداد مدیریتی:

- event_id، timestamp UTC، request_id
- actor_admin_id
- subject_user_id در صورت نمایندگی
- action، entity_type، entity_id
- outcome و reason
- before/after پالایش‌شده، نه شامل secret یا دادهٔ غیرضروری
- source/session context در حد مجاز
- correlation_id برای پیوند با job/payment/incident

امکانات:
- جست‌وجو و فیلتر cursor-based
- نمایش جزئیات رخداد و زنجیرهٔ مرتبط
- export audit برای بررسی مجاز
- ثبت دسترسی و export خود Audit Log
- نگهداری append-only و محدودیت دسترسی
- تشخیص شکاف/قطع logging و alert آن

### 4.19 Business & Product Analytics

- کاربران جدید، فعال و بازگشتی
- conversion از free به paid
- فروش و درآمد به تفکیک پلن و زمان
- renewal/re-purchase و churn
- میزان استفاده از گفتگو و موضوعات/پایه‌ها به‌صورت aggregate
- هزینهٔ AI به تفکیک model/provider و cohort
- هزینهٔ میانگین هر پاسخ/کاربر
- latency، error rate و رضایت/feedback
- funnel ثبت‌نام تا اولین پاسخ و خرید
- export گزارش با کنترل دسترسی و audit

Analytics باید از دادهٔ تجمیعی و تعریف روشن metric استفاده کند؛ metricهای مالی از منبع قطعی مالی و metricهای استفاده از usage_events بازسازی شوند. تعداد کاربران فعال و retention باید تعریف مکتوب داشته باشند تا گزارش‌ها بین صفحات ناسازگار نشوند.

### 4.20 Content & Communication

- مدیریت FAQ، راهنما و صفحات عمومی
- اعلان درون‌برنامه‌ای و پیام تعمیرات
- قالب‌های پیامک/اطلاع‌رسانی با نسخه‌بندی
- ارسال هدفمند بر اساس معیار مجاز و رضایت ارتباطی
- صف و وضعیت ارسال، retry امن و گزارش خطا
- ترجمه‌های fa/en/ar و preview RTL/LTR
- انتشار زمان‌بندی‌شده و rollback
- مدیریت نسخهٔ شرایط استفاده/حریم خصوصی با ثبت زمان پذیرش کاربر

## 5. مدل دسترسی و تأیید عملیات

### 5.1 ماتریس کلی

| سطح عملیات | دسترسی Admin | کنترل الزامی |
|---|---|---|
| مشاهدهٔ اطلاعات عملیاتی | مجاز | احراز هویت و audit برای دادهٔ حساس |
| ویرایش تنظیمات عادی | مجاز | validation، reason، before/after |
| تغییر پلن و قیمت | مجاز | preview اثر، دامنهٔ اعمال، تأیید مجدد |
| تغییر دادهٔ کاربر | مجاز در جریان دامنه | ثبت actor/subject و reason |
| ورود نمایندگی | مجاز | context جدا، دلیل، مدت و audit |
| refund/adjust مالی | از جریان مالی مجاز | step-up، idempotency، ledger event |
| حذف/بی‌نام‌سازی | از جریان privacy | preflight، retention rules و audit |
| اجرای مجدد job | مشروط به policy | idempotency، status guard و audit |
| تغییر provider/model/prompt | مجاز | validation، eval، rollout و rollback |
| مدیریت Secret | محدود به secret manager | write-only، بدون read-back یا log |
| Restore تولید | نه از UI عمومی | runbook و کنترل چندمرحله‌ای ops |

### 5.2 تأیید مجدد و حفاظت در برابر خطا

برای عملیات با اثر بالا، دست‌کم این کنترل‌ها لازم است: re-authentication/step-up، reason، نمایش اثر دقیق، تأیید نهایی و idempotency. عملیات bulk ابتدا dry-run می‌شود و تعداد/دامنهٔ رکوردهای متاثر را نشان می‌دهد. درخواست تکراری نباید دوباره اثر ایجاد کند.

### 5.3 حدود اختیار

Admin تنها نقش مدیریتی محصول است و permission matrix چندنقشی ایجاد نمی‌کنیم. در عین حال، قیود غیرقابل‌دورزدن شامل ledger append-only، عدم افشای Secret، مالکیت و مرزهای امنیتی، integrity constraints، grade ceiling، citation validation و ثبت audit باقی می‌مانند.

## 6. معماری backend و داده (طرح مفهومی)

این موارد نامزد طراحی هستند و به معنی وجود جدول یا migration فعلی نیستند:

| مفهوم | هدف |
|---|---|
| Admin acting session/context | نشست نمایندگی زمان‌دار با actor و subject جدا |
| Support ticket/message | تیکت، پاسخ عمومی و یادداشت داخلی |
| Admin audit event | ثبت عملیات مدیریتی و context |
| Security event | رخدادهای authn/authz و رفتار مشکوک |
| Settings revision | تاریخچهٔ نسخه و rollback تنظیمات |
| Feature flag | تعریف و ارزیابی feature flags |
| Provider/model config | metadata غیرمحرمانه و reference به secret |
| Prompt version/release | نسخه‌بندی، ارزیابی و انتشار prompt |
| Evaluation run/result | مجموعه تست، نسخه‌ها و نتایج کیفیت |
| Incident/alert | چرخهٔ هشدار و رسیدگی |
| Job execution metadata | پیشرفت، retry، dead-letter و نتیجه |
| Privacy request | درخواست export/delete و وضعیت اجرا |
| Backup/restore drill record | شواهد backup و آزمون بازیابی |
| Notification/template | پیام، کانال، نسخه و وضعیت ارسال |

قواعد:
- همهٔ schema changes فقط با Alembic و migrations برگشت‌پذیر/مستند.
- تمام I/O async و جداسازی router/service/repository/adapter طبق AGENTS.
- فهرست‌ها cursor-based و محدودشده‌اند.
- هر endpoint دارای Pydantic request/response schema و error contract استاندارد است.
- هر endpoint مدیریتی authorization سمت سرور دارد.
- تغییرات چندموجودیتی اتمیک‌اند؛ عملیات بیرونی با outbox/job و idempotency هماهنگ می‌شوند.
- روابط و FKها ondelete صریح و ownership/actor fields واضح دارند.

## 7. گروه‌بندی API پیشنهادی

این گروه‌ها فقط مرزبندی resource هستند و route/schema نهایی باید پیش از پیاده‌سازی در docs/API_CONTRACT.md ثبت شود:

- admin/dashboard
- admin/users و admin/acting-sessions
- admin/support/tickets
- admin/billing/products، payments، subscriptions، refunds
- admin/credits، ledger-read، reservations و fair-use
- admin/ai/providers، models، routing، prompts و evaluations
- admin/knowledge/documents، ingestion، indexes و retrieval-inspection
- admin/security/sessions و security-events
- admin/operations/health، metrics، jobs، alerts و incidents
- admin/settings و feature-flags
- admin/backups و restore-drills (read/report/runbook controls)
- admin/privacy/requests
- admin/audit
- admin/analytics
- admin/content و notifications

هیچ endpoint پیشنهادی تا قبل از Phase مربوطه و به‌روزرسانی API_CONTRACT پیاده‌سازی‌شده تلقی نمی‌شود.

## 8. الزامات UI/UX

- رابط فارسی/انگلیسی/عربی و RTL/LTR کامل
- responsive؛ دسکتاپ، تبلت و موبایل
- نوار ناوبری با collapse و جست‌وجوی ماژول
- داشبورد با کارت‌های قابل تنظیم اما نه قابل حذفِ شاخص‌های بحرانی
- فیلتر و cursor pagination استاندارد
- فرم‌های تنظیمات با توضیح، default، range، validation و impact preview
- صفحهٔ جزئیات با timeline واحد و لینک به اشیای مرتبط
- تأیید دوم برای عملیات مخرب/مالی
- پیام موفقیت/شکست واقعی از backend؛ عدم اعلام موفقیت قبل از نتیجه
- نشانهٔ واضح برای دادهٔ stale، unknown یا unavailable
- همهٔ عملیات با keyboard navigation و دسترس‌پذیری پایه
- نمایش timezone و واحد پول/کردیت صریح
- در impersonation نشان دائمی و پررنگ و پایان سریع نشست

## 9. امنیت، حریم خصوصی و حسابرسی

- احراز مجوز سمت سرور در تمام مسیرهای admin و acting context
- عامل دوم برای Admin و step-up برای اقدامات حساس؛ ترجیح Passkey/WebAuthn
- session timeout و re-authentication برای اقدامات حساس طبق ADR
- هیچ token کاربر هدفی برای impersonation تولید یا ذخیره نشود
- audit append-only و مجزا از ledger و application logs
- before/after باید redact و allowlist شود؛ لاگ خام request/response ممنوع
- phone، token، OTP، payment secrets، کلید provider، prompt خصوصی و متن پیام به‌صورت پیش‌فرض در لاگ ذخیره نشوند
- دسترسی و export دادهٔ حساس نیز audit شود
- bulk export، impersonation و تغییرات مالی rate limit و ثبت شوند
- logging failure برای رویدادهای امنیتی/مالی باید قابل تشخیص باشد؛ fail-open/closed هر دسته صریح طراحی شود
- query-level ownership و تست multi-user isolation حفظ شود
- تمام عملیات حساس دارای request_id/correlation_id باشند

## 10. Observability و عملیات

داشبورد باید liveness و readiness را اشتباه نگیرد. برای هر dependency آخرین check و freshness داده نمایش داده شود. وضعیت ناشناخته برابر سالم نیست. متریک‌های حیاتی شامل latency، خطا، throughput، queue depth/age، provider failure، هزینه، reservation stale، reconcile diff، invalid citation و grade leakage است.

هشدارها باید actionable و قابل اتصال به runbook باشند. Incident record شامل timeline، شدت، کاربران متاثر، ریشه، mitigation و اقدام جلوگیری از تکرار است.

## 11. تست و معیارهای پذیرش

Phase 7 فقط زمانی COMPLETE است که معیارهای زیر با شواهد واقعی پاس شوند:

### Access & Admin identity
- تمام endpointهای admin بدون Admin معتبر 401/403 دریافت کنند.
- مخفی‌کردن UI هیچ endpointی را باز نگذارد.
- Admin به قابلیت‌های user-facing دسترسی داشته باشد، بدون تغییر role یا جعل session کاربر.
- impersonation actor و subject را در audit جدا نگه دارد.
- نشست نمایندگی پس از پایان/انقضا قابل استفاده نباشد و token کاربر ساخته نشده باشد.
- تلاش user عادی برای acting session رد شود.

### Audit & Security
- عملیات حساس before/after/reason/actor/outcome ثبت کند.
- Secret، OTP، token و محتوای خصوصی در audit/log نشت نکند.
- دسترسی به audit و export خود audit ثبت شود.
- step-up ناموفق عملیات حساس را متوقف کند.
- audit append-only و قابل فهرست/صفحه‌بندی باشد.

### Finance
- ledger فقط خواندنی باشد و adjustment/refund فقط از service مالی با رویداد جبرانی انجام شود.
- callback یا درخواست مدیریتی تکراری اثر دوگانه نداشته باشد.
- عملیات bulk و تغییر config روی خریدهای فعال dry-run و impact count داشته باشد.
- سیاست انقضا/تمدید/لغو/refund مطابق تصمیم‌های مالک تست شود.
- هیچ پلن مستقلی با تغییر/لغو پلن دیگر ناخواسته تغییر نکند.

### Settings & AI
- مقدار نامعتبر رد شود؛ cache پس از تغییر invalidate شود.
- update تنظیمات audit و rollback مشخص داشته باشد.
- feature flag هرگز authorization را جایگزین نکند.
- تغییر prompt/model بدون eval موردنیاز منتشر نشود.
- embedding/index mismatch قبل از اجرای retrieval رد شود.
- kill switch provider مسیر fallback امن داشته باشد.

### Operations & Privacy
- job retry فقط در وضعیت و policy مجاز باشد و idempotency حفظ شود.
- dead job و alert به مدیر قابل مشاهده باشد.
- وضعیت backup با evidence و timestamp نشان داده شود.
- درخواست export/delete تا پایان واقعی همهٔ مراحل موفق اعلام نشود.
- دسترسی‌ها و خروجی‌های حریم خصوصی audit شوند.

### Quality gates
- lint/typecheck/test-db و migration tests مرتبط پاس شوند.
- تست‌های admin authorization، impersonation، audit redaction، bulk-operation idempotency و multi-user isolation وجود داشته باشد.
- تست واقعی PostgreSQL برای قیود داده و raceها اجرا شود.
- تست UI برای RTL/LTR، responsive و نمایش حالت stale/unavailable انجام شود.
- هیچ معیار صرفاً با mock به‌عنوان اثبات رفتار production اعلام نشود.

## 12. ترتیب پیشنهادی پیاده‌سازی

ترتیب زیر وابستگی‌ها را رعایت می‌کند و به معنی تغییر وضعیت Roadmap نیست:

1. **Admin foundation:** authz، layout، dashboard shell، Audit foundation، pagination، common filters.
2. **User operations:** User 360، session/security overview و acting-session safeguards.
3. **Finance/support:** پلن، پرداخت، Ledger read-only، Fair Use، refund/cancellation workflow و ticketing.
4. **Settings/flags:** settings UI، validation، revision، cache invalidation، feature flags.
5. **AI operations:** Provider/model controls، Prompt versioning، eval/release، trace and quality review.
6. **Knowledge operations:** ingestion, document review, index and retrieval inspection.
7. **System operations:** health, jobs, alerts, incidents, backup status and restore evidence.
8. **Privacy & analytics:** export/delete lifecycle, consent, aggregate analytics, content/communications.
9. **Production hardening:** penetration/security review, load testing, restore drill, operational runbooks and release gates.

قابلیت‌هایی که به فازهای ۳ تا ۶ وابسته‌اند می‌توانند تا آماده‌شدن داده/قراردادشان در UI با وضعیت «در انتظار فعال‌شدن فاز وابسته» نمایش داده شوند؛ endpoint یا دادهٔ ساختگی نساز.

## 13. خارج از دامنه و تصمیم‌های نیازمند ADR

- ساخت نقش‌های مدیریتی متعدد، RBAC قابل‌پیکربندی و تیم‌های سازمانی در این دامنه نیست.
- خودکارسازی تصمیم refund یا تعلیق کاربران بر اساس مدل هوش مصنوعی مجاز نیست.
- نمایش کامل Secret، ذخیرهٔ Secret در جدول settings یا بازگرداندن Secret از API ممنوع است.
- حذف/ویرایش ledger ممنوع است.
- Restore مستقیم production از صفحهٔ عمومی Admin خارج از دامنه است.
- پیاده‌سازی واقعی ماژول‌های AI/RAG قبل از تکمیل فاز مالکشان ممنوع است.
- روش MFA، recovery، طول عمر acting session و جزئیات step-up باید در ADR امنیتی تصویب شود.
- مدل اثر مالی چت در حالت impersonation، حدود دسترسی مدیر به متن گفتگو و retention/audit جزئی باید در ADR/سیاست حریم خصوصی تعیین شود.
- مسیر secret rotation از UI تنها در صورت اتصال به secret manager امن و write-only تصویب می‌شود.
- سیاست حقوقی نهایی Refund/Privacy باید جداگانه تأیید مالک و بررسی حقوقی شود.

## 14. منابع و استانداردهای مرجع

این منابع برای هدایت کنترل‌های امنیتی/عملیاتی استفاده شده‌اند؛ جایگزین بررسی حقوقی یا تحلیل تهدید اختصاصی Darsyar نیستند:

- NIST SP 800-63B-4 — Authenticators and phishing resistance: https://pages.nist.gov/800-63-4/sp800-63b/authenticators/
- OWASP Logging Cheat Sheet — security and application logging: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- OWASP GenAI Security Project — LLM Top 10 2026: https://genai.owasp.org/llm-top-10/
- OpenFeature Specification — vendor-neutral feature flag evaluation and context: https://openfeature.dev/specification/
- PostgreSQL 18 — Continuous Archiving and Point-in-Time Recovery: https://www.postgresql.org/docs/18/continuous-archiving.html
- Google SRE Workbook — Alerting on SLOs: https://sre.google/workbook/alerting-on-slos/

---

**وضعیت نهایی سند:** Draft برای بازبینی/تصویب؛ هیچ endpoint، migration یا قابلیت اجرایی صرفاً با افزودن این سند ایجاد نشده است.
