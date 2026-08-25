"""Web server initialization and entry point (split from web.py)."""

from __future__ import annotations

import json
import os
import sys

from .. import core
from ..env_utils import env_get
from .. import tools
from .. import util_tools as tools_util
from ..runtime import runtime_init as _runtime_init
from ..runtime.logging_setup import log_event
from ..welcome import get_welcome_message

try:
    from ..tools.mcp_servers_shared import ensure_mcp_config_template
except ImportError:

    def ensure_mcp_config_template():
        pass  # type: ignore


import uvicorn

from .app import app
from .io import _web_server_log, web_human_ask, web_set_status
from .rooms import _thread_ctx, web_manager


def init_web():
    print(get_welcome_message())

    # Web process: suppress CLI [STATE] console output for the whole lifetime.
    # Must be set before any set_status() call (including first BUSY).
    try:
        setattr(core, "_is_web", True)
    except Exception:
        pass

    web_manager.original_set_status = core.set_status
    web_manager.original_log_message = core.log_message

    core.set_status = web_set_status

    # Web mode: UI message forwarding is handled per-room; keep core.log_message intact.
    # Tools callback init
    tools_util.init_tools_callbacks(core)

    cb = tools.context.get_callbacks()
    cb.is_gui = True

    # Register ask-user hook for project instruction selection (AGENTS.md).
    # runtime_instructions must not import web (circular); use this callback.
    try:
        from ..runtime.runtime_instructions import set_ask_user_hook

        def _web_ask_user(message: str) -> str:
            room = getattr(_thread_ctx, "room", None)
            if room is None:
                try:
                    with web_manager.active_room_lock:
                        room = web_manager.active_room
                except Exception:
                    room = None
            if room is None:
                return json.dumps(
                    {
                        "user_reply": "",
                        "display_reply": "",
                        "cancelled": True,
                    }
                )
            return web_human_ask(room, {"message": message})

        set_ask_user_hook(_web_ask_user)
    except Exception as e:
        try:
            _web_server_log(f"[web-init] ask hook register failed: {e!r}")
        except Exception:
            pass

    # Wrap tools: bind room context for parallel workers + route human_ask.
    original_run_tool = tools.run_tool

    def _resolve_web_room():
        room = getattr(_thread_ctx, "room", None)
        if room is not None:
            return room
        try:
            with web_manager.active_room_lock:
                return web_manager.active_room
        except Exception:
            return None

    def web_run_tool_wrapper(name, args):
        room = _resolve_web_room()
        # Parallel tool pool threads do not inherit thread-local room.
        # Bind it for the duration of the tool so set_status/logs reach UI.
        prev_room = getattr(_thread_ctx, "room", None)
        if room is not None and prev_room is None:
            _thread_ctx.room = room
        try:
            if name == "human_ask":
                if not room:
                    return json.dumps(
                        {
                            "user_reply": "",
                            "display_reply": "",
                            "cancelled": True,
                        }
                    )
                # Keep room busy while waiting for human input so Stop stays available
                # and reconnect clients see WAIT instead of a false IDLE.
                try:
                    room.set_status(True, "WAIT")
                    if web_manager.original_set_status:
                        # core.status_busy stays True for interrupt path.
                        web_manager.original_set_status(True, "WAIT")
                except Exception:
                    pass
                try:
                    return web_human_ask(room, args)
                finally:
                    try:
                        room.set_status(True, "LLM")
                        if web_manager.original_set_status:
                            web_manager.original_set_status(True, "LLM")
                    except Exception:
                        pass
            return original_run_tool(name, args)
        finally:
            if room is not None and prev_room is None:
                try:
                    _thread_ctx.room = None
                except Exception:
                    pass

    tools.run_tool = web_run_tool_wrapper


