"""محیط Alembic با اتصال async؛ اجرای migration فقط صریح است.

Forward-only guard (R-241): `downgrade` به‌طور پیش‌فرض رد می‌شود تا schema/داده
برگشت‌ناپذیر دست‌نخورده بماند. مهاجرت برگشت‌پذیر همچنان نوشته می‌شود، ولی اجرای
downgrade فقط با متغیر صریح `DARSYAR_ALLOW_DOWNGRADE=1` (محیط/بازیابی کنترل‌شده)
مجاز است. این قیچ با تست‌های `*_downgrade_guard` (returncode≠0 و stderr حاوی
"forward-only") سازگار است.
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from app import models as app_models  # noqa: F401  # اطمینان از تکمیل metadata با همهٔ مدل‌ها
from app.core.config import get_settings
from app.db.base import Base
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

ALLOW_DOWNGRADE_ENV = "DARSYAR_ALLOW_DOWNGRADE"

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
target_metadata = Base.metadata


def _is_downgrade_invocation() -> bool:
    return "downgrade" in sys.argv


if _is_downgrade_invocation() and os.environ.get(ALLOW_DOWNGRADE_ENV) != "1":
    raise SystemExit("forward-only: downgrade blocked unless DARSYAR_ALLOW_DOWNGRADE=1")


def run_migrations_offline() -> None:
    """migration را به SQL متنی تبدیل می‌کند."""
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """migrationها را در اتصال فعال اجرا می‌کند."""
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """engine async را برای اجرای migration ایجاد و آزاد می‌کند."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
