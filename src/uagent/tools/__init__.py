# tools/__init__.py
import os
import sys
import json
import re
from datetime import datetime
import importlib.util
from importlib import import_module, reload
from pkgutil import iter_modules
from typing import Any, Dict, List, Callable, Optional

from .context import ToolCallbacks, get_callbacks, init_callbacks as _init_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

# Raw tool specs passed to the LLM
TOOL_SPECS: List[Dict[str, Any]] = []

# Runners
_RUNNERS: Dict[str, Callable[[Dict[str, Any]], str]] = {}

# Tools that set Busy status labels
# key: tool_name, value: status_label (e.g. "tool:cmd_exec")
_BUSY_LABEL_TOOLS: Dict[str, str] = {}


# ------------------------------
# Tool trace (stdout only)
# ------------------------------

_SECRET_KEY_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in (
        r"pass(word)?",
        r"pwd",
        r"token",
        r"secret",
        r"api[_-]?key",
        r"access[_-]?key",
        r"private[_-]?key",
        r"bearer",
        r"authorization",
        r"auth[_-]?token",
        r"credential",
        r"cookie",
        r"session",
        r"sas",
        r"signature",
        r"user[_-]?reply",  # raw answer for human_ask
    )
]


def _looks_like_secret_key(key: str) -> bool:
    if not key:
        return False
    ks = str(key).lower()
    if ks in ("is_password", "use_password", "enable_password", "mask"):
        return False
    return any(p.search(ks) for p in _SECRET_KEY_PATTERNS)


def _mask_value(v: Any) -> Any:
    if v is None:
        return None
    return "********"


def _mask_args(args: Any) -> Any:
    """Recursively walk arguments and mask secret values."""
    if isinstance(args, dict):
        out: Dict[str, Any] = {}
        for k, v in args.items():
            ks = str(k)
            if _looks_like_secret_key(ks):
                out[k] = _mask_value(v)
            else:
                out[k] = _mask_args(v)
        return out
    elif isinstance(args, list):
        return [_mask_args(item) for item in args]
    elif isinstance(args, str) and len(args) > 300:
        return args[:20] + "...(truncated)..." + args[-20:]
    else:
        return args


