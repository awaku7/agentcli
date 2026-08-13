from __future__ import annotations

# tools/__init__.py
import os
from ..env_utils import env_get
import sys
import json
import re
import shutil
import warnings
from datetime import datetime
import importlib.util
from importlib import import_module, reload
from pkgutil import iter_modules
from typing import Any, Callable, Optional
import concurrent.futures
import threading
from threading import Lock, RLock

from .._pip_auto import install_with_status as _auto_install
from .path_alias_shared import resolve_tool_args

JanomeTokenizer = None
jieba = None
_janome_initialized = False
_jieba_initialized = False


def _ensure_janome() -> bool:
    global JanomeTokenizer, _janome_initialized
    if _janome_initialized:
        return JanomeTokenizer is not None
    _janome_initialized = True
    if not _auto_install("janome", version_spec=">=0.5.0"):
        return False
    try:
        from janome.tokenizer import Tokenizer

        JanomeTokenizer = Tokenizer
    except Exception:
        JanomeTokenizer = None
    return JanomeTokenizer is not None


def _ensure_jieba() -> bool:
    global jieba, _jieba_initialized
    if _jieba_initialized:
        return jieba is not None
    _jieba_initialized = True
    if not _auto_install("jieba", version_spec=">=0.42.1"):
        return False
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"pkg_resources is deprecated as an API.*",
                category=UserWarning,
            )
            import jieba as jieba_module

        jieba = jieba_module
    except Exception:
        jieba = None
    return jieba is not None


# PyThaiNLP creates its data directory when its tokenizers/taggers are
# imported. Do not install/import it during every startup: Thai tokenization
# is only needed when a Thai query is actually searched. This avoids creating
# ``pythainlp-data`` in the user's current working directory on macOS and
# other platforms.
thai_word_tokenize = None
thai_pos_tag = None
_thai_nlp_initialized = False


def _ensure_thai_nlp() -> bool:
    global thai_word_tokenize, thai_pos_tag, _thai_nlp_initialized
    if _thai_nlp_initialized:
        return thai_word_tokenize is not None
    _thai_nlp_initialized = True
    if not os.environ.get("PYTHAINLP_DATA") and not os.environ.get(
        "PYTHAINLP_DATA_DIR"
    ):
        if sys.platform == "darwin":
            cache_root = os.path.expanduser("~/Library/Caches")
        elif os.name == "nt":
            cache_root = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.cache"))
        else:
            cache_root = os.environ.get(
                "XDG_CACHE_HOME", os.path.expanduser("~/.cache")
            )
        os.environ["PYTHAINLP_DATA"] = os.path.join(cache_root, "uag", "pythainlp-data")
    data_dir = os.path.abspath(
        os.path.expanduser(
            os.environ.get("PYTHAINLP_DATA") or os.environ.get("PYTHAINLP_DATA_DIR", "")
        )
    )
    legacy_dir = os.path.abspath(os.path.join(os.getcwd(), "pythainlp-data"))
    if os.path.isdir(legacy_dir) and legacy_dir != data_dir:
        try:
            os.makedirs(data_dir, exist_ok=True)
            shutil.copytree(legacy_dir, data_dir, dirs_exist_ok=True)
            shutil.rmtree(legacy_dir)
        except OSError:
            # A cache migration failure must not prevent normal startup.
            pass
    if not _auto_install("pythainlp", version_spec=">=5.3.4"):
        return False
    try:
        from pythainlp.tokenize import word_tokenize
        from pythainlp.tag import pos_tag

        thai_word_tokenize = word_tokenize
        thai_pos_tag = pos_tag
    except Exception:
        thai_word_tokenize = None
        thai_pos_tag = None
    return thai_word_tokenize is not None


from .context import ToolCallbacks, get_callbacks, init_callbacks as _init_callbacks
from .i18n_helper import clear_tool_i18n_cache, get_locale, make_tool_translator

_ = make_tool_translator(__file__)

# ── GPT-5.4 native tool_search helpers ──────────────────────────


def _should_preload_lazy_specs() -> bool:
    """Check if lazy tool specs should be pre-registered for server-side narrowing.

    Returns True when GPT-5.4 native tool_search is active
    (Responses API + OpenAI/Azure + GPT-5.4+ model, mode != off).

    NOTE: This only affects startup-time registration (TOOL_SPECS).
          It is safe to keep False here; the GPT-5.4+ native mode
          path in _call_openai_azure_round() dynamically loads all
          tools from disk when needed.
    """
    raw = (env_get("UAGENT_GPT54_TOOL_SEARCH") or "").strip().lower()
    if raw in ("native", "1", "true", "yes"):
        return True
    return False


# ─────────────────────────────────────────────────────────────────

# Lazy-loaded tool modules (skip import during _load_plugins())
_LAZY_TOOL_MODULES: set[str] = set()

# Mapping from tool name to module name for lazy tools
# Populated from .spec.json files in _load_lazy_tool_specs()
_LAZY_TOOL_NAME_TO_MODULE: dict[str, str] = {"exstruct": "exstruct_tool"}

# Raw tool specs passed to the LLM
TOOL_SPECS: list[dict[str, Any]] = []

# Cache for get_tool_specs(); rebuilt on demand when TOOL_SPECS changes.
_TOOL_SPECS_CACHE: list[dict[str, Any]] | None = None
_TOOL_SPECS_DIRTY: bool = True

# Pre-built dict: tool_name -> emit_trace flag (avoids linear scan in run_tool).
_TOOL_TRACE_FLAGS: dict[str, bool] = {}


def _get_tool_emit_trace(spec: dict[str, Any]) -> bool:
    """Return emit_trace flag for a tool spec (default: True)."""
    fn = spec.get("function", {})
    if isinstance(fn, dict):
        x_scheck = fn.get("x_scheck", {})
        if isinstance(x_scheck, dict) and x_scheck.get("emit_tool_trace") is False:
            return False
    return True


# Runners
_RUNNERS: dict[str, Callable[[dict[str, Any]], str]] = {}

# Tools that set Busy status labels
# key: tool_name, value: status_label (e.g. "tool:cmd_exec")
_BUSY_LABEL_TOOLS: dict[str, str] = {}

# Dynamic commands registered by tool modules
# Structure: { "command_name": { "subcommand_name": { "handler": handler_func, "help_text": help_text_str } } }
_DYNAMIC_COMMANDS: dict[str, dict[str, dict[str, Any]]] = {}

# Cache of get_dynamic_commands_map(); invalidated whenever _DYNAMIC_COMMANDS changes.
_DYNAMIC_MAP_CACHE: dict[str, list[str]] | None = None

