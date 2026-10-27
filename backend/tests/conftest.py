"""تنظیم مشترک pytest؛ تست DB باید با PostgreSQL و Alembic در make test-db اجرا شود.

فاز صفر هیچ schemaای با metadata.create_all نمی‌سازد. Fixtureهای تراکنش DB با اولین تست‌های دیتابیسیِ فاز مربوطه اضافه می‌شوند.
"""
