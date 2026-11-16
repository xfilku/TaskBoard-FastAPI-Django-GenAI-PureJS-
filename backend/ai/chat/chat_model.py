"""Define the interface between task chat and its model adapters."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ToolCall:
    """Record the name and arguments of a tool requested by a model."""

    name: str
    arguments: dict[str, object]


class ChatModel(Protocol):
    """Accept conversation messages and offer the supplied tools to the model."""

    def chat(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> str | ToolCall:
        """Return an answer or request a tool call."""
        ...
