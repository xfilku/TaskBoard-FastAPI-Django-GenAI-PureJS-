"""Call the API with a bounded timeout and consistent bearer authentication.

HTTP status and transport errors intentionally propagate to the views, which
translate them into form errors, messages or a redirect to the login page.
"""

import math
import os
from datetime import date
from typing import Any

import httpx
from django.conf import settings

API_ADDRESS = settings.TASKBOARD_API_URL
REQUEST_TIMEOUT = 5.0


def _request(
    method: str,
    path: str,
    access_token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = REQUEST_TIMEOUT,
) -> httpx.Response:
    """Send one request and raise HTTPX errors for transport or status failures."""
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    response = httpx.request(
        method,
        f"{API_ADDRESS.rstrip('/')}/{path.lstrip('/')}",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def _serialize_deadline(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a Python date to ISO format while preserving null and omitted fields."""
    deadline = payload.get("deadline")
    if isinstance(deadline, date):
        return {**payload, "deadline": deadline.isoformat()}
    return payload


def _planning_timeout() -> float:
    """Allow the API's configured model timeout plus a bounded network margin."""
    try:
        timeout = float(os.getenv("TASKBOARD_AI_TIMEOUT", "60"))
    except ValueError:
        timeout = 60.0
    if not math.isfinite(timeout):
        timeout = 60.0
    return min(max(timeout, 1.0), 300.0) + 15.0


def login_user(email: str, password: str) -> dict[str, Any]:
    """Exchange credentials for a short-lived access token."""
    return _request("POST", "users/login", payload={"email": email, "password": password}).json()


def register_user(email: str, password: str) -> dict[str, Any]:
    """Create an API account and return its public profile."""
    return _request("POST", "users", payload={"email": email, "password": password}).json()


def get_boards(access_token: str) -> list[dict[str, Any]]:
    """Return the authenticated account's boards."""
    return _request("GET", "boards", access_token).json()


def create_board(name: str, access_token: str, deadline: date | None = None) -> dict[str, Any]:
    """Create a board for the authenticated account with an optional deadline."""
    payload = _serialize_deadline({"name": name, "deadline": deadline})
    return _request("POST", "boards", access_token, payload).json()


def get_board(board_id: int, access_token: str) -> dict[str, Any]:
    """Return one board after the API checks its ownership."""
    return _request("GET", f"boards/{board_id}", access_token).json()


def get_board_tasks(board_id: int, access_token: str) -> list[dict[str, Any]]:
    """Return the tasks belonging to an accessible board."""
    return _request("GET", f"boards/{board_id}/tasks", access_token).json()


def create_task(
    board_id: int, title: str, access_token: str, deadline: date | None = None
) -> dict[str, Any]:
    """Add an unfinished task to a board with an optional deadline."""
    payload = _serialize_deadline({"title": title, "deadline": deadline})
    return _request("POST", f"boards/{board_id}/tasks", access_token, payload).json()


def delete_task(board_id: int, task_id: int, access_token: str) -> None:
    """Delete a task without attempting to parse the empty 204 response."""
    _request("DELETE", f"boards/{board_id}/tasks/{task_id}", access_token)


def patch_task(
    board_id: int, task_id: int, changes: dict[str, Any], access_token: str
) -> dict[str, Any]:
    """Update only the task fields supplied in changes."""
    payload = _serialize_deadline(changes)
    return _request("PATCH", f"boards/{board_id}/tasks/{task_id}", access_token, payload).json()


def get_task(board_id: int, task_id: int, access_token: str) -> dict[str, Any]:
    """Return a task scoped to its board."""
    return _request("GET", f"boards/{board_id}/tasks/{task_id}", access_token).json()


def delete_board(board_id: int, access_token: str) -> None:
    """Delete an empty board; the API rejects boards that still contain tasks."""
    _request("DELETE", f"boards/{board_id}", access_token)


def preview_plan(
    board_id: int, goal: str, min_elements: int, max_elements: int, access_token: str
) -> dict[str, Any]:
    """Request a preview with enough time for local inference; this does not save tasks."""
    return _request(
        "POST",
        f"ai/boards/{board_id}/plan-preview",
        access_token,
        {"goal": goal, "min_elements": min_elements, "max_elements": max_elements},
        timeout=_planning_timeout(),
    ).json()


def create_tasks_batch(
    board_id: int, tasks: list[dict[str, str | date | None]], access_token: str
) -> list[dict[str, Any]]:
    """Persist only the reviewed tasks selected by the user in one API transaction."""
    payload = {"tasks": [_serialize_deadline(task) for task in tasks]}
    return _request("POST", f"boards/{board_id}/tasks/batch", access_token, payload).json()
