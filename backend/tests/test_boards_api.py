import pytest
from models.board import Board
from models.task import Task
from sqlalchemy import select


def test_new_account_has_an_empty_board_list(client, auth_headers):
    response = client.get("/boards", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_board_owner_comes_from_the_token(client, auth_headers, registered_user, db_session):
    response = client.post(
        "/boards",
        json={"name": "New project", "owner_id": 999999},
        headers=auth_headers,
    )

    assert response.status_code == 201
    board = response.json()
    assert set(board) == {"deadline", "id", "name"}
    assert board["name"] == "New project"
    assert board["deadline"] is None
    assert db_session.get(Board, board["id"]).owner_id == registered_user["id"]


def test_board_creation_persists_deadline(client, auth_headers):
    deadline = "2026-11-30"
    response = client.post(
        "/boards",
        json={"name": "Project with a deadline", "deadline": deadline},
        headers=auth_headers,
    )

    assert response.status_code == 201
    board = response.json()
    assert board["deadline"] == deadline

    read = client.get(f"/boards/{board['id']}", headers=auth_headers)
    assert read.status_code == 200
    assert read.json()["deadline"] == deadline


def test_board_lists_are_isolated_between_accounts(
    client, board, auth_headers, other_auth_headers, db_session
):
    other_response = client.post(
        "/boards", json={"name": "Other project"}, headers=other_auth_headers
    )
    assert other_response.status_code == 201
    db_session.add(Board(name="Legacy board", owner_id=None))
    db_session.commit()

    owner_response = client.get("/boards", headers=auth_headers)
    other_list = client.get("/boards", headers=other_auth_headers)

    assert owner_response.status_code == other_list.status_code == 200
    assert owner_response.json() == [board]
    assert other_list.json() == [other_response.json()]


def test_owner_can_read_edit_and_delete_a_board(client, auth_headers, board, db_session):
    path = f"/boards/{board['id']}"
    original_owner_id = db_session.get(Board, board["id"]).owner_id

    response = client.get(path, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == board

    update = client.patch(
        path,
        json={"name": "Renamed project", "owner_id": 999999},
        headers=auth_headers,
    )
    expected = {"id": board["id"], "name": "Renamed project", "deadline": None}
    assert update.status_code == 200
    assert update.json() == expected
    assert client.get(path, headers=auth_headers).json() == expected
    db_session.expire_all()
    assert db_session.get(Board, board["id"]).owner_id == original_owner_id

    empty_update = client.patch(path, json={}, headers=auth_headers)
    assert empty_update.status_code == 200
    assert empty_update.json() == expected

    deletion = client.delete(path, headers=auth_headers)
    assert deletion.status_code == 204
    assert deletion.content == b""
    assert client.get(path, headers=auth_headers).status_code == 404
    assert client.delete(path, headers=auth_headers).status_code == 404


def test_board_patch_preserves_omitted_deadline_and_clears_explicit_null(client, auth_headers, board):
    path = f"/boards/{board['id']}"
    deadline = "2026-11-30"
    scheduled = client.patch(path, json={"deadline": deadline}, headers=auth_headers)
    assert scheduled.status_code == 200
    assert scheduled.json()["deadline"] == deadline

    renamed = client.patch(path, json={"name": "Renamed project"}, headers=auth_headers)
    assert renamed.status_code == 200
    assert renamed.json()["deadline"] == deadline

    cleared = client.patch(path, json={"deadline": None}, headers=auth_headers)
    assert cleared.status_code == 200
    assert cleared.json()["deadline"] is None
    assert client.get(path, headers=auth_headers).json()["deadline"] is None


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_another_account_cannot_access_a_board(
    client, board, auth_headers, other_auth_headers, method
):
    path = f"/boards/{board['id']}"

    denied = client.request(
        method,
        path,
        json={"name": "Unauthorized change"},
        headers=other_auth_headers,
    )
    owner_response = client.get(path, headers=auth_headers)

    assert denied.status_code == 403
    assert owner_response.status_code == 200
    assert owner_response.json() == board


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/boards", None),
        ("POST", "/boards", {"name": "Unauthorized project"}),
        ("GET", "/boards/{board_id}", None),
        ("PATCH", "/boards/{board_id}", {"name": "Unauthorized change"}),
        ("DELETE", "/boards/{board_id}", None),
    ],
)
def test_board_routes_require_authentication(client, board, method, path, payload):
    response = client.request(method, path.format(board_id=board["id"]), json=payload)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_board_list_rejects_an_invalid_token(client):
    response = client.get("/boards", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_missing_board_returns_not_found(client, auth_headers, method):
    response = client.request(
        method,
        "/boards/999999",
        json={"name": "Missing project"},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_legacy_board_without_an_owner_is_forbidden(client, auth_headers, db_session):
    legacy_board = Board(name="Legacy project", owner_id=None)
    db_session.add(legacy_board)
    db_session.commit()

    response = client.get(f"/boards/{legacy_board.id}", headers=auth_headers)

    assert response.status_code == 403


def test_deleting_a_nonempty_board_preserves_its_data(client, auth_headers, board, task):
    path = f"/boards/{board['id']}"
    task_path = f"{path}/tasks/{task['id']}"

    response = client.delete(path, headers=auth_headers)

    assert response.status_code == 409
    assert client.get(path, headers=auth_headers).json() == board
    assert client.get(task_path, headers=auth_headers).json() == task

    assert client.delete(task_path, headers=auth_headers).status_code == 204
    deletion = client.delete(path, headers=auth_headers)
    assert deletion.status_code == 204
    assert deletion.content == b""


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "AB"},
        {"name": "x" * 101},
        {"name": None},
        {},
        {"name": "New project", "deadline": "2026-02-30"},
    ],
    ids=["too-short", "too-long", "null", "missing", "invalid-deadline"],
)
def test_invalid_board_creation_is_rejected(client, auth_headers, db_session, payload):
    response = client.post("/boards", json=payload, headers=auth_headers)

    assert response.status_code == 422
    assert db_session.scalars(select(Board)).all() == []


@pytest.mark.parametrize("name_length", [3, 100])
def test_board_name_length_boundaries_are_accepted(client, auth_headers, name_length):
    name = "x" * name_length

    response = client.post("/boards", json={"name": name}, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["name"] == name


@pytest.mark.parametrize("name", ["AB", "x" * 101, None])
def test_invalid_board_update_preserves_the_original_name(client, auth_headers, board, name):
    path = f"/boards/{board['id']}"

    response = client.patch(path, json={"name": name}, headers=auth_headers)

    assert response.status_code == 422
    assert client.get(path, headers=auth_headers).json() == board


def test_board_access_denial_preserves_tasks(client, board, task, other_auth_headers, db_session):
    response = client.delete(f"/boards/{board['id']}", headers=other_auth_headers)

    assert response.status_code == 403
    assert db_session.get(Task, task["id"]) is not None
