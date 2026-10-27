# سیاست استک و نسخه‌بندی (مطابق AGENTS v4.0)

نسخه‌های زیر خط پایهٔ هدف‌اند، نه ادعای موفقیت build روی همهٔ سیستم‌ها. قفل نسخه تنها پس از حل dependencies و اجرای CI معتبر است.

| فناوری | خط پایهٔ هدف | شرط پذیرش |
|---|---|---|
| Python | 3.13.x | wheel سازگار torch/FlagEmbedding/transformers/tiktoken؛ در غیر این صورت 3.12 با ADR |
| FastAPI | بازهٔ سازگار با فاز صفر و Pydantic v2 | تست نصب/route و قفل uv |
| SQLAlchemy | 2.x async | فقط `Mapped[]`, `mapped_column()` و session جدا برای هر task |
| PostgreSQL | 18.x | نسخهٔ پایدار، نه PG19 RC در production |
| pgvector | 0.8.x سازگار با PG18 | migration و query plan آزموده شود |
| Redis server | **7.4.12** (`redis:7.4.12-bookworm`؛ digest `sha256:bd28fff4…`) — تصمیم تأییدشدهٔ مالک در ADR-044 | Redis هرگز منبع حقیقت مالی نیست |
| redis-py | 5.3.1 (قفل در uv.lock؛ در رنج رسمی 7.4) | client version با server version یکی فرض نشود |
| React | 19.x | تطبیق React DOM و کتابخانه‌های test |
| Vite | 8.x | Node 24 LTS و plugin سازگار |
| Node | 24 LTS | یکسان در CI و dev |
| Python lock | `backend/uv.lock` | با `uv lock`; CI با `uv sync --locked` |
| JS lock | `frontend/package-lock.json` | با npm؛ CI با `npm ci` |

## قواعد
- در Docker production image با tag دقیق و ترجیحاً digest pin شود؛ `latest` ممنوع.
- نسخهٔ major نیازمند ADR، تست کامل و ثبت پیامدهای مهاجرت است.
- patch امنیتی در PR جدا با suite اجراشده قابل ارتقاست.
- پکیج ML فقط در فاز مربوطه و با دلیل/مجوز اضافه شود؛ فاز صفر نباید مدل دانلود کند.
- نبود registry در هنگام تولید ZIP دلیل موجه برای نبود lockfile است؛ lockfile ساختگی ممنوع است.
