"""Web server initialization and entry point (split from web.py)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from .. import core
from ..decision.settings import (
    add_decision_provider_argument,
    configure_decision_settings,
)
from ..env_utils import env_get
from .. import tools
from .. import util_tools as tools_util
from ..runtime import runtime_init as _runtime_init
from ..runtime.logging_setup import log_event
from ..runtime.sandbox_config import resolve_sandbox_mode as _resolve_web_sandbox_mode
from ..welcome import get_welcome_message

try:
    from ..tools.mcp_servers_shared import ensure_mcp_config_template
except ImportError:

    def ensure_mcp_config_template():
        pass  # type: ignore


from .._pip_auto import install_with_status as _install_web_dependency

_install_web_dependency("fastapi", "fastapi")
_install_web_dependency("uvicorn", "uvicorn")
import uvicorn

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from ..runtime.observability.trusted_ingress import RawSocketPeerCaptureMiddleware
from .app import app
from .io import _web_server_log, web_human_ask, web_set_status
from .rooms import _thread_ctx, get_context_web_room, web_manager


def _remote_human_ask_authorized(room) -> bool:
    """Authorize a Web UI confirmation against the current principal and Room."""
    if getattr(web_manager, "execution_profile", "remote") == "local_trusted":
        return True
    try:
        from ..runtime.execution_broker import current_scope, trusted_web_scope
        from ..runtime.identity_context import get_current_turn_context

        turn = get_current_turn_context()
        scope = trusted_web_scope(turn, str(getattr(room, "room_id", "")))
        if scope is None or current_scope() != scope:
            return False
        lock = getattr(room, "_lifecycle_lock", None)
        if lock is not None:
            with lock:
                contexts = tuple(getattr(room, "_connection_contexts", {}).values())
        else:
            contexts = tuple(getattr(room, "_connection_contexts", {}).values())
        for connection in contexts:
            identity = getattr(connection, "identity", None)
            if getattr(identity, "principal_id", None) != turn.principal_id:
                continue
            connection.validate_authentication_configuration()
            connection.validate_room_access(touch_activity=False)
            return True
        # Spawned workers do not receive connection credentials. Their parent
        # process validates inbound responses and broadcasts for this Room.
        return bool(
            getattr(room, "_web_parent_authorizes_connections", False)
            and getattr(room, "active_connections", None)
        )
    except Exception:
        return False


def _current_web_ask_principal(room) -> str:
    """Return the principal from the server-created TurnContext for this Room."""
    try:
        from ..runtime.execution_broker import trusted_web_scope
        from ..runtime.identity_context import get_current_turn_context

        turn = get_current_turn_context()
        if trusted_web_scope(turn, str(getattr(room, "room_id", ""))) is None:
            return ""
        return str(turn.principal_id)
    except Exception:
        return ""


def _initialize_local_web_sandbox(parser, *, sandbox_mode: str):
    """Initialize the verified local MXC backend before starting local Web."""
    from ..i18n import _
    from ..runtime.mxc_backend import (
        MxcSessionManager,
        describe_probe,
        install_session_manager,
        mxc_sdk_is_installed,
    )

    allow_install = False
    if sandbox_mode == "mxc" and not mxc_sdk_is_installed():
        if (
            os.environ.get("UAGENT_NON_INTERACTIVE", "").strip().lower()
            in {
                "1",
                "true",
                "yes",
                "on",
            }
            or not getattr(sys.stdin, "isatty", lambda: False)()
        ):
            parser.error(
                _(
                    "The MXC SDK is missing; non-interactive Web startup will not "
                    "install dependencies. Run `uagw --sandbox mxc` interactively "
                    "after reviewing the dependency prompt."
                )
            )
        try:
            answer = input(
                "Install the pinned MXC SDK (about 105 MB) in your user profile? [y/N] "
            )
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().lower() not in {"y", "yes"}:
            parser.error(
                _("MXC SDK installation was declined; local Web startup stopped.")
            )
        allow_install = True

    try:
        manager, report = MxcSessionManager.initialize(allow_install=allow_install)
    except Exception as exc:
        parser.error(
            _("Local Web Sandbox initialization failed: %(err)s", err=str(exc))
        )
    install_session_manager(manager)
    print(f"[sandbox] enabled: {describe_probe(report)}", file=sys.stderr)
    return manager


def _validate_web_sandbox_startup(
    parser,
    *,
    trusted_local: bool,
    sandbox_enabled: bool,
    backend_ready: bool = False,
) -> None:
    """Fail closed if local Web opted into Sandbox without a ready backend."""
    if trusted_local and sandbox_enabled and not backend_ready:
        from ..i18n import _

        parser.error(
            _(
                "Sandbox was enabled for local Web, but the MXC backend is not "
                "ready; refusing to start."
            )
        )


def _fire_web_lifecycle_hook(event_name: str) -> None:
    """Run a Web lifecycle hook under the trusted startup ingress profile."""
    from ..runtime.execution_broker import SecurityProfile, execution_profile

    if event_name == "SessionStart":
        from ..hooks_engine import fire_session_start as fire_hook
    elif event_name == "Stop":
        from ..hooks_engine import fire_stop as fire_hook
    else:
        raise ValueError(f"Unsupported Web lifecycle hook: {event_name}")

    profile = (
        SecurityProfile.LOCAL_TRUSTED
        if getattr(web_manager, "execution_profile", "remote") == "local_trusted"
        else SecurityProfile.REMOTE
    )
    with execution_profile(
        profile,
        sandbox_enabled=bool(getattr(web_manager, "sandbox_enabled", False)),
    ):
        fire_hook()


def init_web():
    print(get_welcome_message())

    from .sub_agent_jobs import initialize_web_job_runtime

    # Web process: suppress CLI [STATE] console output for the whole lifetime.
    # Must be set before any set_status() call (including first BUSY).
    try:
        setattr(core, "_is_web", True)
    except Exception:
        pass
    initialize_web_job_runtime()

    web_manager.original_set_status = core.set_status

    def _web_image_event(event: dict[str, Any]) -> None:
        room = getattr(_thread_ctx, "room", None)
        if room is None:
            try:
                with web_manager.active_room_lock:
                    room = web_manager.active_room
            except Exception:
                room = None
        if room is None or not getattr(room, "loop", None):
            return
        payload = {"type": "image_event", **dict(event)}
        try:
            asyncio.run_coroutine_threadsafe(room.broadcast(payload), room.loop)
        except Exception:
            pass

    core.image_event = _web_image_event
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
            return web_human_ask(
                room,
                {
                    "message": message,
                    "_expected_principal_id": _current_web_ask_principal(room),
                },
            )

        set_ask_user_hook(_web_ask_user)
    except Exception as e:
        try:
            _web_server_log(f"[web-init] ask hook register failed: {e!r}")
        except Exception:
            pass

    # Wrap tools: bind room context for parallel workers + route human_ask.
    original_run_tool = tools.run_tool

    def _resolve_web_room():
        room = get_context_web_room() or getattr(_thread_ctx, "room", None)
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
                if not room or not _remote_human_ask_authorized(room):
                    return json.dumps(
                        {
                            "user_reply": "",
                            "display_reply": "",
                            "cancelled": True,
                        }
                    )
                _ui_policy_revision = None
                if (
                    getattr(web_manager, "execution_profile", "remote")
                    != "local_trusted"
                ):
                    try:
                        from ..runtime.policy_engine import (
                            PolicyDecision,
                            UnifiedPolicy,
                        )

                        _ui_policy = UnifiedPolicy.from_environment()
                        if (
                            _ui_policy.decide("human_ask", args)
                            is not PolicyDecision.ALLOW
                        ):
                            raise ValueError(
                                "Remote human_ask is not allowed by policy"
                            )
                        _ui_policy_revision = _ui_policy.revision
                    except Exception:
                        return json.dumps(
                            {
                                "user_reply": "",
                                "display_reply": "",
                                "cancelled": True,
                            }
                        )
                # Do not accept an identity supplied by the model in tool args.
                # Bind this confirmation to the authenticated turn context.
                ask_args = dict(args)
                ask_args["_expected_principal_id"] = _current_web_ask_principal(room)
                # Keep the room-level confirmation slot and WAIT/LLM status
                # transition serialized together. web_human_ask() uses the same
                # RLock, so the nested acquisition is intentional.
                with room.human_ask_lock:
                    try:
                        room.set_status(True, "WAIT")
                        if web_manager.original_set_status:
                            # core.status_busy stays True for interrupt path.
                            web_manager.original_set_status(True, "WAIT")
                    except Exception:
                        pass
                    try:
                        reply = web_human_ask(room, ask_args)
                        if not _remote_human_ask_authorized(room):
                            return json.dumps(
                                {
                                    "user_reply": "",
                                    "display_reply": "",
                                    "cancelled": True,
                                }
                            )
                        if _ui_policy_revision is not None:
                            from ..runtime.policy_engine import (
                                PolicyDecision,
                                UnifiedPolicy,
                            )

                            _fresh_ui_policy = UnifiedPolicy.from_environment()
                            if (
                                _fresh_ui_policy.revision != _ui_policy_revision
                                or _fresh_ui_policy.decide("human_ask", args)
                                is not PolicyDecision.ALLOW
                            ):
                                return json.dumps(
                                    {
                                        "user_reply": "",
                                        "display_reply": "",
                                        "cancelled": True,
                                    }
                                )
                        return reply
                    finally:
                        try:
                            room.set_status(True, "LLM")
                            if web_manager.original_set_status:
                                web_manager.original_set_status(True, "LLM")
                        except Exception:
                            pass
            from ..runtime.execution_broker import SecurityProfile, execution_profile

            _profile_name = getattr(web_manager, "execution_profile", "remote")
            _profile = (
                SecurityProfile.LOCAL_TRUSTED
                if _profile_name == "local_trusted"
                else SecurityProfile.REMOTE
            )
            _scope = None
            _sandbox_enabled = bool(getattr(web_manager, "sandbox_enabled", False))
            if _profile is SecurityProfile.REMOTE or _sandbox_enabled:
                try:
                    from ..runtime.identity_context import get_current_turn_context
                    from ..runtime.execution_broker import (
                        TrustedSandboxScope,
                        trusted_web_scope,
                    )

                    _turn = get_current_turn_context()
                    if room is not None and _profile is SecurityProfile.REMOTE:
                        _scope = trusted_web_scope(_turn, str(room.room_id))
                    elif (
                        room is not None
                        and _turn is not None
                        and _turn.entry_point == "web"
                        and _turn.room_id == str(room.room_id)
                        and _turn.authenticated
                        and _turn.authn_kind == "local"
                    ):
                        _scope = TrustedSandboxScope(
                            deployment_id="web",
                            principal_id=_turn.principal_id,
                            project_id=_turn.project_id,
                            scope_kind="web-room",
                            scope_id=_turn.room_id,
                        )
                except (AttributeError, TypeError, ValueError):
                    _scope = None
            with execution_profile(
                _profile,
                sandbox_enabled=bool(getattr(web_manager, "sandbox_enabled", False)),
                scope=_scope,
            ):
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
    add_decision_provider_argument(parser)
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
        "--room-workers",
        type=int,
        default=None,
        help="Maximum concurrent Web rooms (default: UAGENT_WEB_ROOM_WORKERS or 5).",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help=_("Bind address (default: 127.0.0.1). Overrides UAGENT_WEB_HOST env var."),
    )
    parser.add_argument(
        "--sandbox",
        choices=("off", "auto", "mxc"),
        default=None,
        help=_(
            "Sandbox mode (default: off; remote tools remain denied without a compliant backend)."
        ),
    )
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        default=False,
        help=_(
            "Run in API-only mode without frontend (no HTML templates or static files)."
        ),
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
    web_args, _web_unknown = parser.parse_known_args()
    if getattr(web_args, "embedded", False):
        os.environ["UAGENT_SESSION_STORE"] = "0"
        os.environ["UAGENT_EMBEDDED"] = "1"

    # readme/quickstart first-run display removed (files no longer bundled)
    ensure_mcp_config_template()

    try:
        decision = _runtime_init.decide_workdir(env_workdir=env_get("UAGENT_WORKDIR"))
        _runtime_init.apply_workdir(decision)
        _runtime_init.reload_dotenv_custom()
        try:
            web_args.sandbox = _resolve_web_sandbox_mode(
                web_args.sandbox, env_get("UAGENT_SANDBOX_MODE")
            )
        except ValueError as exc:
            parser.error(str(exc))
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
        configure_decision_settings(
            cli_provider=getattr(web_args, "decision_provider", None)
        )
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

    if web_args.sandbox == "off":
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

    # Decide local-only eligibility from trusted startup configuration, never
    # request headers or client-provided identity. Any ambiguity is remote.
    bind_host = "127.0.0.1"
    _env_host = (env_get("UAGENT_WEB_HOST") or "").strip()
    if _env_host:
        bind_host = _env_host
    if web_args.host:
        bind_host = web_args.host
    try:
        from ..runtime.identity_context import resolve_identity_mode

        _identity_mode = resolve_identity_mode()
    except Exception:
        _identity_mode = "invalid"
    from ..runtime.execution_broker import (
        SecurityProfile,
        execution_profile,
        is_trusted_local_web,
    )

    _trusted_local_web = is_trusted_local_web(bind_host, _identity_mode)
    web_manager.execution_profile = "local_trusted" if _trusted_local_web else "remote"
    web_manager.sandbox_enabled = web_args.sandbox != "off"
    web_sandbox_manager = None
    if _trusted_local_web and web_manager.sandbox_enabled:
        web_sandbox_manager = _initialize_local_web_sandbox(
            parser, sandbox_mode=web_args.sandbox
        )
    _validate_web_sandbox_startup(
        parser,
        trusted_local=_trusted_local_web,
        sandbox_enabled=web_manager.sandbox_enabled,
        backend_ready=web_sandbox_manager is not None,
    )
    _web_profile = (
        SecurityProfile.LOCAL_TRUSTED if _trusted_local_web else SecurityProfile.REMOTE
    )
    with execution_profile(
        _web_profile,
        sandbox_enabled=web_manager.sandbox_enabled,
    ):
        # Load hooks/plugins only after the effective ingress profile is known.
        try:
            from ..runtime.runtime_plugins import load_plugins_status_at_startup

            _plugins, _plugins_status = load_plugins_status_at_startup(
                activate=_trusted_local_web and not web_manager.sandbox_enabled
            )
            if _plugins_status:
                print(_plugins_status, file=sys.stderr)
            try:
                setattr(web_manager, "plugins_startup_list", _plugins)
            except Exception:
                pass
        except Exception:
            try:
                setattr(web_manager, "plugins_startup_list", [])
            except Exception:
                pass

    from .process_workers import RoomWorkerPool, room_worker_count

    try:
        room_workers = room_worker_count(web_args.room_workers)
    except ValueError as exc:
        parser.error(str(exc))
    if _trusted_local_web and web_manager.sandbox_enabled:
        # MXC scopes must persist in the owning process across Room turns. The
        # current spawned-worker pool is per-turn, so keep local Sandbox Web
        # single-process until PR 3 adds Room-owned worker/lease lifecycle.
        if room_workers > 1:
            print(
                "[sandbox] local Web Sandbox uses one in-process worker until "
                "Room-owned worker leases are available",
                file=sys.stderr,
            )
        room_workers = 1
    web_manager.room_worker_pool = (
        RoomWorkerPool(room_workers) if room_workers > 1 else None
    )
    init_web()
    # Remote Web remains tool-less until a compliant sandbox backend exists;
    # avoid eager runner/plugin imports in that deployment profile.
    if (
        web_manager.execution_profile == "local_trusted"
        and not web_manager.sandbox_enabled
    ):
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
        _fire_web_lifecycle_hook("SessionStart")
    except Exception:
        pass

    forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1,::1")
    proxied_app = ProxyHeadersMiddleware(app, trusted_hosts=forwarded_allow_ips)
    server_app = RawSocketPeerCaptureMiddleware(proxied_app)
    config = uvicorn.Config(
        server_app,
        host=bind_host,
        port=port,
        ws_max_size=10_000_000,
        proxy_headers=False,
    )
    server = uvicorn.Server(config)
    try:
        server.run()
    finally:
        # Fire Stop hook
        try:
            _fire_web_lifecycle_hook("Stop")
        except Exception:
            pass
        if web_sandbox_manager is not None:
            try:
                web_sandbox_manager.close_all()
            finally:
                from ..runtime.mxc_backend import install_session_manager

                install_session_manager(None)
