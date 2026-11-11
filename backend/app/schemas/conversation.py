"""Schemaهای Pydantic گفتگو و پیام (فاز ۳)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    status: str
    content: str
    sequence: int
    provider_request_id: str | None = None
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    """ایجاد پیام کاربر؛ idempotent با `client_request_id`."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=200000)
    client_request_id: str | None = Field(default=None, min_length=8, max_length=128)


class ChatStreamOut(BaseModel):
    """پاسخ استریم چت (SSE رویدادها جدا از HTTP)."""

    conversation_id: uuid.UUID
    message_id: uuid.UUID | None = None
    request_id: str | None = None


class ChatStreamRequest(BaseModel):
    """درخواست چت استریم؛ idempotent با `client_request_id`."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID | None = None
    content: str = Field(min_length=1, max_length=200000)
    client_request_id: str = Field(min_length=8, max_length=128)
    model: str | None = Field(default=None, max_length=128)


class ConversationListOut(BaseModel):
    items: list[ConversationOut]
    limit: int
    offset: int
    total: int


class HistoryMessageOut(BaseModel):
    """Safe message history shape; excludes provider and internal billing identifiers."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    status: str
    content: str
    sequence: int
    created_at: datetime


class MessageListOut(BaseModel):
    items: list[HistoryMessageOut]
    limit: int
    after_sequence: int | None = None
    next_after_sequence: int | None = None
