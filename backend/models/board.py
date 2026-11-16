"""Persist board names and their account ownership."""

from datetime import date

from database import Base
from sqlalchemy import Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class Board(Base):
    """Store a board; legacy rows with no owner are denied by authorization checks."""

    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
