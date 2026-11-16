"""Describe and execute the task lookup tool available to chat."""

from queries.task_lookup import list_user_tasks
from schemas.chat_tools import ListTasksArgs
from sqlalchemy.orm import Session

LIST_TASKS_TOOL: dict[str, object] = {
    "name": "list_tasks",
    "description": (
        "Pobiera zadania zalogowanego użytkownika ze wszystkich jego tablic. "
        "Opcjonalnie filtruje po statusie i terminie zadania."
    ),
    "parameters": ListTasksArgs.model_json_schema(),
}


def run_list_tasks(
    arguments: dict[str, object], db: Session, user_id: int
) -> list[dict[str, object]]:
    """Validate model-selected filters and look up tasks for the authenticated account."""
    filters = ListTasksArgs.model_validate(arguments)
    return list_user_tasks(
        user_id=user_id,
        db=db,
        start_date=filters.start_date,
        end_date=filters.end_date,
        is_done=filters.is_done,
    )
