from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session


class Base(DeclarativeBase):
    pass


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)


engine = create_engine(
    "sqlite:///orm_practice.db",
    echo=True
)


Base.metadata.create_all(engine)


with Session(engine) as session:
    note = Note(title="Notatka z marginesu w której zapisałem sposób na to jak dorobić sosu przez modulację głosu.")
    session.add(note)
    session.commit()
    session.refresh(note)

    print(f"id: {note.id} ,Tytuł: \"{note.title}\"")