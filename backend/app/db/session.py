"""ساخت engine و session async پایگاه داده."""

from collections.abc import AsyncIterator

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    connect_args={"timeout": settings.database_connect_timeout_seconds},
)
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """یک AsyncSession مستقل برای هر درخواست فراهم می‌کند."""
    async with SessionFactory() as session:
        yield session


async def ping_database() -> None:
    """اتصال پایگاه داده را با query سبک بررسی می‌کند."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def verify_schema_revision() -> None:
    """نسخهٔ DB را با head فعلی تطبیق می‌دهد؛ هرگز migration اجرا نمی‌کند."""
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    expected_heads = set(ScriptDirectory.from_config(alembic_config).get_heads())
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT version_num FROM alembic_version"))
        applied = {str(row[0]) for row in result.fetchall()}
    if not expected_heads or applied != expected_heads:
        raise RuntimeError("schema_out_of_date")
