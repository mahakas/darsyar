"""Profile API tests: explicit grade is self-service and strictly validated."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.api.v1.profile import router
from app.db.session import get_db


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance) -> None:
        return None


@pytest.fixture
def profile_app():
    user = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        phone="+989121234567",
        name="Student",
        role="user",
        selected_grade=None,
    )
    session = FakeSession()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: user

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    return app, user, session


@pytest.mark.asyncio
async def test_profile_returns_unselected_grade_without_default(profile_app) -> None:
    app, _, _ = profile_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/profile/me")
    assert response.status_code == 200
    assert response.json()["selected_grade"] is None


@pytest.mark.asyncio
async def test_profile_grade_update_is_persisted_for_current_user(profile_app) -> None:
    app, user, session = profile_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/profile/me/grade", json={"selected_grade": 8}
        )
    assert response.status_code == 200
    assert response.json()["selected_grade"] == 8
    assert user.selected_grade == 8
    assert session.committed is True


@pytest.mark.asyncio
@pytest.mark.parametrize("grade", [0, 13, -1, "8", True, None])
async def test_profile_rejects_invalid_or_non_integer_grade(profile_app, grade) -> None:
    app, user, session = profile_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/profile/me/grade", json={"selected_grade": grade}
        )
    assert response.status_code == 422
    assert user.selected_grade is None
    assert session.committed is False


@pytest.mark.asyncio
async def test_profile_grade_update_rejects_other_user_fields(profile_app) -> None:
    app, user, session = profile_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/profile/me/grade",
            json={"selected_grade": 6, "user_id": "00000000-0000-0000-0000-000000000002"},
        )
    assert response.status_code == 422
    assert user.selected_grade is None
    assert session.committed is False
