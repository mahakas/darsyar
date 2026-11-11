"""دسترسی دادهٔ گفتگو و پیام؛ مالکیت در query اعمال می‌شود (R-121)."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message


async def create_conversation(session: AsyncSession, *, user_id: uuid.UUID, title: str | None = None) -> Conversation:
    conv = Conversation(user_id=user_id, title=title)
    session.add(conv)
    await session.flush()
    return conv


async def get_owned(session: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_owned(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int, before: uuid.UUID | None = None,
    offset: int = 0,
) -> Sequence[Conversation]:
    statement = select(Conversation).where(Conversation.user_id == user_id)
    if before is not None:
        statement = statement.where(Conversation.id < before)
    statement = statement.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(limit).offset(offset)
    result = await session.execute(statement)
    return result.scalars().all()


async def count_owned(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
    )
    return int(result.scalar_one())


async def create_message(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    status: str = "streaming",
    content: str = "",
    client_request_id: str | None = None,
    provider_request_id: str | None = None,
    reservation_id: uuid.UUID | None = None,
) -> Message:
    max_seq = await session.execute(
        select(func.max(Message.sequence)).where(Message.conversation_id == conversation_id)
    )
    sequence = int(max_seq.scalar_one() or 0) + 1
    msg = Message(
        conversation_id=conversation_id,
        user_id=user_id,
        role=role,
        status=status,
        content=content,
        sequence=sequence,
        client_request_id=client_request_id,
        provider_request_id=provider_request_id,
        reservation_id=reservation_id,
    )
    session.add(msg)
    await session.flush()
    return msg


async def get_message_by_reservation(session: AsyncSession, reservation_id: uuid.UUID) -> Message | None:
    result = await session.execute(select(Message).where(Message.reservation_id == reservation_id))
    return result.scalar_one_or_none()


async def create_message_idempotent(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    content: str,
    client_request_id: str | None = None,
) -> Message:
    """ایجاد پیام idempotent؛ در صورت تکرار `client_request_id` همان سطر بازگردانده می‌شود.

    هم‌زمانی توسط ایندکس یکتای جزئی `uq_messages_conv_client_request` محافظت می‌شود؛
    در صورت برخورد، فراخواننده باید یک تراکنش/بازپرسی امن انجام دهد.
    """
    if client_request_id is not None:
        existing = await get_message_by_client_request(session, conversation_id, client_request_id, user_id)
        if existing is not None:
            return existing
    return await create_message(
        session,
        conversation_id=conversation_id,
        user_id=user_id,
        role=role,
        content=content,
        client_request_id=client_request_id,
    )


async def get_message_by_client_request(
    session: AsyncSession, conversation_id: uuid.UUID, client_request_id: str, user_id: uuid.UUID
) -> Message | None:
    result = await session.execute(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.client_request_id == client_request_id,
            Message.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_messages_for_user(
    session: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID, *,
    after_sequence: int | None = None, limit: int = 100,
) -> Sequence[Message]:
    statement = select(Message).where(
        Message.conversation_id == conversation_id, Message.user_id == user_id
    )
    if after_sequence is not None:
        statement = statement.where(Message.sequence > after_sequence)
    statement = statement.order_by(Message.sequence.asc()).limit(limit)
    result = await session.execute(statement)
    return result.scalars().all()


async def set_message_status(session: AsyncSession, message_id: uuid.UUID, status: str, *, content: str | None = None) -> bool:
    from typing import cast

    from sqlalchemy import update
    from sqlalchemy.engine import CursorResult as _CursorResult

    values: dict[str, object] = {"status": status}
    if content is not None:
        values["content"] = content
    result = await session.execute(update(Message).where(Message.id == message_id).values(**values))
    return cast(_CursorResult[object], result).rowcount == 1
