"""OpenAI hosted web-search tool for Responses API (OpenAI/Azure specific)."""

from __future__ import annotations

from typing import Any, Optional

from ..env_utils import env_get
from .responses_common import as_str, env_json_obj

_OPENAI_WEB_SEARCH_TYPE_ALIASES = {
    "web_search": "web_search",
    "web_search_preview": "web_search_preview",
    "openai:web_search": "web_search",
    "url_search": "web_search",
}

_OPENAI_WEB_SEARCH_TOOL_KEYS = {
    "filters",
    "search_context_size",
    "user_location",
    "external_web_access",
    "return_token_budget",
}


def normalize_openai_builtin_tool(t: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return an OpenAI Responses built-in tool spec, if *t* names one.

    Latest OpenAI docs recommend the hosted Responses tool:
      {"type": "web_search"}

    `web_search_preview` is still accepted for legacy integrations but lacks
    newer controls such as filters, external_web_access, and return_token_budget.
    """
    ty = as_str(t.get("type")).strip()
    mapped = _OPENAI_WEB_SEARCH_TYPE_ALIASES.get(ty)

    if mapped is None:
        fn = t.get("function") if isinstance(t.get("function"), dict) else None
        if isinstance(fn, dict):
            mapped = _OPENAI_WEB_SEARCH_TYPE_ALIASES.get(as_str(fn.get("name")).strip())

    if mapped is None:
        return None

    out: dict[str, Any] = {"type": mapped}
    for key in _OPENAI_WEB_SEARCH_TOOL_KEYS:
        if key in t:
            out[key] = t[key]

    if mapped == "web_search_preview":
        return {
            k: v
            for k, v in out.items()
            if k in ("type", "search_context_size", "user_location")
        }

    return out


def openai_web_search_tool_for_provider(
    provider: str,
) -> Optional[dict[str, Any]]:
    """Build hosted web search only for providers that expose this tool."""
    if (provider or "").strip().lower() not in {"openai", "azure"}:
        return None
    return openai_web_search_tool_from_env()


def openai_web_search_tool_from_env() -> Optional[dict[str, Any]]:
    """Build an optional OpenAI hosted web_search tool from env settings.

    Opt-in with UAGENT_OPENAI_WEB_SEARCH=1.
    """
    raw_enabled = (env_get("UAGENT_OPENAI_WEB_SEARCH") or "").strip().lower()
    if raw_enabled not in ("1", "true", "yes", "on"):
        return None

    requested_type = (env_get("UAGENT_OPENAI_WEB_SEARCH_TYPE") or "web_search").strip()
    tool_type = _OPENAI_WEB_SEARCH_TYPE_ALIASES.get(requested_type, "web_search")
    out: dict[str, Any] = {"type": tool_type}

    context_size = (
        (env_get("UAGENT_OPENAI_WEB_SEARCH_CONTEXT_SIZE") or "").strip().lower()
    )
    if context_size in ("low", "medium", "high"):
        out["search_context_size"] = context_size

    user_location = env_json_obj("UAGENT_OPENAI_WEB_SEARCH_USER_LOCATION_JSON")
    if user_location is not None:
        out["user_location"] = user_location

    if tool_type == "web_search":
        filters = env_json_obj("UAGENT_OPENAI_WEB_SEARCH_FILTERS_JSON")
        if filters is not None:
            out["filters"] = filters

        external_web_access = (
            (env_get("UAGENT_OPENAI_WEB_SEARCH_EXTERNAL_WEB_ACCESS") or "")
            .strip()
            .lower()
        )
        if external_web_access in ("1", "true", "yes", "on"):
            out["external_web_access"] = True
        elif external_web_access in ("0", "false", "no", "off"):
            out["external_web_access"] = False

        return_token_budget = (
            (env_get("UAGENT_OPENAI_WEB_SEARCH_RETURN_TOKEN_BUDGET") or "")
            .strip()
            .lower()
        )
        if return_token_budget in ("default", "unlimited"):
            out["return_token_budget"] = return_token_budget

    return out
