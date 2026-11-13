"""Adapt Ollama's non-streaming chat endpoint to the planner's text model contract."""

from typing import Any

import httpx

from ai.model import InvalidModelResponseError


class OllamaTextModel:
    """Generate schema-constrained JSON through a configured Ollama instance."""

    provider = "ollama"

    def __init__(self, base_url: str, model_name: str, timeout: float) -> None:
        """Keep connection settings without contacting the model during construction."""
        self.base_url = base_url
        self.model_name = model_name
        self.timeout = timeout

    def generate(self, prompt: str, response_schema: dict[str, Any]) -> str:
        """Return message content, preserving transport errors and validating its envelope."""
        response = httpx.post(
            url=f"{self.base_url.rstrip('/')}/api/chat",
            timeout=self.timeout,
            json={
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "format": response_schema,
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        response.raise_for_status()
        try:
            body = response.json()
            content = body["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Missing text content.")
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidModelResponseError("Model zwrócił nieprawidłową odpowiedź.") from exc
        return content
