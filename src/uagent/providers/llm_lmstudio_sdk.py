"""Optional LM Studio Python SDK transport.

The SDK is intentionally opt-in because it has a different API surface from
OpenAI-compatible Chat Completions/Responses.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ..env_utils import env_get


class LMStudioSDKClient:
    """Small OpenAI-shaped adapter for the SDK's text chat API."""

    def __init__(self, model_name: str) -> None:
        import lmstudio as lms

        self._model = lms.llm(model_name or None)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(
        self,
        *,
        model: str = "",
        messages: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        del model, kwargs
        prompt = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in (messages or [])
            if isinstance(m, dict)
        )
        if stream:
            return self._stream(prompt)
        result = self._model.respond(prompt)
        text = str(getattr(result, "content", result) or "")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=text), finish_reason="stop"
                )
            ]
        )

    def _stream(self, prompt: str):
        for fragment in self._model.respond_stream(prompt):
            text = str(getattr(fragment, "content", fragment) or "")
            if text:
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
                )


def make_client(core: Any) -> LMStudioSDKClient:
    getter = getattr(core, "get_env", None)
    if callable(getter):
        model = getter("UAGENT_LMSTUDIO_DEPNAME") or "local-model"
    else:
        model = env_get("UAGENT_LMSTUDIO_DEPNAME", "local-model") or "local-model"
    return LMStudioSDKClient(model)
