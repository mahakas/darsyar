"""Authenticated user profile and explicit student-grade selection (R-019)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/profile", tags=["profile"])


class GradeSelectionUpdate(BaseModel):
    """Explicit canonical student grade; there is intentionally no default."""

    model_config = ConfigDict(extra="forbid", strict=True)

    selected_grade: int = Field(ge=1, le=12)


@router.get("/me", response_model=UserOut)
async def get_my_profile(
    user: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    """Return only the authenticated user's profile."""
    return UserOut.model_validate(user)


@router.patch("/me/grade", response_model=UserOut)
async def update_my_selected_grade(
    payload: GradeSelectionUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    """Persist the grade for the current user; a client cannot target another user."""
    if user.role != "user":
        raise AppError("student_profile_required", 403, "این عملیات فقط برای حساب دانش‌آموزی در دسترس است.")
    user.selected_grade = payload.selected_grade
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)
