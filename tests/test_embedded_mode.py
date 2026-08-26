import sys

from uagent.runtime.session_store import SessionStore
from uagent.util_common import parse_startup_args


def _parse(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["uag"] + argv)
    args, _unknown = parse_startup_args()
    return args


def _reload_tools():
    """Re-initialize the tool registry so env changes take effect.

    Registration decisions (embedded skip) are made during _load_plugins(),
    so tests must reset _INITIALIZED and re-run the plugin scan.
    """
    from uagent import tools as T

    with T._INIT_LOCK:
        T._INITIALIZED = False
        T.TOOL_SPECS.clear()
        T._RUNNERS.clear()
        T._TOOL_SPECS_CACHE = None
        T._TOOL_SPECS_DIRTY = True
        from uagent.tools import _genre_control_util as G

        G._LOADED_SINGLE_TOOLS.clear()
        G._TOOL_DYNAMIC_THRESHOLDS.clear()
        T._load_plugins()
        T._INITIALIZED = True


def _tool_names():
    from uagent import tools as T

    _reload_tools()
    specs = T.get_tool_specs()
    return [s["function"]["name"] for s in specs if isinstance(s.get("function"), dict)]


def _registry_names():
    from uagent import tools as T

    _reload_tools()
    return [s.get("function", {}).get("name") for s in T.TOOL_SPECS]


MANAGEMENT_TOOLS = {"tool_catalog", "tool_load", "unload_tool"}


def test_embedded_flag_parsed(monkeypatch):
    assert _parse(monkeypatch, ["--embedded"])["embedded"] is True


def test_embedded_flag_default_false(monkeypatch):
    assert _parse(monkeypatch, [])["embedded"] is False


def test_embedded_flag_with_other_options(monkeypatch):
    args = _parse(monkeypatch, ["--embedded", "--enable-tool", "md2idx"])
    assert args["embedded"] is True
    assert args["enable_tools"] == ["md2idx"]


def test_embedded_hides_management_tools(monkeypatch):
    monkeypatch.setenv("UAGENT_EMBEDDED", "1")
    names = _tool_names()
    assert not (MANAGEMENT_TOOLS & set(names))


def test_embedded_unregisters_management_tools(monkeypatch):
    monkeypatch.setenv("UAGENT_EMBEDDED", "1")
    names = _registry_names()
    assert not (MANAGEMENT_TOOLS & set(names))


def test_normal_mode_keeps_management_tools(monkeypatch):
    monkeypatch.delenv("UAGENT_EMBEDDED", raising=False)
    names = _tool_names()
    assert MANAGEMENT_TOOLS <= set(names)


def test_normal_mode_registers_management_tools(monkeypatch):
    monkeypatch.delenv("UAGENT_EMBEDDED", raising=False)
    names = _registry_names()
    assert MANAGEMENT_TOOLS <= set(names)


def test_embedded_disables_session_store(monkeypatch):
    monkeypatch.setenv("UAGENT_SESSION_STORE", "0")
    assert SessionStore.from_environment() is None


def test_normal_session_store_enabled(monkeypatch):
    monkeypatch.delenv("UAGENT_SESSION_STORE", raising=False)
    store = SessionStore.from_environment()
    assert store is not None
    store.close()


def test_embedded_no_stale_state_after_failed_load(monkeypatch):
    """Failed single-load must not leak state (registration refused)."""
    monkeypatch.setenv("UAGENT_EMBEDDED", "1")

    _reload_tools()
    from uagent import tools as T
    from uagent.tools import _genre_control_util as G
    from uagent.tools._genre_control_util import enable_single_tool

    orig = T._register_tool_module

    def refused(*_a, **_k):
        return False

    monkeypatch.setattr(T, "_register_tool_module", refused)
    ok = enable_single_tool("md2idx")
    monkeypatch.setattr(T, "_register_tool_module", orig)
    assert ok is False
    assert "md2idx" not in G._LOADED_SINGLE_TOOLS
    assert "md2idx" not in G._TOOL_DYNAMIC_THRESHOLDS


