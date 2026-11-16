"""Adapt Ollama's chat endpoint to the planning and task chat contracts."""

from typing import Any

import httpx

from ai.chat.chat_model import ToolCall
from ai.model import InvalidModelResponseError

INVALID_RESPONSE = "Model zwrócił nieprawidłową odpowiedź."


class OllamaTextModel:
    """Generate plans and handle tool calls through a configured Ollama instance."""

    provider = "ollama"

    def __init__(self, base_url: str, model_name: str, timeout: float) -> None:
        """Keep connection settings without contacting the model during construction."""
        self.base_url = base_url
        self.model_name = model_name
        self.timeout = timeout

    def generate(self, prompt: str, response_schema: dict[str, Any]) -> str:
        """Generate text constrained by the planner's JSON schema."""
        message = self._request_message(
            [{"role": "user", "content": prompt}], format=response_schema
        )
        return _read_content(message)

    def chat(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> str | ToolCall:
        """Return text or a tool call from Ollama."""
        ollama_tools = [{"type": "function", "function": tool} for tool in tools]
        ollama_messages: list[dict[str, object]] = []
        for message in messages:
            call = message.get("tool_call")
            if isinstance(call, ToolCall):
                ollama_messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "index": 0,
                                    "name": call.name,
                                    "arguments": call.arguments,
                                },
                            },
                        ],
                    }
                )
            else:
                ollama_messages.append(message)

        message = self._request_message(ollama_messages, tools=ollama_tools)
        tool_calls = message.get("tool_calls")
        if tool_calls is None or tool_calls == []:
            return _read_content(message)
        if not isinstance(tool_calls, list):
            raise InvalidModelResponseError(INVALID_RESPONSE)

        try:
            function = tool_calls[0]["function"]
            name = function["name"]
            arguments = function["arguments"]
        except (KeyError, TypeError) as exc:
            raise InvalidModelResponseError(INVALID_RESPONSE) from exc
        if not isinstance(name, str) or not name.strip() or not isinstance(arguments, dict):
            raise InvalidModelResponseError(INVALID_RESPONSE)
        return ToolCall(name=name, arguments=arguments)

    def _request_message(
        self, messages: list[dict[str, object]], **payload_fields: object
    ) -> dict[str, Any]:
        response = httpx.post(
            url=f"{self.base_url.rstrip('/')}/api/chat",
            timeout=self.timeout,
            json={
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0},
                **payload_fields,
            },
        )
        response.raise_for_status()

        try:
            message = response.json()["message"]
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidModelResponseError(INVALID_RESPONSE) from exc
        if not isinstance(message, dict):
            raise InvalidModelResponseError(INVALID_RESPONSE)
        return message


def _read_content(message: dict[str, Any]) -> str:
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise InvalidModelResponseError(INVALID_RESPONSE)
    return content