# Lock for tool registry (TOOL_SPECS, _RUNNERS, _BUSY_LABEL_TOOLS, _DYNAMIC_COMMANDS)
# Required for free-threaded Python (--disable-gil) safety.
_TOOLS_LOCK = RLock()

# ------------------------------
# Tool trace (stdout only)
# ------------------------------

from ..utils.secret_mask import (  # noqa: E402
    mask_args as _mask_args,
)


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
        with _TRACE_LOCK:
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

    Priority groups:
      0) runtime single-loaded tools (newest first). Marked via
         x_single_load_seq / _single_load_seq, not static load_order=-1.
      1) static load_order == -1 (core tools such as read_file)
      2) missing load_order
      3) non-negative explicit load_order

    Ties within a group are resolved by tool name.
    """
    func_info = spec.get("function", {}) if isinstance(spec, dict) else {}
    tool_name = ""
    if isinstance(func_info, dict):
        tool_name = str(func_info.get("name") or "")

    if not isinstance(spec, dict):
        return (2, 0, tool_name)

    # Runtime single-load marker (set by enable_single_tool). Newest has the
    # smallest (most negative) sequence and must sort before static -1 tools.
    seq = spec.get("x_single_load_seq", spec.get("_single_load_seq"))
    if isinstance(seq, int):
        return (0, seq, tool_name)
    try:
        if seq is not None:
            return (0, int(seq), tool_name)
    except Exception:
        pass

    if "load_order" not in spec:
        return (2, 0, tool_name)

    try:
        order = int(spec.get("load_order", 0))
    except Exception:
        order = 0

    # Historical meaning: load_order == -1 is the high-priority static group.
    if order == -1:
        return (1, 0, tool_name)

    return (3, order, tool_name)


# Cache for get_external_data_tools()
_EXTERNAL_DATA_TOOLS_CACHE: frozenset[str] | None = None


def get_external_data_tools() -> frozenset[str]:
    """Return tool names that fetch external/third-party content.

    These tools' results are wrapped with isolation markers to prevent
    prompt injection attacks.
    """
    global _EXTERNAL_DATA_TOOLS_CACHE
    if _EXTERNAL_DATA_TOOLS_CACHE is not None:
        return _EXTERNAL_DATA_TOOLS_CACHE
    _ensure_loaded()
    result: set[str] = set()
    for spec in TOOL_SPECS:
        if spec.get("external_data"):
            fn = spec.get("function", {})
            if isinstance(fn, dict):
                name = fn.get("name")
                if name:
                    result.add(name)
    # Also check lazy-loaded tool specs
    for mod_name in list(_LAZY_TOOL_MODULES):
        lazy_spec = _load_lazy_tool_spec(mod_name)
        if lazy_spec and lazy_spec.get("external_data"):
            fn = lazy_spec.get("function", {})
            if isinstance(fn, dict):
                name = fn.get("name")
                if name:
                    result.add(name)
    _EXTERNAL_DATA_TOOLS_CACHE = frozenset(result)
    return _EXTERNAL_DATA_TOOLS_CACHE


def _sort_registered_tools() -> None:
    """Sort registered tool specs and keep runner dict insertion order aligned."""
    with _TOOLS_LOCK:
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
    global _TOOL_SPECS_DIRTY
    spec = getattr(mod, "TOOL_SPEC", None)
    runner = getattr(mod, "run_tool", None)

    if not isinstance(spec, dict) or not callable(runner):
        return False

    # Optional tool level in TOOL_SPEC (default: 0; -1 if tool_genre is set)
    # - tool_level == -1: disabled (do not register/load as LLM tool, but allow dynamic commands)
    # - tool_level == 0 or missing: enabled
    # - tool_level == 1: conditional loading (currently treated as disabled)
    # - Tools with a tool_genre start disabled by default (genre control enables them)
    try:
        default_level = 1 if spec.get("tool_genre") else 0
        tool_level = int(spec.get("tool_level", default_level))
    except Exception:
        tool_level = 1 if spec.get("tool_genre") else 0

    # If the tool's genre is currently enabled, force tool_level to 0
    # so that _load_plugins() clear+reload preserves genre-enabled tools.
    if tool_level == 1 and spec.get("tool_genre"):
        try:
            from ._genre_control_util import _ENABLED_GENRES

            if spec["tool_genre"] in _ENABLED_GENRES:
                tool_level = 0
        except Exception:
            pass

    # In native GPT-5.4 tool_search mode, register all tools regardless of genre
    # so the full tool set is sent to the server for server-side narrowing.
    if tool_level == 1 and _should_preload_lazy_specs():
        tool_level = 0

    # If the tool was individually loaded via :tools load, preserve it across reloads.
    # Also honor an explicit single-load marker on the spec.
    _fi = spec.get("function", {}) if isinstance(spec, dict) else {}
    _fi_name = ""
    if isinstance(_fi, dict):
        _fi_name = str(_fi.get("name") or "").strip()
    if tool_level == 1 and _fi_name:
        try:
            from ._genre_control_util import _LOADED_SINGLE_TOOLS

            if _fi_name in _LOADED_SINGLE_TOOLS:
                tool_level = 0
        except Exception:
            pass
    if tool_level != 0 and (
        isinstance(spec.get("x_single_load_seq"), int)
        or isinstance(spec.get("_single_load_seq"), int)
    ):
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
        with _TOOLS_LOCK:
            # If an existing tool with the same name exists, remove it first.
            for i, existing in enumerate(TOOL_SPECS):
                if existing.get("function", {}).get("name") == tool_name:
                    TOOL_SPECS.pop(i)
                    break

            TOOL_SPECS.append(spec)
            _TOOL_SPECS_DIRTY = True
            _TOOL_TRACE_FLAGS[tool_name] = _get_tool_emit_trace(spec)
            _RUNNERS[tool_name] = runner
            _sort_registered_tools()

            # Busy label setting
            busy_flag = getattr(mod, "BUSY_LABEL", False)
            if busy_flag:
                status_label = getattr(mod, "STATUS_LABEL", f"tool:{tool_name}")
                _BUSY_LABEL_TOOLS[tool_name] = status_label
    elif tool_name and not is_llm_tool:
        # Still register the runner so tool_load/run_tool can execute it, but it
        # is not visible to the LLM until re-registered as an LLM tool.
        with _TOOLS_LOCK:
            _RUNNERS[tool_name] = runner
            _TOOL_TRACE_FLAGS[tool_name] = _get_tool_emit_trace(spec)

    # Optional second tool spec (TOOL_SPEC_2) - same runner, different spec
    spec2 = getattr(mod, "TOOL_SPEC_2", None)
    if isinstance(spec2, dict) and callable(runner):
        _register_extra_spec(spec2, runner, mod)

    # Optional third tool spec (TOOL_SPEC_3) - supports a custom runner via TOOL_SPEC_3_RUNNER
    spec3 = getattr(mod, "TOOL_SPEC_3", None)
    if isinstance(spec3, dict):
        spec3_runner = getattr(mod, "TOOL_SPEC_3_RUNNER", runner)
        if callable(spec3_runner):
            _register_extra_spec(spec3, spec3_runner, mod)

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
            help_text = cmd_spec.get("help_text", "") or ""
            help_detail = cmd_spec.get("help_detail", "") or ""
            usage = cmd_spec.get("usage", "") or ""
            if cmd_name and callable(handler):
                if cmd_name not in _DYNAMIC_COMMANDS:
                    _DYNAMIC_COMMANDS[cmd_name] = {}
                # Prefer non-empty help when re-registering the same subcommand.
                prev = _DYNAMIC_COMMANDS[cmd_name].get(subcmd_name) or {}
                _DYNAMIC_COMMANDS[cmd_name][subcmd_name] = {
                    "handler": handler,
                    "help_text": help_text or prev.get("help_text", ""),
                    "help_detail": help_detail or prev.get("help_detail", ""),
                    "usage": usage or prev.get("usage", ""),
                }

    if cmd_specs:
        # Dynamic command map may have changed.
        _invalidate_dynamic_map_cache()

    return True


def _register_extra_spec(
    spec: dict[str, Any],
    runner: Callable[[dict[str, Any]], str],
    mod: Any,
) -> bool:
    """Register an additional tool spec from the same module (e.g. TOOL_SPEC_2)."""
    global _TOOL_SPECS_DIRTY
    try:
        default_level = 1 if spec.get("tool_genre") else 0
        tool_level = int(spec.get("tool_level", default_level))
    except Exception:
        tool_level = 1 if spec.get("tool_genre") else 0

    # Genre enable check
    if tool_level == 1 and spec.get("tool_genre"):
        try:
            from ._genre_control_util import _ENABLED_GENRES

            if spec["tool_genre"] in _ENABLED_GENRES:
                tool_level = 0
        except Exception:
            pass

    # Native GPT-5.4 tool_search mode: register all tools regardless of genre
    if tool_level == 1 and _should_preload_lazy_specs():
        tool_level = 0

    # Single tool load check
    if tool_level == 1:
        _fi = spec.get("function", {})
        if isinstance(_fi, dict) and _fi.get("name"):
            try:
                from ._genre_control_util import _LOADED_SINGLE_TOOLS

                if _fi["name"] in _LOADED_SINGLE_TOOLS:
                    tool_level = 0
            except Exception:
                pass

    if tool_level in (-1, 1):
        return False

    func_info = spec.get("function", {})
    tool_name = func_info.get("name")
    if not tool_name:
        return False

    with _TOOLS_LOCK:
        for i, existing in enumerate(TOOL_SPECS):
            if existing.get("function", {}).get("name") == tool_name:
                TOOL_SPECS.pop(i)
                break
        TOOL_SPECS.append(spec)
        _TOOL_SPECS_DIRTY = True
        _TOOL_TRACE_FLAGS[tool_name] = _get_tool_emit_trace(spec)
        _RUNNERS[tool_name] = runner
        _sort_registered_tools()

        busy_flag = getattr(mod, "BUSY_LABEL", False)
        if busy_flag:
            status_label = getattr(mod, "STATUS_LABEL", f"tool:{tool_name}")
            _BUSY_LABEL_TOOLS[tool_name] = status_label

    return True


def _load_lazy_tool_spec(mod_name: str) -> dict[str, Any] | None:
    """Load TOOL_SPEC metadata from a .spec.json file.

    Returns the spec dict, or None if not found.

    Also populates _LAZY_TOOL_NAME_TO_MODULE from the file.
    """
    spec_path = os.path.join(os.path.dirname(__file__), f"{mod_name}.spec.json")
    if not os.path.isfile(spec_path):
        return None
    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)
        # Populate tool name -> module name mapping
        fn = spec.get("function", {})
        if isinstance(fn, dict):
            tool_name = fn.get("name")
            if tool_name:
                _LAZY_TOOL_NAME_TO_MODULE[tool_name] = mod_name
        return spec
    except Exception:
        return None


def _ensure_lazy_tool_loaded(mod_name: str) -> None:
    """Import and register a lazy tool module on demand.

    Forces tool_level=0 so the tool becomes usable immediately.
    """
    if mod_name not in _LAZY_TOOL_MODULES:
        return
    full_name = f"{__name__}.{mod_name}"
    try:
        if full_name in sys.modules:
            mod = reload(sys.modules[full_name])
        else:
            mod = import_module(full_name)
        # Force tool_level to 0 so the tool gets registered as LLM-visible
        spec = getattr(mod, "TOOL_SPEC", None)
        if isinstance(spec, dict):
            spec["tool_level"] = 0
        _register_tool_module(mod, full_name)
    except Exception:
        return


def _load_plugins() -> None:
    """Discover and load tool plugin modules under tools/."""
    with _TOOLS_LOCK:
        TOOL_SPECS.clear()
        _RUNNERS.clear()
        _BUSY_LABEL_TOOLS.clear()
        global _TOOL_SPECS_DIRTY
        _TOOL_SPECS_DIRTY = True
        _TOOL_TRACE_FLAGS.clear()

    # 1. Load internal tools
    pkg_dir = os.path.dirname(__file__)
    for m in iter_modules([pkg_dir]):
        if m.name.startswith("_") or m.name == "context":
            continue

        # Lazy-loaded modules are skipped here; imported on demand
        # (e.g. when genre is enabled or tool is individually loaded).
        if m.name in _LAZY_TOOL_MODULES:
            lazy_spec = _load_lazy_tool_spec(m.name)
            # In native GPT-5.4 tool_search mode, pre-register lazy tool specs
            # so the full tool set is sent to the server for server-side narrowing.
            if lazy_spec and _should_preload_lazy_specs():
                with _TOOLS_LOCK:
                    TOOL_SPECS.append(lazy_spec)
                    _lazy_fn = lazy_spec.get("function", {})
                    if isinstance(_lazy_fn, dict):
                        _lazy_name = _lazy_fn.get("name")
                        if _lazy_name:
                            _TOOL_TRACE_FLAGS[_lazy_name] = _get_tool_emit_trace(
                                lazy_spec
                            )
            continue

        mod_name = f"{__name__}.{m.name}"
        try:
            if mod_name in sys.modules:
                _existing_mod = sys.modules[mod_name]
                # Never reload already-imported helper modules (those without
                # TOOL_SPEC + run_tool). importlib.reload() re-executes the
                # module body and wipes runtime state — e.g. pybitchat_shared's
                # _LLM_EVENT_QUEUE / _CHAT_MODE / _RUNNING — which silently
                # breaks bitchat chat_mode="llm" injection (peer messages are
                # displayed but never reach the LLM).
                if not (
                    isinstance(getattr(_existing_mod, "TOOL_SPEC", None), dict)
                    and callable(getattr(_existing_mod, "run_tool", None))
                ):
                    continue
                mod = reload(_existing_mod)
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

    # 2. Load external tools (UAGENT_EXTERNAL_TOOLS_DIRS / UAGENT_EXTERNAL_TOOLS_DIR)
    _ext_dirs_raw = (
        env_get("UAGENT_EXTERNAL_TOOLS_DIRS")
        or env_get("UAGENT_EXTERNAL_TOOLS_DIR")
        or ""
    )
    for _ext_dir in _ext_dirs_raw.split(os.pathsep):
        _ext_dir = _ext_dir.strip()
        if not _ext_dir or not os.path.isdir(_ext_dir):
            continue
        for entry in os.scandir(_ext_dir):
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

    # 3. Load Rust wrapper files from tools_rust/ directory
    _rust_dir = os.path.join(os.path.dirname(__file__), "..", "tools_rust")
    _rust_dir = os.path.normpath(_rust_dir)
    if os.path.isdir(_rust_dir):
        for _entry in os.scandir(_rust_dir):
            if (
                _entry.is_file()
                and _entry.name.endswith("_tool.py")
                and not _entry.name.startswith("_")
            ):
                _mod_name = f"_rust_wrapper_{_entry.name[:-3]}"
                try:
                    _spec = importlib.util.spec_from_file_location(
                        _mod_name, _entry.path
                    )
                    if _spec and _spec.loader:
                        _mod = importlib.util.module_from_spec(_spec)
                        sys.modules[_mod_name] = _mod
                        _spec.loader.exec_module(_mod)
                        if _register_tool_module(_mod, _entry.name):
                            pass
                except Exception:
                    pass


def handle_dynamic_command(cmd: str, arg: str, **kwargs: Any) -> Any:
    """Execute a dynamic command registered by a tool module.

    Returns:
        The result of the handler (CommandResult or bool), or None if no matching handler is found.
    """
    _ensure_loaded()
    if cmd not in _DYNAMIC_COMMANDS:
        return None

    parts = arg.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else ""
    subarg = parts[1].strip() if len(parts) > 1 else ""

    # 0. Try two-level subcommand: "geo list" -> full key "geo list"
    if subarg:
        subarg_parts = subarg.split(maxsplit=1)
        subarg_first = subarg_parts[0]
        subarg_rest = subarg_parts[1].strip() if len(subarg_parts) > 1 else ""
        two_level_key = f"{subcmd} {subarg_first}"
        if two_level_key in _DYNAMIC_COMMANDS[cmd]:
            handler_info = _DYNAMIC_COMMANDS[cmd][two_level_key]
            return handler_info["handler"](subarg_rest, **kwargs)

    # 1. Try to match single-level subcommand
    if subcmd in _DYNAMIC_COMMANDS[cmd]:
        handler_info = _DYNAMIC_COMMANDS[cmd][subcmd]
        return handler_info["handler"](subarg, **kwargs)

    # 2. Try to match default handler (empty subcommand)
    if "" in _DYNAMIC_COMMANDS[cmd]:
        handler_info = _DYNAMIC_COMMANDS[cmd][""]
        return handler_info["handler"](arg, **kwargs)

    return None


def get_dynamic_commands_help() -> list[str]:
    """Return short help lines for all registered dynamic commands (overview).

    One compact line per top-level command. Full subcommand text is for :help <cmd>.
    """
    _ensure_loaded()
    help_lines: list[str] = []
    for cmd in sorted(_DYNAMIC_COMMANDS.keys()):
        subs = _DYNAMIC_COMMANDS[cmd]
        sub_names = [k for k in sorted(subs.keys()) if k]
        if sub_names:
            # Keep overview short: show subcommand names only.
            shown = sub_names[:8]
            more = "" if len(sub_names) <= 8 else ", ..."
            help_lines.append(
                f"  :{cmd} <{'|'.join(shown)}{more}>  (dynamic; :help {cmd})"
            )
        else:
            ht = (subs.get("").get("help_text") or "").strip() if "" in subs else ""
            if ht:
                first = ht.splitlines()[0].strip()
                if not first.startswith(":"):
                    first = f":{cmd}  {first}"
                help_lines.append("  " + first if not first.startswith("  ") else first)
            else:
                help_lines.append(f"  :{cmd}  (dynamic; :help {cmd})")
    return help_lines


def _invalidate_dynamic_map_cache() -> None:
    """Drop the cached dynamic command map (call whenever _DYNAMIC_COMMANDS changes)."""
    global _DYNAMIC_MAP_CACHE
    _DYNAMIC_MAP_CACHE = None


def _build_dynamic_map_snapshot() -> dict[str, list[str]]:
    """Build command -> sorted subcommand map from the current registry.

    Lock-free snapshot: callers that need consistency across plugin loads
    should use get_dynamic_commands_map(block=True) instead.
    """
    result: dict[str, list[str]] = {}
    for cmd in sorted(_DYNAMIC_COMMANDS.keys()):
        subcmds = [k for k in _DYNAMIC_COMMANDS[cmd].keys() if k]
        if subcmds:
            result[cmd] = sorted(subcmds)
    return result


def get_dynamic_commands_map(*, block: bool = True) -> dict[str, list[str]]:
    """Return a mapping of command -> sorted list of subcommand names.

    The result is cached and invalidated whenever dynamic commands change.

    With block=True (default) the tool plugins are loaded on first access,
    so the returned map is complete. With block=False the map is built from
    whatever is currently registered and never blocks on the (potentially
    slow) first-time plugin import — used by interactive tab-completion so
    the prompt stays responsive while the background warmup is still loading
    heavy tool modules.
    """
    global _DYNAMIC_MAP_CACHE
    if block:
        _ensure_loaded()
    cache = _DYNAMIC_MAP_CACHE
    if cache is not None:
        return cache
    try:
        snapshot = _build_dynamic_map_snapshot()
    except Exception:
        snapshot = {}
    if block:
        with _TOOLS_LOCK:
            if _DYNAMIC_MAP_CACHE is None:
                _DYNAMIC_MAP_CACHE = snapshot
            return _DYNAMIC_MAP_CACHE
    _DYNAMIC_MAP_CACHE = snapshot
    return snapshot


def get_dynamic_subcommands(cmd: str, *, block: bool = True) -> list[str]:
    """Return sorted subcommand names for one dynamic command.

    Completion-friendly: accepts ":cmd", "cmd" or mixed case. See
    get_dynamic_commands_map() for the meaning of block.
    """
    name = (cmd or "").strip().lstrip(":").lower()
    return get_dynamic_commands_map(block=block).get(name, [])


def list_dynamic_command_names() -> list[str]:
    """Return sorted top-level dynamic command names."""
    _ensure_loaded()
    return sorted(_DYNAMIC_COMMANDS.keys())


def register_dynamic_command(
    command: str,
    handler: Any,
    *,
    subcommand: str = "",
    help_text: str = "",
    help_detail: str = "",
    usage: str = "",
    overwrite: bool = False,
    source: str = "",
) -> dict[str, Any]:
    """Register a dynamic ":" command/subcommand at runtime (plugins).

    Returns ok/error dict. Refuses overwrite unless overwrite=True.
    """
    cmd = (command or "").strip()
    sub = (subcommand or "").strip()
    if not cmd or not callable(handler):
        return {"ok": False, "error": "command and callable handler required"}

    with _TOOLS_LOCK:
        bucket = _DYNAMIC_COMMANDS.setdefault(cmd, {})
        if sub in bucket and not overwrite:
            prev_src = (bucket[sub] or {}).get("source") or ""
            return {
                "ok": False,
                "error": f"command already registered: :{cmd}"
                + (f" {sub}" if sub else ""),
                "existing_source": prev_src,
            }
        bucket[sub] = {
            "handler": handler,
            "help_text": help_text or "",
            "help_detail": help_detail or "",
            "usage": usage or "",
            "source": source or "",
        }
        _invalidate_dynamic_map_cache()
    return {"ok": True, "command": cmd, "subcommand": sub}


def unregister_dynamic_commands_by_source(source: str) -> dict[str, Any]:
    """Remove all dynamic commands registered with the given source tag."""
    src = (source or "").strip()
    if not src:
        return {"ok": False, "error": "source required", "removed": 0}

    removed = 0
    with _TOOLS_LOCK:
        empty_cmds: list[str] = []
        for cmd, subs in list(_DYNAMIC_COMMANDS.items()):
            for sub in list(subs.keys()):
                info = subs.get(sub) or {}
                if info.get("source") == src:
                    del subs[sub]
                    removed += 1
            if not subs:
                empty_cmds.append(cmd)
        for cmd in empty_cmds:
            _DYNAMIC_COMMANDS.pop(cmd, None)
        if removed:
            _invalidate_dynamic_map_cache()
    return {"ok": True, "removed": removed, "source": src}


def get_dynamic_command_sources() -> dict[str, str]:
    """Map \"cmd\" or \"cmd sub\" -> source tag."""
    out: dict[str, str] = {}
    with _TOOLS_LOCK:
        for cmd, subs in _DYNAMIC_COMMANDS.items():
            for sub, info in subs.items():
                key = f"{cmd} {sub}".strip()
                src = (info or {}).get("source") or ""
                if src:
                    out[key] = src
    return out


