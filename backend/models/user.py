"""Persist account identities and one-way password hashes."""

from database import Base
from sqlalchemy.orm import Mapped, mapped_column


class User(Base):
    """Store a unique email address and a hash, never the plaintext password."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str] = mapped_column(nullable=False)
