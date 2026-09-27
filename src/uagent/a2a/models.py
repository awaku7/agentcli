from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:
    from .._pip_auto import install_with_status as _install_pd

    _install_pd("pydantic")
    from pydantic import BaseModel, Field


_A2A_INPUT_CONTENT_IS_EXACT_TEXT: ContextVar[bool] = ContextVar(
    "uagent_a2a_input_content_is_exact_text",
    default=False,
)


def current_a2a_input_content_is_exact_text() -> bool:
    """Whether the current A2A request arrived with exact plain-string content."""

    return bool(_A2A_INPUT_CONTENT_IS_EXACT_TEXT.get())


class A2AMessage(BaseModel):
    role: str = Field(..., description="user|assistant")
    content: Any = Field(..., description="string or structured content")

    def model_post_init(self, __context: Any) -> None:
        # Preserve request provenance before server.py stringifies content for the
        # existing engine contract. Structured/file content must never be promoted
        # into the trusted plain-text capture path merely because str() can render it.
        _A2A_INPUT_CONTENT_IS_EXACT_TEXT.set(type(self.content) is str)


class SendMessageRequest(BaseModel):
    # Best-effort subset. We also accept extra fields.
    message: A2AMessage
    returnImmediately: Optional[bool] = None

    model_config = {"extra": "allow"}


class Task(BaseModel):
    id: str
    status: str
    createdAt: str
    updatedAt: str

    inputMessage: Optional[dict[str, Any]] = None
    outputMessage: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None


class SendMessageResponse(BaseModel):
    task: Task


class ListTasksResponse(BaseModel):
    tasks: list[Task]


def task_to_model(rec: Any) -> Task:
    return Task(
        id=rec.id,
        status=rec.status,
        createdAt=rec.created_at,
        updatedAt=rec.updated_at,
        inputMessage=rec.input_message,
        outputMessage=rec.output_message,
        error=rec.error,
    )