def get_dynamic_command_detail(cmd: str, subcmd: str | None = None) -> str | None:
    """Return detailed help for a dynamic command (and optional subcommand).

    Returns None if the command is not registered.
    """
    _ensure_loaded()
    name = (cmd or "").strip().lstrip(":").lower()
    if not name or name not in _DYNAMIC_COMMANDS:
        return None

    subs = _DYNAMIC_COMMANDS[name]
    want_sub = (subcmd or "").strip().lower()

    lines: list[str] = []
    lines.append(f":{name}  (dynamic command)")

    if want_sub:
        info = subs.get(want_sub)
        if info is None:
            known = ", ".join(sorted(k for k in subs if k)) or "(none)"
            lines.append(f"Unknown subcommand: {want_sub}")
            lines.append(f"Available: {known}")
            return "\n".join(lines)
        targets = [(want_sub, info)]
    else:
        # Default handler first, then named subcommands.
        order = sorted(subs.keys(), key=lambda s: (s != "", s))
        targets = [(k, subs[k]) for k in order]

    sub_list = [k for k in sorted(subs.keys()) if k]
    if sub_list and not want_sub:
        lines.append("Subcommands: " + ", ".join(sub_list))
        lines.append("")

    for sk, info in targets:
        label = f":{name}" if not sk else f":{name} {sk}"
        lines.append(label)
        usage = (info.get("usage") or "").strip()
        detail = (info.get("help_detail") or "").strip()
        short = (info.get("help_text") or "").strip()
        if usage:
            lines.append(f"  Usage: {usage}")
        if detail:
            for dl in detail.splitlines():
                lines.append("  " + dl if dl.strip() else "")
        elif short:
            for sl in short.splitlines():
                s2 = sl.strip()
                if s2.startswith(":"):
                    lines.append("  " + s2)
                elif s2:
                    lines.append("  " + s2)
        else:
            lines.append("  (no help_text; see CMD_SPEC help_text/help_detail)")
        lines.append("")

    # Trim trailing blank
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def format_tool_names_for_log(tool_specs: list[dict[str, Any]] | None) -> list[str]:
    """Extract tool names in send order for user-visible logging."""
    names: list[str] = []
    for spec in tool_specs or []:
        if not isinstance(spec, dict):
            continue
        # Responses flat form: {"type":"function","name":...}
        n = spec.get("name")
        if isinstance(n, str) and n.strip():
            names.append(n.strip())
            continue
        # Chat/completions form: {"type":"function","function":{"name":...}}
        fn = spec.get("function")
        if isinstance(fn, dict):
            n2 = fn.get("name")
            if isinstance(n2, str) and n2.strip():
                names.append(n2.strip())
                continue
        # Built-in tools: {"type":"web_search"}
        ty = spec.get("type")
        if isinstance(ty, str) and ty.strip() and ty.strip() != "function":
            names.append(ty.strip())
    return names


