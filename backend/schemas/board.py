"""Validate board payloads and define their public API representation."""

from typing import Annotated

from datetime import date

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, Field

BoardDeadline = Annotated[date | None, Field(description="Deadline tablicy")]
BoardName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)]

class BoardCreate(BaseModel):
    """Accept a trimmed board name; ownership is assigned by the server."""

    name: BoardName
    deadline: BoardDeadline = None


class BoardResponse(BaseModel):
    """Expose a board's identifier and name without internal ownership fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    deadline: date | None


class BoardUpdate(BaseModel):
    """Allow an omitted name for a no-op PATCH while rejecting explicit null."""

    name: BoardName | None = None
    deadline: BoardDeadline | None = None

    @field_validator("name")
    @classmethod
    def reject_null_name(cls, value: str | None) -> str:
        """Require a real name when the client includes the field."""
        if value is None:
            raise ValueError("Board name cannot be null.")
        return value
