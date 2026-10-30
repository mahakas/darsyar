"""تطبیق read-only ledger↔projection و هشدار پایدار (Slice C-1)."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.credit_account import CreditAccount
from app.repositories import credit_ledger as ledger_repo
from app.repositories import reconciliation_alerts as alerts_repo

ALERT_TYPE_LEDGER_PROJECTION = "ledger_projection_mismatch"
SEVERITY_WARNING = "warning"

MAX_SERIALIZATION_RETRIES = 2


@dataclass(frozen=True, slots=True)
class ReconcileSummary:
    scanned: int = 0
    alerts_upserted: int = 0
    alerts_resolved: int = 0
    mismatches: int = 0
    next_cursor: uuid.UUID | None = None
    scanned_user_ids: tuple[uuid.UUID, ...] = ()


def _active_identity_hash(user_id: uuid.UUID) -> str:
    """هویت پایدار هشدار فعال (کاربر+نوع)؛ diff در هویت نیست."""
    canonical = f"{user_id}:{ALERT_TYPE_LEDGER_PROJECTION}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ReconcileService:
    """فقط‌خواندنی مالی؛ هیچ ledger/موجودی‌ای اصلاح نمی‌شود."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._threshold = self._settings.credit_reconcile_alert_threshold

    def _now(self) -> datetime:
        return datetime.now(UTC)

    async def _ensure_snapshot_isolation(self) -> None:
        if not self._session.in_transaction():
            await self._session.begin()
        await self._session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))

    async def reconcile_credits(
        self,
        *,
        user_id: uuid.UUID | None = None,
        batch_limit: int = 100,
        cursor_user_id: uuid.UUID | None = None,
    ) -> ReconcileSummary:
        if batch_limit < 1 or batch_limit > 1000:
            from app.core.errors import AppError

            raise AppError("invalid_batch_limit", 422, "سقف دسته نامعتبر است.")

        for attempt in range(MAX_SERIALIZATION_RETRIES + 1):
            try:
                return await self._reconcile_once(
                    user_id=user_id, batch_limit=batch_limit, cursor_user_id=cursor_user_id
                )
            except (OperationalError, DBAPIError) as exc:
                sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", "")
                is_serialization = sqlstate in ("40001", "40P01")
                if not is_serialization or attempt >= MAX_SERIALIZATION_RETRIES:
                    raise
                await self._session.rollback()
        raise AssertionError("unreachable")

    async def _reconcile_once(
        self,
        *,
        user_id: uuid.UUID | None,
        batch_limit: int,
        cursor_user_id: uuid.UUID | None,
    ) -> ReconcileSummary:
        await self._ensure_snapshot_isolation()

        if user_id is not None:
            targets: list[tuple[uuid.UUID, uuid.UUID]] = []
            account = (
                await self._session.execute(select(CreditAccount).where(CreditAccount.user_id == user_id))
            ).scalar_one_or_none()
            if account is not None:
                targets.append((account.id, account.user_id))
            next_cursor: uuid.UUID | None = None
        else:
            statement = (
                select(CreditAccount.id, CreditAccount.user_id)
                .order_by(CreditAccount.id.asc())
                .limit(batch_limit)
            )
            if cursor_user_id is not None:
                statement = statement.where(CreditAccount.id > cursor_user_id)
            rows = (await self._session.execute(statement)).all()
            targets = [(row[0], row[1]) for row in rows]
            next_cursor = targets[-1][0] if targets else None

        summary = ReconcileSummary(next_cursor=next_cursor)
        for _, target_user_id in targets:
            result = await self._reconcile_user(target_user_id)
            summary = ReconcileSummary(
                scanned=summary.scanned + 1,
                alerts_upserted=summary.alerts_upserted + result["upserted"],
                alerts_resolved=summary.alerts_resolved + result["resolved"],
                mismatches=summary.mismatches + result["mismatch"],
                next_cursor=summary.next_cursor,
                scanned_user_ids=summary.scanned_user_ids + (target_user_id,),
            )
        return summary

    async def _reconcile_user(self, user_id: uuid.UUID) -> dict[str, int]:
        account = (
            await self._session.execute(select(CreditAccount).where(CreditAccount.user_id == user_id))
        ).scalar_one_or_none()
        if account is None:
            return {"upserted": 0, "resolved": 0, "mismatch": 0}
        ledger_sum = await ledger_repo.sum_balance_affecting(self._session, user_id)
        diff = account.available_balance - ledger_sum

        if abs(diff) > self._threshold:
            context: dict[str, object] = {
                "available_balance": account.available_balance,
                "ledger_sum": ledger_sum,
                "diff": diff,
            }
            await alerts_repo.upsert_active(
                self._session,
                user_id=user_id,
                alert_type=ALERT_TYPE_LEDGER_PROJECTION,
                severity=SEVERITY_WARNING,
                context=context,
                alert_hash=_active_identity_hash(user_id),
                now=self._now(),
            )
            return {"upserted": 1, "resolved": 0, "mismatch": 1}

        resolved = await alerts_repo.resolve_active(
            self._session,
            user_id=user_id,
            alert_type=ALERT_TYPE_LEDGER_PROJECTION,
            now=self._now(),
        )
        return {"upserted": 0, "resolved": resolved, "mismatch": 0}
