"""Pydantic schemas for authenticated user profile operations."""

from pydantic import BaseModel, ConfigDict, Field


class GradeSelectionUpdate(BaseModel):
    """Explicit canonical student grade; there is intentionally no default."""

    model_config = ConfigDict(extra="forbid", strict=True)

    selected_grade: int = Field(ge=1, le=12)
