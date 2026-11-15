"""Manage tasks within a board after checking the board's ownership."""

from collections.abc import Sequence

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.task import Task
from models.user import User
from schemas.tasks import TaskBatchCreate, TaskCreate, TaskResponse, TaskUpdate
from security import get_current_user, get_own_board
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/boards/{board_id}/tasks", tags=["tasks"])


@router.post("", status_code=201, response_model=TaskResponse)
def create_task(
    board_id: int,
    task: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Task:
    """Add an unfinished task to the owned board identified by the URL."""
    board = get_own_board(board_id=board_id, user=user, db=db)

    new_task = Task(title=task.title, is_done=False, board_id=board.id, deadline=task.deadline)

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return new_task


@router.post("/batch", status_code=201, response_model=list[TaskResponse])
def create_tasks(
    board_id: int,
    data: TaskBatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TaskResponse]:
    """Save reviewed tasks in one transaction after checking the board's ownership."""
    board = get_own_board(board_id=board_id, user=user, db=db)
    tasks = []

    for task in data.tasks:
        tasks.append(Task(title=task.title, board_id=board.id, is_done=False, deadline=task.deadline))

    db.add_all(tasks)
    db.flush()

    result = [TaskResponse.model_validate(task) for task in tasks]

    db.commit()

    return result


@router.get("", response_model=list[TaskResponse])
def get_board_tasks(
    board_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Sequence[Task]:
    """List the tasks in a board after verifying that the caller owns it."""
    board = get_own_board(board_id=board_id, user=user, db=db)

    statement = select(Task).where(Task.board_id == board.id)
    tasks = db.scalars(statement).all()

    return tasks


@router.get("/{task_id}", response_model=TaskResponse)
def get_board_task(
    board_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Task:
    """Return an owned board's task or raise HTTP 404 for an out-of-board ID."""
    board = get_own_board(board_id=board_id, user=user, db=db)

    statement = select(Task).where(Task.board_id == board.id, Task.id == task_id)

    task = db.scalars(statement).first()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task o wskazanym identyfikatorze {task_id} nie istnieje w tablicy {board_id}...",
        )

    return task


@router.patch("/{task_id}", response_model=TaskResponse)
def patch_board_task(
    board_id: int,
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Task:
    """Apply only supplied fields after checking both board ownership and task scope."""
    board = get_own_board(board_id=board_id, user=user, db=db)

    statement = select(Task).where(Task.board_id == board.id, Task.id == task_id)

    task = db.scalars(statement).first()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task o wskazanym identyfikatorze {task_id} nie istnieje w tablicy {board_id}...",
        )

    changes = data.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(task, field, value)

    if changes:
        db.commit()
        db.refresh(task)

    return task


@router.delete("/{task_id}", status_code=204)
def delete_board_task(
    board_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Delete a task only when it belongs to the URL's board and the caller owns it."""
    board = get_own_board(board_id=board_id, user=user, db=db)

    statement = select(Task).where(Task.board_id == board.id, Task.id == task_id)

    task = db.scalars(statement).first()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task o wskazanym identyfikatorze {task_id} nie istnieje w tablicy {board_id}...",
        )

    db.delete(task)
    db.commit()
