from __future__ import annotations

# tools/__init__.py
import os
from ..env_utils import env_get
import sys
import json
import importlib.util
from importlib import import_module, reload
from pkgutil import iter_modules
from typing import Any, Callable, Optional
import concurrent.futures
from threading import RLock

from .path_alias_shared import resolve_tool_args


from .context import ToolCallbacks, get_callbacks, init_callbacks as _init_callbacks
from .i18n_helper import clear_tool_i18n_cache, get_locale, make_tool_translator

_ = make_tool_translator(__file__)

# ── GPT-5.4 native tool_search helpers ──────────────────────────


# Tool management tools excluded in embedded mode unless explicitly loaded
# (--enable-tool / :tools load). The three tools come from one module
# (catalog_tool: TOOL_SPEC / TOOL_SPEC_2 / TOOL_SPEC_3), so they are grouped:
# explicitly loading any one of them (practically tool_catalog) enables the
# whole group, keeping tool discovery and loading functional together.
_EMBEDDED_EXCLUDED_TOOLS: frozenset[str] = frozenset(
    {"tool_catalog", "tool_load", "unload_tool"}
)
_EMBEDDED_EXCLUDED_TOOL_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"tool_catalog", "tool_load", "unload_tool"}),
)

_SUB_AGENT_JOB_TOOL_NAMES = frozenset(
    {
        "spawn_sub_agent",
        "get_sub_agent_job",
        "wait_sub_agent_job",
        "send_sub_agent_message",
        "cancel_sub_agent_job",
    }
)


def _sub_agent_job_tools_visible() -> bool:
    """Expose Job orchestration only to an integrated foreground Main Agent."""
    try:
        from ..runtime.sub_agent_job_access import get_job_runtime_context

        return get_job_runtime_context() is not None
    except Exception:
        return False


def _filter_sub_agent_job_tools(
    specs: list[dict[str, Any]], *, allowed: bool | None = None
) -> list[dict[str, Any]]:
    visible = _sub_agent_job_tools_visible() if allowed is None else allowed
    if visible:
        return specs
    return [
        spec
        for spec in specs
        if str((spec.get("function") or {}).get("name") or "")
        not in _SUB_AGENT_JOB_TOOL_NAMES
    ]


def _embedded_management_tool_allowed(tool_name: str) -> bool:
    """Return True when a management tool may be used in embedded mode.

    A management tool is allowed when any tool from its module group was
    explicitly loaded (enable_single_tool registers it in _LOADED_SINGLE_TOOLS
    before registration). Non-management tools are always allowed.
    """
    if not _is_embedded_mode():
        return True
    try:
        from ._tool_load_util import _LOADED_SINGLE_TOOLS

        loaded = set(_LOADED_SINGLE_TOOLS)
    except Exception:
        loaded = set()
    for group in _EMBEDDED_EXCLUDED_TOOL_GROUPS:
        if tool_name in group:
            return bool(group & loaded)
    return True


