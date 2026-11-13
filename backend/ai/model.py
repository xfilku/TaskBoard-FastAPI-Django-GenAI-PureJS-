"""Define the text generation contract shared by planner providers."""

from typing import Any, Protocol


class InvalidModelResponseError(Exception):
    """Signal a malformed provider response without exposing its raw content."""


class TextModel(Protocol):
    """Generate structured task proposals without persisting application data."""

    provider: str

    def generate(self, prompt: str, response_schema: dict[str, Any]) -> str:
        """Return JSON text matching the supplied schema or raise a provider error."""
        ...
