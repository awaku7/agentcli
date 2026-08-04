"""Management operations for OpenAI-compatible Responses APIs.

The normal Responses request/streaming path lives in ``llm_round_helpers``.
This module isolates lifecycle operations so provider capability checks and
fallback behavior do not leak into the generation loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class UnsupportedResponsesOperation(RuntimeError):
    """Raised when a provider does not advertise a management operation."""

    def __init__(self, operation: str, provider: str) -> None:
        self.operation = operation
        self.provider = provider
        super().__init__(
            f"Responses API operation '{operation}' is not supported by "
            f"provider '{provider}'"
        )


@dataclass(frozen=True)
class ResponsesCapabilities:
    create: bool = False
    streaming: bool = False
    retrieve: bool = False
    cancel: bool = False
    delete: bool = False
    list_input_items: bool = False
    count_input_tokens: bool = False
    compact: bool = False
    previous_response_id: bool = False


# Conservative defaults: only OpenAI/Azure management operations are enabled
# until another provider has been verified against the live endpoint.
_CAPABILITIES: dict[str, ResponsesCapabilities] = {
    "openai": ResponsesCapabilities(
        create=True,
        streaming=True,
        retrieve=True,
        cancel=True,
        delete=True,
        list_input_items=True,
        count_input_tokens=True,
        compact=True,
        previous_response_id=True,
    ),
    "azure": ResponsesCapabilities(
        create=True,
        streaming=True,
        retrieve=True,
        cancel=True,
        delete=True,
        list_input_items=True,
        count_input_tokens=True,
        compact=True,
        previous_response_id=True,
    ),
    "openrouter": ResponsesCapabilities(create=True, streaming=True),
    "deepseek": ResponsesCapabilities(create=True, streaming=True),
    "bedrock": ResponsesCapabilities(create=True, streaming=True),
    "ollama": ResponsesCapabilities(create=True, streaming=True),
    "alibaba": ResponsesCapabilities(create=True, streaming=True),
    "lmstudio": ResponsesCapabilities(create=True, streaming=True),
    "sakana": ResponsesCapabilities(create=True, streaming=True),
}


def get_responses_capabilities(provider: str) -> ResponsesCapabilities:
    """Return conservative Responses capabilities for a provider."""
    return _CAPABILITIES.get((provider or "").strip().lower(), ResponsesCapabilities())


def cancel_active_response(core: Any) -> bool:
    """Best-effort cancellation of the Response currently tracked on ``core``.

    Returns True only when the provider accepted the cancel request. Missing
    state, unsupported providers, and API errors are deliberately non-fatal;
    the caller still performs the existing local interrupt flow.
    """
    state = getattr(core, "responses_state", None)
    response_id = state.get("active_response_id") if isinstance(state, dict) else None
    client = getattr(core, "_responses_client", None)
    provider = getattr(core, "_responses_provider", "")
    model = getattr(core, "_responses_model", "")
    if not response_id or client is None:
        return False
    try:
        ResponsesManager(client, provider=provider, model=model).cancel(response_id)
    except Exception:
        return False
    try:
        from ..core import clear_responses_continuation

        clear_responses_continuation()
    except Exception:
        pass
    return True


class ResponsesManager:
    """Provider-neutral wrapper around ``client.responses`` management APIs."""

    def __init__(self, client: Any, *, provider: str, model: str = "") -> None:
        self.client = client
        self.provider = (provider or "").strip().lower()
        self.model = model or ""
        self.capabilities = get_responses_capabilities(self.provider)

    def _require(self, operation: str) -> Any:
        if not getattr(self.capabilities, operation, False):
            raise UnsupportedResponsesOperation(operation, self.provider)
        responses = getattr(self.client, "responses", None)
        if responses is None:
            raise UnsupportedResponsesOperation(operation, self.provider)
        return responses

    def retrieve(self, response_id: str) -> Any:
        return self._require("retrieve").retrieve(response_id)

    def cancel(self, response_id: str) -> Any:
        return self._require("cancel").cancel(response_id)

    def delete(self, response_id: str) -> Any:
        return self._require("delete").delete(response_id)

    def list_input_items(
        self, response_id: str, *, limit: int | None = None
    ) -> Any:
        responses = self._require("list_input_items")
        kwargs = {} if limit is None else {"limit": limit}
        return responses.input_items.list(response_id, **kwargs)

    def count_input_tokens(
        self,
        *,
        input: Any,
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> Any:
        responses = self._require("count_input_tokens")
        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "input": input,
        }
        if tools is not None:
            kwargs["tools"] = tools
        return responses.input_tokens.count(**kwargs)

    def compact(self, response_id: str, *, input: Any = None) -> Any:
        responses = self._require("compact")
        kwargs: dict[str, Any] = {"response_id": response_id}
        if input is not None:
            kwargs["input"] = input
        compact_fn = getattr(responses, "compact", None)
        if not callable(compact_fn):
            raise UnsupportedResponsesOperation("compact", self.provider)
        return compact_fn(**kwargs)
