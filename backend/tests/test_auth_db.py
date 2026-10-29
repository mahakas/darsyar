"""تست‌های یکپارچهٔ احراز هویت روی PostgreSQL واقعی (R-212/R-221)."""

import os
from datetime import timedelta

import pytest
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import token_digest
from app.models.otp_challenge import OtpChallenge
from app.models.user import User
from app.repositories import refresh_tokens as refresh_repo
from app.repositories import users as users_repo
from app.services.auth import AuthService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

TEST_ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
TEST_SESSION_FACTORY = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


class RecordingSms:
    def __init__(self) -> None:
        self.sent: dict[str, str] = {}

    async def send_otp(self, phone: str, code: str) -> None:
        self.sent[phone] = code


@pytest.fixture()
async def auth_ctx():
    session = TEST_SESSION_FACTORY()
    sms = RecordingSms()
    service = AuthService(session, sms)
    try:
        yield service, session, sms
    finally:
        await session.rollback()
        await session.close()


@pytest.mark.asyncio
async def test_full_otp_flow_auto_registers_and_never_stores_plaintext(auth_ctx) -> None:
    service, session, sms = auth_ctx
    await service.request_otp("09121234567")
    code = sms.sent["+989121234567"]
    access, refresh, jti, expires_in, user = await service.verify_otp("09121234567", code)
    assert expires_in == 900
    assert access and refresh and jti
    assert user.role == "user"
    challenges = (await session.execute(select(OtpChallenge))).scalars().all()
    assert len(challenges) == 1
    assert challenges[0].code_digest != code
    assert code not in challenges[0].code_digest
    assert challenges[0].consumed_at is not None
    assert challenges[0].attempts == 0
    db_user = await users_repo.get_by_phone(session, "+989121234567")
    assert db_user is not None
    assert db_user.id == user.id


@pytest.mark.asyncio
async def test_wrong_code_increments_attempts_and_locks(auth_ctx) -> None:
    service, session, sms = auth_ctx
    await service.request_otp("09121234567")
    code = sms.sent["+989121234567"]
    settings = get_settings()
    for _ in range(settings.otp_max_attempts):
        with pytest.raises(AppError):
            await service.verify_otp("09121234567", "000000")
    # بعد از سقف تلاش، حتی کد درست هم رد می‌شود.
    with pytest.raises(AppError) as excinfo:
        await service.verify_otp("09121234567", code)
    assert excinfo.value.code == "otp_attempts_exceeded"
    challenges = (await session.execute(select(OtpChallenge))).scalars().all()
    assert challenges[0].attempts == settings.otp_max_attempts


@pytest.mark.asyncio
async def test_consumed_challenge_rejected(auth_ctx) -> None:
    service, session, sms = auth_ctx
    await service.request_otp("09121234567")
    code = sms.sent["+989121234567"]
    await service.verify_otp("09121234567", code)
    with pytest.raises(AppError) as excinfo:
        await service.verify_otp("09121234567", code)
    assert excinfo.value.code == "invalid_otp"


@pytest.mark.asyncio
async def test_refresh_garbage_token_rejected(auth_ctx) -> None:
    service, session, sms = auth_ctx
    with pytest.raises(AppError) as excinfo:
        await service.rotate_refresh("not-a-real-token")
    assert excinfo.value.code == "invalid_refresh_token"


@pytest.mark.asyncio
async def test_concurrent_rotation_cas_keeps_single_active(auth_ctx) -> None:
    """رقابت دو درخواست هم‌زمان: حداکثر یک چرخش موفق؛ بازنده 409 بدون چرخش (ADR-046)."""
    service, session, sms = auth_ctx
    await service.request_otp("09121234567")
    _, refresh_a, _, _, _ = await service.verify_otp("09121234567", sms.sent["+989121234567"])

    stored = await refresh_repo.get_by_hash(session, token_digest(refresh_a))
    # برندهٔ شبیه‌سازی‌شده ابتدا CAS را می‌برد و عضو فعال جدید می‌سازد.
    now = service._now()
    claimed = await refresh_repo.try_mark_revoked(session, stored.id, now, "winner-jti")
    assert claimed is True

    await refresh_repo.create(
        session,
        user_id=stored.user_id,
        jti="winner-jti",
        token_hash="winner-token-hash",
        family_id=stored.family_id,
        expires_at=now + timedelta(days=7),
    )
    await session.flush()

    # درخواست دوم با توکن قدیمی (در پنجرهٔ grace): 409 بدون چرخش و بدون فرزند جدید.
    with pytest.raises(AppError) as excinfo:
        await service.rotate_refresh(refresh_a)
    assert excinfo.value.code == "refresh_conflict_retry"
    assert excinfo.value.http_status == 409

    family_tokens = await refresh_repo.get_all_by_family(session, stored.family_id)
    active_members = [t for t in family_tokens if t.revoked_at is None]
    assert len(active_members) == 1
    assert active_members[0].token_hash == "winner-token-hash"


