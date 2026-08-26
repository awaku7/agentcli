import sys

from uagent.runtime.session_store import SessionStore
from uagent.util_common import parse_startup_args


def _parse(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["uag"] + argv)
    args, _unknown = parse_startup_args()
    return args


def _tool_names():
    from uagent import tools as T

    # Invalidate the spec cache so env changes take effect.
    T._TOOL_SPECS_DIRTY = True
    specs = T.get_tool_specs()
    return [s["function"]["name"] for s in specs if isinstance(s.get("function"), dict)]


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


def test_normal_mode_keeps_management_tools(monkeypatch):
    monkeypatch.delenv("UAGENT_EMBEDDED", raising=False)
    names = _tool_names()
    assert MANAGEMENT_TOOLS <= set(names)


def test_embedded_disables_session_store(monkeypatch):
    monkeypatch.setenv("UAGENT_SESSION_STORE", "0")
    assert SessionStore.from_environment() is None


def test_normal_session_store_enabled(monkeypatch):
    monkeypatch.delenv("UAGENT_SESSION_STORE", raising=False)
    store = SessionStore.from_environment()
    assert store is not None
    store.close()
