"""Validate task creation and partial updates without accepting board reassignment."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

TaskTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=300)]


class TaskCreate(BaseModel):
    """Accept a trimmed title for a new, unfinished task."""

    title: TaskTitle


class TaskBatchCreate(BaseModel):
    """Accept a bounded group of reviewed task titles for one atomic insert."""

    tasks: list[TaskCreate] = Field(min_length=1, max_length=50)


class TaskResponse(BaseModel):
    """Expose the task's public fields and parent board identifier."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    is_done: bool
    board_id: int


class TaskUpdate(BaseModel):
    """Update only explicitly supplied fields; null values are invalid."""

    title: TaskTitle | None = None
    is_done: bool = False

    @field_validator("title")
    @classmethod
    def reject_null_title(cls, value: str | None) -> str:
        """Require a real title when the client includes the field."""
        if value is None:
            raise ValueError("Task title cannot be null.")
        return value
