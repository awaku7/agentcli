from typing import Any, Dict

from .env_utils import env_get


def apply_openrouter_extra_body(chat_kwargs: Dict[str, Any], *, provider: str) -> None:
    """Apply OpenRouter-only ChatCompletions extensions via extra_body."""

    if provider != "openrouter":
        return

    # Enable OpenRouter reasoning_details (Chat Completions extension)
    try:
        _raw_reason = (
            (env_get("UAGENT_OPENROUTER_REASONING", "1") or "").strip().lower()
        )
        if _raw_reason in ("1", "true", "yes", "on", "enabled"):
            _eb = chat_kwargs.get("extra_body")
            if not isinstance(_eb, dict):
                _eb = {}
            _eb["reasoning"] = {"enabled": True}
            chat_kwargs["extra_body"] = _eb
    except Exception:
        pass

    try:
        _raw_ignore = (env_get("UAGENT_OPENROUTER_PROVIDER_IGNORE", "") or "").strip()
        if _raw_ignore:
            _ignores = [s.strip() for s in _raw_ignore.split(",") if s.strip()]
            if _ignores:
                _eb = chat_kwargs.get("extra_body")
                if not isinstance(_eb, dict):
                    _eb = {}
                _eb["provider"] = {"ignore": _ignores}
                chat_kwargs["extra_body"] = _eb
                # Ensure we don't send unsupported top-level 'provider'
                chat_kwargs.pop("provider", None)
    except Exception:
        pass


