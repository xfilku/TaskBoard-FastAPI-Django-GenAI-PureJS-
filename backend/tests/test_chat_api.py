"""Exercise task chat through FastAPI, SQLite and the Ollama HTTP adapter."""

import json
from datetime import date
from unittest.mock import patch

import httpx
import pytest
from ai.dependencies import get_chat_model
from ai.providers.ollama import OllamaTextModel
from main import app
from models.board import Board
from models.task import Task
from models.user import User
from sqlalchemy import func, select


@pytest.fixture
def ollama_post(monkeypatch):
    adapter = OllamaTextModel("http://model.test", "test-model", timeout=5)
    monkeypatch.setitem(app.dependency_overrides, get_chat_model, lambda: adapter)
    with patch("ai.providers.ollama.httpx.post") as post:
        yield post


@pytest.fixture
def chat_tasks(db_session, registered_user, board):
    other_owner = User(email="other-chat@example.com", password_hash="test-hash")
    second_board = Board(name="Second owned board", owner_id=registered_user["id"])
    foreign_board = Board(name="Another user's board")
    unowned_board = Board(name="Legacy board")
    db_session.add_all([other_owner, second_board, foreign_board, unowned_board])
    db_session.flush()
    foreign_board.owner_id = other_owner.id

    def task_row(title, board_id, day=None, *, is_done=False):
        deadline = date(2026, 12, day) if day is not None else None
        return Task(title=title, board_id=board_id, deadline=deadline, is_done=is_done)

    tasks = {
        "before": task_row("Earlier open task", board["id"], 9),
        "start": task_row("Start of range", board["id"], 10),
        "done": task_row("Completed task", board["id"], 12, is_done=True),
        "end": task_row("End of range", second_board.id, 14),
        "after": task_row("Later open task", second_board.id, 15),
        "undated": task_row("Task without a deadline", second_board.id),
        "foreign": task_row("Another user's task", foreign_board.id, 12),
        "unowned": task_row("Task on a legacy board", unowned_board.id, 12),
    }
    db_session.add_all(tasks.values())
    db_session.commit()
    return {key: task.id for key, task in tasks.items()}


def _ollama_reply(message, status=200):
    request = httpx.Request("POST", "http://model.test/api/chat")
    return httpx.Response(status, request=request, json={"message": message})


def _tool_reply(arguments, name="list_tasks"):
    return _ollama_reply(
        {
            "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
        }
    )


def _ask(client, auth_headers, question="Jakie zadania mam do zrobienia?"):
    return client.post("/ai/chat", json={"message": question}, headers=auth_headers)


def test_chat_requires_authentication_before_contacting_model(client, ollama_post):
    response = _ask(client, {})

    assert response.status_code == 401
    ollama_post.assert_not_called()


@pytest.mark.parametrize("question", ["   ", "x" * 1001], ids=["blank", "too-long"])
def test_chat_rejects_invalid_questions(client, auth_headers, ollama_post, question):
    response = _ask(client, auth_headers, question)

    assert response.status_code == 422
    ollama_post.assert_not_called()


def test_chat_trims_question_and_supplies_server_date(client, auth_headers, ollama_post):
    ollama_post.return_value = _ollama_reply({"content": "Cześć!"})
    with patch("ai.chat.service.date") as calendar:
        calendar.today.return_value = date(2026, 11, 16)
        response = _ask(client, auth_headers, "  Hej  ")

    assert response.status_code == 200
    assert response.json() == {"answer": "Cześć!"}
    ollama_post.assert_called_once()
    body = ollama_post.call_args.kwargs["json"]
    system, user = body["messages"]
    assert system["role"] == "system"
    assert "2026-11-16" in system["content"]
    assert user == {"role": "user", "content": "Hej"}
    assert body["tools"][0]["function"]["name"] == "list_tasks"


