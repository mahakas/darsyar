# چیدمان منابع آموزشی

## مسیر استاندارد

```text
resources/
  math/grade1/<book-file>.pdf
  science/grade7/<book-file>.pdf
  persian/grade3/<book-file>.pdf
  manifest.yaml
```

این ZIP برای درس‌های مجاز پوشه‌های خالی و `.gitkeep` دارد تا مسیرها در Git باقی بمانند؛ هیچ کتابی داخل بسته نیست و وجود پوشه به معنی تأیید موجود بودن آن درس در پایه نیست.

## Manifest
هر سند حداقل این کلیدها را دارد: `path`, `subject`, `grade`, `edition_year`, `title`, `publisher`, `license_note`. manifest با schema اعتبارسنجی می‌شود. مسیر استاندارد یا manifest صریح قابل قبول است؛ metadata مبهم باعث `needs_review` یا `failed` می‌شود و ingestion حق حدس ندارد.

## چرخهٔ ingestion
`pending` → `processing` → `ready | failed | needs_review`. کلید idempotency بر پایهٔ checksum فایل، سال چاپ، subject و grade است. chunkهای پیشین در replacement کنترل‌شده جایگزین می‌شوند.

## مجوز
هر منبع در `docs/licenses/` یا manifest باید license note/شرایط پردازش داشته باشد. ورود منبع فاقد ثبت مجوز در production ممنوع است. شرایط دریافت، OCR، embedding، ذخیره و نمایش باید برای هر منبع بررسی شوند.