def apply_openrouter_tool_schema_compat(
    chat_kwargs: Dict[str, Any], *, provider: str
) -> None:
    """Apply OpenRouter/Azure-proxy tool schema compatibility workarounds."""

    if provider != "openrouter":
        return

    # OpenRouter/Azure-proxy compatibility: some stacks validate tools[i].parameters
    # at the top-level (older/alternate schema), so mirror function.parameters.
    try:
        _new_tools = []
        for _t in chat_kwargs.get("tools") or []:
            if (
                isinstance(_t, dict)
                and "parameters" not in _t
                and isinstance(_t.get("function"), dict)
                and isinstance(_t["function"].get("parameters"), dict)
            ):
                _t2 = _t.copy()
                _t2["parameters"] = _t["function"]["parameters"]
                _new_tools.append(_t2)
            else:
                _new_tools.append(_t)
        chat_kwargs["tools"] = _new_tools
    except Exception:
        pass

    # Rename schema key to 'operations' for Azure/OpenAI-proxy compatibility; runtime accepts both.
    try:
        _fixed_tools = []
        for _t in chat_kwargs.get("tools") or []:
            if not (isinstance(_t, dict) and isinstance(_t.get("function"), dict)):
                _fixed_tools.append(_t)
                continue

            _t2 = _t.copy()
            _fn = _t2.get("function") or {}
            _fn2 = _fn.copy() if isinstance(_fn, dict) else _fn

            if isinstance(_fn2, dict) and _fn2.get("name") == "libcst_transform":
                _params = _fn2.get("parameters")
                if isinstance(_params, dict) and _params.get("type") == "object":
                    _props = _params.get("properties")
                    if (
                        isinstance(_props, dict)
                        and "ops" in _props
                        and "operations" not in _props
                    ):
                        _params2 = _params.copy()
                        _props2 = _props.copy()
                        _props2["operations"] = _props2.pop("ops")
                        _params2["properties"] = _props2
                        _req = _params2.get("required")
                        if isinstance(_req, list):
                            _params2["required"] = [
                                ("operations" if x == "ops" else x) for x in _req
                            ]
                        _fn2["parameters"] = _params2
                        _t2["function"] = _fn2
                        if isinstance(_t2.get("parameters"), dict):
                            _t2["parameters"] = _params2

            _fixed_tools.append(_t2)
        chat_kwargs["tools"] = _fixed_tools
    except Exception:
        pass

    # OpenRouter/Azure-proxy odd validator: handle_mcp_v2 rejects tool_arguments as required.
    # To avoid Azure/OpenAI proxy schema rejection, drop tool_arguments from schema surface.
    try:
        _fixed_tools = []
        for _t in chat_kwargs.get("tools") or []:
            if not (isinstance(_t, dict) and isinstance(_t.get("function"), dict)):
                _fixed_tools.append(_t)
                continue

            _t2 = _t.copy()
            _fn = _t2.get("function") or {}
            _fn2 = _fn.copy() if isinstance(_fn, dict) else _fn

            if isinstance(_fn2, dict) and _fn2.get("name") == "handle_mcp_v2":
                _params = _fn2.get("parameters")
                if isinstance(_params, dict) and _params.get("type") == "object":
                    _props = _params.get("properties")
                    if isinstance(_props, dict) and "tool_arguments" in _props:
                        _params2 = _params.copy()
                        _props2 = _props.copy()
                        _props2.pop("tool_arguments", None)
                        _params2["properties"] = _props2
                        # keep required as-is here; it will be re-normalized below.
                        _fn2["parameters"] = _params2
                        _t2["function"] = _fn2
                        if isinstance(_t2.get("parameters"), dict):
                            _t2["parameters"] = _params2

            _fixed_tools.append(_t2)
        chat_kwargs["tools"] = _fixed_tools
    except Exception:
        pass

    # OpenRouter/OpenAI-proxy strict schema: mcp_servers_add.env is a free-form mapping.
    # Some validators effectively disallow object properties without fixed 'properties', causing the
    # property to be dropped and then failing because 'required' still includes 'env'.
    # To avoid request rejection, hide 'env' from the tool schema surface for openrouter.
    try:
        _fixed_tools = []
        for _t in chat_kwargs.get("tools") or []:
            if not (isinstance(_t, dict) and isinstance(_t.get("function"), dict)):
                _fixed_tools.append(_t)
                continue

            _t2 = _t.copy()
            _fn = _t2.get("function") or {}
            _fn2 = _fn.copy() if isinstance(_fn, dict) else _fn

            if isinstance(_fn2, dict) and _fn2.get("name") == "mcp_servers_add":
                _params = _fn2.get("parameters")
                if isinstance(_params, dict) and _params.get("type") == "object":
                    _props = _params.get("properties")
                    if isinstance(_props, dict) and "env" in _props:
                        _params2 = _params.copy()
                        _props2 = _props.copy()
                        _props2.pop("env", None)
                        _params2["properties"] = _props2
                        _req = _params2.get("required")
                        if isinstance(_req, list):
                            _params2["required"] = [x for x in _req if x != "env"]
                        _fn2["parameters"] = _params2
                        _t2["function"] = _fn2
                        if isinstance(_t2.get("parameters"), dict):
                            _t2["parameters"] = _params2

            _fixed_tools.append(_t2)
        chat_kwargs["tools"] = _fixed_tools
    except Exception:
        pass

    # OpenRouter/Azure-proxy strict schema: required must include all property keys.
    # Some providers reject schemas where required is missing or incomplete.
    try:
        _fixed_tools = []
        for _t in chat_kwargs.get("tools") or []:
            if not (isinstance(_t, dict) and isinstance(_t.get("function"), dict)):
                _fixed_tools.append(_t)
                continue

            _t2 = _t.copy()
            _fn = _t2.get("function") or {}
            _fn2 = _fn.copy() if isinstance(_fn, dict) else _fn
            _params = _fn2.get("parameters") if isinstance(_fn2, dict) else None

            if isinstance(_params, dict) and _params.get("type") == "object":
                _props = _params.get("properties")
                if isinstance(_props, dict) and _props:
                    _params2 = _params.copy()
                    _params2["required"] = list(_props.keys())
                    _fn2["parameters"] = _params2
                    _t2["function"] = _fn2
                    if isinstance(_t2.get("parameters"), dict):
                        _t2["parameters"] = _params2

            _fixed_tools.append(_t2)
        chat_kwargs["tools"] = _fixed_tools
    except Exception:
        pass

    # OpenRouter/Azure-proxy strict schema: recursively enforce additionalProperties:false
    # for all object schemas (including nested objects/arrays/combinators).
    try:

        def _fix_schema(_s: Any) -> Any:
            if not isinstance(_s, dict):
                return _s

            _t = _s.get("type")
            if _t == "object":
                _props = _s.get("properties")
                if isinstance(_props, dict):
                    # Only enforce additionalProperties:false on objects that declare properties.
                    # Some strict validators reject object schemas with additionalProperties:false
                    # but without properties.
                    if "additionalProperties" not in _s:
                        _s = _s.copy()
                        _s["additionalProperties"] = False

                    _new_props = {}
                    _changed = False
                    for _k, _v in _props.items():
                        _v2 = _fix_schema(_v)
                        _new_props[_k] = _v2
                        _changed = _changed or (_v2 is not _v)
                    if _changed:
                        _s = _s.copy()
                        _s["properties"] = _new_props

            # arrays
            if _t == "array" and isinstance(_s.get("items"), (dict, list)):
                _items = _s.get("items")
                if isinstance(_items, dict):
                    _it2 = _fix_schema(_items)
                    if _it2 is not _items:
                        _s = _s.copy()
                        _s["items"] = _it2
                elif isinstance(_items, list):
                    _new_items = []
                    _changed = False
                    for _it in _items:
                        _it2 = _fix_schema(_it)
                        _new_items.append(_it2)
                        _changed = _changed or (_it2 is not _it)
                    if _changed:
                        _s = _s.copy()
                        _s["items"] = _new_items

            # combinators
            for _ck in ("anyOf", "oneOf", "allOf"):
                _cv = _s.get(_ck)
                if isinstance(_cv, list) and _cv:
                    _new_cv = []
                    _changed = False
                    for _it in _cv:
                        _it2 = _fix_schema(_it)
                        _new_cv.append(_it2)
                        _changed = _changed or (_it2 is not _it)
                    if _changed:
                        _s = _s.copy()
                        _s[_ck] = _new_cv

            return _s

        _tools2 = []
        for _t in chat_kwargs.get("tools") or []:
            if not (isinstance(_t, dict) and isinstance(_t.get("function"), dict)):
                _tools2.append(_t)
                continue
            _t2 = _t.copy()
            _fn = _t2.get("function") or {}
            _fn2 = _fn.copy() if isinstance(_fn, dict) else _fn
            _params = _fn2.get("parameters") if isinstance(_fn2, dict) else None
            if isinstance(_params, dict):
                _params2 = _fix_schema(_params)
                if _params2 is not _params:
                    _fn2["parameters"] = _params2
                    _t2["function"] = _fn2
                    if isinstance(_t2.get("parameters"), dict):
                        _t2["parameters"] = _params2
            _tools2.append(_t2)
        chat_kwargs["tools"] = _tools2
    except Exception:
        pass