def main():
    from ..runtime.logging_setup import bind_event_context

    bind_event_context(session_id="web", correlation_id="web")
    log_event("web.start")
    sys.__stdout__.reconfigure(encoding="utf-8")
    import argparse

    from ..i18n import _

    parser = argparse.ArgumentParser(prog="uagw", add_help=False)
    parser.add_argument(
        "--tool-genre-mask",
        type=int,
        default=None,
        help=_(
            "Tool genre bitmask (1=basic,2=comm,4=office,8=devel,16=iot,32=exec,64=external,128=media,256=file,512=index,1023=all). Skips the interactive genre prompt when specified."
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
        "--host",
        type=str,
        default=None,
        help=_("Bind address (default: 127.0.0.1). Overrides UAGENT_WEB_HOST env var."),
    )
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        default=False,
        help=_(
            "Run in API-only mode without frontend (no HTML templates or static files)."
        ),
    )
    web_args, _web_unknown = parser.parse_known_args()

    # readme/quickstart first-run display removed (files no longer bundled)
    ensure_mcp_config_template()

    # Load and activate enabled plugins (MCP / agents / hooks); status for chat later
    try:
        from ..runtime.runtime_plugins import load_plugins_status_at_startup

        _plugins, _plugins_status = load_plugins_status_at_startup(activate=True)
        if _plugins_status:
            print(_plugins_status, file=sys.stderr)
        try:
            # Keep raw list so each room can format with its own locale.
            setattr(web_manager, "plugins_startup_list", _plugins)
        except Exception:
            pass
    except Exception:
        try:
            setattr(web_manager, "plugins_startup_list", [])
        except Exception:
            pass

    try:
        decision = _runtime_init.decide_workdir(env_workdir=env_get("UAGENT_WORKDIR"))
        _runtime_init.apply_workdir(decision)
        _runtime_init.reload_dotenv_custom()
        try:
            from ..runtime.session_store import attach_opt_in_session_store

            attach_opt_in_session_store(
                core,
                project_path=decision.chosen_expanded,
                entry_point="web",
            )
        except Exception as exc:
            print("[WARN] Session store unavailable: " + str(exc), file=sys.stderr)
        if getattr(web_args, "computer_use", None) is not None:
            os.environ["UAGENT_COMPUTER_USE"] = "1" if web_args.computer_use else "0"
        # Fail-fast env validation (aggregate missing vars)
        _runtime_init.validate_or_exit_startup_env(context="web")
        banner = _runtime_init.build_startup_banner(
            core=core,
            workdir=decision.chosen_expanded,
            workdir_source=decision.chosen_source,
        )
        print(banner, end="")

    except Exception as e:
        print(_("[FATAL] Failed to set workdir: %(err)s") % {"err": e}, file=sys.stderr)
        sys.exit(1)

    if web_args.tool_genre_mask is not None:
        from ..cli_startup import _apply_startup_tool_genre_mask

        _apply_startup_tool_genre_mask(web_args.tool_genre_mask)
    else:
        from ..cli_startup import _apply_startup_tool_genre_mask

        _apply_startup_tool_genre_mask(0)

    # Initialize runtime tools_enabled flag.
    # Priority: --use-tool / --no-use-tool CLI arg > UAGENT_USE_TOOL env var > default ON.
    _use_tool_arg = getattr(web_args, "use_tool", None)
    if _use_tool_arg is not None:
        core.tools_enabled = bool(_use_tool_arg)
    else:
        _use_tool_env = (env_get("UAGENT_USE_TOOL") or "").strip().lower()
        core.tools_enabled = _use_tool_env not in ("0", "false", "no", "off")

    init_web()
    try:
        tools.start_tools_warmup()
    except Exception:
        pass

    if web_args.no_frontend:
        # Remove frontend routes (/, /room/{room_id}, /static) for API-only mode
        _routes_to_remove = []
        for _route in list(app.router.routes):
            _path = getattr(_route, "path", "")
            if _path in ("/", "/room/{room_id}"):
                _routes_to_remove.append(_route)
            if type(_route).__name__ == "Mount" and _path == "/static":
                _routes_to_remove.append(_route)
        for _route in _routes_to_remove:
            app.router.routes.remove(_route)
        print(_("Starting in API-only mode (no frontend)."))
    import socket

    # Resolve bind host: --host arg > UAGENT_WEB_HOST env > default 127.0.0.1
    bind_host = "127.0.0.1"
    _env_host = (env_get("UAGENT_WEB_HOST") or "").strip()
    if _env_host:
        bind_host = _env_host
    if web_args.host:
        bind_host = web_args.host

    def get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    local_ip = get_local_ip()
    port = 8000
    sys.__stdout__.write(_("Starting server on") + f" http://localhost:{port}\n")
    if bind_host == "0.0.0.0" and local_ip and local_ip != "127.0.0.1":
        sys.__stdout__.write(_("External URL:") + f" http://{local_ip}:{port}\n")
    sys.__stdout__.flush()
    # Fire SessionStart hook
    try:
        from ..hooks_engine import fire_session_start

        fire_session_start()
    except Exception:
        pass

    config = uvicorn.Config(app, host=bind_host, port=port, ws_max_size=10_000_000)
    server = uvicorn.Server(config)
    try:
        server.run()
    finally:
        # Fire Stop hook
        try:
            from ..hooks_engine import fire_stop

            fire_stop()
        except Exception:
            pass
