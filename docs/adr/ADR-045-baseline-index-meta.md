# ADR-045: ساخت جدول رجیستری `index_meta` در فاز صفر — تأییدشده

- **وضعیت:** accepted (تصمیم مالک، 2026-10-27)
- **تاریخ:** 2026-10-27
- **هم‌راستا با:** R-087، R-088، R-089، R-090، R-079، R-057

## زمینه

R-087 جدول `index_meta` با ستون‌های `(id, embedding_model, embedding_dim, distance_metric, created_at, is_active)` را الزامی می‌کند و هر ingestion/کوئری باید ابتدا رکورد فعال را بخواند. فازهای ingestion/RAG (۴ و ۵) بعداً اضافه می‌شوند، ولی schema از همین حالا باید از مسیر مهاجرت Alembic بسازد.

## تصمیم تأییدشده

مهاجرت `0002_index_meta_registry` جدول `index_meta` را با کلید UUID، `created_at timestamptz`، `is_active` و قید یکتای جزئی روی `is_active` (حداکثر یک رکورد فعال) می‌سازد. هیچ منطق محصولی، seed یا query در این فاز به آن متصل نیست؛ مدل ORM با سبک `Mapped[]` اضافه شده تا metadata کامل باشد.

## شواهد تأیید (2026-10-27)

- مدل `app/models/index_meta.py`، مهاجرت `0002` و schema واقعی PostgreSQL با هم مقایسه و منطبق تأیید شدند.
- هر شش ستون (`id`, `embedding_model`, `embedding_dim`, `distance_metric`, `created_at`, `is_active`) در DB وجود دارند؛ همه `NOT NULL` با پیش‌فرض‌های `gen_random_uuid()`/`now()`/`false`.
- قید یکتای جزئی `uq_index_meta_active … WHERE is_active` در `pg_indexes` تأیید شد؛ تست جدید درج دومین رکورد فعال را رد می‌کند (`IntegrityError`)، چند رکورد غیرفعال مجاز است و درج `NULL` به‌صورت آگاهانه رد می‌شود.
- `alembic_version` = `0002_index_meta_registry` (head).
- `make test-db` (معادل): `24 passed`.

## گزینه‌های ردشده

- به‌تعویق‌انداختن کامل تا فاز ۴: بدهی مستند R-087 در خط پایه و ریسک فراموشی.
- ساخت با `create_all` یا auto-migration: ممنوع طبق R-057.

## پیامدها

- تغییر schema فقط از طریق سرویس یک‌بارمصرف `migrate` قابل اجراست (R-084).
- در فازهای بعدی، رکورد فعال این جدول باید با `EMBEDDING_MODEL`/`EMBEDDING_DIM` (R-088) هم‌خوان باشد و تغییر مدل فقط با مسیر reindex مستند R-089 انجام شود.
- `distance_metric` در این جدول ثبت می‌شود؛ پارامترهای HNSW (R-090) از تنظیمات می‌آیند و در docstring مهاجرت/مستندات ثبت می‌شوند.
- هیچ معکوس‌پذیری داده‌ای وجود ندارد؛ `downgrade` جدول را حذف می‌کند.


## اجرای الزامات R-087 در فازهای ۴/۵ — 2026-11-12

این بخش تصمیم مالک ADR را تغییر نمی‌دهد؛ implementation follow-up برای اجرای همان قرارداد است:

- سرویس indexing قبل از هر replacement دقیقاً یک رکورد فعال را می‌خواند و با `FOR SHARE` قفل می‌کند؛ مدل provider، dimension بردارها، metric cosine و پوشش parent/child را پیش از حذف chunkهای قبلی اعتبارسنجی می‌کند.
- سرویس query نیز باید دقیقاً یک رکورد فعال بخواند؛ نبود/ابهام رکورد، dimension نامتطابق یا metric ناسازگار → fail-closed.
- بُعد فعلی schema و HNSW برابر 1024 و cosine است؛ dimension/metric دیگر بدون migration و reindex plan قابل فعال‌سازی نیست.
- **هیچ active index row به‌صورت خودکار seed نشده است.** در محیط عملیاتی، تا زمان provision صریح یک model record که با provider واقعی و schema/index فیزیکی سازگار و آزمایش شده باشد، indexing/retrieval عمداً با 503 متوقف می‌شود.
- تست‌های PostgreSQL synthetic فقط داخل fixture، رکورد موقت `test / 1024 / cosine` می‌سازند و پس از تست پاک می‌کنند؛ این رکورد نمونه مجوز فعال‌سازی محیط توسعه/production نیست.

Evidence candidate: branch `feat/active-index-meta-enforcement`, HEAD `259b13916a4579d2e947da27209e504a71f94ea4`, GitHub Actions Run [43129891289](https://github.com/mahakas/darsyar/actions/runs/43129891289): Backend 492 passed / 21 skipped / 1 warning; Ruff, Frontend and Linux SIGTERM PASS. Merge is pending at the time of this note.