def finalize_tool_schema_sync(chat_kwargs: Dict[str, Any]) -> None:
    """Final OpenRouter/Azure-proxy compatibility sync.

    - ensure tools[i].parameters always mirrors function.parameters
    - ensure required matches properties keys (no extra required keys)
    """

    try:
        _fixed_tools = []
        for _t in chat_kwargs.get("tools") or []:
            if not (isinstance(_t, dict) and isinstance(_t.get("function"), dict)):
                _fixed_tools.append(_t)
                continue

            _t2 = _t.copy()
            _fn = _t2.get("function") or {}
            _fn2 = _fn.copy() if isinstance(_fn, dict) else _fn
            _params = _fn2.get("parameters") if isinstance(_fn2, dict) else None

            if isinstance(_params, dict):
                # Always mirror to top-level parameters (some stacks validate only this)
                _t2["parameters"] = _params

                # Strict validator: required must be an array containing every property key,
                # and must not contain keys not present in properties.
                if _params.get("type") == "object":
                    _props = _params.get("properties")
                    if isinstance(_props, dict):
                        _params2 = _params.copy()
                        _params2["required"] = list(_props.keys())
                        _fn2["parameters"] = _params2
                        _t2["function"] = _fn2
                        _t2["parameters"] = _params2

            _fixed_tools.append(_t2)

        chat_kwargs["tools"] = _fixed_tools
    except Exception:
        pass


def apply_openrouter_fallback_models(
    chat_kwargs: Dict[str, Any],
    *,
    provider: str,
    depname: str,
) -> None:
    """Apply OpenRouter fallback models (openrouter/auto) support."""

    if provider != "openrouter":
        return
    if (depname or "").strip() != "openrouter/auto":
        return

    raw_fb = (env_get("UAGENT_OPENROUTER_FALLBACK_MODELS", "") or "").strip()
    if not raw_fb:
        return

    fb_models = [s.strip() for s in raw_fb.split(",") if s.strip()]
    if fb_models:
        chat_kwargs["models"] = fb_models
