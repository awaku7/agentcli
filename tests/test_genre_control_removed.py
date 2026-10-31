"""Genre-wide activation is retired; per-tool discovery remains available."""

import inspect
from pathlib import Path

from uagent.util_common import parse_startup_args
from uagent.web_impl.app import app


def test_genre_mask_cli_option_removed(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["uag"])
    args, _unknown = parse_startup_args()
    assert "tool_genre_mask" not in args
    assert "--tool-genre-mask" not in inspect.getsource(parse_startup_args)


def test_genre_control_api_removed():
    assert not any(
        getattr(route, "path", "") == "/api/tool-genres" for route in app.routes
    )


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

def test_web_clients_no_longer_request_genre_controls():
    root = Path(__file__).resolve().parents[1]
    paths = (
        "frontend/src/App.svelte",
        "frontend/src/lib/components/UnifiedPanel.svelte",
        "frontend/src/lib/stores.svelte.js",
        "src/uagent/static/assets/index.js",
        "src/uagent/templates/index.html",
    )
    for path in paths:
        source = (root / path).read_text(encoding="utf-8")
        assert "/api/tool-genres" not in source
        assert "toggleGenre(" not in source


def test_tool_genre_remains_catalog_metadata():
    from uagent.tools import get_tool_catalog

    assert callable(get_tool_catalog)
