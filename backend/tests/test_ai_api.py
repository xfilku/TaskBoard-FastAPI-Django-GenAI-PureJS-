"""Verify preview authorization, model-output boundaries and atomic batch persistence."""

import json
from unittest.mock import Mock

import httpx
import pytest
from ai.dependencies import get_text_model
from ai.model import InvalidModelResponseError
from main import app
from models.board import Board
from models.task import Task
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


@pytest.fixture
def text_model():
    model = Mock(provider="ollama")
    model.generate.return_value = json.dumps({"tasks": [{"title": "Prepare the project outline"}]})
    app.dependency_overrides[get_text_model] = lambda: model
    yield model
    app.dependency_overrides.pop(get_text_model, None)


def preview(client, board, auth_headers, **changes):
    data = {"goal": "Build a portfolio website", "min_elements": 1, "max_elements": 5}
    data.update(changes)
    return client.post(f"/ai/boards/{board['id']}/plan-preview", json=data, headers=auth_headers)


def task_count(db_session):
    return db_session.scalar(select(func.count()).select_from(Task))


def test_preview_returns_editable_proposals_without_writing_tasks(
    client, board, auth_headers, text_model, db_session
):
    response = preview(client, board, auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "tasks": [{"title": "Prepare the project outline"}],
        "provider": "ollama",
    }
    assert task_count(db_session) == 0
    assert text_model.generate.call_count == 1


@pytest.mark.parametrize("status,owner", [(403, "other"), (404, "missing"), (401, "anonymous")])
def test_preview_never_generates_for_unauthorized_boards(
    client, board, auth_headers, other_auth_headers, text_model, status, owner
):
    target = {"id": 999999} if owner == "missing" else board
    headers = (
        other_auth_headers if owner == "other" else {} if owner == "anonymous" else auth_headers
    )
    response = preview(client, target, headers)
    assert response.status_code == status
    text_model.generate.assert_not_called()


def test_preview_rejects_legacy_unowned_boards(client, auth_headers, text_model, db_session):
    legacy = Board(name="Legacy board", owner_id=None)
    db_session.add(legacy)
    db_session.commit()
    response = preview(client, {"id": legacy.id}, auth_headers)
    assert response.status_code == 403
    text_model.generate.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    [
        {"goal": "    "},
        {"goal": "a" * 1001},
        {"goal": None},
        {"min_elements": 0},
        {"max_elements": 51},
        {"min_elements": 5, "max_elements": 2},
        {"min_elements": True},
        {"max_elements": "5"},
        {"max_elements": 1.5},
    ],
)
def test_invalid_planning_input_never_calls_model(client, board, auth_headers, text_model, changes):
    assert preview(client, board, auth_headers, **changes).status_code == 422
    text_model.generate.assert_not_called()


def test_prompt_contains_only_current_board_titles(
    client, board, auth_headers, text_model, task, db_session
):
    other = Board(name="Private other board", owner_id=None)
    db_session.add(other)
    db_session.flush()
    db_session.add(Task(title="Unrelated private task", board_id=other.id))
    db_session.commit()
    assert preview(client, board, auth_headers).status_code == 200
    prompt = text_model.generate.call_args.kwargs["prompt"]
    assert task["title"] in prompt
    assert "Unrelated private task" not in prompt


@pytest.mark.parametrize(
    "answer",
    [
        "not json",
        "```json\n{}\n```",
        "{}",
        '{"tasks": []}',
        json.dumps({"tasks": [{"title": "tiny"}]}),
        json.dumps({"tasks": [{"title": "x" * 301}]}),
        json.dumps({"tasks": [{"title": "Repeated task"}, {"title": "  REPEATED TASK  "}]}),
        json.dumps({"tasks": [{"title": f"Task number {index}"} for index in range(51)]}),
    ],
)
def test_untrusted_model_content_is_rejected_without_writes(
    client, board, auth_headers, text_model, db_session, answer
):
    text_model.generate.return_value = answer
    response = preview(client, board, auth_headers)
    assert response.status_code == 502
    assert task_count(db_session) == 0


