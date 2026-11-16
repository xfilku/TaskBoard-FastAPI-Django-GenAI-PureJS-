"""Validate the filters a model can supply to the task lookup tool."""

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ListTasksArgs(BaseModel):
    """Accept optional deadline bounds and a completion status."""

    model_config = ConfigDict(extra="forbid")

    start_date: date | None = Field(default=None, description="Najwcześniejszy termin włącznie.")
    end_date: date | None = Field(default=None, description="Najpóźniejszy termin włącznie.")
    is_done: bool | None = Field(
        default=None, description="False oznacza zadania do zrobienia, true oznacza ukończone."
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        """Reject a date range whose end precedes its start."""
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError(
                "Data początkowa musi być wcześniejsza od daty końcowej lub jej równa."
            )
        return self
