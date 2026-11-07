# ADR-054: پشتیبانی رسمی Remote Embedding/Inference

- **وضعیت:** accepted (تصمیم مالک — 2026-11-08؛ تأیید صریح)
- **هم‌راستا با:** ADR-036 (پیش‌نیاز/توسعه)، R-029/R-030/R-031/R-036/R-040/R-087؛ D-09/D-11
- **رابطه با ADR-036:** این ADR **جایگزین/توسعه** بخشی از ADR-036 است. ADR-036 `service` را به‌عنوان حالت اصلی پذیرفت و `remote` را به‌عنوان «گزینهٔ جایگزین پیکربندی‌پذیر» ذکر کرد (بدون تصویب به‌عنوان حالت عملیاتی). این ADR به‌صراحت `remote` را به‌عنوان **backend پشتیبانی‌شده** در چارچوب همان معماری دو-process ثبت می‌کند.

## زمینه

ممیزی Remote Inference نشان داد:
- `RemoteInferenceBackend` در Inference Service پیاده‌سازی شده و از `EMBEDDING_BACKEND=remote` استفاده می‌کند.
- کلید Provider فقط در Inference process در دسترس است؛ API هیچ مدل ML یا کلید provider را بارگذاری/دریافت نمی‌کند.
- هیچ درخواست `/embed`/`/rerank` هنوز از API به Inference ارسال نمی‌شود (Retrieval/RAG در فاز ۵ است).
- ADR-036 در «گزینهٔ ردشدهٔ ۳» نصب/remote را به‌عنوان حالت اصلی رد کرده بود؛ این ADR به‌روزرسانی آن تعارض را مشخص می‌کند.

## تصمیم پیشنهادی

1. **اصل اول — جداسازی Process:** معماری دایماً دو process مستقل دارد: API و Inference Service. API مستقیماً provider embedding را فراخوانی نمی‌کند، مدل ML بارگذاری نمی‌کند، و کلید provider فقط در Inference process در دسترس است.
2. **اصل دوم — جداسازی Execution Mode از Backend Selection:**
   - `INFERENCE_MODE` نحوهٔ اجرای Inference را تعیین می‌کند (`service`/`remote`).
   - `EMBEDDING_BACKEND` backend تولید embedding را تعیین می‌کند (`service`/`remote`).
   - این دو مستقل از هم پیکربندی می‌شوند؛ backend remote همیشه از طریق Inference Service اجرا می‌شود.
3. **اصل سوم — پشتیبانی Remote:** Remote Embedding با provider قابل پیکربندی پشتیبانی می‌شود. OpenRouter یکی از providerهای قابل استفاده است، نه وابستگی دائمی منطق Retrieval. **هیچ fallback خودکاری میان Remote و Local مجاز نیست**؛ اگر remote انتخاب شده ولی پیکربندی/provider در دسترس نباشد، خطای شفاف تولید می‌شود.
4. **اصل چهارم — پشتیبانی Local در آینده:** معماری امکان اجرای BGE-M3 و مدل‌های محلی سازگار را در Inference Service حفظ می‌کند. نبود GPU نباید معماری API را تغییر دهد. Local و Remote پشت abstraction مشترک (`embedding.py`/`rerank.py`) باقی می‌مانند.
5. **اصل پنجم — قرارداد Retrieval:** قرارداد کامل ذخیره/بازیابی Embedding در فاز Retrieval/RAG تعریف می‌شود (مدل/نسخه دقیق، ابعاد، query/document encoding compatibility، normalization، distance metric، مدل indexing، سیاست تغییر مدل و reindex، metadata لازم در index_meta). تا اجرای این تصمیم در فاز مربوطه، سازگاری کامل با RAG ادعا نمی‌شود.
6. **اصل ششم — Reranker:** Remote و Local Reranker می‌توانند پشتیبانی شوند، اما راه‌اندازی/انتخاب provider آن مطابق نیاز واقعی Retrieval و تصمیمات فاز RAG است. نبود Reranker در فاز فعلی blocker برای Remote Embedding نیست.

## گزینه‌های ردشده

1. **اتصال مستقیم API به OpenRouter** — نقض اصل جداسازی process؛ کلید در API در دسترس می‌شد (R-029/R-040).
2. **fallback خودکار Remote↔Local** — منبع ابهامِ هزینه و رفتار؛ رد شد (R-031).
3. **فقط Local (عدم پشتیبانی remote)** — نیازمند GPU/حافظه؛ در محیط فعلی (بدون GPU و محدودیت دیسک) عملیاتی نیست.

## پیامدها

- **بدون تغییر runtime در این تصمیم:** فقط ثبت معماری. پیاده‌سازی از قبل در `backend/app/inference/remote.py` موجود است.
- **رابطه با ADR-036:** با پذیرش این ADR، بند «remote به‌عنوان گزینهٔ جایگزین» در ADR-036 توسعه می‌یابد؛ ADR-036 بازنویسی نمی‌شود، بلکه با ارجاع به ADR-054 تکمیل می‌شود.
- **فایل‌های متأثر (در ادامه/پس از تصویب):** `docs/DECISIONS.md` (ثبت D-11)، `docs/FILE_MAP.md`، و (فقط پس از تصویب) در صورت نیاز مستندات ارجاعی.

## تست‌های لازم برای اعتبارسنجی

- تست واحد: انتخاب backend بر اساس `EMBEDDING_BACKEND`/`INFERENCE_MODE`.
- تست: در نبود پیکربندی remote، `startup`/`ready`/`/embed` خطای شفاف (`model_runtime_not_ready`/`inference_remote_error`) می‌دهند.
- تست: هیچ مدل محلی در API process لود نمی‌شود.
- تست: عدم fallback خودکار بین remote و local.
- تست زندهٔ یک‌بار (پس از تصویب مالک) برای اثبات ابعاد/سازگاری واقعی provider.
