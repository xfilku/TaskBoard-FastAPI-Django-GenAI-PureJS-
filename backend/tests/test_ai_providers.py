"""Exercise local provider configuration, response parsing and deterministic demo behavior."""

import json
from unittest.mock import patch

import httpx
import pytest
from ai.demo import DemoTextModel
from ai.dependencies import get_text_model
from ai.model import InvalidModelResponseError
from ai.planner import build_plan_prompt, generate_plan
from ai.providers.ollama import OllamaTextModel
from fastapi import HTTPException


@pytest.mark.parametrize("minimum,maximum", [(1, 1), (3, 3), (7, 10), (50, 50)])
def test_demo_honors_requested_count_without_a_model_service(minimum, maximum):
    plan = generate_plan("demo goal", DemoTextModel(), minimum, maximum)
    assert minimum <= len(plan.tasks) <= maximum
    assert len({task.title for task in plan.tasks}) == len(plan.tasks)
    assert plan.provider == "demo"


def test_prompt_preserves_user_data_as_json():
    goal = 'A goal with "quotes"\nand instructions in its text'
    titles = ['Title "one"', "Second title"]
    prompt = build_plan_prompt(goal, 2, 5, titles)
    data = json.loads(prompt.split("Dane wejściowe:\n", 1)[1])
    assert data == {"goal": goal, "min_elements": 2, "max_elements": 5, "existing_titles": titles}
    assert "2 do 5" in prompt


def test_missing_provider_defaults_to_demo(monkeypatch):
    monkeypatch.delenv("TASKBOARD_AI_PROVIDER", raising=False)
    assert isinstance(get_text_model(), DemoTextModel)


@pytest.mark.parametrize(
    "name,value",
    [
        ("TASKBOARD_AI_PROVIDER", "unknown"),
        ("TASKBOARD_AI_MODEL", ""),
        ("TASKBOARD_AI_TIMEOUT", "invalid"),
        ("TASKBOARD_AI_TIMEOUT", "nan"),
        ("TASKBOARD_AI_TIMEOUT", "inf"),
        ("TASKBOARD_AI_TIMEOUT", "0"),
        ("TASKBOARD_AI_TIMEOUT", "301"),
        ("TASKBOARD_AI_BASE_URL", "file:///tmp/model"),
        ("TASKBOARD_AI_BASE_URL", "http://"),
        ("TASKBOARD_AI_BASE_URL", "http://user:password@localhost"),
        ("TASKBOARD_AI_BASE_URL", "http://localhost:invalid"),
    ],
)
def test_bad_configuration_returns_service_unavailable(monkeypatch, name, value):
    monkeypatch.setenv("TASKBOARD_AI_PROVIDER", "ollama")
    monkeypatch.setenv("TASKBOARD_AI_MODEL", "local-model")
    monkeypatch.setenv("TASKBOARD_AI_TIMEOUT", "60")
    monkeypatch.setenv("TASKBOARD_AI_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv(name, value)
    with pytest.raises(HTTPException) as error:
        get_text_model()
    assert error.value.status_code == 503


def test_ollama_adapter_is_built_without_contacting_service(monkeypatch):
    monkeypatch.setenv("TASKBOARD_AI_PROVIDER", " OLLAMA ")
    monkeypatch.setenv("TASKBOARD_AI_MODEL", "local-model")
    with patch("ai.providers.ollama.httpx.post") as post:
        model = get_text_model()
    assert isinstance(model, OllamaTextModel)
    post.assert_not_called()


def test_ollama_sends_json_schema_and_disables_streaming():
    request = httpx.Request("POST", "http://model.test/api/chat")
    response = httpx.Response(200, request=request, json={"message": {"content": '{"tasks": []}'}})
    schema = {"type": "object"}
    with patch("ai.providers.ollama.httpx.post", return_value=response) as post:
        text = OllamaTextModel("http://model.test/", "local-model", 60).generate("Goal", schema)
    assert text == '{"tasks": []}'
    data = post.call_args.kwargs
    assert data["url"] == "http://model.test/api/chat"
    assert data["timeout"] == 60
    assert data["json"]["format"] == schema
    assert data["json"]["stream"] is False
    assert data["json"]["messages"] == [{"role": "user", "content": "Goal"}]


@pytest.mark.parametrize(
    "body",
    [{}, [], None, {"message": None}, {"message": {"content": 3}}, {"message": {"content": "  "}}],
)
def test_malformed_ollama_envelopes_raise_a_safe_provider_error(body):
    request = httpx.Request("POST", "http://model.test/api/chat")
    response = httpx.Response(200, request=request, content=json.dumps(body))
    with (
        patch("ai.providers.ollama.httpx.post", return_value=response),
        pytest.raises(InvalidModelResponseError),
    ):
        OllamaTextModel("http://model.test", "model", 60).generate("Goal", {})


def test_non_json_ollama_response_is_a_provider_error():
    request = httpx.Request("POST", "http://model.test/api/chat")
    response = httpx.Response(200, request=request, text="not json")
    with (
        patch("ai.providers.ollama.httpx.post", return_value=response),
        pytest.raises(InvalidModelResponseError),
    ):
        OllamaTextModel("http://model.test", "model", 60).generate("Goal", {})
