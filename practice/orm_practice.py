"""Demonstrate SQLAlchemy CRUD in a database separate from the application."""

from pathlib import Path

from sqlalchemy import URL, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DEFAULT_DATABASE = Path(__file__).resolve().with_name("orm_practice.db")


class Base(DeclarativeBase):
    """Collect table metadata for this standalone example."""


class Note(Base):
    """Store a sample note used to demonstrate ORM operations."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)


def main(database_path: Path = DEFAULT_DATABASE) -> None:
    """Create, read, update and delete a new sample note without touching older rows.

    Args:
        database_path: SQLite file used only by this learning example.
    """
    engine = create_engine(URL.create("sqlite", database=str(database_path)), echo=True)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            note = Note(title="Pierwsza notatka")
            session.add(note)
            session.commit()
            session.refresh(note)
            print(f"Added note: {note.id}")
            print([item.title for item in session.scalars(select(Note)).all()])
            note.title = "SQLAlchemy CRUD"
            session.commit()
            session.delete(note)
            session.commit()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
