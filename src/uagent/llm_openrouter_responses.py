from __future__ import annotations

import json
from typing import Any, Dict, List

from .env_utils import env_get


def apply_openrouter_responses_compat(
    resp_kwargs: Dict[str, Any],
    *,
    provider: str,
    depname: str,
) -> None:
    """Apply OpenRouter Responses-API compatibility workarounds.

    Mutates resp_kwargs in-place.

    Observed OpenRouter Responses quirks:
      - `input` must be a string (OpenAI/Azure-style list-of-messages is rejected).
      - `tools` is validated as a strict union of:
          - function tool (flat): {type:"function", name, parameters, description?}
          - built-in tools: {type:"openrouter:web_search"} / {type:"openrouter:datetime"}
      - Some routes reject tool_choice.
    """

    if provider != "openrouter":
        return

    _ = depname  # reserved for future model-specific quirks

    debug_env = (env_get("UAGENT_OPENROUTER_RESPONSES_DEBUG", "") or "").strip().lower()
    debug_enabled = debug_env in ("1", "true", "yes", "on")

    def _debug_dump(label: str, obj: Any) -> None:
        if not debug_enabled:
            return
        try:
            import os

            os.makedirs("./outputs", exist_ok=True)
            with open(
                "./outputs/openrouter_responses_debug.jsonl",
                "a",
                encoding="utf-8",
            ) as fp:
                fp.write(
                    json.dumps(
                        {"label": label, "obj": obj},
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )
        except Exception:
            pass

    # Some OpenRouter routes do not accept tool_choice.
    try:
        if resp_kwargs.get("tool_choice") == "auto":
            resp_kwargs.pop("tool_choice", None)
    except Exception:
        pass

    # OpenRouter rejects OpenAI-style Responses input (array-of-messages/content-items).
    # Convert to a plain string prompt.
    try:
        _in = resp_kwargs.get("input")

        def _content_item_to_text(it: Any) -> str:
            if it is None:
                return ""
            if isinstance(it, str):
                return it
            if isinstance(it, dict):
                t = it.get("type")
                if t in (
                    "text",
                    "input_text",
                    "output_text",
                    "summary_text",
                    "reasoning_text",
                ):
                    v = it.get("text")
                    return v if isinstance(v, str) else ("" if v is None else str(v))
                if t in ("image_url", "input_image"):
                    iu = it.get("image_url")
                    if isinstance(iu, str) and iu:
                        return f"[image:{iu}]"
                    if isinstance(iu, dict) and iu.get("url"):
                        return f"[image:{iu.get('url')}]"
                    return "[image]"
                return f"[{t or 'content'}]"
            if isinstance(it, list):
                parts = [_content_item_to_text(x) for x in it]
                return "\n".join([p for p in parts if (p or "").strip()])
            return str(it)

        if isinstance(_in, list):
            _debug_dump("input_before", _in)

            lines: List[str] = []
            for m in _in:
                if isinstance(m, dict) and "role" in m:
                    role = str(m.get("role") or "user").upper()
                    txt = _content_item_to_text(m.get("content"))
                    if txt.strip():
                        lines.append(f"[{role}]\n{txt}")
                else:
                    txt = _content_item_to_text(m)
                    if txt.strip():
                        lines.append(txt)

            flat = "\n\n".join(lines).strip()
            resp_kwargs["input"] = flat
            _debug_dump("input_after", flat)
        elif isinstance(_in, dict):
            resp_kwargs["input"] = json.dumps(_in, ensure_ascii=False, default=str)
    except Exception:
        pass

    # Hard guarantee: never send list/dict/etc as input to OpenRouter.
    try:
        _in2 = resp_kwargs.get("input")
        if not isinstance(_in2, str):
            try:
                resp_kwargs["input"] = json.dumps(_in2, ensure_ascii=False, default=str)
            except Exception:
                resp_kwargs["input"] = "" if _in2 is None else str(_in2)
    except Exception:
        resp_kwargs["input"] = ""

    # Tools compat: normalize into OpenRouter's Responses union shapes.
    try:

        def _fix_schema(s: Any) -> Any:
            if not isinstance(s, dict):
                return s

            t = s.get("type")
            if t == "object":
                props = s.get("properties")
                if isinstance(props, dict):
                    if "additionalProperties" not in s:
                        s = s.copy()
                        s["additionalProperties"] = False

                    new_props: Dict[str, Any] = {}
                    changed = False
                    for k, v in props.items():
                        v2 = _fix_schema(v)
                        new_props[k] = v2
                        changed = changed or (v2 is not v)
                    if changed:
                        s = s.copy()
                        s["properties"] = new_props

            if t == "array":
                items = s.get("items")
                if isinstance(items, dict):
                    it2 = _fix_schema(items)
                    if it2 is not items:
                        s = s.copy()
                        s["items"] = it2
                elif isinstance(items, list):
                    new_items = []
                    changed = False
                    for it in items:
                        it2 = _fix_schema(it)
                        new_items.append(it2)
                        changed = changed or (it2 is not it)
                    if changed:
                        s = s.copy()
                        s["items"] = new_items

            for ck in ("anyOf", "oneOf", "allOf"):
                cv = s.get(ck)
                if isinstance(cv, list) and cv:
                    new_cv = []
                    changed = False
                    for it in cv:
                        it2 = _fix_schema(it)
                        new_cv.append(it2)
                        changed = changed or (it2 is not it)
                    if changed:
                        s = s.copy()
                        s[ck] = new_cv

            return s

        raw_tools = resp_kwargs.get("tools")
        if isinstance(raw_tools, list) and raw_tools:
            _debug_dump("tools_before", raw_tools)

            builtin_map = {
                "web_search": "openrouter:web_search",
                "web_search_preview": "openrouter:web_search",
                "datetime": "openrouter:datetime",
                "openrouter:web_search": "openrouter:web_search",
                "openrouter:datetime": "openrouter:datetime",
            }

            new_tools: List[Dict[str, Any]] = []

            for t in raw_tools:
                if not isinstance(t, dict):
                    continue

                t2 = t.copy()
                ty = t2.get("type")

                # Built-in tools: keep only the type.
                mapped = builtin_map.get(ty)
                if mapped is not None:
                    new_tools.append({"type": mapped})
                    continue

                # Function tools: accept both nested (ChatCompletions) and flat (Responses) shapes.
                fn = (
                    t2.get("function") if isinstance(t2.get("function"), dict) else None
                )
                if isinstance(fn, dict):
                    if not (
                        isinstance(t2.get("name"), str)
                        and (t2.get("name") or "").strip()
                    ):
                        if (
                            isinstance(fn.get("name"), str)
                            and (fn.get("name") or "").strip()
                        ):
                            t2["name"] = fn.get("name")
                    if not isinstance(t2.get("description"), str):
                        if isinstance(fn.get("description"), str):
                            t2["description"] = fn.get("description")
                    if not isinstance(t2.get("parameters"), dict):
                        if isinstance(fn.get("parameters"), dict):
                            t2["parameters"] = fn.get("parameters")
                    t2.pop("function", None)

                # Force flat function-tool shape.
                t2["type"] = "function"

                name = t2.get("name")
                if not (isinstance(name, str) and name.strip()):
                    continue

                params = t2.get("parameters")
                if not isinstance(params, dict):
                    params = {"type": "object", "properties": {}}

                # Strictness: required must match properties keys.
                if params.get("type") == "object":
                    props = params.get("properties")
                    if isinstance(props, dict):
                        params = params.copy()
                        params["required"] = list(props.keys())

                t2["parameters"] = _fix_schema(params)

                # Description is optional.
                if "description" in t2 and not isinstance(t2.get("description"), str):
                    try:
                        t2["description"] = str(t2.get("description"))
                    except Exception:
                        t2.pop("description", None)

                new_tools.append(t2)

            if new_tools:
                resp_kwargs["tools"] = new_tools
                _debug_dump("tools_after", new_tools)
            else:
                resp_kwargs.pop("tools", None)

    except Exception:
        pass
