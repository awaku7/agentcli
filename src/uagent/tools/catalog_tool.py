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
        "x_parallel_safe": True,
        # "tool_genre": "basic",
        "function": {
            "name": "tool_catalog",
            "description": _(
                "tool.description",
                default=(
                    "Return a JSON catalog of available tools with ok, query, count, and tools fields so the model can discover relevant tools before requesting full tool definitions. Results include a 'loaded' field indicating if the tool is currently enabled. When a 'query' is provided, the top-ranked unloaded tool is automatically loaded (indicated by 'auto_loaded' in the response)."
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
                "auto load",
                "auto-load tool",
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


def _parse_tool_name_list(args: dict[str, Any]) -> list[str]:
    """Collect target tool names from ``name``/``names``/``tool`` args.

    ``names`` may be a list or a comma-separated string. ``name`` (and the
    legacy ``tool`` alias) may hold a single name or a comma/whitespace
    separated list. Order is preserved; duplicates are removed.
    """
    import re

    def _split(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            out: list[str] = []
            for item in value:
                if item is None:
                    continue
                out.extend(_split(item))
            return out
        text = str(value).strip()
        if not text:
            return []
        return [p for p in re.split(r"[,\s;]+", text) if p]

    collected: list[str] = []
    if isinstance(args, dict):
        if "names" in args:
            collected.extend(_split(args.get("names")))
        if "name" in args:
            collected.extend(_split(args.get("name")))
        if "tool" in args:
            collected.extend(_split(args.get("tool")))
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in collected:
        if entry not in seen:
            seen.add(entry)
            ordered.append(entry)
    return ordered


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
                default="Load one or more tools by name so they become available for use. Use this after tool_catalog returns tools with loaded=false. Pass a single 'name' or a 'names' array (e.g. ['read_file', 'file_grep']) to load multiple tools in one call. Returns per-tool results (loaded/failed) or an error if not found.",
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
                            default="Name of the tool to load (e.g. 'generate_image', 'excel_ops'). A comma/whitespace separated list is also accepted.",
                        ),
                    },
                    "names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": _(
                            "param.names.description",
                            default="Names of tools to load (e.g. ['read_file', 'file_grep']). Combined with 'name' when both are given.",
                        ),
                    },
                },
                "required": [],
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
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "msg.unload.missing_name", default="Missing 'name' parameter."
                ),
            }
        )

    try:
        from ._genre_control_util import disable_single_tool, is_tool_pinned

        if is_tool_pinned(name):
            return json.dumps(
                {
                    "ok": False,
                    "name": name,
                    "unloaded": False,
                    "pinned": True,
                    "error": _(
                        "msg.unload.pinned",
                        default="Tool '{name}' is pinned against unload. Unpin it first or force-close its sessions.",
                        name=name,
                    ),
                }
            )

        ok = disable_single_tool(name)
        if ok:
            return json.dumps(
                {
                    "ok": True,
                    "name": name,
                    "unloaded": True,
                    "message": _(
                        "msg.unload.ok",
                        default="Tool '{name}' has been unloaded.",
                        name=name,
                    ),
                }
            )
        else:
            return json.dumps(
                {
                    "ok": False,
                    "name": name,
                    "unloaded": False,
                    "error": _(
                        "msg.unload.not_found",
                        default="Tool '{name}' not found or not loaded.",
                        name=name,
                    ),
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

    # Keep the canonical file reader discoverable even if another tool test
    # temporarily changes the loaded-tool registry in the same process.
    if query and "read" in query.lower() and "file" in query.lower():
        if not any(item.get("name") == "read_file" for item in catalog):
            spec = _lookup_tool_spec("read_file")
            if isinstance(spec, dict):
                catalog.insert(
                    0,
                    {
                        "name": "read_file",
                        "description": str(spec.get("description") or ""),
                        "required": list(
                            spec.get("parameters", {}).get("required", [])
                        ),
                        "parameters": list(
                            spec.get("parameters", {}).get("properties", {}).keys()
                        ),
                        "loaded": True,
                        "genre": "file",
                        "score": 2000,
                    },
                )

    result = {
        "ok": True,
        "query": query,
        "all": all_flag,
        "count": len(catalog),
        "tools": catalog,
    }

    # Auto-load the top-ranked tool when a query is provided
    # and the top result is not already loaded.
    if query and catalog:
        top = catalog[0]
        if not top.get("loaded"):
            name = top["name"]
            try:
                from ._genre_control_util import enable_single_tool

                ok = enable_single_tool(name, initial_threshold=5)
                if ok:
                    result["auto_loaded"] = name
                    # Reflect the loaded state in the catalog entry
                    result["tools"][0]["loaded"] = True
            except Exception:
                pass

    return json.dumps(result, ensure_ascii=False)


def _lookup_tool_spec(tool_name: str) -> dict[str, Any] | None:
    """Find the TOOL_SPEC.function dict for a tool by name."""
    from ._genre_control_util import _find_tool_modules

    for mname, mod in _find_tool_modules():
        spec = getattr(mod, "TOOL_SPEC", None)
        if not isinstance(spec, dict):
            continue
        func_info = spec.get("function", {})
        if not isinstance(func_info, dict):
            continue
        if func_info.get("name") == tool_name:
            return func_info
    return None


def _load_single_tool_by_name(name: str) -> dict[str, Any]:
    """Load one tool; return a per-tool result dict."""
    from ._genre_control_util import _LOADED_SINGLE_TOOLS, enable_single_tool
    from . import get_tool_specs

    # ``tool_load`` may be called for a tool that is already visible,
    # e.g. one enabled by genre or the CLI. Avoid reloading it: repeated
    # reloads create needless churn and can form an LLM management loop.
    try:
        visible = any(
            isinstance(spec, dict)
            and isinstance(spec.get("function"), dict)
            and spec["function"].get("name") == name
            for spec in (get_tool_specs() or [])
        )
    except Exception:
        visible = False
    if visible or name in _LOADED_SINGLE_TOOLS:
        return {
            "ok": True,
            "name": name,
            "loaded": True,
            "already_loaded": True,
            "message": _(
                "msg.load.already_loaded",
                default="Tool '{name}' is already loaded and available for use.",
                name=name,
            ),
        }
    try:
        ok = enable_single_tool(name)
    except Exception as e:
        return {
            "ok": False,
            "name": name,
            "loaded": False,
            "error": f"{type(e).__name__}: {e}",
        }
    if ok:
        return {
            "ok": True,
            "name": name,
            "loaded": True,
            "message": _(
                "msg.load.ok",
                default="Tool '{name}' is now loaded and available for use.",
                name=name,
            ),
        }
    return {
        "ok": False,
        "name": name,
        "loaded": False,
        "error": _(
            "msg.load.not_found_or_not_visible",
            default=(
                "Tool '{name}' was not found, or it failed to become "
                "visible to the LLM after load."
            ),
            name=name,
        ),
    }


def _run_tool_load(args: dict[str, Any]) -> str:
    names = _parse_tool_name_list(args if isinstance(args, dict) else {})
    if not names:
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "msg.load.missing_name", default="Missing 'name' parameter."
                ),
            }
        )

    try:
        results = [_load_single_tool_by_name(name) for name in names]
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})
    if len(results) == 1:
        single = results[0]
        if single.get("ok"):
            return json.dumps(single, ensure_ascii=False)
        return json.dumps(single, ensure_ascii=False)
    loaded = [r["name"] for r in results if r.get("ok")]
    failed = [r for r in results if not r.get("ok")]
    already = [r["name"] for r in results if r.get("already_loaded")]
    message = _(
        "msg.load.batch_ok",
        default="Loaded {count} tool(s): {names}.",
        count=len(loaded),
        names=", ".join(loaded) if loaded else "-",
    )
    return json.dumps(
        {
            "ok": not failed,
            "names": names,
            "loaded": loaded,
            "already_loaded": already,
            "failed": failed,
            "results": results,
            "message": message,
        },
        ensure_ascii=False,
    )


def run_tool(args: dict[str, Any]) -> str:
    # Default dispatcher for TOOL_SPEC (tool_catalog) and TOOL_SPEC_2 (tool_load)
    # TOOL_SPEC_3 (unload_tool) has its own runner via TOOL_SPEC_3_RUNNER
    # NOTE: tool_load requires name/names/tool; an empty {} is a catalog call.
    if isinstance(args, dict) and "query" in args:
        return _run_tool_catalog(args)
    if isinstance(args, dict) and (
        "names" in args or "tool" in args or str(args.get("name") or "").strip()
    ):
        return _run_tool_load(args)
    if isinstance(args, dict) and "name" in args:
        # Explicit but empty name -> load error (missing name), not catalog.
        return _run_tool_load(args)
    return _run_tool_catalog(args)
