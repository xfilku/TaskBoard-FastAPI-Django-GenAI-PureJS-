import pytest
from models.board import Board
from models.task import Task
from sqlalchemy import select

TASK_ROUTES = [
    ("POST", "/boards/{board_id}/tasks", {"title": "New task"}),
    ("GET", "/boards/{board_id}/tasks", None),
    ("GET", "/boards/{board_id}/tasks/{task_id}", None),
    ("PATCH", "/boards/{board_id}/tasks/{task_id}", {"is_done": True}),
    ("DELETE", "/boards/{board_id}/tasks/{task_id}", None),
]


def test_task_creation_uses_the_authorized_board_and_defaults(
    client, auth_headers, board, db_session
):
    response = client.post(
        f"/boards/{board['id']}/tasks",
        json={"title": "New task", "board_id": 999999, "is_done": True},
        headers=auth_headers,
    )

    assert response.status_code == 201
    task = response.json()
    assert set(task) == {"id", "title", "is_done", "board_id", "deadline"}
    assert task["title"] == "New task"
    assert task["board_id"] == board["id"]
    assert task["is_done"] is False
    assert task["deadline"] is None
    stored_task = db_session.get(Task, task["id"])
    assert stored_task.title == task["title"]
    assert stored_task.board_id == board["id"]


def test_task_creation_persists_deadline(client, auth_headers, board):
    path = f"/boards/{board['id']}/tasks"
    deadline = "2026-11-30"
    response = client.post(
        path, json={"title": "Prepare the demo", "deadline": deadline}, headers=auth_headers
    )

    assert response.status_code == 201
    task = response.json()
    assert task["deadline"] == deadline

    read = client.get(f"{path}/{task['id']}", headers=auth_headers)
    assert read.status_code == 200
    assert read.json()["deadline"] == deadline


