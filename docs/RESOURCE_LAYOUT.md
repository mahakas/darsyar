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
هر سند حداقل این کلیدها را دارد: `path`, `source_origin`, `subject`, `grade`, `edition_year`, `title`, `publisher`, `license_note`. manifest با schema اعتبارسنجی می‌شود. `edition_year` برای همان سند اجباری است و مقدار پیش‌فرض سراسری ندارد. مسیرهای `pre_university` و `grade_pre` نگاشت خودکار ندارند و تا بررسی انسانی، تأیید صریح مالک و ثبت `grade` canonical در manifest در `needs_review` می‌مانند. مسیر استاندارد یا manifest صریح قابل قبول است؛ metadata مبهم باعث `needs_review` یا `failed` می‌شود و ingestion حق حدس ندارد.

## چرخهٔ ingestion
`pending` → `processing` → `ready | failed | needs_review`. کلید idempotency بر پایهٔ checksum فایل، سال چاپ، subject و grade است. chunkهای پیشین در replacement کنترل‌شده جایگزین می‌شوند.

## مجوز
هر منبع در `docs/licenses/` یا manifest باید `license_note` و شواهد قابل بررسی داشته باشد. مبنای دریافت و اجازهٔ ذخیره‌سازی، OCR/استخراج، embedding/نمایه‌سازی، نمایش/توزیع و نقل‌قول/اقتباس باید برای هر منبع، جداگانه و در صورت کاربرد بررسی و ثبت شود. منبع با مجوز ناقص یا نامشخص در `needs_review` می‌ماند؛ ingestion تولیدی فقط پس از تأیید مستند همان عملیات مجاز است (ADR-024).