def log_tools_being_sent(
    tool_specs: list[dict[str, Any]] | None, *, where: str = ""
) -> None:
    """Print the tool list that will be sent to the model (in order).

    Opt-in only: set UAGENT_DEBUG_TOOLS=1.
    """
    if str(env_get("UAGENT_DEBUG_TOOLS", "")).strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    names = format_tool_names_for_log(tool_specs)
    prefix = f"[TOOLS sent{(':' + where) if where else ''}]"
    if not names:
        print(f"{prefix} (none)", flush=True)
        return
    joined = ", ".join(names)
    if len(joined) <= 200:
        print(f"{prefix} ({len(names)}): {joined}", flush=True)
    else:
        print(f"{prefix} ({len(names)}):", flush=True)
        for i, name in enumerate(names, 1):
            print(f"  {i:02d}. {name}", flush=True)


def get_tool_specs() -> list[dict[str, Any]]:
    """Return tool specs for the LLM."""
    _ensure_loaded()
    global _TOOL_SPECS_CACHE, _TOOL_SPECS_DIRTY
    if not _TOOL_SPECS_DIRTY and _TOOL_SPECS_CACHE is not None:
        return _TOOL_SPECS_CACHE

    # Native GPT-5.4 tool_search: exclude management tools (server handles all)
    # and hidden tools (disabled/private) that shouldn't reach the LLM.
    _native_exclusions: set[str] = set()
    if _should_preload_lazy_specs():
        _native_exclusions = {"tool_catalog", "tool_load", "unload_tool"}
    # Note:
    # - Both Chat Completions and Responses expect tools without a top-level "name".
    #   The canonical form is: {"type":"function","function":{"name":..., ...}}
    # - Some SDKs/proxies mirrored name to top-level, but strict APIs (HuggingFace
    #   router, etc.) reject tools[i].name, so we no longer include it.

    clean_specs: list[dict[str, Any]] = []
    for spec in TOOL_SPECS:
        # Skip native-mode exclusions (management tools, hidden tools)
        if _native_exclusions:
            _fn = spec.get("function", {})
            _tn = _fn.get("name", "") if isinstance(_fn, dict) else ""
            if _tn in _native_exclusions:
                continue
            # Skip disabled/hidden tools
            if spec.get("disabled") or spec.get("tool_level") == -1:
                continue

        spec_copy = spec.copy()
        # Remove internal-only keys from tool specs before sending to LLM.
        # (OpenAI/Responses schema expects only {type,function}).
        spec_copy.pop("disabled", None)
        spec_copy.pop("tool_level", None)
        spec_copy.pop("load_order", None)
        spec_copy.pop("tool_genre", None)
        spec_copy.pop("_single_load_seq", None)
        # Remove top-level extended fields (x_* prefixed) that strict OpenAI-compatible
        # APIs (e.g. HuggingFace router) reject.
        for key in list(spec_copy.keys()):
            if key.startswith("x_"):
                spec_copy.pop(key, None)
        if "function" in spec_copy and isinstance(spec_copy["function"], dict):
            func_copy = spec_copy["function"].copy()
            spec_copy["function"] = func_copy

            # Ensure OpenAI/OpenRouter strict schema compatibility:
            # Many proxies require parameters.additionalProperties to be explicitly set.
            params = func_copy.get("parameters")
            if isinstance(params, dict) and params.get("type") == "object":
                if "additionalProperties" not in params:
                    params = params.copy()
                    params["additionalProperties"] = False
                    func_copy["parameters"] = params

            # Remove extended fields (x_* prefixed) from function dict as well.
            for key in list(func_copy.keys()):
                if key.startswith("x_"):
                    func_copy.pop(key, None)

        # Remove the top-level "name" mirror -- the canonical location is
        # function.name. Strict OpenAI-compatible APIs (e.g. HuggingFace
        # router) reject tools[i].name outright.
        spec_copy.pop("name", None)

        clean_specs.append(spec_copy)
    _TOOL_SPECS_CACHE = clean_specs
    _TOOL_SPECS_DIRTY = False
    return clean_specs


