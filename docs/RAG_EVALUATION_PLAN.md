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
