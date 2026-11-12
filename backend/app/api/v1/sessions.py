"""Authenticated conversation history endpoints (Phase 6, R-121)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.repositories import conversations as conv_repo
from app.schemas.conversation import (
    ConversationListOut,
    ConversationOut,
    HistoryMessageOut,
    MessageListOut,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListOut)
async def list_conversations(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> ConversationListOut:
    """List only the caller's conversations using bounded pagination and title search."""
    rows = await conv_repo.list_owned(session, user.id, limit=limit, offset=offset, query=q)
    total = await conv_repo.count_owned(session, user.id, query=q)
    return ConversationListOut(
        items=[ConversationOut.model_validate(row) for row in rows],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get("/{conversation_id}/messages", response_model=MessageListOut)
async def list_conversation_messages(
    conversation_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    after_sequence: Annotated[int | None, Query(ge=0)] = None,
) -> MessageListOut:
    """Read a message page only after verifying conversation ownership."""
    conversation = await conv_repo.get_owned(session, conversation_id, user.id)
    if conversation is None:
        raise AppError("conversation_not_found", 404, "گفتگو یافت نشد.")
    rows = await conv_repo.list_messages_for_user(
        session,
        conversation_id,
        user.id,
        after_sequence=after_sequence,
        limit=limit + 1,
    )
    has_more = len(rows) > limit
    items = [HistoryMessageOut.model_validate(row) for row in rows[:limit]]
    next_sequence = items[-1].sequence if has_more and items else None
    return MessageListOut(
        items=items,
        limit=limit,
        after_sequence=after_sequence,
        next_after_sequence=next_sequence,
    )
