"""Create missing API tables without changing existing tables or data."""

from database import Base, engine
from models.board import Board  # noqa: F401 -- register model metadata
from models.task import Task  # noqa: F401 -- register model metadata
from models.user import User  # noqa: F401 -- register model metadata


def main() -> None:
    """Initialize the configured database; schema changes require migrations."""
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    main()
