# طرح ارزیابی RAG

## مجموعهٔ طلایی
R-171 حداقل ۱۵۰ پرسش در پایه‌ها و درس‌های مختلف با پاسخ مرجع و evidence مشخص می‌خواهد. این ZIP پاسخ/شاهد ساختگی ندارد؛ مالک باید منابع مجاز و پرسش‌های معتبر را فراهم کند و هر مجموعه versioned شود.

## معیارها
- grade leakage: صفر
- citation خارج از evidence_set: صفر
- recall@k برای بازیابی dense و lexical به‌صورت جداگانه و پس از RRF
- groundedness/faithfulness با نمونه‌گیری انسانی
- امتیاز rerank و آستانه‌ها با dataset تنظیم شوند، نه حدس
- latency: retrieval/rerank بودجهٔ صریح دارد

## گزارش
هر اجرا مدل embedding، ابعاد، edition، تنظیمات chunk، پارامترهای retrieval، مدل reranker، نسخهٔ dataset، تعداد نمونه و نرخ خطا را ثبت کند. هر تغییر در splitter، embedding یا آستانه نیازمند اجرای evaluation است.


## اندازه‌گیری صادقانهٔ معیارها (2026-11-12)

- `grade_leakage` بر تعداد chunkهای بازیابی‌شده نرمال می‌شود، نه تعداد پرسش‌ها.
- `invalid_citation_rate` بر تعداد candidateهای واقعاً نمایش‌پذیر در top-5 نرمال می‌شود و متادیتای سمت سرور (شناسه‌های UUID، عنوان، درس، پایه، شمارهٔ قطعه و صفحهٔ معتبر/نامشخص) را بررسی می‌کند.
- `retrieval_precision_at_5` فقط precision بازیابی است؛ معادل groundedness پاسخ تولیدشده نیست.
- `answer_groundedness` در harness بازیابی‌محور فعلی **NOT MEASURED** باقی می‌ماند تا زمانی که خروجی پاسخ، شناسه‌های evidence استفاده‌شده و بازبینی انسانی در قرارداد evaluation وارد شوند.
