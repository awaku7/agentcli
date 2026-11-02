"""Genre-wide activation is retired; per-tool discovery remains available."""

import inspect
from pathlib import Path

from uagent.util_common import parse_startup_args


def test_genre_mask_cli_option_removed(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["uag"])
    args, _unknown = parse_startup_args()
    assert "tool_genre_mask" not in args
    assert "--tool-genre-mask" not in inspect.getsource(parse_startup_args)


def test_individual_tool_discovery_remains():
    from uagent.tools._genre_control_util import enable_single_tool, is_tool_loadable
    from uagent.tools.tools_control_tool import _register_tools_subcommands

    assert callable(enable_single_tool)
    assert callable(is_tool_loadable)
    _register_tools_subcommands()
    from uagent.tools import tools_control_tool

    commands = {spec["subcommand"] for spec in tools_control_tool.CMD_SPECS}
    assert {"list", "load", "reload"} <= commands
    assert "on" not in commands
    assert "off" not in commands


def test_tool_genre_remains_catalog_metadata():
    from uagent.tools import get_tool_catalog

    assert callable(get_tool_catalog)


def test_retired_startup_masks_are_absent_in_gui_and_a2a():
    root = Path(__file__).resolve().parents[1]
    entrypoints = (
        "src/uagent/scheckgui_impl/main.py",
        "src/uagent/a2a/server.py",
    )
    for path in entrypoints:
        source = (root / path).read_text(encoding="utf-8")
        assert "--tool-genre-mask" not in source


def test_translated_tools_help_hides_retired_genre_command():
    from types import SimpleNamespace

    from uagent.util_help import format_help_detail

    # Some translations localize the placeholder itself (for example, pt).
    def translated(value):
        return value.replace("<genre>", "<gênero>")

    result = format_help_detail("tools", core=SimpleNamespace(tr=translated))
    assert ":tools on|off" in result
    assert ":tools list" in result
    assert ":tools load" in result
    assert "<gênero>" not in result
    assert "Enable/disable a tool genre" not in result


def test_current_documentation_does_not_advertise_genre_switches():
    root = Path(__file__).resolve().parents[1]
    communication = (root / "docs/COMMUNICATION.md").read_text(encoding="utf-8")
    flow = (root / "src/uagent/docs/TOOL_FLOW.md").read_text(encoding="utf-8")
    develop_ja = (root / "src/uagent/docs/DEVELOP.ja.md").read_text(encoding="utf-8")
    assert "comm_control enable" not in communication
    assert "UAGENT_COMM_ENABLED=1" not in communication
    assert "Registration is controlled by `tool_level`, `tool_genre`" not in flow
    assert "起動時の genre mask でフィルタ" not in develop_ja
    for path in (root / "docs").glob("TOOL_CREATOR_GUIDE.*.md"):
        assert "Enables genre-based control" not in path.read_text(encoding="utf-8")