def _expand_catalog_token(token: str) -> list[str]:
    t = (token or "").strip().lower()
    return [t] if t else []


def _collect_janome_query_terms(query: str) -> list[str]:
    q = (query or "").strip()
    if not q or not _ensure_janome():
        return []
    try:
        jt = JanomeTokenizer()
        out: list[str] = []
        for t in jt.tokenize(q):
            pos = str(getattr(t, "part_of_speech", "") or "").split(",", 1)[0]
            if pos not in {"Noun", "Verb"}:
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
    if not q or not _ensure_jieba():
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
    if not q or not _ensure_thai_nlp():
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
    all_items: bool = False,
) -> list[dict[str, Any]]:
    """Return a lightweight searchable catalog of tools.

    If all_items is True, return all loaded + unloaded tools without query filtering.
    """
    q = (query or "").strip().lower() if not all_items else ""
    try:
        limit = int(max_results)
    except Exception:
        limit = 12
    if limit <= 0:
        limit = 12
    if all_items:
        limit = None

    debug_tools = str(env_get("UAGENT_DEBUG_TOOLS", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    tokens = _tokenize_catalog_query(q) if q else []
    if debug_tools:
        try:
            print(
                f"[TOOLCAT] query={q!r} tokens={tokens!r} limit={limit} all_items={all_items}",
                flush=True,
            )
        except Exception:
            pass

    specs = get_tool_specs() if tool_specs is None else tool_specs

    # Build set of loaded tool names for dedup
    loaded_names: set[str] = set()
    for spec in specs or []:
        fn = spec.get("function") or {}
        if isinstance(fn, dict):
            n = str(fn.get("name") or "").strip()
            if n:
                loaded_names.add(n)

    rows: list[dict[str, Any]] = []

    def _score_spec(
        name: str,
        description: str,
        param_names: list[str],
        search_terms_en: list[str],
        search_terms: list[str],
    ) -> int:
        if not q:
            return 1
        s = 0
        st = search_terms_en + search_terms
        sh = " ".join([p for p in st if p]).lower()
        hp = [name, description] + param_names + st
        hs = " ".join([p for p in hp if p]).lower()
        search_hit = False
        for tok in tokens:
            if tok in sh:
                search_hit = True
                s += 200
            if tok == name.lower():
                s += 100
            elif tok in name.lower():
                s += 40
            if tok in description.lower():
                s += 15
            for pn in param_names:
                pnl = pn.lower()
                if tok == pnl:
                    s += 20
                elif tok in pnl:
                    s += 8
        if q in sh:
            search_hit = True
            s += 400
        if q in hs:
            s += 25
        if search_hit:
            s += 1000
        return s

    # 1. Process loaded tools
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
        param_names = list(properties.keys()) if isinstance(properties, dict) else []
        st_en = _collect_search_terms(fn.get("x_search_terms_en"))
        st = _collect_search_terms(fn.get("x_search_terms"))
        score = _score_spec(name, description, param_names, st_en, st)
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
                "loaded": True,
                "genre": str(spec.get("tool_genre") or ""),
                "score": score,
            }
        )

    # 2. Also search unloaded tool modules (for discovery)
    if q or all_items:
        try:
            from ._genre_control_util import _find_tool_modules

            for _mname, mod in _find_tool_modules(skip_lazy=True):
                spec = getattr(mod, "TOOL_SPEC", None)
                if not isinstance(spec, dict):
                    continue
                fn = spec.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                name = str(fn.get("name") or "").strip()
                if not name or name in loaded_names:
                    continue
                description = str(fn.get("description") or "").strip()
                parameters = fn.get("parameters") or {}
                properties = parameters.get("properties") or {}
                param_names = (
                    list(properties.keys()) if isinstance(properties, dict) else []
                )
                st_en = _collect_search_terms(fn.get("x_search_terms_en"))
                st = _collect_search_terms(fn.get("x_search_terms"))
                score = _score_spec(name, description, param_names, st_en, st)
                if score <= 0 and q:
                    continue
                rows.append(
                    {
                        "name": name,
                        "description": description,
                        "required": [],
                        "parameters": param_names,
                        "loaded": False,
                        "genre": str(spec.get("tool_genre") or ""),
                        "score": score - 100 if q else 0,
                    }
                )
        except Exception:
            pass

    # 3. Also search lazy-loaded tool specs (fast: read .spec.json or use already-imported module)
    if q or all_items:
        # Collect names already added by sections 1/2 for dedup
        _cataloged_names = {r["name"] for r in rows if r.get("name")}
        _lazy_locale = get_locale()

        # Scan for lazy modules using fast file check (_is_lazy_module reads
        # only the first few lines; os.scandir is a single directory read).
        _lazy_mod_names: list[str] = []
        try:
            from ._genre_control_util import _is_lazy_module

            _pkg_dir = os.path.dirname(__file__)
            for _entry in os.scandir(_pkg_dir):
                if _entry.name.endswith("_tool.py") and not _entry.name.startswith("_"):
                    _mn = _entry.name[:-3]
                    if _is_lazy_module(_mn):
                        _lazy_mod_names.append(_mn)
        except Exception:
            _lazy_mod_names = list(_LAZY_TOOL_MODULES)  # fallback

        for mod_name in _lazy_mod_names:
            # Try .spec.json first (fast, no import)
            spec = _load_lazy_tool_spec(mod_name)
            if not spec:
                # No .spec.json; try already-imported module (lazy tools are
                # still imported during _load_plugins() even if disabled).
                _full = f"uagent.tools.{mod_name}"
                _mod = sys.modules.get(_full)
                if _mod is not None:
                    spec = getattr(_mod, "TOOL_SPEC", None)
                if not isinstance(spec, dict):
                    continue
            fn = spec.get("function", {})
            if not isinstance(fn, dict):
                continue
            name = str(fn.get("name") or "").strip()
            if not name or name in loaded_names or name in _cataloged_names:
                continue
            # Use locale-aware description if available
            _i18n = spec.get("i18n", {}) if isinstance(spec, dict) else {}
            _td_key = "tool.description"
            _td = _i18n.get(_td_key, {}) if isinstance(_i18n, dict) else {}
            if isinstance(_td, dict) and _lazy_locale in _td:
                description = str(_td[_lazy_locale])
            else:
                description = str(fn.get("description") or "").strip()
            parameters = fn.get("parameters", {})
            properties = parameters.get("properties", {})
            param_names = (
                list(properties.keys()) if isinstance(properties, dict) else []
            )
            st_en = _collect_search_terms(fn.get("x_search_terms_en"))
            st = _collect_search_terms(fn.get("x_search_terms"))
            score = _score_spec(name, description, param_names, st_en, st)
            if score <= 0 and q:
                continue
            rows.append(
                {
                    "name": name,
                    "description": description,
                    "required": [],
                    "parameters": param_names,
                    "loaded": False,
                    "genre": str(spec.get("tool_genre") or ""),
                    "score": score - 100 if q else 0,
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
                "loaded": row["loaded"],
                "genre": row["genre"],
            }
        )

    # Ensure web_search and fetch_url are always included in catalog results
    if not any(r["name"] == "search_web" for r in out):
        try:
            from ._genre_control_util import _find_tool_modules

            for _mname, mod in _find_tool_modules(skip_lazy=True):
                spec = getattr(mod, "TOOL_SPEC", None)
                if not isinstance(spec, dict):
                    continue
                fn = spec.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                if fn.get("name") != "search_web":
                    continue
                description = str(fn.get("description") or "").strip()
                parameters = fn.get("parameters") or {}
                properties = parameters.get("properties") or {}
                required = parameters.get("required") or []
                param_names = (
                    list(properties.keys()) if isinstance(properties, dict) else []
                )
                out.append(
                    {
                        "name": "search_web",
                        "description": description,
                        "required": (
                            [str(x) for x in required]
                            if isinstance(required, list)
                            else []
                        ),
                        "parameters": param_names,
                        "loaded": False,
                        "genre": str(spec.get("tool_genre") or ""),
                    }
                )
                break
        except Exception:
            pass

    # Ensure fetch_url is always included in catalog results
    if not any(r["name"] == "fetch_url" for r in out):
        try:
            from ._genre_control_util import _find_tool_modules

            for _mname, mod in _find_tool_modules(skip_lazy=True):
                spec = getattr(mod, "TOOL_SPEC", None)
                if not isinstance(spec, dict):
                    continue
                fn = spec.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                if fn.get("name") != "fetch_url":
                    continue
                description = str(fn.get("description") or "").strip()
                parameters = fn.get("parameters") or {}
                properties = parameters.get("properties") or {}
                required = parameters.get("required") or []
                param_names = (
                    list(properties.keys()) if isinstance(properties, dict) else []
                )
                out.append(
                    {
                        "name": "fetch_url",
                        "description": description,
                        "required": (
                            [str(x) for x in required]
                            if isinstance(required, list)
                            else []
                        ),
                        "parameters": param_names,
                        "loaded": False,
                        "genre": str(spec.get("tool_genre") or ""),
                    }
                )
                break
        except Exception:
            pass

    if debug_tools:
        try:
            print(
                f"[TOOLCAT] matched={[(r['name'], r['score'], r['loaded']) for r in rows[:limit]]}",
                flush=True,
            )
        except Exception:
            pass
    return out