def test_preview_rejects_proposals_already_on_the_board(
    client, board, auth_headers, task, text_model, db_session
):
    text_model.generate.return_value = json.dumps({"tasks": [{"title": "  WRITE   TESTS  "}]})
    response = preview(client, board, auth_headers)
    assert response.status_code == 502
    assert task_count(db_session) == 1


def test_requested_count_is_enforced(client, board, auth_headers, text_model):
    assert preview(client, board, auth_headers, min_elements=2).status_code == 502
    schema = text_model.generate.call_args.kwargs["response_schema"]
    assert schema["properties"]["tasks"]["minItems"] == 2
    assert schema["properties"]["tasks"]["maxItems"] == 5


@pytest.mark.parametrize(
    "error,status",
    [
        (httpx.ReadTimeout("private upstream detail"), 504),
        (httpx.ConnectError("private upstream detail"), 503),
        (InvalidModelResponseError("private upstream detail"), 502),
    ],
)
def test_provider_failures_have_safe_status_responses(
    client, board, auth_headers, text_model, error, status
):
    text_model.generate.side_effect = error
    response = preview(client, board, auth_headers)
    assert response.status_code == status
    assert "private upstream detail" not in response.text


def test_upstream_http_error_is_not_exposed(client, board, auth_headers, text_model):
    request = httpx.Request("POST", "http://model.test/api/chat")
    response = httpx.Response(500, request=request)
    text_model.generate.side_effect = httpx.HTTPStatusError(
        "private diagnostic", request=request, response=response
    )
    assert preview(client, board, auth_headers).status_code == 502


def test_provenance_comes_from_adapter_not_generated_json(client, board, auth_headers, text_model):
    text_model.generate.return_value = json.dumps(
        {"tasks": [{"title": "Valid proposed task"}], "provider": "demo"}
    )
    assert preview(client, board, auth_headers).json()["provider"] == "ollama"


def test_batch_creates_only_path_scoped_unfinished_tasks(client, board, auth_headers, db_session):
    response = client.post(
        f"/boards/{board['id']}/tasks/batch",
        headers=auth_headers,
        json={
            "tasks": [
                {"title": "  Reviewed task one  ", "is_done": True, "board_id": 999},
                {"title": "Reviewed task two"},
            ]
        },
    )
    assert response.status_code == 201
    assert len(response.json()) == 2
    assert all(
        task["board_id"] == board["id"] and task["is_done"] is False for task in response.json()
    )
    assert response.json()[0]["title"] == "Reviewed task one"
    assert task_count(db_session) == 2


@pytest.mark.parametrize(
    "tasks", [[], [{"title": "Valid task title"}, {"title": "no"}], [{"title": "Valid title"}] * 51]
)
def test_invalid_batches_are_rejected_without_partial_writes(
    client, board, auth_headers, db_session, tasks
):
    response = client.post(
        f"/boards/{board['id']}/tasks/batch", headers=auth_headers, json={"tasks": tasks}
    )
    assert response.status_code == 422
    assert task_count(db_session) == 0


def test_batch_cannot_write_to_another_users_board(client, board, other_auth_headers, db_session):
    response = client.post(
        f"/boards/{board['id']}/tasks/batch",
        headers=other_auth_headers,
        json={"tasks": [{"title": "Unauthorized task"}]},
    )
    assert response.status_code == 403
    assert task_count(db_session) == 0


def test_batch_rolls_back_when_commit_fails(client, board, auth_headers, db_session, monkeypatch):
    def fail_commit(self):
        raise SQLAlchemyError("Simulated commit failure")

    monkeypatch.setattr(Session, "commit", fail_commit)
    with pytest.raises(SQLAlchemyError):
        client.post(
            f"/boards/{board['id']}/tasks/batch",
            headers=auth_headers,
            json={"tasks": [{"title": "Must not persist"}]},
        )
    assert task_count(db_session) == 0
