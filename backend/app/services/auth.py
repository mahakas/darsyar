"""دامنهٔ احراز هویت: چرخهٔ OTP، صدور/چرخش refresh و ابطال زنجیره (R-100 تا R-107)."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.phone import PHONE_NORMALIZATION_ERROR, normalize_e164
from app.core.security import (
    create_token,
    gen_otp_code,
    gen_refresh_token,
    otp_matches,
    resolve_pepper_for,
    token_digest,
)
from app.models.refresh_token import RefreshToken
from app.repositories import otp_challenges as otp_repo
from app.repositories import refresh_tokens as refresh_repo
from app.repositories import users as users_repo
from app.services.sms import SmsProvider

INVALID_CREDENTIALS = AppError("invalid_otp", 401, "کد واردشده نامعتبر یا منقضی است.")
CHALLENGE_LOCKED = AppError("otp_attempts_exceeded", 429, "تلاش‌های زیاد؛ کد جدید درخواست کنید.")
RATE_LIMITED = AppError("rate_limited", 429, "تعداد درخواست‌ها از سقف مجاز گذشت.")
REFRESH_INVALID = AppError("invalid_refresh_token", 401, "نشست نامعتبر یا منقضی است.")
logger = get_logger("app.services.auth")


class AuthService:
    """orchestration دامنهٔ OTP و نشست."""

    def __init__(self, session: AsyncSession, sms: SmsProvider) -> None:
        self._session = session
        self._sms = sms
        self._settings = get_settings()

    def _now(self) -> datetime:
        return datetime.now(UTC)

    async def request_otp(self, raw_phone: str) -> None:
        try:
            phone = normalize_e164(raw_phone)
        except ValueError:
            raise AppError(PHONE_NORMALIZATION_ERROR, 422, "شمارهٔ موبایل معتبر نیست.") from None
        code = gen_otp_code(self._settings.otp_code_length)
        pepper = self._settings.otp_pepper.get_secret_value() if self._settings.otp_pepper else ""
        from app.core.security import otp_digest

        await otp_repo.create(
            self._session,
            phone=phone,
            code_digest=otp_digest(code, pepper),
            pepper_id=self._settings.otp_pepper_id,
            expires_at=self._now() + timedelta(seconds=self._settings.otp_expire_seconds),
        )
        await self._session.flush()
        try:
            await self._sms.send_otp(phone, code)
        except Exception:
            await self._session.rollback()
            raise AppError("sms_send_failed", 503, "ارسال پیامک در حال حاضر ممکن نیست؛ دوباره تلاش کنید.") from None

    async def verify_otp(self, raw_phone: str, code: str) -> tuple[str, str, str, int, object]:
        """اعتبارسنجی چالش، مصرف یک‌باره و صدور توکن‌ها. tuple: (access_token, refresh_token, jti, expires_in, user)"""
        try:
            phone = normalize_e164(raw_phone)
        except ValueError:
            raise AppError(PHONE_NORMALIZATION_ERROR, 422, "شمارهٔ موبایل معتبر نیست.") from None
        now = self._now()
        challenge = await otp_repo.get_latest_active(self._session, phone, now)
        if challenge is None:
            raise INVALID_CREDENTIALS
        if challenge.attempts >= self._settings.otp_max_attempts:
            raise CHALLENGE_LOCKED
        try:
            pepper = resolve_pepper_for(challenge.pepper_id)
        except ValueError:
            raise INVALID_CREDENTIALS from None
        if not otp_matches(code, challenge.code_digest, pepper):
            challenge.attempts += 1
            await self._session.flush()
            raise INVALID_CREDENTIALS
        challenge.consumed_at = now
        user = await users_repo.get_by_phone(self._session, phone)
        if user is None:
            user = await users_repo.create(self._session, phone=phone, role="user")
        await self._session.flush()
        access_token, refresh_token, jti, expires_in = await self._issue_tokens(user.id, user.role)
        return access_token, refresh_token, jti, expires_in, user

    async def _issue_tokens(self, user_id: uuid.UUID, role: str) -> tuple[str, str, str, int]:
        jti = secrets.token_urlsafe(16)
        refresh_raw = gen_refresh_token()
        family_id = uuid.uuid4()
        lifetime = timedelta(days=self._settings.refresh_token_expire_days)
        await refresh_repo.create(
            self._session,
            user_id=user_id,
            jti=jti,
            token_hash=token_digest(refresh_raw),
            family_id=family_id,
            expires_at=self._now() + lifetime,
        )
        await self._session.flush()
        access = create_token(
            str(user_id),
            role,
            "access",
            jti,
            lifetime=timedelta(minutes=self._settings.access_token_expire_minutes),
        )
        return access, refresh_raw, jti, self._settings.access_token_expire_minutes * 60

    async def rotate_refresh(self, raw_token: str) -> tuple[str, str, str, int, object]:
        """چرخش refresh با تشخیص reuse، grace و ابطال زنجیره (R-107).

        چرخش با compare-and-swap اتمیک انجام می‌شود تا دو درخواست هم‌زمان
        فقط یک عضو فعال جدید در خانواده بسازند.
        """
        token_hash = token_digest(raw_token)
        now = self._now()
        stored = await refresh_repo.get_by_hash(self._session, token_hash)
        if stored is None:
            raise REFRESH_INVALID
        if stored.expires_at <= now:
            raise REFRESH_INVALID
        if stored.revoked_at is None:
            rotated = await self._try_rotate(stored, now)
            if rotated is not None:
                return rotated
            # CAS از دست رفت: درخواست هم‌زمان دیگر همین عضو را چرخاند؛ ادامه در مسیر grace.
            stored = await refresh_repo.get_by_hash(self._session, token_hash)
            if stored is None or stored.expires_at <= now:
                raise REFRESH_INVALID
        # توکن باطل است: یا reuse واقعی است یا درخواست هم‌زمان در پنجرهٔ grace.
        # سیاست ADR-046: بازپخش والدِ باطل‌شده در پنجرهٔ grace هرگز عضو فعال را
        # نمی‌چرخاند و فرزند جدیدی نمی‌سازد؛ فقط 409 بدون Set-Cookie برمی‌گرداند.
        revoked_at = stored.revoked_at
        if revoked_at is None:
            raise REFRESH_INVALID
        grace_until = revoked_at + timedelta(seconds=self._settings.refresh_grace_seconds)
        if now <= grace_until:
            raise AppError(
                "refresh_conflict_retry",
                409,
                "نشست در حال چرخش است؛ کمی بعد دوباره تلاش کنید.",
            )
        await refresh_repo.revoke_family(self._session, stored.family_id, now)
        await self._session.flush()
        logger.warning("refresh_reuse_detected", extra={"user_id": str(stored.user_id), "family_id": str(stored.family_id)})
        raise AppError("refresh_reuse_detected", 401, "نشست باطل شد؛ دوباره وارد شوید.")

    async def _try_rotate(self, token: RefreshToken, now: datetime) -> tuple[str, str, str, int, object] | None:
        new_jti = secrets.token_urlsafe(16)
        refresh_raw = gen_refresh_token()
        claimed = await refresh_repo.try_mark_revoked(self._session, token.id, now, new_jti)
        if not claimed:
            return None
        await refresh_repo.create(
            self._session,
            user_id=token.user_id,
            jti=new_jti,
            token_hash=token_digest(refresh_raw),
            family_id=token.family_id,
            expires_at=now + timedelta(days=self._settings.refresh_token_expire_days),
        )
        await self._session.flush()
        user = await users_repo.get_by_id(self._session, token.user_id)
        if user is None:
            raise REFRESH_INVALID
        access = create_token(
            str(user.id),
            user.role,
            "access",
            new_jti,
            lifetime=timedelta(minutes=self._settings.access_token_expire_minutes),
        )
        return access, refresh_raw, new_jti, self._settings.access_token_expire_minutes * 60, user

    async def logout_family(self, raw_token: str) -> None:
        stored = await refresh_repo.get_by_hash(self._session, token_digest(raw_token))
        if stored is not None:
            await refresh_repo.revoke_family(self._session, stored.family_id, self._now())
            await self._session.flush()
