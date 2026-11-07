# ADR-036: انتخاب مسیر inference — سرویس داخلی (service)

- **وضعیت:** accepted (تصمیم مالک — 2026-11-07؛ بخشی از شروع‌به‌کار فاز ۳)
- **هم‌راستا با:** R-029/R-030/R-031/R-036/R-040؛ ADR-041

## زمینه

مدل‌های سنگین (embedding/rerank) نباید در process وب لود شوند (R-029) و مسیر چت نباید برای embedding/rerank منتظر صف worker بماند. پروژه دو حالت از پیش تعریف کرده است: `INFERENCE_MODE=service` (سرویس داخلی اختصاصی روی همان image) یا `remote` (API سازگار بیرونی).

## تصمیم تأییدشده

`INFERENCE_MODE=service` به‌عنوان حالت اصلی و پیش‌فرض معماری فاز ۳ انتخاب می‌شود.

- سرویس `inference` با **همان image بک‌اند** و دستور متفاوت اجرا می‌شود: `uvicorn app.inference.main:app --port 8100` (R-036/R-030).
- مدل‌ها (BAAI/bge-m3 و BAAI/bge-reranker-v2-m3) یک‌بار در startup لود و برای طول عمر process در حافظه نگه داشته می‌شوند.
- endpointها: `POST /embed`، `POST /rerank`، `GET /health` (liveness)، `GET /ready` (فقط وقتی مدل‌ها واقعاً آماده‌اند).
- سرویس هیچ پورتی روی host منتشر نمی‌کند؛ فقط در شبکهٔ داخلی Compose دیده می‌شود (R-031)؛ `backend`/`worker` با healthcheck سالم به آن وابسته‌اند.
- `remote` به‌عنوان حالت جایگزین/مستقر در آینده پیکربندی‌پذیر باقی می‌ماند؛ **هیچ fallback خاموش به provider دوردست هنگام شکست سرویس محلی انجام نمی‌شود** — شکست سرویس محلی منجر به خطای صریح می‌شود، نه جابه‌جایی بی‌صدا.

## گزینه‌های ردشده

1. **لود مدل ML در API/process وب** — نقض R-029؛ نشت هزینه/تأخیر به درخواست‌های وب.
2. **مسیر worker-queue برای embedding/rerank چت** — نقض R-029/R-197؛ تأخیر صف هدف کارایی را نقض می‌کند.
3. **`remote` به‌عنوان حالت اصلی** — نیازمند زیرساخت بیرونی و مدیریت راز خارجی؛ برای استقرار اولیه روی یک VPS بدون GPU و با معماری داخلی، حالت service هم‌راستاتر است.

## پیامدهای عملیاتی

- پورت inference فقط internal؛ بدون انتشار host.
- `backend`/`worker` به `INFERENCE_URL` و `INFERENCE_TIMEOUT_SECONDS` وابسته‌اند.
- startup سرویس inference فقط وقتی مدل‌ها بارگذاری شده‌اند `ready` می‌دهد؛ پیش از آن `503 model_runtime_not_ready`.
- اگر سرویس inference در دسترس نباشد، مسیر چت باید با خطای صریح شکست بخورد (نه fallback خاموش).

## معناشناسی readiness و شکست

- `GET /health`: زنده‌بودن process (بدون وابستگی به مدل).
- `GET /ready`: 200 فقط وقتی هر دو مدل (embed/rerank) لود و آماده‌اند؛ وگرنه 503 با دلیل.
- خطای `POST /embed` یا `POST /rerank` در نبود مدل: 503 `model_runtime_not_ready`.
- بارگذاری ناموفق مدل در startup: process با کد غیرصفر خارج می‌شود (fail fast).

## امنیت و حریم خصوصی

- سرویس فقط روی شبکهٔ داخلی؛ بدون API key عمومی.
- ورودی/خروجی اعتبارسنجی‌شده و محدودشده به batch/اندازه (R-041/053).
- هیچ دادهٔ محرمانه یا prompt کامل در لاگ ثبت نمی‌شود (R-060).

## پیکربندی لازم

- `INFERENCE_MODE=service`
- `INFERENCE_URL` (internal، مثال `http://inference:8100`)
- `INFERENCE_TIMEOUT_SECONDS`
- `INFERENCE_DEVICE` (مثلاً `cpu`)
- `EMBEDDING_MODEL=BAAI/bge-m3`، `EMBEDDING_DIM=1024`
- `RERANKER_MODEL=BAAI/bge-reranker-v2-m3`
- `HF_CACHE_DIR`/`HF_HOME` (cache volume در Compose)

## تست‌های لازم برای اعتبارسنجی تصمیم

- تست unit/ج: `ready` در نبود مدل 503 می‌دهد.
- تست: `/health` مستقل از مدل است.
- تست: `/embed` و `/rerank` قرارداد ورودی/خروجی را اعتبارسنجی می‌کنند.
- تست: مدل در فرایند API/وب لود نمی‌شود (بدون import سنگین).

## رابطه با ADR-054 (جایگزینی جزئی)

ADR-054 به‌عنوان تصمیم تکمیلی پذیرفته‌شده، پشتیبانی عملیاتی Remote Inference را مجاز می‌کند و بخش مربوط به رد Remote به‌عنوان حالت عملیاتی جایگزین را توسعه می‌دهد. تصمیم ADR-036 درباره حفظ Inference Service مستقل همچنان معتبر است. در صورت تعارض میان مفاد دو ADR، ADR-054 فقط در محدوده‌ای که صریحاً تعیین کرده است مرجع جدید خواهد بود. (ثبت: D-11؛ 2026-11-08)

## فایل‌های متأثر

- `backend/app/inference/main.py`، `backend/app/inference/models.py`
- `backend/app/services/embedding.py`، `backend/app/services/rerank.py` (کلاینت‌ها)
- `docker-compose.yml` (سرویس inference موجود)
- `docs/TECH_STACK.md`، `docs/FILE_MAP.md`
- `backend/app/core/config.py` (پیش‌فرض `inference_mode`)
