"""دسترسی دادهٔ لاگ حسابرسی ادمین (append-only)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit_log import AdminAuditLog


async def create(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    reason: str,
    actor_user_id: uuid.UUID | None = None,
    entity_id: str | None = None,
    before: dict[str, object] | None = None,
    after: dict[str, object] | None = None,
) -> AdminAuditLog:
    entry = AdminAuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        reason=reason,
    )
    session.add(entry)
    await session.flush()
    return entry
