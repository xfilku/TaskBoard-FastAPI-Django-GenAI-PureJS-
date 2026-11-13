"""Provide board CRUD endpoints restricted to the authenticated owner."""

from collections.abc import Sequence
from sqlite3 import SQLITE_CONSTRAINT_FOREIGNKEY

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.board import Board
from models.user import User
from schemas.board import BoardCreate, BoardResponse, BoardUpdate
from security import get_current_user, get_own_board
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(prefix="/boards", tags=["boards"])


@router.get("", response_model=list[BoardResponse])
def get_boards(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Sequence[Board]:
    """List only boards owned by the authenticated account."""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Coś poszło nie tak... Spróbuj zalogować się ponownie.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    statement = select(Board).where(Board.owner_id == user.id)
    boards = db.scalars(statement).all()

    return boards


@router.get("/{board_id}", response_model=BoardResponse)
def get_board(
    board_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Board:
    """Return one board after verifying ownership."""
    board = get_own_board(board_id=board_id, user=user, db=db)

    return board


@router.post("", status_code=201, response_model=BoardResponse)
def create_board(
    board: BoardCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Board:
    """Create a board whose owner comes from the token rather than the request body."""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Coś poszło nie tak... Spróbuj zalogować się ponownie.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_board = Board(name=board.name, owner_id=user.id)

    db.add(new_board)
    db.commit()
    db.refresh(new_board)

    return new_board


@router.patch("/{board_id}", response_model=BoardResponse)
def patch_board(
    board_id: int,
    data: BoardUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Board:
    """Apply supplied board fields; an empty PATCH leaves the board unchanged."""
    board = get_own_board(board_id=board_id, user=user, db=db)

    changes = data.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(board, field, value)

    if changes:
        db.commit()
        db.refresh(board)

    return board


@router.delete("/{board_id}", status_code=204)
def delete_board(
    board_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    """Delete an owned board, returning HTTP 409 while it still contains tasks."""
    board = get_own_board(board_id=board_id, user=user, db=db)

    db.delete(board)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlite_errorcode", None) == SQLITE_CONSTRAINT_FOREIGNKEY:
            raise HTTPException(
                status_code=409, detail=f"Tablica {board_id} zawiera zadania. Najpierw je usuń."
            ) from exc
        raise