@pytest.mark.parametrize(
    "arguments,expected",
    [
        ({}, ["before", "start", "done", "end", "after", "undated"]),
        ({"is_done": False}, ["before", "start", "end", "after", "undated"]),
        ({"is_done": True}, ["done"]),
        (
            {"start_date": "2026-12-10", "end_date": "2026-12-14", "is_done": False},
            ["start", "end"],
        ),
        ({"end_date": "2026-12-14", "is_done": False}, ["before", "start", "end"]),
        ({"start_date": "2026-12-14", "end_date": "2026-12-14"}, ["end"]),
    ],
    ids=["all", "open", "done", "inclusive-range", "until", "same-day"],
)
def test_chat_uses_only_matching_owned_tasks(
    client, auth_headers, chat_tasks, db_session, ollama_post, arguments, expected
):
    ollama_post.side_effect = [
        _tool_reply(arguments),
        _ollama_reply({"content": "Oto Twoje zadania."}),
    ]

    response = _ask(client, auth_headers)

    assert response.status_code == 200
    assert response.json() == {"answer": "Oto Twoje zadania."}
    assert ollama_post.call_count == 2
    first, second = [call.kwargs["json"] for call in ollama_post.call_args_list]
    assert second["tools"] == []
    assert second["messages"][:2] == first["messages"]
    assistant, result = second["messages"][2:]
    assert assistant["role"] == "assistant"
    tool = assistant["tool_calls"][0]["function"]
    assert tool["name"] == "list_tasks"
    assert tool["arguments"] == arguments
    assert result["role"] == "tool"
    assert result["tool_name"] == "list_tasks"
    rows = json.loads(result["content"])
    assert [row["id"] for row in rows] == [chat_tasks[key] for key in expected]
    if "end" in expected:
        last_day_task = next(row for row in rows if row["id"] == chat_tasks["end"])
        assert last_day_task["deadline"] == "2026-12-14"
        assert last_day_task["board_name"] == "Second owned board"
    assert db_session.scalar(select(func.count()).select_from(Task)) == len(chat_tasks)


def test_chat_passes_empty_results_back_to_the_model(client, auth_headers, ollama_post):
    ollama_post.side_effect = [_tool_reply({}), _ollama_reply({"content": "Nie masz zadań."})]

    response = _ask(client, auth_headers)

    assert response.status_code == 200
    assert response.json() == {"answer": "Nie masz zadań."}
    result = ollama_post.call_args.kwargs["json"]["messages"][-1]
    assert json.loads(result["content"]) == []


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("list_tasks", {"start_date": "2026-12-15", "end_date": "2026-12-14"}),
        ("list_tasks", {"user_id": 123}),
        ("list_tasks", []),
        ("delete_tasks", {}),
    ],
    ids=["inverted-range", "unexpected-user-id", "malformed-arguments", "unknown-tool"],
)
def test_chat_returns_bad_gateway_for_invalid_model_tool_calls(
    client, auth_headers, ollama_post, name, arguments
):
    ollama_post.return_value = _tool_reply(arguments, name)

    response = _ask(client, auth_headers)

    assert response.status_code == 502
    ollama_post.assert_called_once()


def test_chat_stops_after_one_tool_execution(client, auth_headers, ollama_post):
    ollama_post.side_effect = [_tool_reply({}), _tool_reply({})]

    response = _ask(client, auth_headers)

    assert response.status_code == 502
    assert ollama_post.call_count == 2
    assert ollama_post.call_args.kwargs["json"]["tools"] == []


@pytest.mark.parametrize(
    "outcome,status",
    [
        (_ollama_reply({"content": "Internal service detail"}, status=500), 502),
        (httpx.ReadTimeout("Internal service detail"), 504),
        (httpx.ConnectError("Internal service detail"), 503),
    ],
    ids=["upstream-status", "timeout", "connection"],
)
def test_chat_maps_provider_failures_to_public_errors(
    client, auth_headers, ollama_post, outcome, status
):
    ollama_post.side_effect = [outcome]

    response = _ask(client, auth_headers)

    assert response.status_code == status
    assert "Internal service detail" not in response.text


def test_chat_reports_unavailable_model_in_demo_mode(client, auth_headers, monkeypatch):
    monkeypatch.setenv("TASKBOARD_AI_PROVIDER", "demo")
    with patch("ai.providers.ollama.httpx.post") as post:
        response = _ask(client, auth_headers)

    assert response.status_code == 503
    assert response.json()["detail"] == "Czat wymaga skonfigurowania modelu Ollama."
    post.assert_not_called()
