"""Validate planning goals, generated task content and server-provided provenance."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from schemas.tasks import TaskCreate

UserGoal = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]


class GeneratedPlan(BaseModel):
    """Accept one to fifty validated tasks from an untrusted model response."""

    tasks: list[TaskCreate] = Field(min_length=1, max_length=50)


class PlanResponse(GeneratedPlan):
    """Return proposals and identify whether a real model or demo adapter produced them."""

    provider: Literal["demo", "ollama"]


class PlanRequest(BaseModel):
    """Accept a goal and an inclusive, bounded range for the number of proposals."""

    goal: UserGoal
    min_elements: int = Field(default=1, ge=1, le=50, strict=True)
    max_elements: int = Field(default=10, ge=1, le=50, strict=True)

    @model_validator(mode="after")
    def check_elements_range(self) -> Self:
        """Reject an inverted range before any generation request is made."""
        if self.min_elements > self.max_elements:
            raise ValueError("min_elements nie może być większe niż max_elements.")
        return self
