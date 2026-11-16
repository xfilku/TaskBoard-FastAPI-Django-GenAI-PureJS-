"""Read tasks across the boards owned by one account."""

from datetime import date

from models.board import Board
from models.task import Task
from sqlalchemy import select
from sqlalchemy.orm import Session


def list_user_tasks(
    user_id: int,
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
    is_done: bool | None = None,
) -> list[dict[str, object]]:
    """Return owned tasks with board details and optional inclusive filters."""
    statement = (
        select(
            Task.id,
            Task.title,
            Task.deadline,
            Task.is_done,
            Board.id.label("board_id"),
            Board.name.label("board_name"),
        )
        .join(Board, Board.id == Task.board_id)
        .where(Board.owner_id == user_id)
        .order_by(Task.deadline.asc().nulls_last(), Task.id)
    )

    if start_date is not None:
        statement = statement.where(Task.deadline >= start_date)

    if end_date is not None:
        statement = statement.where(Task.deadline <= end_date)

    if is_done is not None:
        statement = statement.where(Task.is_done.is_(is_done))

    rows = db.execute(statement).mappings().all()
    return [dict(row) for row in rows]
