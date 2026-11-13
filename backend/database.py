"""Configure the SQLite engine and request-scoped database sessions."""

import os
from collections.abc import Iterator
from pathlib import Path
from sqlite3 import Connection

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.pool import ConnectionPoolEntry

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR.parent / ".env", override=False)
database_url = os.environ.get("TASKBOARD_DATABASE_URL") or URL.create(
    "sqlite", database=str(BACKEND_DIR / "taskboard_dev.db")
)
engine = create_engine(database_url, hide_parameters=True)


class Base(DeclarativeBase):
    """Share SQLAlchemy metadata across the TaskBoard models."""


def get_db() -> Iterator[Session]:
    """Yield a session for one request and close it even when the request fails."""
    with Session(engine) as db:
        yield db


@event.listens_for(engine, "connect")
def enable_foreign_keys(connection: Connection, _connection_record: ConnectionPoolEntry) -> None:
    """Enforce SQLite foreign keys on every newly opened connection."""
    cursor = connection.execute("PRAGMA foreign_keys = ON")
    cursor.close()
