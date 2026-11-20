"""SSE replay cursors and durable citation replay."""

import uuid
from types import SimpleNamespace

import pytest
from app.services.chat_service import EVENT_SNAPSHOT, EVENT_SOURCES, ChatStreamService


@pytest.mark.asyncio
async def test_replay_continues_from_last_event_id_and_sends_snapshot() -> None:
    service = object.__new__(ChatStreamService)
    assistant = SimpleNamespace(
        id=uuid.uuid4(),
        content="پاسخ کامل",
        status="completed",
        sources=["[کتاب: ریاضی | صفحه ۳]"],
    )
    conversation_id = uuid.uuid4()

    events = [event async for event in service._replay(assistant, conversation_id, "7")]

    ids = [int(event.splitlines()[0].removeprefix("id:")) for event in events]
    assert ids == [8, 9, 10, 11, 12]
    assert ids == sorted(ids)
    assert f"event:{EVENT_SOURCES}" in events[2]
    assert f"event:{EVENT_SNAPSHOT}" in events[3]
    assert "پاسخ کامل" in events[3]


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 0), ("", 0), ("not-a-number", 0), ("42", 42), ("999999999999", 1_000_000)],
)
def test_last_event_id_is_bounded(value: str | None, expected: int) -> None:
    assert ChatStreamService._parse_last_event_id(value) == expected