def reload_plugins() -> None:
    """Reload tool plugins (reserved for future extensions)."""
    global _EXTERNAL_DATA_TOOLS_CACHE
    _EXTERNAL_DATA_TOOLS_CACHE = None
    clear_tool_i18n_cache()
    _load_plugins()


# ------------------------------
# parallel execution
# ------------------------------

_PARALLEL_WORKERS = int(env_get("UAGENT_PARALLEL_WORKERS", "8"))
_PARALLEL_TOOL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=_PARALLEL_WORKERS,
    thread_name_prefix="tool_par",
)

# Lock for thread-safe [TOOL] trace output
_TRACE_LOCK = Lock()


def is_parallel_safe(tool_name: str, args: dict[str, Any] | None = None) -> bool:
    """Check whether a tool call is safe for parallel execution.

    Most tools use a static ``x_parallel_safe`` flag. HTTP requests are
    method-sensitive: read-only methods may run in parallel, while writes
    remain serial.
    """
    _ensure_loaded()
    if tool_name == "http_request":
        method = str((args or {}).get("method") or "GET").upper()
        return method in {"GET", "HEAD", "OPTIONS"}
    for spec in TOOL_SPECS:
        if spec.get("function", {}).get("name") == tool_name:
            return bool(spec.get("x_parallel_safe", False))
    return False