def _emit_tool_trace(name: str, args: Dict[str, Any]) -> None:
    """Print a one-line tool trace before execution."""
    try:
        masked = _mask_args(args or {})
        try:
            arg_str = json.dumps(
                masked,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        except Exception:
            arg_str = str(masked)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[TOOL] {ts} name={name} args={arg_str}", flush=True)
    except Exception:
        return


# ------------------------------
# framework
# ------------------------------


def init_callbacks(callbacks: ToolCallbacks) -> None:
    """Inject callback functions from the host."""
    _init_callbacks(callbacks)


def _safe_set_status(busy: bool, label: str = "") -> None:
    cb = get_callbacks().set_status
    if cb is None:
        return
    try:
        cb(busy, label)
    except Exception:
        # Tool execution should continue even if UI updates fail.
        return


def _register_tool_module(mod: Any, mod_name: str) -> bool:
    """Register a module as a tool."""
    spec = getattr(mod, "TOOL_SPEC", None)
    runner = getattr(mod, "run_tool", None)

    if not isinstance(spec, dict) or not callable(runner):
        return False

    func_info = spec.get("function", {})
    tool_name = func_info.get("name")
    if not tool_name:
        return False

    # If an existing tool with the same name exists, remove it first.
    for i, existing in enumerate(TOOL_SPECS):
        if existing.get("function", {}).get("name") == tool_name:
            TOOL_SPECS.pop(i)
            break

    TOOL_SPECS.append(spec)
    _RUNNERS[tool_name] = runner

    # Busy label setting
    busy_flag = getattr(mod, "BUSY_LABEL", False)
    if busy_flag:
        status_label = getattr(mod, "STATUS_LABEL", f"tool:{tool_name}")
        _BUSY_LABEL_TOOLS[tool_name] = status_label
    return True


def _load_plugins() -> None:
    """Discover and load tool plugin modules under tools/."""
    TOOL_SPECS.clear()
    _RUNNERS.clear()
    _BUSY_LABEL_TOOLS.clear()

    # 1. Load internal tools
    pkg_dir = os.path.dirname(__file__)
    for m in iter_modules([pkg_dir]):
        if m.name.startswith("_") or m.name == "context":
            continue

        mod_name = f"{__name__}.{m.name}"
        try:
            if mod_name in sys.modules:
                mod = reload(sys.modules[mod_name])
            else:
                mod = import_module(mod_name)
            _register_tool_module(mod, mod_name)
        except Exception as e:
            print(
                _(
                    "log.load_fail.internal",
                    default=f"[tools] Failed to load internal plugin {mod_name}: {e!r}",
                ).format(mod_name=mod_name, err=repr(e)),
                file=sys.stderr,
            )

    # 2. Load external tools (UAGENT_EXTERNAL_TOOLS_DIR)
    ext_dir = os.environ.get("UAGENT_EXTERNAL_TOOLS_DIR")
    if ext_dir and os.path.isdir(ext_dir):
        for entry in os.scandir(ext_dir):
            if (
                entry.is_file()
                and entry.name.endswith(".py")
                and not entry.name.startswith("_")
            ):
                mod_name = f"external_tool_{entry.name[:-3]}"
                try:
                    spec = importlib.util.spec_from_file_location(mod_name, entry.path)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules[mod_name] = mod
                        spec.loader.exec_module(mod)
                        if _register_tool_module(mod, mod_name):
                            print(
                                _(
                                    "log.load_ok.external",
                                    default=f"[tools] Loaded external tool: {entry.name}",
                                ).format(entry_name=entry.name),
                                file=sys.stderr,
                            )
                except Exception as e:
                    print(
                        _(
                            "log.load_fail.external",
                            default=f"[tools] Failed to load external plugin {entry.path}: {e!r}",
                        ).format(entry_path=entry.path, err=repr(e)),
                        file=sys.stderr,
                    )

    if TOOL_SPECS:
        names = [s["function"]["name"] for s in TOOL_SPECS]
        print(
            _(
                "log.loaded_tools",
                default=f"[tools] Loaded tools: {', '.join(names)}",
            ).format(names=", ".join(names)),
            file=sys.stderr,
        )
    else:
        print(
            _(
                "log.no_valid_tools",
                default="[tools] No valid tools were found.",
            ),
            file=sys.stderr,
        )


def get_tool_specs() -> List[Dict[str, Any]]:
    """Return tool specs for the LLM."""
    # To comply with OpenAI/Azure API schema, remove custom extended fields (e.g., system_prompt).
    #
    # Note:
    # - Both Chat Completions and Responses expect tools without a top-level "name".
    #   The canonical form is: {"type":"function","function":{"name":..., ...}}
    # - However, some SDKs/proxies/compat layers require tools[i].name.
    #   To be robust, mirror the function name to the top-level "name" as well.

    clean_specs: List[Dict[str, Any]] = []
    for spec in TOOL_SPECS:
        spec_copy = spec.copy()
        if "function" in spec_copy and isinstance(spec_copy["function"], dict):
            func_copy = spec_copy["function"].copy()
            func_copy.pop("system_prompt", None)
            spec_copy["function"] = func_copy

            # compatibility: mirror name to top-level
            fn_name = func_copy.get("name")
            if fn_name and not spec_copy.get("name"):
                spec_copy["name"] = fn_name

        clean_specs.append(spec_copy)
    return clean_specs


def get_tool_catalog(
    *,
    query: str,
    max_results: int = 12,
    tool_specs: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Return a lightweight searchable catalog of tools."""
    q = (query or "").strip().lower()
    try:
        limit = int(max_results)
    except Exception:
        limit = 12
    if limit <= 0:
        limit = 12

    specs = get_tool_specs() if tool_specs is None else tool_specs
    rows: List[Dict[str, Any]] = []

    for spec in specs or []:
        if not isinstance(spec, dict):
            continue
        fn = spec.get("function") or {}
        if not isinstance(fn, dict):
            continue

        name = str(fn.get("name") or "").strip()
        if not name:
            continue

        description = str(fn.get("description") or "").strip()
        parameters = fn.get("parameters") or {}
        properties = parameters.get("properties") or {}
        required = parameters.get("required") or []

        param_names: List[str] = []
        if isinstance(properties, dict):
            param_names = [str(k) for k in properties.keys()]

        haystack_parts = [name, description] + param_names
        haystack = " ".join([p for p in haystack_parts if p]).lower()

        score = 0
        if q:
            tokens = [tok for tok in re.split(r"\s+", q) if tok]
            for tok in tokens:
                if tok == name.lower():
                    score += 100
                elif tok in name.lower():
                    score += 40
                if tok in description.lower():
                    score += 15
                for pn in param_names:
                    pnl = pn.lower()
                    if tok == pnl:
                        score += 20
                    elif tok in pnl:
                        score += 8
            if q in haystack:
                score += 25
        else:
            score = 1

        if score <= 0 and q:
            continue

        rows.append(
            {
                "name": name,
                "description": description,
                "required": [str(x) for x in required] if isinstance(required, list) else [],
                "parameters": param_names,
                "score": score,
            }
        )

    rows.sort(key=lambda x: (-int(x.get("score", 0)), str(x.get("name", ""))))

    out: List[Dict[str, Any]] = []
    for row in rows[:limit]:
        out.append(
            {
                "name": row["name"],
                "description": row["description"],
                "required": row["required"],
                "parameters": row["parameters"],
            }
        )
    return out


def reload_plugins() -> None:
    """Reload tool plugins (reserved for future extensions)."""
    _load_plugins()


def run_tool(name: str, args: Dict[str, Any]) -> str:
    """Entry point for executing a tool_call."""
    runner = _RUNNERS.get(name)
    if runner is None:
        return f"[tool error] unknown tool: {name}"

    # ---- trace (pre) ----
    # Allow suppressing [TOOL] trace via TOOL_SPEC's extended flags.
    # Default: emit.
    try:
        spec = next(
            (s for s in TOOL_SPECS if s.get("function", {}).get("name") == name),
            None,
        )
        x_scheck = (spec or {}).get("function", {}).get("x_scheck", {})
        emit_trace = True
        if isinstance(x_scheck, dict):
            if x_scheck.get("emit_tool_trace") is False:
                emit_trace = False
        if emit_trace:
            _emit_tool_trace(name, args)
    except Exception:
        # Exceptions here must not prevent tool execution.
        _emit_tool_trace(name, args)

    # During human_ask, Busy should be turned off (it will wait for input).
    # After completion, set Busy back to "LLM" so GUI does not look stuck in IDLE.
    if name == "human_ask":
        # human_ask needs to set active state before clearing Busy,
        # so we delegate status handling to the runner implementation.
        try:
            return runner(args)
        finally:
            _safe_set_status(True, "LLM")

    # Busy-labeled tools
    status_label = _BUSY_LABEL_TOOLS.get(name)
    if status_label is not None:
        _safe_set_status(True, status_label)
        try:
            return runner(args)
        finally:
            _safe_set_status(True, "LLM")

    # Otherwise do not touch status
    return runner(args)


# Load once on module import
_load_plugins()
