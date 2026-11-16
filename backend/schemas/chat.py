"""Validate the HTTP request and response for task chat."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints

ChatMessage = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


class ChatRequest(BaseModel):
    """Accept a single question from an authenticated user."""

    message: ChatMessage


class ChatResponse(BaseModel):
    """Return the final answer for one question."""

    answer: str