def run_tools_parallel(
    calls: list[tuple[str, dict[str, Any]]],
) -> list[tuple[str, dict[str, Any], str]]:
    """Execute multiple tool calls in parallel using a thread pool.

    Args:
        calls: List of (tool_name, args) tuples.

    Returns:
        List of (tool_name, args, result) tuples in the same order as input.
    """
    _ensure_loaded()
    future_map: dict[concurrent.futures.Future, tuple[int, str, dict[str, Any]]] = {}

    for idx, (name, args) in enumerate(calls):
        future = _PARALLEL_TOOL_EXECUTOR.submit(run_tool, name, args)
        future_map[future] = (idx, name, args)

    results: list[tuple[str, dict[str, Any], str] | None] = [None] * len(calls)
    for future in concurrent.futures.as_completed(future_map):
        idx, name, args = future_map[future]
        try:
            result = future.result()
        except Exception as e:
            result = f"[tool runtime error] name={name!r} err={type(e).__name__}: {e}"
        except SystemExit as e:
            # Thread-pool re-raises SystemExit from workers; never kill the host.
            result = f"[tool runtime error] name={name!r} err=SystemExit: {e}"
        results[idx] = (name, args, result)

    # All slots must be filled by now; cast for type checker.
    return [(n, a, r) for n, a, r in results]  # type: ignore[misc]