def _is_embedded_mode() -> bool:
    """Check if embedded mode is active (UAGENT_EMBEDDED=1).

    Embedded mode skips tool management tools (tool_catalog, tool_load,
    unload_tool) unless explicitly loaded, and disables the session store;
    normally enabled via --embedded.
    """
    raw = (env_get("UAGENT_EMBEDDED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _should_preload_lazy_specs() -> bool:
    """Check if lazy specs should be pre-registered for provider tool search.

    Returns True when native OpenAI Responses or OpenRouter Responses/Messages
    tool_search, DeepSeek client-side Responses/Messages tool_search, Anthropic
    Messages tool_search, or Gemini Interactions retrieval is active.

    NOTE: This only affects startup-time registration (TOOL_SPECS).
          Native provider paths need all eligible schemas registered so the
          server or client can retrieve them without a catalog round-trip.
    """
    try:
        from ..runtime.tool_discovery import resolve_tool_discovery_from_environment

        if resolve_tool_discovery_from_environment().uses_native_search:
            return True
        from ..runtime.tool_discovery import (
            gemini_interactions_tool_retrieval_enabled_from_environment,
        )

        if gemini_interactions_tool_retrieval_enabled_from_environment():
            return True
        from ..runtime.tool_discovery import (
            anthropic_messages_tool_search_variant_from_environment,
        )

        if anthropic_messages_tool_search_variant_from_environment() is not None:
            return True
        from ..runtime.tool_discovery import (
            messages_tool_search_enabled_from_environment,
        )

        return messages_tool_search_enabled_from_environment()
    except Exception:
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
_ANALYZE_IMAGE_HIDDEN: bool | None = None
# Embedded-mode state at cache build time. The cache must be invalidated when
# UAGENT_EMBEDDED changes (management tools appear/disappear).
_TOOL_SPECS_CACHE_EMBEDDED: bool | None = None

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


def _get_tool_describer(mod: Any, tool_name: str) -> Optional[Callable[..., Any]]:
    """Return a module's optional pre-execution describer for ``tool_name``.

    Contract: the callable receives the tool ``args`` dict and returns one short
    sentence describing what is about to happen. It must not print and must not
    embed raw payloads; the host still masks secrets and bounds the length.
    """

    table = getattr(mod, "TOOL_DESCRIBERS", None)
    if isinstance(table, dict):
        fn = table.get(tool_name)
        if callable(fn):
            return fn
    fn = getattr(mod, "TOOL_DESCRIBER", None)
    if callable(fn):
        return fn
    return None


def _register_tool_describer(mod: Any, tool_name: str) -> None:
    """Bind or clear the action describer for one tool name."""

    describer = _get_tool_describer(mod, tool_name)
    if describer is None:
        _TOOL_DESCRIBERS.pop(tool_name, None)
    else:
        _TOOL_DESCRIBERS[tool_name] = describer


# Runners
_RUNNERS: dict[str, Callable[[dict[str, Any]], str]] = {}

# Per-tool localized pre-execution describers (UAGENT_SHOW_TOOL_RESULTS=2).
# key: tool_name, value: callable(args) -> str
_TOOL_DESCRIBERS: dict[str, Callable[..., Any]] = {}

# Tools that set Busy status labels
# key: tool_name, value: status_label (e.g. "tool:cmd_exec")
_BUSY_LABEL_TOOLS: dict[str, str] = {}


# Lock for tool registry (TOOL_SPECS, _RUNNERS, _BUSY_LABEL_TOOLS, _DYNAMIC_COMMANDS)
# Required for free-threaded Python (--disable-gil) safety.
_TOOLS_LOCK = RLock()

from ._dynamic_commands import (  # noqa: E402,F401
    _DYNAMIC_COMMANDS,
    _invalidate_dynamic_map_cache,
    _register_dynamic_commands,
    get_dynamic_command_catalog,
    get_dynamic_command_detail,
    get_dynamic_command_sources,
    get_dynamic_commands_help,
    get_dynamic_commands_map,
    get_dynamic_subcommands,
    handle_dynamic_command,
    list_dynamic_command_names,
    register_dynamic_command,
    unregister_dynamic_commands_by_source,
)
from ._dynamic_commands import _reset_dynamic_command_registry  # noqa: E402

# Executing this module (first import or importlib.reload for ":tools reload")
# starts from an empty command registry, as when the registry lived here.
_reset_dynamic_command_registry()

from ._trace import (  # noqa: E402,F401
    _emit_remote_tool_progress,
    _emit_tool_trace,
    _generic_tool_action,
    _localized_tool_action,
    _should_emit_tool_trace,
    _tool_trace_body,
    tool_action_sentence,
)

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
        # Some modules provide only CLI commands (for example skill lifecycle
        # commands) and intentionally have no LLM-facing TOOL_SPEC.
        _register_dynamic_commands(mod)
        return bool(getattr(mod, "CMD_SPECS", None) or getattr(mod, "CMD_SPEC", None))
    _loadable_check = getattr(mod, "is_loadable", None)
    if callable(_loadable_check):
        try:
            if not bool(_loadable_check()):
                return False
        except Exception:
            return False

    # Embedded mode: skip tool management tools unless explicitly loaded
    # via --enable-tool / :tools load. enable_single_tool() registers the
    # name in _LOADED_SINGLE_TOOLS before calling this function, which acts
    # as the explicit-load marker.
    if _is_embedded_mode():
        _fn0 = spec.get("function", {})
        _tn0 = _fn0.get("name", "") if isinstance(_fn0, dict) else ""
        if _tn0 in _EMBEDDED_EXCLUDED_TOOLS and not _embedded_management_tool_allowed(
            _tn0
        ):
            return False

    # Tool availability is controlled only by tool_level.
    # -1: never register; 0: always register; 1: dynamically load on demand.
    try:
        default_level = 0
        tool_level = int(spec.get("tool_level", default_level))
    except Exception:
        tool_level = 0

    # In native GPT-5.4 tool_search mode, register all tools regardless of tool_level
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
            from ._tool_load_util import _LOADED_SINGLE_TOOLS

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
            _register_tool_describer(mod, tool_name)
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
            _register_tool_describer(mod, tool_name)

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
    _register_dynamic_commands(mod)

    return True


def _register_extra_spec(
    spec: dict[str, Any],
    runner: Callable[[dict[str, Any]], str],
    mod: Any,
) -> bool:
    """Register an additional tool spec from the same module (e.g. TOOL_SPEC_2)."""
    global _TOOL_SPECS_DIRTY
    _fn2 = spec.get("function", {}) if isinstance(spec, dict) else {}
    _tn2 = _fn2.get("name", "") if isinstance(_fn2, dict) else ""
    if _tn2 in _EMBEDDED_EXCLUDED_TOOLS and not _embedded_management_tool_allowed(_tn2):
        return False
    try:
        default_level = 0
        tool_level = int(spec.get("tool_level", default_level))
    except Exception:
        tool_level = 0

    # Native GPT-5.4 tool_search mode: register all tools regardless of tool_level
    if tool_level == 1 and _should_preload_lazy_specs():
        tool_level = 0

    # Single tool load check
    if tool_level == 1:
        _fi = spec.get("function", {})
        if isinstance(_fi, dict) and _fi.get("name"):
            try:
                from ._tool_load_util import _LOADED_SINGLE_TOOLS

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
        _register_tool_describer(mod, tool_name)
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


# Modules under tools/ that are not plugins and must not be imported by the
# loader. ``qr_reader_ui`` is a standalone Tkinter script launched in a
# subprocess by ``qr_reader_tool``; importing it would load tkinter and numpy
# for nothing.
_NON_PLUGIN_MODULES: frozenset[str] = frozenset({"context", "qr_reader_ui"})

# Cached specs of lazy plugin modules that have not been imported yet
# (short module name -> {"TOOL_SPEC": ..., ...}). Read by
# ``_tool_load_util._find_tool_modules`` so discovery does not import them.
_MANIFEST_VIEWS: dict[str, dict[str, Any]] = {}


class _LazyRunner:
    """Runner placeholder for a plugin registered from the tool manifest.

    The real module is imported and registered the first time the tool is
    resolved (``run_tool``, ``get_tool_describer``) or called directly.
    """

    __slots__ = ("module_name", "tool_name")

    def __init__(self, module_name: str, tool_name: str) -> None:
        self.module_name = module_name
        self.tool_name = tool_name

    def resolve(self) -> Optional[Callable[[dict[str, Any]], str]]:
        """Import and register the real module; return its runner (or None)."""
        mod = sys.modules.get(self.module_name)
        if mod is None:
            mod = import_module(self.module_name)
        _register_tool_module(mod, self.module_name)
        with _TOOLS_LOCK:
            _MANIFEST_VIEWS.pop(self.module_name.rsplit(".", 1)[-1], None)
            runner = _RUNNERS.get(self.tool_name)
        if runner is None or isinstance(runner, _LazyRunner):
            return None
        return runner

    def __call__(self, args: dict[str, Any]) -> str:
        runner = self.resolve()
        if runner is None:
            raise RuntimeError(f"tool {self.tool_name!r} could not be loaded")
        return runner(args)

    def __repr__(self) -> str:
        return f"<_LazyRunner {self.tool_name} from {self.module_name}>"


def _resolve_lazy_runner(name: str) -> Optional[Callable[[dict[str, Any]], str]]:
    """Return the real runner for ``name``, importing a lazy plugin if needed."""
    with _TOOLS_LOCK:
        runner = _RUNNERS.get(name)
    if isinstance(runner, _LazyRunner):
        return runner.resolve()
    return runner


class _ManifestSession:
    """Per-``_load_plugins`` manifest state: cached entries in, new entries out."""

    def __init__(self, pkg_dir: str) -> None:
        from . import _manifest

        self.locale = get_locale()
        self.fingerprint = _manifest.compute_fingerprint(pkg_dir, self.locale)
        self.path = _manifest.manifest_path(pkg_dir, self.locale)
        self.cached = _manifest.load_manifest(self.path, self.fingerprint) or {}
        self.entries: dict[str, dict[str, Any]] = {}

    def record(self, short_name: str, mod: Any) -> None:
        from . import _manifest

        try:
            entry = _manifest.classify_module(mod, frozenset(_EMBEDDED_EXCLUDED_TOOLS))
        except Exception:
            entry = None
        if entry is not None:
            self.entries[short_name] = entry

    def save(self) -> None:
        from . import _manifest

        if self.entries != self.cached:
            _manifest.save_manifest(self.path, self.fingerprint, self.entries)


def _open_manifest_session(pkg_dir: str) -> Optional[_ManifestSession]:
    """Return a manifest session, or None when lazy loading must not be used."""
    from . import _manifest

    if not _manifest.manifest_enabled():
        return None
    # Native tool search needs every module's real registration for server- or
    # client-side lookup; keep the eager path there.
    if _should_preload_lazy_specs():
        return None
    try:
        return _ManifestSession(pkg_dir)
    except Exception:
        return None


def _register_from_manifest(short_name: str, entry: dict[str, Any]) -> bool:
    """Register a plugin from its manifest entry without importing it.

    Mirrors what ``_register_tool_module`` does for a module whose specs are
    all hidden from the LLM (``tool_level`` 1 or -1): the main spec gets a
    runner and a trace flag; extra specs get nothing. Returns False when the
    module must be imported instead.
    """
    from . import _manifest

    kind = entry.get("kind")
    if kind == _manifest.KIND_SKIP:
        return True
    if kind != _manifest.KIND_LAZY:
        return False
    specs = entry.get("specs")
    if not isinstance(specs, dict):
        return False
    spec = specs.get("TOOL_SPEC")
    names = _manifest.tool_names_of(entry)
    if not isinstance(spec, dict) or not names:
        return False
    try:
        from ._tool_load_util import _LOADED_SINGLE_TOOLS

        # Individually loaded tools must become LLM-visible: import them.
        if any(name in _LOADED_SINGLE_TOOLS for name in names):
            return False
    except Exception:
        return False
    if any(name in _EMBEDDED_EXCLUDED_TOOLS for name in names):
        return False
    tool_name = names[0]
    module_name = f"{__name__}.{short_name}"
    with _TOOLS_LOCK:
        _RUNNERS[tool_name] = _LazyRunner(module_name, tool_name)
        _TOOL_TRACE_FLAGS[tool_name] = _get_tool_emit_trace(spec)
        _TOOL_DESCRIBERS.pop(tool_name, None)
        _MANIFEST_VIEWS[short_name] = specs
    return True


def _load_plugins() -> None:
    """Discover and load tool plugin modules under tools/."""
    with _TOOLS_LOCK:
        TOOL_SPECS.clear()
        _RUNNERS.clear()
        _BUSY_LABEL_TOOLS.clear()
        global _TOOL_SPECS_DIRTY
        _TOOL_SPECS_DIRTY = True
        _TOOL_TRACE_FLAGS.clear()
        _TOOL_DESCRIBERS.clear()
        _MANIFEST_VIEWS.clear()

    # 1. Load internal tools
    pkg_dir = os.path.dirname(__file__)
    manifest = _open_manifest_session(pkg_dir)
    for m in iter_modules([pkg_dir]):
        if m.name.startswith("_") or m.name in _NON_PLUGIN_MODULES:
            continue

        # Lazy-loaded modules are skipped here; imported on demand
        # (e.g. when an on-demand tool is loaded individually).
        if m.name in _LAZY_TOOL_MODULES:
            lazy_spec = _load_lazy_tool_spec(m.name)
            # Pre-register lazy specs when the active provider searches the
            # complete catalog server-side or client-side.
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
        # Fast path: register from the cached manifest without importing.
        # Modules imported earlier in this process keep the reload path below.
        if manifest is not None and mod_name not in sys.modules:
            cached_entry = manifest.cached.get(m.name)
            if cached_entry is not None and _register_from_manifest(
                m.name, cached_entry
            ):
                manifest.entries[m.name] = cached_entry
                continue
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
                    # Preserve CLI-only modules already imported as helpers;
                    # they still may contribute CMD_SPEC/CMD_SPECS entries.
                    _register_dynamic_commands(_existing_mod)
                    if manifest is not None:
                        manifest.record(m.name, _existing_mod)
                    continue
                mod = reload(_existing_mod)
            else:
                mod = import_module(mod_name)
            # Classify before registering: registration may mutate the spec.
            if manifest is not None:
                manifest.record(m.name, mod)
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
                    default="[tools] Failed to load internal plugin {mod_name}: {err}",
                    mod_name=mod_name,
                    err=repr(e),
                ),
                file=sys.stderr,
            )

    if manifest is not None:
        manifest.save()

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
                                    default="[tools] Loaded external tool: {entry_name}",
                                    entry_name=entry.name,
                                ),
                                file=sys.stderr,
                            )
                except Exception as e:
                    print(
                        _(
                            "log.load_fail.external",
                            default="[tools] Failed to load external plugin {entry_path}: {err}",
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


def _computer_use_is_enabled() -> bool:
    """Return the shared Computer Use enablement flag for tool filtering."""
    return (env_get("UAGENT_COMPUTER_USE", "0") or "0").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _computer_use_allowed_for_current_execution() -> bool:
    try:
        from ..runtime.execution_broker import computer_use_allowed

        return computer_use_allowed()
    except Exception:
        return False


def _filter_computer_use_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _computer_use_allowed_for_current_execution():
        return specs
    from ..runtime.execution_broker import is_computer_use_tool_spec

    return [spec for spec in specs if not is_computer_use_tool_spec(spec)]


def is_computer_use_conflict(spec: dict[str, Any] | None) -> bool:
    """Whether a TOOL_SPEC must be hidden by the active Computer Use policy."""
    if not isinstance(spec, dict):
        return False
    if not _computer_use_allowed_for_current_execution():
        from ..runtime.execution_broker import is_computer_use_tool_spec

        if is_computer_use_tool_spec(spec):
            return True
    return bool(
        _computer_use_is_enabled() and spec.get("computer_use_conflict") is True
    )


def _hide_analyze_image_for_chat_vision() -> bool:
    """Hide analyze_image when the main chat can carry image_url input.

    Evaluate this at tool-spec request time because provider/model environment
    variables may be loaded after tool modules are imported.
    """
    try:
        from ..env_utils import env_get
        from ..util_image import provider_allows_chat_vision

        provider = (env_get("UAGENT_PROVIDER") or "").strip().lower()
        use_responses = (env_get("UAGENT_RESPONSES") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        return bool(
            provider
            and provider_allows_chat_vision(
                provider,
                use_responses_api=use_responses,
            )
        )
    except Exception:
        return False


def get_tool_specs() -> list[dict[str, Any]]:
    """Return tool specs for the LLM."""
    # In Sandbox mode, including Remote Web/A2A, never load Host plugins to
    # build the catalog. Only static operations implemented by the Worker show.
    try:
        from ..runtime.execution_broker import (
            SecurityProfile as _SecurityProfile,
            current_profile as _current_profile,
            current_sandbox_enabled as _current_sandbox_enabled,
        )

        if (
            _current_profile()
            in {_SecurityProfile.LOCAL_TRUSTED, _SecurityProfile.REMOTE}
            and _current_sandbox_enabled()
        ):
            from ..runtime.mxc_backend import sandbox_tool_specs

            sandbox_specs = sandbox_tool_specs()
            try:
                from .. import core as _sandbox_core

                register = getattr(_sandbox_core, "register_tool_context_names", None)
                if callable(register):
                    register(
                        [
                            spec["function"]["name"]
                            for spec in sandbox_specs
                            if isinstance(spec.get("function"), dict)
                        ]
                    )
            except Exception:
                pass
            return sandbox_specs
    except ImportError:
        pass
    global _TOOL_SPECS_CACHE, _TOOL_SPECS_DIRTY, _ANALYZE_IMAGE_HIDDEN
    global _TOOL_SPECS_CACHE_EMBEDDED
    _ensure_loaded()
    # Discovery owns the names; core only transports opaque per-tool slots.
    try:
        from .. import core as _core

        register = getattr(_core, "register_tool_context_names", None)
        if callable(register):
            register(
                [
                    spec.get("function", {}).get("name")
                    for spec in _filter_sub_agent_job_tools(TOOL_SPECS)
                    if isinstance(spec, dict) and isinstance(spec.get("function"), dict)
                ]
            )
    except Exception:
        pass
    hide_analyze_image = _hide_analyze_image_for_chat_vision()
    _embedded_now = _is_embedded_mode()
    if (
        not _TOOL_SPECS_DIRTY
        and _TOOL_SPECS_CACHE is not None
        and _ANALYZE_IMAGE_HIDDEN == hide_analyze_image
        and _TOOL_SPECS_CACHE_EMBEDDED == _embedded_now
    ):
        return _filter_computer_use_specs(
            _filter_sub_agent_job_tools(_TOOL_SPECS_CACHE)
        )

    # Embedded mode hides management tools unless explicitly loaded. Native
    # tool_search filtering belongs to the delivery layer, not this catalog
    # source, so normal-mode catalog callers always see the full registry.
    _native_exclusions: set[str] = set()
    if _is_embedded_mode():
        # Embedded mode: hide management tools from the LLM unless one tool
        # from their module group was explicitly loaded (--enable-tool /
        # :tools load). Loading tool_catalog therefore also surfaces
        # tool_load / unload_tool so discovery keeps working.
        try:
            from ._tool_load_util import _LOADED_SINGLE_TOOLS

            _loaded = set(_LOADED_SINGLE_TOOLS)
            _native_exclusions = {
                name
                for name in _EMBEDDED_EXCLUDED_TOOLS
                if not any(
                    name in group and (group & _loaded)
                    for group in _EMBEDDED_EXCLUDED_TOOL_GROUPS
                )
            }
        except Exception:
            _native_exclusions = set(_EMBEDDED_EXCLUDED_TOOLS)
    # Note:
    # - Both Chat Completions and Responses expect tools without a top-level "name".
    #   The canonical form is: {"type":"function","function":{"name":..., ...}}
    # - Some SDKs/proxies mirrored name to top-level, but strict APIs (HuggingFace
    #   router, etc.) reject tools[i].name, so we no longer include it.

    clean_specs: list[dict[str, Any]] = []
    for spec in TOOL_SPECS:
        if is_computer_use_conflict(spec):
            continue
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
        spec_copy.pop("computer_use_conflict", None)
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
    _TOOL_SPECS_CACHE_EMBEDDED = _embedded_now
    _ANALYZE_IMAGE_HIDDEN = hide_analyze_image
    return _filter_computer_use_specs(_filter_sub_agent_job_tools(clean_specs))


def get_tool_catalog(
    *,
    query: str,
    max_results: int = 12,
    tool_specs: Optional[list[dict[str, Any]]] = None,
    all_items: bool = False,
) -> list[dict[str, Any]]:
    """Return a lightweight searchable catalog of tools.

    If all_items is True, return all loaded + unloaded tools without query
    filtering. Implemented in ``_catalog`` (imported on first use).
    """
    from ._catalog import get_tool_catalog as _get_tool_catalog

    return _get_tool_catalog(
        query=query,
        max_results=max_results,
        tool_specs=tool_specs,
        all_items=all_items,
    )


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
_CONFIRMATION_CALLBACK = None


def set_confirmation_callback(callback):
    """Install a host/UI confirmation callback for side-effecting tools."""
    global _CONFIRMATION_CALLBACK
    _CONFIRMATION_CALLBACK = callback


def get_confirmation_callback():
    """Return the currently configured host confirmation callback."""
    return _CONFIRMATION_CALLBACK


def configure_default_confirmation() -> None:
    from .tool_policy import default_confirmation_callback, reset_confirmation_grants

    reset_confirmation_grants()
    set_confirmation_callback(default_confirmation_callback)


def get_tool_policy(tool_name: str, args: dict[str, Any] | None = None):
    """Return the normalized side-effect policy for a tool call."""
    from .tool_policy import policy_for

    return policy_for(tool_name, args)


def is_parallel_safe(tool_name: str, args: dict[str, Any] | None = None) -> bool:
    """Check whether a tool call is safe for parallel execution.

    Most tools use a static ``x_parallel_safe`` flag. HTTP requests are
    method-sensitive: read-only methods may run in parallel, while writes
    remain serial.
    """
    from ..runtime.execution_broker import (
        ExecutionClass,
        SecurityProfile,
        current_profile,
        current_sandbox_enabled,
        current_authorization_valid,
        route_tool,
    )

    if current_profile() is SecurityProfile.LOCAL_TRUSTED and current_sandbox_enabled():
        # Sandbox-safe reads need no Host plugin metadata. Mutating/exec tools
        # remain serial; the adapter also serializes all per-session IPC.
        return tool_name in {"file_exists", "read_file"}
    if current_profile() is SecurityProfile.REMOTE:
        if not current_authorization_valid(require_check=True):
            return False
        known_tool = tool_name in _RUNNERS or tool_name in _LAZY_TOOL_NAME_TO_MODULE
        decision = route_tool(
            tool_name,
            args,
            profile=current_profile(),
            sandbox_enabled=current_sandbox_enabled(),
            backend_available=False,
            known_tool=known_tool,
        )
        if (
            not decision.allowed
            or decision.execution_class is not ExecutionClass.BROKERED
        ):
            return False
    else:
        _ensure_loaded()

    from .tool_policy import is_parallel_safe as _policy_is_parallel_safe

    policy_result = _policy_is_parallel_safe(tool_name, args)
    if policy_result:
        return True
    # Compatibility fallback for existing plugin declarations. Unknown tools
    # remain serial unless they explicitly opted into the legacy flag.
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
    future_map: dict[concurrent.futures.Future, tuple[int, str, dict[str, Any]]] = {}

    from ..runtime.identity_context import submit_with_current_context

    for idx, (name, args) in enumerate(calls):
        future = submit_with_current_context(
            _PARALLEL_TOOL_EXECUTOR, run_tool, name, args
        )
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


def _call_tool_runner(
    name: str, runner: Any, args: dict[str, Any], *, tool_call_id: str
) -> str:
    """Invoke a tool runner without letting it terminate the host process."""
    import time

    started = time.perf_counter()
    tool_active_token = None
    reset_tool_runner_active = None
    try:
        from ..runtime.execution import (
            mark_tool_running,
            mark_tool_waiting,
            reset_tool_runner_active,
            set_tool_runner_active,
        )

        mark_tool_waiting()
        tool_active_token = set_tool_runner_active(True)
    except Exception:
        mark_tool_running = None
        mark_tool_waiting = None
    try:
        result = runner(args)
    except Exception as e:
        try:
            from ..runtime.logging_setup import log_event

            log_event(
                "tool.failed",
                tool=name,
                tool_call_id=tool_call_id,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                status="error",
                error_type=type(e).__name__,
            )
        except Exception:
            pass
        return f"[tool runtime error] name={name!r} err={type(e).__name__}: {e}"
    except SystemExit as e:
        # Tools must return errors, not exit the agent process.
        try:
            from ..runtime.logging_setup import log_event

            log_event(
                "tool.failed",
                tool=name,
                tool_call_id=tool_call_id,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                status="error",
                error_type="SystemExit",
            )
        except Exception:
            pass
        return f"[tool runtime error] name={name!r} err=SystemExit: {e}"
    finally:
        if callable(mark_tool_running):
            mark_tool_running()
        if tool_active_token is not None and callable(reset_tool_runner_active):
            reset_tool_runner_active(tool_active_token)
        # Opt in to the extra GC pass after each tool. Normal execution keeps
        # Python's default reference counting / generational GC behavior.
        if (os.getenv("UAGENT_GC_AFTER_TOOL", "0") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            try:
                import gc

                gc.collect()
            except Exception:
                pass

    try:
        from ..runtime.logging_setup import log_event

        log_event(
            "tool.completed",
            tool=name,
            tool_call_id=tool_call_id,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            status="ok",
        )
    except Exception:
        pass
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False)
    except Exception:
        return str(result)


def _record_policy_audit(
    *,
    tool_name: str,
    args: dict[str, Any],
    decision: str,
    reason: str = "",
    tool_call_id: str | None = None,
) -> None:
    """Best-effort persistence of policy decisions for the active session."""
    try:
        from .. import core as _core

        store = getattr(_core, "session_store", None)
        session_id = getattr(_core, "session_id", None)
        if store is not None and session_id:
            store.record_policy_decision(
                session_id,
                tool_name=tool_name,
                decision=decision,
                args=args,
                reason=reason,
                tool_call_id=tool_call_id,
            )
    except Exception:
        # Auditing must not make an otherwise valid tool call fail.
        pass


def get_tool_describer(tool_name: str) -> Optional[Callable[..., Any]]:
    """Return the registered action describer for ``tool_name`` (if any)."""

    with _TOOLS_LOCK:
        describer = _TOOL_DESCRIBERS.get(tool_name)
        lazy = isinstance(_RUNNERS.get(tool_name), _LazyRunner)
    if describer is None and lazy:
        # A lazy plugin registers its describer when it is imported.
        try:
            _resolve_lazy_runner(tool_name)
        except Exception:
            return None
        with _TOOLS_LOCK:
            describer = _TOOL_DESCRIBERS.get(tool_name)
    return describer


def build_tool_description(tool_name: str, args: Any) -> str:
    """Return the tool-owned localized action line for ``args``, or ``""``.

    The text is flattened, secret-masked, and bounded here, so callers can print
    it unchanged. An empty string means "no describer" and the caller must fall
    back to the classic ``name=... args=...`` trace.
    """

    describer = get_tool_describer(tool_name)
    if describer is None:
        return ""
    safe_args: dict[str, Any] = args if isinstance(args, dict) else {}
    try:
        text = describer(safe_args)
    except Exception:
        # A broken describer must never break tool execution or the trace.
        return ""
    if text is None:
        return ""
    from ..runtime.tool_result_display import bound_display_text

    return bound_display_text(text)


def run_tool(name: str, args: dict[str, Any]) -> str:
    """Entry point for executing a tool_call."""
    # Every ingress is routed before plugin loading, so rejected remote tools
    # cannot trigger lazy-import side effects. This stage has no sandbox backend.
    from ..runtime.execution_broker import (
        ExecutionClass,
        SecurityProfile,
        current_profile,
        current_sandbox_enabled,
        current_scope,
        route_tool,
        run_brokered_tool,
        current_authorization_valid,
        computer_use_allowed,
        is_computer_use_tool_name,
    )

    # Resolve @A{0}..@A{9} path aliases at the common dispatch boundary.
    # Sandbox-routed calls are the exception: the worker expands aliases
    # from its workspace-local store instead, because the host store is
    # outside the isolation boundary and cannot see aliases registered
    # inside the sandbox (nor should sandbox calls resolve host aliases).
    _sandbox_routed = False
    if (
        current_profile() in {SecurityProfile.LOCAL_TRUSTED, SecurityProfile.REMOTE}
        and current_sandbox_enabled()
    ):
        from ..runtime.mxc_backend import TOOL_NAMES as _sandbox_tool_names

        _sandbox_routed = name in _sandbox_tool_names
    if not _sandbox_routed:
        try:
            args = resolve_tool_args(args)
        except ValueError as exc:
            return f"[tool argument error] name={name!r} err={exc}"
    # Never trust an approval marker supplied by the model or caller. It is
    # added below only after the common confirmation callback approves.
    if name == "rename_path":
        from .tool_policy import CONFIRMATION_GRANTED_ARG

        args = dict(args)
        args.pop(CONFIRMATION_GRANTED_ARG, None)
    from uuid import uuid4

    tool_call_id = str(uuid4())
    if is_computer_use_tool_name(name) and not computer_use_allowed():
        _record_policy_audit(
            tool_name=name,
            args=args,
            decision="deny",
            reason="Computer Use is restricted to trusted local Sandbox-off execution",
            tool_call_id=tool_call_id,
        )
        return "[tool policy] Computer Use is disabled for this execution profile"
    policy = get_tool_policy(name, args)
    try:
        from .enterprise_policy import get_enterprise_policy
        from .. import core as _core

        if (
            getattr(_core, "auto_pilot_active", False)
            and get_enterprise_policy().auto_pilot_requires_confirmation(name, args)
        ) or (
            os.environ.get("UAGENT_INJECT_MODE") == "1"
            and get_enterprise_policy().inject_requires_confirmation(name, args)
        ):
            policy = policy.__class__(
                side_effect=policy.side_effect,
                parallel_safe=policy.parallel_safe,
                resource_key=policy.resource_key,
                requires_confirmation=True,
            )
    except Exception:
        pass
    unified_policy = None
    unified_policy_revision = ""
    unified_decision = None
    try:
        from ..runtime.policy_engine import PolicyDecision, UnifiedPolicy

        unified_policy = UnifiedPolicy.from_environment()
        unified_policy_revision = getattr(unified_policy, "revision", "")
        unified_decision = unified_policy.decide(name, args)
        if unified_decision is PolicyDecision.DENY:
            _record_policy_audit(
                tool_name=name,
                args=args,
                decision="deny",
                reason="configured policy",
                tool_call_id=tool_call_id,
            )
            return "[tool policy] denied by configured policy"
        if unified_decision is PolicyDecision.CONFIRM:
            if _CONFIRMATION_CALLBACK is None:
                _record_policy_audit(
                    tool_name=name,
                    args=args,
                    decision="confirm",
                    reason="confirmation unavailable",
                    tool_call_id=tool_call_id,
                )
                return "[tool policy] confirmation unavailable"
            policy = policy.__class__(
                side_effect=policy.side_effect,
                parallel_safe=policy.parallel_safe,
                resource_key=policy.resource_key,
                requires_confirmation=True,
            )
    except Exception as exc:
        return f"[tool policy] unified policy error: {type(exc).__name__}: {exc}"

    # Authorization and side-effect policy are settled before execution class
    # selection. Capability rejection happens before a confirmation or Runner.
    profile = current_profile()
    trusted_scope = current_scope()
    sandboxed_execution = (
        profile in {SecurityProfile.LOCAL_TRUSTED, SecurityProfile.REMOTE}
        and current_sandbox_enabled()
    )
    sandbox_manager = None
    sandbox_capabilities = None
    sandbox_tool_names: frozenset[str] = frozenset()
    if sandboxed_execution:
        from ..runtime.mxc_backend import (
            TOOL_NAMES as sandbox_tool_names,
            current_session_manager,
        )

        sandbox_manager = current_session_manager()
        sandbox_capabilities = getattr(sandbox_manager, "capabilities", None)
        if trusted_scope is None:
            return "[tool policy] trusted sandbox scope is required"
        if name not in sandbox_tool_names:
            brokered = False
            if profile is SecurityProfile.REMOTE:
                from ..runtime.execution_broker import (
                    ExecutionClass,
                    classify_tool,
                )

                brokered = classify_tool(name, args) is ExecutionClass.BROKERED
            if not brokered:
                local_denial = profile is SecurityProfile.LOCAL_TRUSTED
                _record_policy_audit(
                    tool_name=name,
                    args=args,
                    decision="deny",
                    reason=(
                        "tool is not in the local MXC allowlist"
                        if local_denial
                        else "tool is not in the MXC allowlist or remote broker"
                    ),
                    tool_call_id=tool_call_id,
                )
                if local_denial:
                    return "[tool policy] tool is not available in the local sandbox"
                return "[tool policy] tool is not available in the configured sandbox"
    known_tool = (
        name in _RUNNERS
        or name in _LAZY_TOOL_NAME_TO_MODULE
        or (sandboxed_execution and name in sandbox_tool_names)
    )
    routing = route_tool(
        name,
        args,
        profile=profile,
        sandbox_enabled=current_sandbox_enabled(),
        backend_available=(
            sandbox_manager is not None and sandbox_capabilities is not None
        ),
        backend_capabilities=sandbox_capabilities,
        known_tool=known_tool,
    )
    if not routing.allowed:
        _record_policy_audit(
            tool_name=name,
            args=args,
            decision="deny",
            reason=routing.reason,
            tool_call_id=tool_call_id,
        )
        return f"[tool policy] execution denied: {routing.reason}"
    if not current_authorization_valid(require_check=profile is SecurityProfile.REMOTE):
        _record_policy_audit(
            tool_name=name,
            args=args,
            decision="deny",
            reason="current principal or scope authorization is no longer valid",
            tool_call_id=tool_call_id,
        )
        return "[tool policy] current authorization is no longer valid"
    brokered_remote = (
        profile is SecurityProfile.REMOTE
        and routing.execution_class is ExecutionClass.BROKERED
    )
    if name in _SUB_AGENT_JOB_TOOL_NAMES and not _sub_agent_job_tools_visible():
        return json.dumps(
            {
                "status": "blocked",
                "reason": "foreground_main_agent_only",
                "message": "Sub-Agent Job orchestration is available only to an integrated foreground Main Agent.",
            },
            ensure_ascii=False,
        )
    if not brokered_remote and not sandboxed_execution:
        _ensure_loaded()
    runner = None if sandboxed_execution else _RUNNERS.get(name)
    if runner is None and not brokered_remote and not sandboxed_execution:
        # Lazy-load fallback: unknown remote tools never reach this import path.
        mod_name = _LAZY_TOOL_NAME_TO_MODULE.get(name)
        if mod_name:
            _ensure_lazy_tool_loaded(mod_name)
            runner = _RUNNERS.get(name)
        if runner is None:
            try:
                from ._tool_load_util import enable_single_tool

                if enable_single_tool(name):
                    runner = _RUNNERS.get(name)
            except Exception:
                pass
        if runner is None:
            return f"[tool error] unknown tool: {name}"
    if isinstance(runner, _LazyRunner):
        # Import the plugin now so its describer, busy label and real runner
        # are registered before the trace and the call below.
        try:
            runner = runner.resolve()
        except Exception as exc:
            return (
                f"[tool error] failed to load tool {name}: "
                f"{type(exc).__name__}: {exc}"
            )
        if runner is None:
            return f"[tool error] unknown tool: {name}"

    _record_policy_audit(
        tool_name=name,
        args=args,
        decision="confirm" if policy.requires_confirmation else "allow",
        reason="tool policy",
        tool_call_id=tool_call_id,
    )

    # Display the final, masked arguments before confirmation or execution so
    # the user can see what a side-effecting call is about to do. Keeping this
    # in the common dispatcher also covers serial and parallel execution.
    if _should_emit_tool_trace(name):
        _emit_tool_trace(name, args)
    _emit_remote_tool_progress(name, args)

    try:
        from ..runtime.logging_setup import log_event

        log_event(
            "tool.dispatch",
            tool=name,
            tool_call_id=tool_call_id,
            side_effect=policy.side_effect.value,
            resource_key=policy.resource_key,
        )
    except Exception:
        pass
    if policy.requires_confirmation:
        if _CONFIRMATION_CALLBACK is None:
            _record_policy_audit(
                tool_name=name,
                args=args,
                decision="deny",
                reason="confirmation unavailable",
                tool_call_id=tool_call_id,
            )
            return "[tool policy] confirmation unavailable"
        _approved_args = json.dumps(
            args, sort_keys=True, ensure_ascii=False, default=str
        )
        try:
            if not bool(_CONFIRMATION_CALLBACK(name, args, policy)):
                _record_policy_audit(
                    tool_name=name,
                    args=args,
                    decision="deny",
                    reason="confirmation denied",
                    tool_call_id=tool_call_id,
                )
                return "[tool policy] confirmation denied"
            if (
                json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
                != _approved_args
            ):
                _record_policy_audit(
                    tool_name=name,
                    args=args,
                    decision="deny",
                    reason="arguments changed during confirmation",
                    tool_call_id=tool_call_id,
                )
                return "[tool policy] confirmation invalidated"
            if name == "rename_path":
                from .tool_policy import (
                    CONFIRMATION_GRANTED_ARG,
                    CONFIRMATION_GRANTED_TOKEN,
                )

                args[CONFIRMATION_GRANTED_ARG] = CONFIRMATION_GRANTED_TOKEN
        except Exception as exc:
            return f"[tool policy] confirmation failed: {type(exc).__name__}"

    # Re-evaluate authorization after any confirmation wait. A policy edit,
    # role/permission change, or newly-denied decision invalidates this call.
    if unified_policy is not None:
        try:
            from ..runtime.policy_engine import UnifiedPolicy

            fresh_policy = UnifiedPolicy.from_environment()
            fresh_decision = fresh_policy.decide(name, args)
            if (
                getattr(fresh_policy, "revision", "") != unified_policy_revision
                or fresh_decision != unified_decision
            ):
                _record_policy_audit(
                    tool_name=name,
                    args=args,
                    decision="deny",
                    reason="policy changed while awaiting execution",
                    tool_call_id=tool_call_id,
                )
                return "[tool policy] policy changed; execution denied"
        except Exception as exc:
            return f"[tool policy] revalidation failed: {type(exc).__name__}"
    if current_profile() is not profile or current_scope() != trusted_scope:
        return "[tool policy] trusted execution binding changed; execution denied"
    if not current_authorization_valid(require_check=profile is SecurityProfile.REMOTE):
        _record_policy_audit(
            tool_name=name,
            args=args,
            decision="deny",
            reason="principal, project, room, or task authorization was revoked",
            tool_call_id=tool_call_id,
        )
        return "[tool policy] current authorization is no longer valid"
    refreshed_route = route_tool(
        name,
        args,
        profile=current_profile(),
        sandbox_enabled=current_sandbox_enabled(),
        backend_available=(
            sandbox_manager is not None and sandbox_capabilities is not None
        ),
        backend_capabilities=sandbox_capabilities,
        known_tool=known_tool,
    )
    if not refreshed_route.allowed or refreshed_route != routing:
        return "[tool policy] execution route changed; execution denied"
    if brokered_remote:
        return run_brokered_tool(name)
    if sandboxed_execution:
        from ..runtime.mxc_backend import run_sandbox_tool

        return run_sandbox_tool(trusted_scope, name, args)

    # Bind only the outcome of the common policy confirmation to this runner.
    # Keep _call_tool_runner's public signature stable for tracing wrappers.
    def _run_with_confirmation() -> str:
        from .tool_confirmation import dispatched_tool

        with dispatched_tool(name, approved=policy.requires_confirmation):
            return _call_tool_runner(name, runner, args, tool_call_id=tool_call_id)

    # During human_ask, Busy should be turned off (it will wait for input).
    # After completion, set Busy back to "LLM" so GUI does not look stuck in IDLE.
    if name == "human_ask":
        # human_ask needs to set active state before clearing Busy,
        # so we delegate status handling to the runner implementation.
        try:
            return _run_with_confirmation()
        finally:
            _safe_set_status(True, "LLM")

    # Busy-labeled tools
    status_label = _BUSY_LABEL_TOOLS.get(name)
    if status_label is not None:
        _safe_set_status(True, status_label)
        try:
            return _run_with_confirmation()
        finally:
            _safe_set_status(True, "LLM")

    # Otherwise do not touch status
    return _run_with_confirmation()


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
    """Optionally preload tool plugins synchronously.

    Warmup is disabled by default. Set ``UAGENT_TOOLS_WARMUP=1`` to opt in to
    a blocking preload. This must stay synchronous: plugin imports can trigger
    optional-dependency installation, and doing that in a daemon thread causes
    packages to be installed in the background without being tied to a
    foreground operation. Without warmup, plugins are loaded synchronously on
    first access by :func:`_ensure_loaded`.
    """
    if (os.getenv("UAGENT_TOOLS_WARMUP", "0") or "").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
        "",
    ):
        return

    global _WARMUP_STARTED
    with _WARMUP_LOCK:
        if _INITIALIZED or _WARMUP_STARTED:
            return
        _WARMUP_STARTED = True

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
