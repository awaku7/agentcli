from __future__ import annotations

import json
from typing import Any

from . import get_tool_catalog
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _build_tool_catalog_spec() -> dict[str, Any]:
    return {
        "tool_level": 0,
        "type": "function",
        # "tool_genre": "basic",
        "function": {
            "name": "tool_catalog",
            "description": _(
                "tool.description",
                default=(
                    "Return a JSON catalog of available tools with ok, query, count, and tools fields so the model can discover relevant tools before requesting full tool definitions. Results include a 'loaded' field indicating if the tool is currently enabled."
                ),
            ),
            "x_search_terms": _(
                "x_search_terms",
                default=[
                    "catalog",
                    "tool catalog",
                    "discover tools",
                    "tool discovery",
                    "list all tools",
                ],
            ),
            "x_search_terms_en": [
                "catalog",
                "tool catalog",
                "discover tools",
                "tool discovery",
                "list all tools",
            ],
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": _(
                            "param.query.description",
                            default="Natural-language query describing the needed capability. Ignored when all=true.",
                        ),
                    },
                    "all": {
                        "type": "boolean",
                        "description": _(
                            "param.all.description",
                            default="If true, return all available tools (loaded + unloaded) without query filtering.",
                        ),
                        "default": False,
                    },
                },
            },
        },
    }


def _build_tool_load_spec() -> dict[str, Any]:
    return {
        "tool_level": 0,
        "type": "function",
        # tool_load is infrastructure; not controlled by genre toggling
        # "tool_genre": "basic",
        "function": {
            "name": "tool_load",
            "description": _(
                "tool_load.description",
                default="Load a tool by name so it becomes available for use. Use this after tool_catalog returns a tool with loaded=false. Returns the loaded tool info or an error if not found.",
            ),
            "x_search_terms": _(
                "x_search_terms",
                default=[
                    "tool_load",
                    "load tool",
                    "enable tool",
                    "activate tool",
                ],
            ),
            "x_search_terms_en": [
                "tool_load",
                "load tool",
                "enable tool",
                "activate tool",
            ],
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": _(
                            "param.name.description",
                            default="Name of the tool to load (e.g. 'generate_image', 'excel_ops').",
                        ),
                    },
                    "persist": {
                        "type": "integer",
                        "description": _(
                            "param.persist.description",
                            default="Number of uses before auto-unload. -1 = unlimited (session lifetime, default). 0 = do not load. >0 = unload after N uses.",
                        ),
                        "default": -1,
                    },
                },
                "required": ["name"],
            },
        },
    }


TOOL_SPEC: dict[str, Any] = _build_tool_catalog_spec()

# Also register tool_load as a second tool from this module
TOOL_SPEC_2: dict[str, Any] = _build_tool_load_spec()

# Also register unload_tool as a third tool from this module
def _build_tool_unload_spec() -> dict[str, Any]:
    return {
        "tool_level": 0,
        "type": "function",
        "function": {
            "name": "unload_tool",
            "description": _(
                "unload_tool.description",
                default="Unload a tool by name so it is no longer available for use. Use this to remove a previously loaded tool from the session.",
            ),
            "x_search_terms": [
                "unload_tool",
                "unload tool",
                "disable tool",
                "remove tool",
                "deactivate tool",
            ],
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": _(
                            "param.name.description",
                            default="Name of the tool to unload (e.g. 'browser_playwright', 'generate_image').",
                        ),
                    },
                },
                "required": ["name"],
            },
        },
    }


def _run_tool_unload(args: dict[str, Any]) -> str:
    name = str(args.get("name") or "").strip()
    if not name:
        return json.dumps({"ok": False, "error": _("msg.unload.missing_name", default="Missing 'name' parameter.")})

    try:
        from ._genre_control_util import disable_single_tool

        ok = disable_single_tool(name)
        if ok:
            return json.dumps(
                {
                    "ok": True,
                    "name": name,
                    "unloaded": True,
                    "message": _("msg.unload.ok", default="Tool '{name}' has been unloaded.", name=name),
                }
            )
        else:
            return json.dumps(
                {
                    "ok": False,
                    "name": name,
                    "unloaded": False,
                    "error": _("msg.unload.not_found", default="Tool '{name}' not found or not loaded.", name=name),
                }
            )
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})





# Also register unload_tool as a third tool from this module
TOOL_SPEC_3: dict[str, Any] = _build_tool_unload_spec()
TOOL_SPEC_3_RUNNER = _run_tool_unload

def _run_tool_catalog(args: dict[str, Any]) -> str:
    query = str(args.get("query") or "").strip()
    all_flag = bool(args.get("all", False))

    catalog = get_tool_catalog(query=query, max_results=12, all_items=all_flag)
    return json.dumps(
        {
            "ok": True,
            "query": query,
            "all": all_flag,
            "count": len(catalog),
            "tools": catalog,
        },
        ensure_ascii=False,
    )


def _run_tool_load(args: dict[str, Any]) -> str:
    name = str(args.get("name") or "").strip()
    if not name:
        return json.dumps({"ok": False, "error": _("msg.load.missing_name", default="Missing 'name' parameter.")})

    persist_raw = args.get("persist", -1)
    try:
        persist = int(persist_raw)
    except Exception:
        persist = -1

    try:
        from ._genre_control_util import enable_single_tool

        ok = enable_single_tool(name, persist=persist)
        if ok:
            persist_msg = (
                _("msg.load.persist_unlimited", default="unlimited (session)")
                if persist == -1
                else _("msg.load.persist_count", default="{n} use(s)", n=persist)
            )
            return json.dumps(
                {
                    "ok": True,
                    "name": name,
                    "loaded": True,
                    "persist": persist,
                    "message": _("msg.load.ok", default="Tool '{name}' has been loaded (persist={persist}) and is now available.", name=name, persist=persist_msg),
                }
            )
        else:
            return json.dumps(
                {
                    "ok": False,
                    "name": name,
                    "loaded": False,
                    "error": _("msg.load.not_found", default="Tool '{name}' not found.", name=name),
                }
            )
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})


def run_tool(args: dict[str, Any]) -> str:
    # Default dispatcher for TOOL_SPEC (tool_catalog) and TOOL_SPEC_2 (tool_load)
    # TOOL_SPEC_3 (unload_tool) has its own runner via TOOL_SPEC_3_RUNNER
    if "name" in args and "query" not in args:
        return _run_tool_load(args)
    return _run_tool_catalog(args)
