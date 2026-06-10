from __future__ import annotations

# tools/__init__.py
import os
from ..env_utils import env_get
import sys
import json
import re
import warnings
from datetime import datetime
import importlib.util
from importlib import import_module, reload
from pkgutil import iter_modules
from typing import Any, Callable, Optional

try:
    from janome.tokenizer import Tokenizer as JanomeTokenizer
except Exception:  # pragma: no cover
    JanomeTokenizer = None

try:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"pkg_resources is deprecated as an API.*",
            category=UserWarning,
        )
        import jieba
except Exception:  # pragma: no cover
    jieba = None

try:
    from pythainlp.tokenize import word_tokenize as thai_word_tokenize
    from pythainlp.tag import pos_tag as thai_pos_tag
except Exception:  # pragma: no cover
    thai_word_tokenize = None
    thai_pos_tag = None

from .context import ToolCallbacks, get_callbacks, init_callbacks as _init_callbacks
from .i18n_helper import clear_tool_i18n_cache, get_locale, make_tool_translator

_ = make_tool_translator(__file__)

# Raw tool specs passed to the LLM
TOOL_SPECS: list[dict[str, Any]] = []

# Runners
_RUNNERS: dict[str, Callable[[dict[str, Any]], str]] = {}

# Tools that set Busy status labels
# key: tool_name, value: status_label (e.g. "tool:cmd_exec")
_BUSY_LABEL_TOOLS: dict[str, str] = {}

# Dynamic commands registered by tool modules
# Structure: { "command_name": { "subcommand_name": { "handler": handler_func, "help_text": help_text_str } } }
_DYNAMIC_COMMANDS: dict[str, dict[str, dict[str, Any]]] = {}

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
        out: dict[str, Any] = {}
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


def _emit_tool_trace(name: str, args: dict[str, Any]) -> None:
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


def _tool_load_order_key(spec: dict[str, Any]) -> tuple[int, int, str]:
    """Return a stable sort key for registered tools.

    load_order == -1 is treated as the highest priority.
    Missing load_order is next priority.
    Tools with any other explicit load_order are ordered by its integer value.
    Ties are resolved by tool name for deterministic output.
    """
    func_info = spec.get("function", {}) if isinstance(spec, dict) else {}
    tool_name = ""
    if isinstance(func_info, dict):
        tool_name = str(func_info.get("name") or "")

    if not isinstance(spec, dict) or "load_order" not in spec:
        return (0, 0, tool_name)

    try:
        order = int(spec.get("load_order", 0))
    except Exception:
        order = 0

    if order == -1:
        return (-1, 0, tool_name)

    return (1, order, tool_name)


def _sort_registered_tools() -> None:
    """Sort registered tool specs and keep runner dict insertion order aligned."""
    TOOL_SPECS.sort(key=_tool_load_order_key)

    ordered_runners: dict[str, Callable[[dict[str, Any]], str]] = {}
    for spec in TOOL_SPECS:
        func_info = spec.get("function", {})
        if not isinstance(func_info, dict):
            continue
        tool_name = func_info.get("name")
        if tool_name in _RUNNERS:
            ordered_runners[tool_name] = _RUNNERS[tool_name]

    # Preserve any runner not represented in TOOL_SPECS as a safety fallback.
    for tool_name, runner in _RUNNERS.items():
        if tool_name not in ordered_runners:
            ordered_runners[tool_name] = runner

    _RUNNERS.clear()
    _RUNNERS.update(ordered_runners)