def _call_tool_runner(name: str, runner: Any, args: dict[str, Any]) -> str:
    """Invoke a tool runner without letting it terminate the host process."""
    try:
        result = runner(args)
    except Exception as e:
        return f"[tool runtime error] name={name!r} err={type(e).__name__}: {e}"
    except SystemExit as e:
        # Tools must return errors, not exit the agent process.
        return f"[tool runtime error] name={name!r} err=SystemExit: {e}"

    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False)
    except Exception:
        return str(result)


def run_tool(name: str, args: dict[str, Any]) -> str:
    """Entry point for executing a tool_call."""
    _ensure_loaded()
    # Resolve @A{0}..@A{9} path aliases at the common dispatch boundary.
    try:
        args = resolve_tool_args(args)
    except ValueError as exc:
        return f"[tool argument error] name={name!r} err={exc}"
    runner = _RUNNERS.get(name)
    if runner is None:
        # Lazy-load fallback: try to import and register the module on demand.
        mod_name = _LAZY_TOOL_NAME_TO_MODULE.get(name)
        if mod_name:
            _ensure_lazy_tool_loaded(mod_name)
            runner = _RUNNERS.get(name)
        # Auto-load fallback: try to enable a single tool by name.
        # This handles tools that exist in the module directory but are
        # currently unloaded (e.g., genre-disabled, not-yet-loaded).
        if runner is None:
            try:
                from ._genre_control_util import enable_single_tool

                if enable_single_tool(name):
                    runner = _RUNNERS.get(name)
            except Exception:
                pass
        if runner is None:
            return f"[tool error] unknown tool: {name}"

    # ---- trace (pre) ----
    # Use pre-built flag to avoid linear scan of TOOL_SPECS.
    emit_trace = _TOOL_TRACE_FLAGS.get(name, True)
    if emit_trace:
        _emit_tool_trace(name, args)

    # During human_ask, Busy should be turned off (it will wait for input).
    # After completion, set Busy back to "LLM" so GUI does not look stuck in IDLE.
    if name == "human_ask":
        # human_ask needs to set active state before clearing Busy,
        # so we delegate status handling to the runner implementation.
        try:
            return _call_tool_runner(name, runner, args)
        finally:
            _safe_set_status(True, "LLM")

    # Busy-labeled tools
    status_label = _BUSY_LABEL_TOOLS.get(name)
    if status_label is not None:
        _safe_set_status(True, status_label)
        try:
            return _call_tool_runner(name, runner, args)
        finally:
            _safe_set_status(True, "LLM")

    # Otherwise do not touch status
    return _call_tool_runner(name, runner, args)


# Lazy initialization: tools are loaded on first use
_INITIALIZED = False
# Guards _ensure_loaded() so warmup thread and main thread don't race
_INIT_LOCK = RLock()


def _ensure_loaded() -> None:
    """Load tool plugins on first access (thread-safe)."""
    global _INITIALIZED
    if not _INITIALIZED:
        with _INIT_LOCK:
            if not _INITIALIZED:
                _load_plugins()
                _INITIALIZED = True


_WARMUP_STARTED = False
_WARMUP_LOCK = RLock()


def start_tools_warmup(*, quiet: bool = True) -> None:
    """Preload tool plugins in a background thread.

    Speeds up the first ':' command / completion by overlapping plugin import
    with idle time after CLI/GUI/web startup.
    Safe to call multiple times; only the first call starts a worker.
    """
    global _WARMUP_STARTED
    with _WARMUP_LOCK:
        if _INITIALIZED or _WARMUP_STARTED:
            return
        _WARMUP_STARTED = True

    def _worker() -> None:
        try:
            _ensure_loaded()
            # Touch dynamic command map so completers are hot too.
            try:
                get_dynamic_commands_map()
            except Exception:
                pass
        except Exception as e:
            if not quiet:
                try:
                    print(
                        f"[WARN] tools warmup failed: {type(e).__name__}: {e}",
                        file=sys.stderr,
                    )
                except Exception:
                    pass

    try:
        t = threading.Thread(
            target=_worker,
            name="uagent-tools-warmup",
            daemon=True,
        )
        t.start()
    except Exception:
        # Fallback: best-effort synchronous load if thread cannot start.
        try:
            _ensure_loaded()
        except Exception:
            pass
