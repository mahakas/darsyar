"""طھط³طھâ€Œظ‡ط§غŒ غŒع©ظ¾ط§ط±ع†ظ‡ظ” ع¯ط±ط§ظ†طھ ط±ط§غŒع¯ط§ظ† (ADR-048) ط±ظˆغŒ PostgreSQL ظˆط§ظ‚ط¹غŒ."""

import asyncio
import os
import uuid

import pytest
from app.core.config import get_settings
from app.core.phone import normalize_e164
from app.repositories import credit_accounts as accounts_repo
from app.repositories import credit_ledger as ledger_repo
from app.repositories import users as users_repo
from app.services.auth import AuthService
from app.services.free_grant import FREE_GRANT_KIND, create_user_with_free_grant, grant_if_new
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

TEST_ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
TEST_SESSION_FACTORY = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


def _new_phone() -> str:
    return f"+989{str(uuid.uuid4().int)[:9]}"


class RecordingSms:
    def __init__(self) -> None:
        self.sent: dict[str, str] = {}

    async def send_otp(self, phone: str, code: str) -> None:
        self.sent[phone] = code


async def _count_ledger(session, user_id: uuid.UUID, kind: str) -> int:
    result = await session.execute(
        text("SELECT count(*) FROM credit_ledger WHERE user_id = :u AND kind = :k"),
        {"u": str(user_id), "k": kind},
    )
    return int(result.scalar_one())


async def _balance(session, user_id: uuid.UUID) -> int | None:
    account = await accounts_repo.get_for_update(session, user_id)
    return account.available_balance


@pytest.mark.asyncio
async def _cleanup_otp_user(phone: str, user_id: uuid.UUID | None) -> None:
    """پاک‌سازی چالش‌های OTP همین تست.

    حذف فیزیکی کاربر ممکن نیست (trigger تغییرناپذیری ledger، حذف cascade رکوردهای
    مالی را برای حفظ تاریخچه رد می‌کند)؛ فقط چالش‌ها بدون FK رها می‌شوند و
    دیگر تست‌های auth (که چالش‌ها را بدون فیلتر می‌شمارند) آلوده نمی‌شوند.
    """
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("DELETE FROM otp_challenges WHERE phone = :p"), {"p": normalize_e164(phone)})
        await session.commit()


@pytest.mark.asyncio
async def test_new_user_via_real_otp_lifecycle_gets_single_free_grant() -> None:
    phone = "0912" + str(uuid.uuid4().int)[:7]
    user_id: uuid.UUID | None = None
    try:
        async with TEST_SESSION_FACTORY() as session:
            sms = RecordingSms()
            service = AuthService(session, sms)
            await service.request_otp(phone)
            code = sms.sent[normalize_e164(phone)]
            _, _, _, _, user = await service.verify_otp(phone, code)
            await session.commit()
            user_id = user.id
        async with TEST_SESSION_FACTORY() as session:
            assert await _count_ledger(session, user_id, FREE_GRANT_KIND) == 1
            assert await _balance(session, user_id) == 5
            amount = (
                await session.execute(text("SELECT amount FROM credit_ledger WHERE user_id = :u AND kind = :k"), {"u": str(user_id), "k": FREE_GRANT_KIND})
            ).scalar_one()
            assert amount == 5
    finally:
        await _cleanup_otp_user(phone, user_id)


@pytest.mark.asyncio
async def test_existing_user_login_no_extra_grant() -> None:
    phone = "0912" + str(uuid.uuid4().int)[:7]
    user_id: uuid.UUID | None = None
    try:
        async with TEST_SESSION_FACTORY() as session:
            sms = RecordingSms()
            service = AuthService(session, sms)
            await service.request_otp(phone)
            await service.verify_otp(phone, sms.sent[normalize_e164(phone)])
            await session.commit()
        async with TEST_SESSION_FACTORY() as session:
            sms = RecordingSms()
            service = AuthService(session, sms)
            await service.request_otp(phone)
            _, _, _, _, user = await service.verify_otp(phone, sms.sent[normalize_e164(phone)])
            await session.commit()
            user_id = user.id
            assert await _count_ledger(session, user.id, FREE_GRANT_KIND) == 1
            assert await _balance(session, user.id) == 5
    finally:
        await _cleanup_otp_user(phone, user_id)


@pytest.mark.asyncio
async def test_duplicate_grant_via_service_no_balance_change() -> None:
    user_id = uuid.uuid4()
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=_new_phone(), role="user")
        await accounts_repo.create(session, user_id=user.id, available_balance=0)
        await session.commit()
        user_id = user.id
    async with TEST_SESSION_FACTORY() as session:
        await grant_if_new(user_id, session)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        await grant_if_new(user_id, session)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        assert await _count_ledger(session, user_id, FREE_GRANT_KIND) == 1
        assert await _balance(session, user_id) == 5


@pytest.mark.asyncio
async def test_database_level_partial_unique_index_rejects_duplicate() -> None:
    user_id = uuid.uuid4()
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=_new_phone(), role="user")
        await accounts_repo.create(session, user_id=user.id, available_balance=0)
        await ledger_repo.create(
            session, user_id=user.id, kind=FREE_GRANT_KIND, amount=5,
            idempotency_key=f"free-grant:{user.id}:once",
        )
        await session.commit()
        user_id = user.id
    async with TEST_SESSION_FACTORY() as session:
        with pytest.raises(sqlalchemy_exc.IntegrityError):
            await ledger_repo.create(
                session, user_id=user_id, kind=FREE_GRANT_KIND, amount=5,
                idempotency_key="forged-second-grant",
            )
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        assert await _count_ledger(session, user_id, FREE_GRANT_KIND) == 1


@pytest.mark.asyncio
async def test_atomic_rollback_leaves_no_partial_state() -> None:
    import app.services.free_grant as fg_module

    phone = _new_phone()
    original_create = fg_module.ledger_repo.create

    async def failing_ledger_create(*args, **kwargs):
        raise RuntimeError("forced-grant-failure")

    async with TEST_SESSION_FACTORY() as session:
        fg_module.ledger_repo.create = failing_ledger_create
        try:
            with pytest.raises(RuntimeError, match="forced-grant-failure"):
                await create_user_with_free_grant(session, phone=phone, role="user")
        finally:
            fg_module.ledger_repo.create = original_create
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.get_by_phone(session, phone)
        assert user is None
        rows = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id IN (SELECT id FROM users WHERE phone = :p)"), {"p": phone})
        assert rows.scalar_one() == 0


@pytest.mark.asyncio
async def test_concurrent_creation_single_user_single_grant() -> None:
    phone = _new_phone()

    async def attempt() -> str:
        async with TEST_SESSION_FACTORY() as session:
            try:
                user = await create_user_with_free_grant(session, phone=phone, role="user")
                await session.commit()
                return str(user.id)
            except sqlalchemy_exc.IntegrityError:
                await session.rollback()
                return "conflict"

    results = await asyncio.gather(attempt(), attempt(), attempt())
    ok_ids = [r for r in results if r != "conflict"]
    assert len(ok_ids) == 1
    user_id = uuid.UUID(ok_ids[0])
    async with TEST_SESSION_FACTORY() as session:
        users_count = (
            await session.execute(text("SELECT count(*) FROM users WHERE phone = :p"), {"p": phone})
        ).scalar_one()
        assert users_count == 1
        assert await _count_ledger(session, user_id, FREE_GRANT_KIND) == 1
        assert await _balance(session, user_id) == 5