def _register_tool_module(mod: Any, mod_name: str) -> bool:
    """Register a module as a tool."""
    spec = getattr(mod, "TOOL_SPEC", None)
    runner = getattr(mod, "run_tool", None)

    if not isinstance(spec, dict) or not callable(runner):
        return False

    # Optional tool level in TOOL_SPEC (default: 0)
    # - tool_level == -1: disabled (do not register/load as LLM tool, but allow dynamic commands)
    # - tool_level == 0 or missing: enabled
    # - tool_level == 1: conditional loading (currently treated as disabled)
    try:
        tool_level = int(spec.get("tool_level", 0))
    except Exception:
        tool_level = 0

    is_llm_tool = True
    if tool_level == -1:
        is_llm_tool = False

    if tool_level == 1:
        # Reserved for future: load only when necessary.
        # For now, do not register the tool.
        is_llm_tool = False

    func_info = spec.get("function", {})
    tool_name = func_info.get("name")

    if is_llm_tool and tool_name:
        # If an existing tool with the same name exists, remove it first.
        for i, existing in enumerate(TOOL_SPECS):
            if existing.get("function", {}).get("name") == tool_name:
                TOOL_SPECS.pop(i)
                break

        TOOL_SPECS.append(spec)
        _RUNNERS[tool_name] = runner
        _sort_registered_tools()

        # Busy label setting
        busy_flag = getattr(mod, "BUSY_LABEL", False)
        if busy_flag:
            status_label = getattr(mod, "STATUS_LABEL", f"tool:{tool_name}")
            _BUSY_LABEL_TOOLS[tool_name] = status_label

    # Dynamic command registration (always allowed even if tool_level == -1)
    cmd_specs = getattr(mod, "CMD_SPECS", None)
    if not isinstance(cmd_specs, list):
        cmd_spec = getattr(mod, "CMD_SPEC", None)
        cmd_specs = [cmd_spec] if isinstance(cmd_spec, dict) else []

    for cmd_spec in cmd_specs:
        if isinstance(cmd_spec, dict):
            cmd_name = cmd_spec.get("command")
            subcmd_name = cmd_spec.get("subcommand", "")
            handler = cmd_spec.get("handler")
            help_text = cmd_spec.get("help_text", "")
            if cmd_name and callable(handler):
                if cmd_name not in _DYNAMIC_COMMANDS:
                    _DYNAMIC_COMMANDS[cmd_name] = {}
                _DYNAMIC_COMMANDS[cmd_name][subcmd_name] = {
                    "handler": handler,
                    "help_text": help_text,
                }

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
            loaded = _register_tool_module(mod, mod_name)
            reason = getattr(mod, "LOAD_DISABLED_REASON", "")
            if (not loaded) and reason:
                print(
                    _(
                        "log.load_disabled.internal",
                        default=(
                            "[tools] Internal plugin {mod_name} is disabled:\n"
                            "[tools] {reason}"
                        ),
                    ).format(mod_name=mod_name, reason=reason),
                    file=sys.stderr,
                )
        except Exception as e:
            print(
                _(
                    "log.load_fail.internal",
                    default=f"[tools] Failed to load internal plugin {mod_name}: {e!r}",
                ).format(mod_name=mod_name, err=repr(e)),
                file=sys.stderr,
            )

    # 2. Load external tools (UAGENT_EXTERNAL_TOOLS_DIR)
    ext_dir = env_get("UAGENT_EXTERNAL_TOOLS_DIR")
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
                                    entry_name=entry.name,
                                ),
                                file=sys.stderr,
                            )
                except Exception as e:
                    print(
                        _(
                            "log.load_fail.external",
                            default=f"[tools] Failed to load external plugin {entry.path}: {e!r}",
                            entry_path=entry.path,
                            err=repr(e),
                        ),
                        file=sys.stderr,
                    )

    if TOOL_SPECS:
        names = [s["function"]["name"] for s in TOOL_SPECS]
        print(
            _(
                "log.loaded_tools",
                default=f"[tools] Loaded tools: {', '.join(names)}",
                names=", ".join(names),
            ),
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


def handle_dynamic_command(cmd: str, arg: str, **kwargs: Any) -> Any:
    """Execute a dynamic command registered by a tool module.

    Returns:
        The result of the handler (CommandResult or bool), or None if no matching handler is found.
    """
    if cmd not in _DYNAMIC_COMMANDS:
        return None

    parts = arg.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else ""
    subarg = parts[1].strip() if len(parts) > 1 else ""

    # 1. Try to match subcommand
    if subcmd in _DYNAMIC_COMMANDS[cmd]:
        handler_info = _DYNAMIC_COMMANDS[cmd][subcmd]
        return handler_info["handler"](subarg, **kwargs)

    # 2. Try to match default handler (empty subcommand)
    if "" in _DYNAMIC_COMMANDS[cmd]:
        handler_info = _DYNAMIC_COMMANDS[cmd][""]
        return handler_info["handler"](arg, **kwargs)

    return None


def get_dynamic_commands_help() -> list[str]:
    """Return help lines for all registered dynamic commands."""
    help_lines: list[str] = []
    for cmd in sorted(_DYNAMIC_COMMANDS.keys()):
        for subcmd in sorted(_DYNAMIC_COMMANDS[cmd].keys()):
            help_text = _DYNAMIC_COMMANDS[cmd][subcmd].get("help_text")
            if help_text:
                help_lines.append(help_text)
    return help_lines


def get_tool_specs() -> list[dict[str, Any]]:
    """Return tool specs for the LLM."""
    # To comply with OpenAI/Azure API schema, remove custom extended fields (e.g., system_prompt).
    #
    # Note:
    # - Both Chat Completions and Responses expect tools without a top-level "name".
    #   The canonical form is: {"type":"function","function":{"name":..., ...}}
    # - However, some SDKs/proxies/compat layers require tools[i].name.
    #   To be robust, mirror the function name to the top-level "name" as well.

    clean_specs: list[dict[str, Any]] = []
    for spec in TOOL_SPECS:
        spec_copy = spec.copy()
        # Remove internal-only keys from tool specs before sending to LLM.
        # (OpenAI/Responses schema expects only {type,function} (+ optional name mirror)).
        spec_copy.pop("disabled", None)
        spec_copy.pop("tool_level", None)
        spec_copy.pop("load_order", None)
        if "function" in spec_copy and isinstance(spec_copy["function"], dict):
            func_copy = spec_copy["function"].copy()
            func_copy.pop("system_prompt", None)
            spec_copy["function"] = func_copy

            # Ensure OpenAI/OpenRouter strict schema compatibility:
            # Many proxies require parameters.additionalProperties to be explicitly set.
            params = func_copy.get("parameters")
            if isinstance(params, dict) and params.get("type") == "object":
                if "additionalProperties" not in params:
                    params = params.copy()
                    params["additionalProperties"] = False
                    func_copy["parameters"] = params

            # compatibility: mirror name to top-level
            fn_name = func_copy.get("name")
            if fn_name and not spec_copy.get("name"):
                spec_copy["name"] = fn_name

        clean_specs.append(spec_copy)
    return clean_specs


def _expand_catalog_token(token: str) -> list[str]:
    t = (token or "").strip().lower()
    return [t] if t else []


def _collect_janome_query_terms(query: str) -> list[str]:
    q = (query or "").strip()
    if not q or JanomeTokenizer is None:
        return []
    try:
        jt = JanomeTokenizer()
        out: list[str] = []
        for t in jt.tokenize(q):
            pos = str(getattr(t, "part_of_speech", "") or "").split(",", 1)[0]
            if pos not in {"名詞", "動詞"}:
                continue
            term = str(getattr(t, "base_form", "") or "").strip().lower()
            if not term or term == "*":
                term = str(getattr(t, "surface", "") or "").strip().lower()
            if term:
                out.append(term)
        return out
    except Exception:
        return []


def _collect_jieba_query_terms(query: str) -> list[str]:
    q = (query or "").strip()
    if not q or jieba is None:
        return []
    try:
        out: list[str] = []
        for tok in jieba.lcut(q):
            term = str(tok or "").strip().lower()
            if term and not term.isspace():
                out.append(term)
        return out
    except Exception:
        return []


def _collect_thai_query_terms(query: str) -> list[str]:
    q = (query or "").strip()
    if not q or thai_word_tokenize is None:
        return []
    try:
        out: list[str] = []
        tokens = list(thai_word_tokenize(q, engine="newmm"))
        if thai_pos_tag is not None:
            try:
                tags = thai_pos_tag(tokens, engine="perceptron", corpus="orchid")
            except Exception:
                tags = [(tok, "") for tok in tokens]
        else:
            tags = [(tok, "") for tok in tokens]
        for tok, pos in tags:
            term = str(tok or "").strip().lower()
            if not term or term.isspace():
                continue
            if pos and not str(pos).startswith(("N", "V")):
                continue
            out.append(term)
        return out
    except Exception:
        return []


def _has_japanese_script(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff]", text))


def _has_thai_script(text: str) -> bool:
    return bool(re.search(r"[\u0e00-\u0e7f]", text))


def _has_cjk_script(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _tokenize_catalog_query(query: str) -> list[str]:
    q = (query or "").strip().lower()
    if not q:
        return []

    loc = get_locale()
    base_tokens = [tok for tok in re.split(r"\s+", q) if tok]
    tokens: list[str] = []

    if _has_thai_script(q):
        tokens.extend(_collect_thai_query_terms(q))
    elif _has_japanese_script(q):
        tokens.extend(_collect_janome_query_terms(q))
    elif _has_cjk_script(q):
        if loc.startswith("zh"):
            tokens.extend(_collect_jieba_query_terms(q))
        elif loc.startswith("ja"):
            tokens.extend(_collect_janome_query_terms(q))
        else:
            tokens.extend(_collect_jieba_query_terms(q))
    else:
        tokens.extend(base_tokens)

    tokens.extend(base_tokens)
    tokens.append(q)

    expanded: list[str] = []
    seen = set()
    for tok in tokens:
        for e in _expand_catalog_token(tok):
            if e not in seen:
                seen.add(e)
                expanded.append(e)

    return expanded


def _collect_search_terms(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        term = value.strip()
        return [term] if term else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_collect_search_terms(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_collect_search_terms(item))
        return out
    term = str(value).strip()
    return [term] if term else []


def get_tool_catalog(
    *,
    query: str,
    max_results: int = 12,
    tool_specs: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Return a lightweight searchable catalog of tools."""
    q = (query or "").strip().lower()
    try:
        limit = int(max_results)
    except Exception:
        limit = 12
    if limit <= 0:
        limit = 12

    debug_tools = str(env_get("UAGENT_DEBUG_TOOLS", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    tokens = _tokenize_catalog_query(q) if q else []
    if debug_tools:
        try:
            print(f"[TOOLCAT] query={q!r} tokens={tokens!r} limit={limit}", flush=True)
        except Exception:
            pass

    specs = get_tool_specs() if tool_specs is None else tool_specs
    rows: list[dict[str, Any]] = []

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

        param_names: list[str] = []
        if isinstance(properties, dict):
            param_names = [str(k) for k in properties.keys()]

        search_terms = _collect_search_terms(fn.get("x_search_terms_en"))
        search_terms += _collect_search_terms(fn.get("x_search_terms"))
        search_haystack = " ".join([p for p in search_terms if p]).lower()
        haystack_parts = [name, description] + param_names + search_terms
        haystack = " ".join([p for p in haystack_parts if p]).lower()

        score = 0
        hit_details: list[str] = []
        if q:
            search_term_hit = False
            for tok in tokens:
                if tok in search_haystack:
                    search_term_hit = True
                    score += 200
                    hit_details.append(f"search:{tok}")
                if tok == name.lower():
                    score += 100
                    hit_details.append(f"name=={tok}")
                elif tok in name.lower():
                    score += 40
                    hit_details.append(f"name~{tok}")
                if tok in description.lower():
                    score += 15
                    hit_details.append(f"desc~{tok}")
                for pn in param_names:
                    pnl = pn.lower()
                    if tok == pnl:
                        score += 20
                        hit_details.append(f"param=={tok}")
                    elif tok in pnl:
                        score += 8
                        hit_details.append(f"param~{tok}")
            if q in search_haystack:
                search_term_hit = True
                score += 400
                hit_details.append("q in search_terms")
            if q in haystack:
                score += 25
                hit_details.append("q in haystack")
            if search_term_hit:
                score += 1000
                hit_details.append("search_term_hit")
        else:
            score = 1

        if debug_tools and q:
            try:
                print(
                    f"[TOOLCAT] name={name} score={score} hits={hit_details} haystack={haystack!r} search_haystack={search_haystack!r}",
                    flush=True,
                )
            except Exception:
                pass

        if score <= 0 and q:
            continue

        rows.append(
            {
                "name": name,
                "description": description,
                "required": (
                    [str(x) for x in required] if isinstance(required, list) else []
                ),
                "parameters": param_names,
                "score": score,
            }
        )

    rows.sort(key=lambda x: (-int(x.get("score", 0)), str(x.get("name", ""))))

    out: list[dict[str, Any]] = []
    for row in rows[:limit]:
        out.append(
            {
                "name": row["name"],
                "description": row["description"],
                "required": row["required"],
                "parameters": row["parameters"],
            }
        )
    if debug_tools:
        try:
            print(
                f"[TOOLCAT] matched={[(r['name'], r['score']) for r in rows[:limit]]}",
                flush=True,
            )
        except Exception:
            pass
    return out


def reload_plugins() -> None:
    """Reload tool plugins (reserved for future extensions)."""
    clear_tool_i18n_cache()
    _load_plugins()


def run_tool(name: str, args: dict[str, Any]) -> str:
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
            result = runner(args)
        finally:
            _safe_set_status(True, "LLM")
        return result

    # Otherwise do not touch status
    result = runner(args)
    return result


# Load once on module import
_load_plugins()
