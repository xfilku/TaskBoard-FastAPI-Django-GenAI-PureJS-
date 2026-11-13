"""Resolve and validate the configured AI provider for each planning request."""

import math
import os
from urllib.parse import urlsplit

from fastapi import HTTPException

from ai.demo import DemoTextModel
from ai.model import TextModel
from ai.providers.ollama import OllamaTextModel


def get_text_model() -> TextModel:
    """Build the selected adapter or report unavailable configuration as HTTP 503.

    Configuration errors never reveal environment values or trigger an implicit
    fallback to demo mode. Demo mode must be selected deliberately or by default.
    """
    provider = os.getenv("TASKBOARD_AI_PROVIDER", "demo").strip().lower()
    if provider == "demo":
        return DemoTextModel()
    if provider != "ollama":
        raise HTTPException(503, "Nieprawidłowa konfiguracja dostawcy AI.")
    model_name = os.getenv("TASKBOARD_AI_MODEL", "").strip()
    base_url = os.getenv("TASKBOARD_AI_BASE_URL", "http://127.0.0.1:11434").strip()
    try:
        timeout = float(os.getenv("TASKBOARD_AI_TIMEOUT", "60"))
        parsed = urlsplit(base_url)
        _ = parsed.port  # Validate malformed or out-of-range ports before contacting HTTPX.
        valid_url = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        valid_url = valid_url and not parsed.username and not parsed.password
        valid_timeout = math.isfinite(timeout) and 1 <= timeout <= 300
    except ValueError as exc:
        raise HTTPException(503, "Nieprawidłowa konfiguracja połączenia z AI.") from exc
    if not model_name or not valid_url or not valid_timeout:
        raise HTTPException(503, "Uzupełnij konfigurację lokalnego modelu AI.")
    return OllamaTextModel(base_url=base_url, model_name=model_name, timeout=timeout)
