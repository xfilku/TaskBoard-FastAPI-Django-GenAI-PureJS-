"""Persist tasks and their parent board references."""

from datetime import date

from database import Base
from sqlalchemy import Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class Task(Base):
    """Store a task title and completion state within one board."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    is_done: Mapped[bool] = mapped_column(default=False)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id"))
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
