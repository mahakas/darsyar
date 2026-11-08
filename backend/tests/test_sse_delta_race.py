"""تست DB-free برای قرارداد تأیید Delta در برابر Recovery.

قرارداد:
- Authorization در `_assert_stream_owned` / `_mark_billable_durable` linearize می‌شود.
- بین «بررسی مالکیت» و «yield شبکه»، recovery می‌تواند commit کند؛ این یک ابهام
  in-flight اجتناب‌ناپذیر است و «تضمین مطلق عدم تحویل پس از recovery» ادعا نمی‌شود.
- پس از باطل‌شدن مالکیت، هر تأیید بعدی باید fail شود (بدون fallback).
"""

import uuid

import pytest
from app.services.chat_service import ChatStreamService


class _StubResult:
    def __init__(self, value) -> None:
        self._value = value

    def first(self):
        return self._value


class _StubSession:
    def __init__(self, value) -> None:
        self._value = value

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, *a, **k):
        return _StubResult(self._value)

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _service_with_result(first_value) -> ChatStreamService:
    service = ChatStreamService(provider=None)

    class _Factory:
        def __call__(self):
            class _CM:
                async def __aenter__(self):
                    return _StubSession(first_value)

                async def __aexit__(self, *a):
                    return False

            return _CM()

    service._session_factory = _Factory()
    return service


@pytest.mark.asyncio
async def test_authorize_after_recovery_returns_false() -> None:
    # recovery مالکیت را باطل کرده → اولین() برای select، None برمی‌گرداند
    service = _service_with_result(None)
    assert await service._assert_stream_owned(uuid.uuid4(), "old-owner") is False


@pytest.mark.asyncio
async def test_authorize_when_still_owned_returns_true() -> None:
    service = _service_with_result((uuid.uuid4(),))
    assert await service._assert_stream_owned(uuid.uuid4(), "owner") is True


@pytest.mark.asyncio
async def test_first_billable_marker_after_recovery_not_persisted() -> None:
    service = _service_with_result(None)
    assert await service._mark_billable_durable(uuid.uuid4(), "old-owner") is False


def test_delta_authorization_contract_documented() -> None:
    # قرارداد: authorization linearization؛ ابهام in-flight مستند است.
    from app.services import chat_service as mod

    src = open(mod.__file__, encoding="utf-8").read()
    assert "_assert_stream_owned" in src
    assert "linearization point" in src