def test_task_lists_are_scoped_to_the_requested_board(client, auth_headers, board, task):
    other_board_response = client.post(
        "/boards", json={"name": "Second project"}, headers=auth_headers
    )
    assert other_board_response.status_code == 201
    other_board = other_board_response.json()
    other_task_response = client.post(
        f"/boards/{other_board['id']}/tasks",
        json={"title": "Other project task"},
        headers=auth_headers,
    )
    assert other_task_response.status_code == 201

    response = client.get(f"/boards/{board['id']}/tasks", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == [task]


def test_empty_board_has_an_empty_task_list(client, auth_headers, board):
    response = client.get(f"/boards/{board['id']}/tasks", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_owner_can_read_a_task(client, auth_headers, board, task):
    response = client.get(f"/boards/{board['id']}/tasks/{task['id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == task


@pytest.mark.parametrize("updates", [{"title": "Renamed task"}, {}], ids=["title", "empty"])
def test_task_patch_preserves_unspecified_fields(client, auth_headers, board, task, updates):
    path = f"/boards/{board['id']}/tasks/{task['id']}"
    completed = client.patch(path, json={"is_done": True}, headers=auth_headers)
    assert completed.status_code == 200
    expected = {**task, "is_done": True, **updates}

    response = client.patch(path, json=updates, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == expected
    assert client.get(path, headers=auth_headers).json() == expected


def test_task_patch_preserves_omitted_deadline_and_clears_explicit_null(
    client, auth_headers, board, task
):
    path = f"/boards/{board['id']}/tasks/{task['id']}"
    deadline = "2026-11-30"
    scheduled = client.patch(path, json={"deadline": deadline}, headers=auth_headers)
    assert scheduled.status_code == 200
    assert scheduled.json()["deadline"] == deadline

    completed = client.patch(path, json={"is_done": True}, headers=auth_headers)
    assert completed.status_code == 200
    assert completed.json()["deadline"] == deadline

    cleared = client.patch(path, json={"deadline": None}, headers=auth_headers)
    assert cleared.status_code == 200
    assert cleared.json()["deadline"] is None
    assert client.get(path, headers=auth_headers).json()["deadline"] is None


def test_completed_task_can_be_reopened(client, auth_headers, board, task):
    path = f"/boards/{board['id']}/tasks/{task['id']}"
    completed = client.patch(path, json={"is_done": True}, headers=auth_headers)
    assert completed.status_code == 200
    assert completed.json()["is_done"] is True

    response = client.patch(path, json={"is_done": False}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["is_done"] is False
    assert client.get(path, headers=auth_headers).json()["is_done"] is False


def test_both_task_fields_can_be_updated_together(client, auth_headers, board, task):
    path = f"/boards/{board['id']}/tasks/{task['id']}"
    updates = {"title": "Completed task", "is_done": True}

    response = client.patch(path, json=updates, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {**task, **updates}
    assert client.get(path, headers=auth_headers).json() == {**task, **updates}


def test_deleting_one_task_preserves_its_board_and_other_tasks(client, auth_headers, board, task):
    other_response = client.post(
        f"/boards/{board['id']}/tasks",
        json={"title": "Keep this task"},
        headers=auth_headers,
    )
    assert other_response.status_code == 201
    path = f"/boards/{board['id']}/tasks/{task['id']}"

    response = client.delete(path, headers=auth_headers)

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(path, headers=auth_headers).status_code == 404
    assert client.delete(path, headers=auth_headers).status_code == 404
    assert client.get(f"/boards/{board['id']}", headers=auth_headers).json() == board
    assert client.get(f"/boards/{board['id']}/tasks", headers=auth_headers).json() == [
        other_response.json()
    ]


@pytest.mark.parametrize(("method", "path", "payload"), TASK_ROUTES)
def test_task_routes_require_authentication(client, board, task, db_session, method, path, payload):
    response = client.request(
        method, path.format(board_id=board["id"], task_id=task["id"]), json=payload
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    stored_tasks = db_session.scalars(select(Task)).all()
    assert len(stored_tasks) == 1
    assert stored_tasks[0].title == task["title"]
    assert stored_tasks[0].is_done is False


@pytest.mark.parametrize(("method", "path", "payload"), TASK_ROUTES)
def test_another_account_cannot_access_tasks(
    client, board, task, db_session, other_auth_headers, method, path, payload
):
    response = client.request(
        method,
        path.format(board_id=board["id"], task_id=task["id"]),
        json=payload,
        headers=other_auth_headers,
    )

    assert response.status_code == 403
    stored_tasks = db_session.scalars(select(Task)).all()
    assert len(stored_tasks) == 1
    assert stored_tasks[0].title == task["title"]
    assert stored_tasks[0].is_done is False


@pytest.mark.parametrize(("method", "path", "payload"), TASK_ROUTES)
def test_task_routes_reject_a_missing_board(client, auth_headers, method, path, payload):
    response = client.request(
        method,
        path.format(board_id=999999, task_id=999999),
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_missing_task_returns_not_found(client, auth_headers, board, method):
    response = client.request(
        method,
        f"/boards/{board['id']}/tasks/999999",
        json={"is_done": True},
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_task_cannot_be_accessed_through_another_owned_board(client, auth_headers, task, method):
    response = client.post("/boards", json={"name": "Second project"}, headers=auth_headers)
    assert response.status_code == 201
    other_board_id = response.json()["id"]

    denied = client.request(
        method,
        f"/boards/{other_board_id}/tasks/{task['id']}",
        json={"is_done": True},
        headers=auth_headers,
    )

    assert denied.status_code == 404
    original = client.get(f"/boards/{task['board_id']}/tasks/{task['id']}", headers=auth_headers)
    assert original.status_code == 200
    assert original.json() == task


def test_task_creation_in_a_legacy_board_is_forbidden(client, auth_headers, db_session):
    legacy_board = Board(name="Legacy project", owner_id=None)
    db_session.add(legacy_board)
    db_session.commit()

    response = client.post(
        f"/boards/{legacy_board.id}/tasks",
        json={"title": "Unauthorized task"},
        headers=auth_headers,
    )

    assert response.status_code == 403
    assert db_session.scalars(select(Task)).all() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "abcd"},
        {"title": "x" * 301},
        {"title": None},
        {},
        {"title": "New task", "deadline": "2026-02-30"},
    ],
    ids=["too-short", "too-long", "null", "missing", "invalid-deadline"],
)
def test_invalid_task_creation_writes_no_task(client, auth_headers, board, db_session, payload):
    response = client.post(f"/boards/{board['id']}/tasks", json=payload, headers=auth_headers)

    assert response.status_code == 422
    assert db_session.scalars(select(Task)).all() == []


@pytest.mark.parametrize("title_length", [5, 300])
def test_task_title_length_boundaries_are_accepted(client, auth_headers, board, title_length):
    title = "x" * title_length

    response = client.post(
        f"/boards/{board['id']}/tasks",
        json={"title": title},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["title"] == title


@pytest.mark.parametrize(
    "updates",
    [
        {"title": "abcd"},
        {"title": "x" * 301},
        {"title": None},
        {"is_done": None},
        {"is_done": "maybe"},
    ],
    ids=["short-title", "long-title", "null-title", "null-state", "invalid-state"],
)
def test_invalid_task_update_preserves_the_task(client, auth_headers, board, task, updates):
    path = f"/boards/{board['id']}/tasks/{task['id']}"

    response = client.patch(path, json=updates, headers=auth_headers)

    assert response.status_code == 422
    assert client.get(path, headers=auth_headers).json() == task
