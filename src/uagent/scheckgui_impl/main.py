"""GUI entry point (split from scheckgui.py)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import _, detect_lang
from .. import core
from ..runtime import runtime_init as _runtime_init
from ..runtime.logging_setup import log_event
from ..utils.paths import get_state_dir
from ..welcome import get_welcome_message
from . import state
from .config import GuiConfig, _load_font_size_config
from .mainwindow import MainWindow
from .theme import _GUI_STYLESHEET, _is_high_contrast
from .widgets import RedirectToLog


def main():
    from ..runtime.logging_setup import bind_event_context

    bind_event_context(session_id="gui", correlation_id="gui")
    log_event("gui.start")
    # Redirect stdout/stderr to in-memory buffer (no intermediate file)
    # Do this before any startup output.  A gui-scripts launcher has no
    # console on Windows, so stdout/stderr may also be None.
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    if original_stdout is not None:
        try:
            original_stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError, ValueError):
            pass
    sys.stdout = RedirectToLog(state._log_buffer, original_stdout)
    sys.stderr = RedirectToLog(state._log_buffer, original_stderr)

    # readme/quickstart first-run display removed (files no longer bundled)
    print(get_welcome_message())
    try:
        from ..tools.mcp_servers_shared import ensure_mcp_config_template
    except ImportError:

        def ensure_mcp_config_template():
            pass  # type: ignore

    ensure_mcp_config_template()

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--workdir",
        "-C",
        dest="workdir",
        help=_(
            "Specify the working directory. If omitted, use the UAGENT_WORKDIR environment variable or the current directory."
        ),
    )
    parser.add_argument(
        "--tool-genre-mask",
        type=int,
        default=None,
        help=_(
            "Tool genre bitmask (1=basic,2=comm,4=office,8=devel,16=iot,32=exec,64=external,128=media,256=file,512=index,1024=dev,2048=web,4096=utility,8191=all). Skips the interactive genre prompt when specified."
        ),
    )
    parser.add_argument(
        "--use-tool",
        dest="use_tool",
        action="store_true",
        default=None,
        help=_("Enable tool sending to LLM (overrides UAGENT_USE_TOOL env var)."),
    )
    parser.add_argument(
        "--no-use-tool",
        dest="use_tool",
        action="store_false",
        default=None,
        help=_("Disable tool sending to LLM (overrides UAGENT_USE_TOOL env var)."),
    )
    parser.add_argument(
        "--computer-use",
        dest="computer_use",
        action="store_true",
        default=None,
        help=_("Enable Computer Use (overrides UAGENT_COMPUTER_USE env var)."),
    )
    parser.add_argument(
        "--no-computer-use",
        dest="computer_use",
        action="store_false",
        default=None,
        help=_("Disable Computer Use (overrides UAGENT_COMPUTER_USE env var)."),
    )
    parser.add_argument(
        "--embedded",
        dest="embedded",
        action="store_true",
        default=False,
        help=_(
            "Embedded mode: disables the session store (UAGENT_SESSION_STORE=0) "
            "and hides tool management tools (tool_catalog, tool_load, unload_tool)."
        ),
    )
    args, unknown = parser.parse_known_args()
    if getattr(args, "embedded", False):
        os.environ["UAGENT_SESSION_STORE"] = "0"
        os.environ["UAGENT_EMBEDDED"] = "1"

    decision = _runtime_init.decide_workdir(
        cli_workdir=getattr(args, "workdir", None),
        env_workdir=os.environ.get("UAGENT_WORKDIR"),
    )
    _runtime_init.apply_workdir(decision)
    _runtime_init.reload_dotenv_custom()
    try:
        from ..runtime.session_store import attach_opt_in_session_store

        attach_opt_in_session_store(
            core,
            project_path=decision.chosen_expanded,
            entry_point="gui",
        )
    except Exception as exc:
        print("[WARN] Session store unavailable: " + str(exc), file=sys.stderr)
    if getattr(args, "computer_use", None) is not None:
        os.environ["UAGENT_COMPUTER_USE"] = "1" if args.computer_use else "0"

    _runtime_init.validate_or_exit_startup_env(context="gui")

    _mask = getattr(args, "tool_genre_mask", None)
    if _mask is None:
        _mask = 0  # default: nothing
    from ..cli_startup import _apply_startup_tool_genre_mask

    _apply_startup_tool_genre_mask(_mask)

    # Initialize runtime tools_enabled flag.
    # Priority: --use-tool / --no-use-tool CLI arg > UAGENT_USE_TOOL env var > default ON.
    from ..env_utils import env_get as _env_get

    _use_tool_arg = getattr(args, "use_tool", None)
    if _use_tool_arg is not None:
        core.tools_enabled = bool(_use_tool_arg)
    else:
        _use_tool_env = (_env_get("UAGENT_USE_TOOL") or "").strip().lower()
        core.tools_enabled = _use_tool_env not in ("0", "false", "no", "off")

    prov = (os.environ.get("UAGENT_PROVIDER") or "azure").lower()
    model = ""

    app = QtWidgets.QApplication(sys.argv)

    # Resolve font size config file path
    try:
        state._FONT_SIZE_CONFIG_FILE = str(Path(get_state_dir()) / "gui_font_size.json")
    except Exception:
        pass

    # Load saved font size
    state._FONT_SIZE_LEVEL = _load_font_size_config()

    # ---- Modern font (base; _apply_font_size will fine-tune) ----
    try:
        _fd = QtGui.QFontDatabase()
        _is_mac = sys.platform == "darwin"
        ui_sizes = state._UI_FONT_SIZES_MAC if _is_mac else state._UI_FONT_SIZES
        _ui_size = ui_sizes[state._FONT_SIZE_LEVEL]
        if sys.platform == "win32":
            _font_name = "Segoe UI Variable"
            if not _fd.hasFamily(_font_name):
                _font_name = "Segoe UI"
            _font = QtGui.QFont(_font_name, _ui_size)
        elif _is_mac:
            _font_name = "SF Pro" if _fd.hasFamily("SF Pro") else "Helvetica Neue"
            _font = QtGui.QFont(_font_name, _ui_size)
        else:
            _font_name = "Noto Sans" if _fd.hasFamily("Noto Sans") else "sans-serif"
            _font = QtGui.QFont(_font_name, _ui_size)
        app.setFont(_font)
    except Exception:
        pass

    # ---- Stylesheet (skip in high contrast mode to respect system palette) ----
    try:
        if not _is_high_contrast():
            app.setStyleSheet(_GUI_STYLESHEET)
    except Exception:
        pass

    try:
        if detect_lang() == "ar":
            app.setLayoutDirection(QtCore.Qt.RightToLeft)
    except Exception:
        pass
    win = MainWindow(GuiConfig(prov, model, unknown[0] if unknown else None))
    win.show()

    # Fire SessionStart hook and inject stdout into the open conversation
    try:
        from ..hooks_engine import (
            fire_session_start,
            inject_hook_context,
            take_pending_session_hook_texts,
        )

        _ss_results = fire_session_start()
        msgs = getattr(win, "messages", None)
        if isinstance(msgs, list):
            inject_hook_context(
                msgs, _ss_results, event_name="SessionStart", replace_event=False
            )
            take_pending_session_hook_texts()
    except Exception:
        pass

    exit_code = app.exec()

    # Fire Stop hook
    try:
        from ..hooks_engine import fire_stop

        fire_stop()
    except Exception:
        pass

    sys.exit(exit_code)