@pytest.mark.asyncio
async def test_grace_replay_conflict_does_not_rotate_or_create_child(auth_ctx) -> None:
    """بازپخش والد در پنجرهٔ grace: بدون چرخش، بدون فرزند، خانواده دست‌نخورده."""
    service, session, sms = auth_ctx
    await service.request_otp("09121234567")
    _, refresh_a, _, _, _ = await service.verify_otp("09121234567", sms.sent["+989121234567"])

    _, refresh_b, _, _, _ = await service.rotate_refresh(refresh_a)
    active_before = await refresh_repo.get_active_by_family(session, (await refresh_repo.get_by_hash(session, token_digest(refresh_a))).family_id)

    for _ in range(3):
        with pytest.raises(AppError) as excinfo:
            await service.rotate_refresh(refresh_a)
        assert excinfo.value.code == "refresh_conflict_retry"

    family = (await refresh_repo.get_by_hash(session, token_digest(refresh_a))).family_id
    active_after = await refresh_repo.get_active_by_family(session, family)
    assert active_after is not None
    assert active_after.id == active_before.id
    assert active_after.token_hash == token_digest(refresh_b)
    family_tokens = await refresh_repo.get_all_by_family(session, family)
    active_members = [t for t in family_tokens if t.revoked_at is None]
    assert len(active_members) == 1


@pytest.mark.asyncio
async def test_expired_challenge_rejected(auth_ctx) -> None:
    service, session, sms = auth_ctx
    await service.request_otp("09121234567")
    challenge = (await session.execute(select(OtpChallenge))).scalars().one()
    challenge.expires_at = service._now() - timedelta(seconds=10)
    await session.flush()
    with pytest.raises(AppError):
        await service.verify_otp("09121234567", sms.sent["+989121234567"])


@pytest.mark.asyncio
async def test_multi_user_isolation(auth_ctx) -> None:
    service, session, sms = auth_ctx
    phone_a = "+989121234567"
    phone_b = "+989129876543"
    await service.request_otp("09121234567")
    await service.request_otp("09129876543")
    code_a = sms.sent[phone_a]
    code_b = sms.sent[phone_b]
    # کد کاربر A نباید برای کاربر B کار کند.
    with pytest.raises(AppError):
        await service.verify_otp("09129876543", code_a)
    await service.verify_otp("09121234567", code_a)
    await service.verify_otp("09129876543", code_b)
    # فقط دو شمارهٔ مرتبط؛ مستقل از دادهٔ باقی‌مانده از تست‌های دیگر.
    users = (
        await session.execute(select(User).where(User.phone.in_([phone_a, phone_b])).order_by(User.phone))
    ).scalars().all()
    assert len(users) == 2
    assert {u.phone for u in users} == {phone_a, phone_b}
    assert users[0].id != users[1].id


@pytest.mark.asyncio
async def test_refresh_rotation_reuse_detection_and_grace(auth_ctx) -> None:
    service, session, sms = auth_ctx
    await service.request_otp("09121234567")
    _, refresh_a, _, _, _ = await service.verify_otp("09121234567", sms.sent["+989121234567"])

    access2, refresh_b, _, _, _ = await service.rotate_refresh(refresh_a)
    assert refresh_b != refresh_a

    # بازپخش والد در پنجرهٔ grace → 409، بدون چرخش (سیاست ADR-046).
    with pytest.raises(AppError) as excinfo:
        await service.rotate_refresh(refresh_a)
    assert excinfo.value.code == "refresh_conflict_retry"

    # شبیه‌سازی عبور از grace با قدیمی‌کردن revoked_at والد.
    stored_a = await refresh_repo.get_by_hash(session, token_digest(refresh_a))
    stored_a.revoked_at = service._now() - timedelta(seconds=get_settings().refresh_grace_seconds + 1)
    await session.flush()

    with pytest.raises(AppError) as excinfo:
        await service.rotate_refresh(refresh_a)
    assert excinfo.value.code == "refresh_reuse_detected"
    family_tokens = await refresh_repo.get_all_by_family(session, stored_a.family_id)
    assert all(t.revoked_at is not None for t in family_tokens)


@pytest.mark.asyncio
async def test_logout_revokes_family(auth_ctx) -> None:
    service, session, sms = auth_ctx
    await service.request_otp("09121234567")
    _, refresh, _, _, _ = await service.verify_otp("09121234567", sms.sent["+989121234567"])
    await service.logout_family(refresh)
    stored = await refresh_repo.get_by_hash(session, token_digest(refresh))
    assert stored is not None and stored.revoked_at is not None
    with pytest.raises(AppError):
        await service.rotate_refresh(refresh)


@pytest.mark.asyncio
async def test_admin_seed_requires_explicit_action_and_audits(auth_ctx) -> None:
    from app.scripts.seed_admin import seed_admin

    service, session, sms = auth_ctx
    await seed_admin(session, phone="09121112233", name="Admin", email="admin@example.com", with_password=False)
    admin = await users_repo.get_by_phone(session, "+989121112233")
    assert admin is not None
    assert admin.role == "admin"
    from app.models.admin_audit_log import AdminAuditLog

    logs = (await session.execute(select(AdminAuditLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].action == "seed_admin"
    assert logs[0].reason.startswith("initial admin bootstrap")
    assert logs[0].after["role"] == "admin"
