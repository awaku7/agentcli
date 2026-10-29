"""Runtime compatibility for vLLM's Responses API input schema."""

from __future__ import annotations

import json
from typing import Any, Mapping

_CLIENT_STRING_INPUT_FLAG = "_uagent_vllm_responses_string_input"


def is_vllm_string_input_schema_error(error: BaseException) -> bool:
    """Return whether a vLLM error says Responses input must be a string.

    vLLM-compatible hosted endpoints differ by version. Some accept the full
    Responses input-item array, while others validate only a string, including
    string-only message content. Match that specific validation failure rather
    than treating arbitrary bad requests as a compatibility signal.
    """
    parts = [str(error)]
    body = getattr(error, "body", None)
    if body is not None:
        try:
            parts.append(json.dumps(body, ensure_ascii=False, default=str))
        except Exception:
            parts.append(str(body))
    response = getattr(error, "response", None)
    if response is not None:
        try:
            parts.append(str(getattr(response, "text", "") or ""))
        except Exception:
            pass
    text = "\n".join(parts).lower()
    return "body.input" in text and "input should be a valid string" in text


def _stringify_input(input_value: Any) -> str:
    """Encode structured Responses items as a JSON transcript."""
    if isinstance(input_value, str):
        return input_value
    try:
        serialized = json.dumps(input_value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        serialized = str(input_value)
    return (
        "Conversation input encoded as JSON using OpenAI Responses input-item "
        "shapes:\n" + serialized
    )


def create_vllm_responses(
    client: Any,
    request: Mapping[str, Any],
    *,
    provider: str,
    stream: bool | None = None,
) -> Any:
    """Create a Responses request, retrying with string input on schema mismatch.

    The normal structured request is always attempted first. If a vLLM
    endpoint specifically rejects the input-item array because it requires a
    string, retry the same Responses request with the conversation encoded as
    a JSON transcript. Tool definitions and other options remain unchanged.
    The observed endpoint quirk is cached on the client for subsequent calls.
    """
    params = dict(request)
    if stream is not None:
        params["stream"] = stream

    if (provider or "").strip().lower() != "vllm":
        return client.responses.create(**params)

    if getattr(client, _CLIENT_STRING_INPUT_FLAG, False):
        params["input"] = _stringify_input(params.get("input", ""))
        return client.responses.create(**params)

    try:
        return client.responses.create(**params)
    except Exception as exc:
        if not isinstance(
            params.get("input"), list
        ) or not is_vllm_string_input_schema_error(exc):
            raise

        params["input"] = _stringify_input(params["input"])
        try:
            setattr(client, _CLIENT_STRING_INPUT_FLAG, True)
        except Exception:
            pass
        return client.responses.create(**params)
