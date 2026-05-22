from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class A2AMessage(BaseModel):
    role: str = Field(..., description="user|assistant")
    content: Any = Field(..., description="string or structured content")


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
