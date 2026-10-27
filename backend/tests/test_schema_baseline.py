"""تست‌های پایهٔ schema روی PostgreSQL واقعی؛ فقط در `make test-db` (DARSYAR_TEST_DB=1) اجرا می‌شوند."""

import os

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.config import get_settings
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)


def _fresh_engine() -> AsyncEngine:
    """engine مستقل بدون pool برای هر تست؛ از اتصال‌های بین event loopها جلوگیری می‌کند."""
    return create_async_engine(get_settings().database_url, poolclass=NullPool)


async def _fetch_one(statement: str) -> str | None:
    engine = _fresh_engine()
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text(statement))
            row = result.first()
        return str(row[0]) if row else None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_schema_baseline_alembic_head_applied() -> None:
    alembic_config = Config("alembic.ini")
    expected_heads = set(ScriptDirectory.from_config(alembic_config).get_heads())
    applied = await _fetch_one("SELECT version_num FROM alembic_version")
    assert applied is not None
    assert {applied} == expected_heads


@pytest.mark.asyncio
async def test_schema_baseline_extensions_present() -> None:
    vector = await _fetch_one("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    trgm = await _fetch_one("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
    assert vector == "1"
    assert trgm == "1"


@pytest.mark.asyncio
async def test_schema_baseline_index_meta_table_present() -> None:
    table = await _fetch_one(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'index_meta'"
    )
    assert table == "1"
    active_count = await _fetch_one("SELECT count(*) FROM index_meta WHERE is_active")
    assert active_count == "0"


@pytest.mark.asyncio
async def test_schema_baseline_only_one_active_row_allowed() -> None:
    """درج دو رکورد فعال رد شود؛ رکوردهای غیرفعال متعدد مجاز باشند؛ NULL آگاهانه ممنوع است."""
    engine = _fresh_engine()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text(
                        "INSERT INTO index_meta (embedding_model, embedding_dim, distance_metric, is_active) "
                        "VALUES ('m1', 1024, 'cosine', true)"
                    )
                )
                with pytest.raises(IntegrityError) as excinfo:
                    async with connection.begin_nested():
                        await connection.execute(
                            text(
                                "INSERT INTO index_meta (embedding_model, embedding_dim, distance_metric, is_active) "
                                "VALUES ('m2', 1024, 'cosine', true)"
                            )
                        )
                assert "uq_index_meta_active" in str(excinfo.value)

                with pytest.raises(IntegrityError):
                    async with connection.begin_nested():
                        await connection.execute(
                            text(
                                "INSERT INTO index_meta (embedding_model, embedding_dim, distance_metric, is_active) "
                                "VALUES ('m3', 1024, 'cosine', NULL)"
                            )
                        )

                for model in ("i1", "i2"):
                    await connection.execute(
                        text(
                            "INSERT INTO index_meta (embedding_model, embedding_dim, distance_metric, is_active) "
                            "VALUES (:model, 1024, 'cosine', false)"
                        ),
                        {"model": model},
                    )

                active_count = (await connection.execute(text("SELECT count(*) FROM index_meta WHERE is_active"))).scalar_one()
                inactive_count = (await connection.execute(text("SELECT count(*) FROM index_meta WHERE NOT is_active"))).scalar_one()
                assert active_count == 1
                assert inactive_count == 2
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
