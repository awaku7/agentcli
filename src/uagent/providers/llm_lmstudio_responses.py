"""LM Studio OpenAI-compatible Responses API transport."""

from __future__ import annotations

from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..env_utils import env_get


def endpoint_available(core: Any = None, *, timeout: float = 2.0) -> bool:
    """Check whether the LM Studio server exposes ``/v1/responses``.

    The endpoint was added in LM Studio v0.3.29. LM Studio does not expose a
    stable version endpoint, so an endpoint probe is more reliable than
    guessing from a locally installed desktop version.
    """
    getter = getattr(core, "get_env", None)

    def get(name: str, default: str = "") -> str:
        if callable(getter):
            return str(getter(name) or default)
        return str(env_get(name, default) or default)

    base = get("UAGENT_LMSTUDIO_BASE_URL", "http://localhost:1234/v1").rstrip("/")
    try:
        request = Request(f"{base}/responses", method="OPTIONS")
        with urlopen(request, timeout=timeout) as response:
            return int(getattr(response, "status", 200)) < 500
    except HTTPError as exc:
        # 400/405 means the route exists; 404/501 means an old server.
        return exc.code not in {404, 501}
    except (URLError, OSError, ValueError):
        return False


def prepare_kwargs(kwargs: dict[str, Any]) -> None:
    """Remove Chat Completions-only fields before calling Responses."""
    if kwargs.pop("_lmstudio_transport", None) != "responses":
        return
    kwargs.pop("messages", None)
    kwargs.pop("max_tokens", None)
    kwargs.pop("stream_options", None)