def test_embedded_explicit_load_management_tool(monkeypatch):
    """Explicitly requested management tools load even in embedded mode."""
    monkeypatch.setenv("UAGENT_EMBEDDED", "1")

    _reload_tools()
    from uagent import tools as T
    from uagent.tools._genre_control_util import enable_single_tool

    assert enable_single_tool("tool_catalog") is True
    names = [s.get("function", {}).get("name") for s in T.TOOL_SPECS]
    # tool_catalog is the module primary spec; tool_load / unload_tool come
    # from the same catalog_tool module (TOOL_SPEC_2 / TOOL_SPEC_3) and are
    # loaded together with it.
    assert MANAGEMENT_TOOLS <= set(names)
    # The loaded management tools are visible to the LLM.
    T._TOOL_SPECS_DIRTY = True
    llm_names = [
        s["function"]["name"]
        for s in T.get_tool_specs()
        if isinstance(s.get("function"), dict)
    ]
    assert MANAGEMENT_TOOLS <= set(llm_names)


def test_embedded_explicit_load_management_tool_catalog(monkeypatch):
    """Loaded management tools appear in the catalog with loaded=True."""
    monkeypatch.setenv("UAGENT_EMBEDDED", "1")

    _reload_tools()
    from uagent import tools as T
    from uagent.tools._genre_control_util import enable_single_tool

    assert enable_single_tool("tool_catalog") is True
    rows = T.get_tool_catalog(query="", all_items=True)
    by_name = {row.get("name"): row for row in rows}
    for name in MANAGEMENT_TOOLS:
        assert name in by_name, name
        assert by_name[name]["loaded"] is True, name


def test_embedded_catalog_excludes_management_tools(monkeypatch):
    """get_tool_catalog() must not surface management tools in embedded mode."""
    monkeypatch.setenv("UAGENT_EMBEDDED", "1")
    from uagent import tools as T

    _reload_tools()
    names = {row.get("name") for row in T.get_tool_catalog(query="", all_items=True)}
    assert not (MANAGEMENT_TOOLS & names)


def test_normal_catalog_includes_management_tools(monkeypatch):
    monkeypatch.delenv("UAGENT_EMBEDDED", raising=False)
    from uagent import tools as T

    _reload_tools()
    names = {row.get("name") for row in T.get_tool_catalog(query="", all_items=True)}
    assert MANAGEMENT_TOOLS <= names


def test_embedded_disables_catalog_steering(monkeypatch):
    """Catalog steering must not be emitted when management tools are absent."""
    monkeypatch.setenv("UAGENT_EMBEDDED", "1")
    from uagent.tools.llm_tool_narrowing import should_emit_catalog_steering

    assert should_emit_catalog_steering() is False
    assert (
        should_emit_catalog_steering(
            provider="openai", depname="gpt-5.6", use_responses_api=True
        )
        is False
    )


def test_normal_mode_keeps_catalog_steering(monkeypatch):
    monkeypatch.delenv("UAGENT_EMBEDDED", raising=False)
    from uagent.tools.llm_tool_narrowing import should_emit_catalog_steering

    assert should_emit_catalog_steering() is True


def test_embedded_legacy_narrowing_excludes_management_tools(monkeypatch):
    """GPT-5.4 legacy narrowing must not leak management tools in embedded mode."""
    monkeypatch.setenv("UAGENT_EMBEDDED", "1")
    from uagent.tools.llm_tool_narrowing import _select_tool_specs_legacy

    calls = [{"role": "user", "content": "markdownのファイルを並べ替えたい"}]
    specs = _select_tool_specs_legacy(calls)
    names = {
        s.get("function", {}).get("name")
        for s in specs
        if isinstance(s.get("function"), dict)
    }
    assert not (MANAGEMENT_TOOLS & names)
    assert "human_ask" in names
