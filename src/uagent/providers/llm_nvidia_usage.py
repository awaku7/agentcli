"""NVIDIA NIM Chat usage option compatibility.

NIM model routes do not all support OpenAI stream_options. Retry only when
the endpoint explicitly rejects that option before returning a stream.
"""

from __future__ import annotations

from typing import Any, Mapping


def _unsupported_stream_options(error: Exception) -> bool:
    status = getattr(error, "status_code", None)
    if status not in (400, 422):
        return False
    body = getattr(error, "body", None)
    text = str(error)
    if body is not None:
        text += " " + str(body)
    lowered = text.lower()
    markers = (
        "unsupported",
        "not supported",
        "unrecognized",
        "unknown",
        "extra",
        "not permitted",
        "not allowed",
        "invalid",
        "unexpected",
        "forbidden",
        "reject",
    )
    return "stream_options" in lowered and any(
        marker in lowered for marker in markers
    )


def create_nvidia_chat_completion(
    client: Any, payload: Mapping[str, Any], *, streaming: bool
) -> Any:
    """Only retry before stream consumption and on explicit option rejection."""
    kwargs = dict(payload)
    try:
        return client.chat.completions.create(**kwargs, stream=streaming)
    except Exception as exc:
        if "stream_options" not in kwargs or not _unsupported_stream_options(exc):
            raise
    kwargs.pop("stream_options")
    return client.chat.completions.create(**kwargs, stream=streaming)
