from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .runtime.startup_timing import checkpoint

_ROLE_FILE_MAX_BYTES = 64 * 1024


def _read_role_file(role_file: str, *, base_dir: str) -> str:
    """Read a deliberately selected UTF-8 role prompt with a bounded size."""
    raw_path = str(role_file).strip()
    if not raw_path:
        raise ValueError("the role-file path is empty")

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path(base_dir) / path
    try:
        path = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"cannot resolve {raw_path!r}: {exc}") from exc

    if not path.is_file():
        raise ValueError(f"{str(path)!r} is not a regular file")
    try:
        with path.open("rb") as role_stream:
            data = role_stream.read(_ROLE_FILE_MAX_BYTES + 1)
    except OSError as exc:
        raise ValueError(f"cannot read {str(path)!r}: {exc}") from exc

    if len(data) > _ROLE_FILE_MAX_BYTES:
        raise ValueError(f"{str(path)!r} exceeds the {_ROLE_FILE_MAX_BYTES}-byte limit")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{str(path)!r} is not valid UTF-8") from exc
    if "\x00" in text:
        raise ValueError(f"{str(path)!r} contains a NUL character")
    if not text.strip():
        raise ValueError(f"{str(path)!r} is empty")
    return text.strip()


@dataclass
class CliStartupState:
    provider: str
    client: Any
    depname: str
    banner: str
    messages: list[dict[str, Any]]
    session_store: Any = None
    session_id: str | None = None
    inject_message_auto: str | None = None
    should_exit: bool = False
    startup_timing_enabled: bool = False
    startup_timing_started: float | None = None
    startup_timing_marks: dict[str, float] | None = None


def _preload_laya_torch_for_startup(
    decision_settings: Any, *, sandbox_enabled: bool, preload: Any
) -> None:
    """Never import host-side Laya dependencies during a sandboxed startup."""
    if not sandbox_enabled:
        preload(decision_settings)


def _configure_cli_startup_tools(
    *,
    sandbox_enabled: bool,
    enable_tools: list[str] | None,
) -> None:
    """Apply host tool selection only when startup is not sandboxed."""
    if sandbox_enabled:
        return
    if not enable_tools:
        return

    from .tools._genre_control_util import enable_single_tool, pin_tool
    from .i18n import _

    # enable_single_tool() registers single-loaded tools newest-first
    # (smallest x_single_load_seq sorts to the front), so iterate in reverse to
    # preserve the user's order in the LLM tool list.
    for tname in reversed(enable_tools):
        try:
            if enable_single_tool(tname):
                pin_tool(tname, reason="enabled via --enable-tool at startup")
        except Exception as exc:
            print(
                "[WARN] "
                + _("Failed to enable tool '%(name)s': %(err)s")
                % {"name": tname, "err": exc},
                file=sys.stderr,
            )


def _call_cli_startup_turn(
    fn: Any,
    *args: Any,
    project_path: str,
    session_id: str,
    sandbox_enabled: bool = False,
    **kwargs: Any,
) -> Any:
    """Run one startup-triggered LLM turn under the canonical Agent lifecycle."""
    from .runtime.execution import lifecycle_execution
    from .runtime.turn_context_runtime import call_with_resolved_turn_context

    def _run_turn() -> Any:
        with lifecycle_execution():
            return call_with_resolved_turn_context(
                fn,
                *args,
                entry_point="cli",
                project_path=project_path,
                session_id=session_id,
                **kwargs,
            )

    if not sandbox_enabled:
        return _run_turn()

    from .runtime.execution_broker import SecurityProfile, execution_profile
    from .runtime.mxc_backend import startup_scope

    scope = startup_scope(
        entry_point="cli",
        project_path=project_path,
        session_id=session_id,
    )
    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True, scope=scope
    ):
        return _run_turn()


def _load_cli_startup_plugins(
    *, sandbox_enabled: bool
) -> tuple[list[dict[str, Any]], str | None]:
    """Do not apply host plugin configuration while running a sandbox session."""
    from .runtime.runtime_plugins import load_plugins_status_at_startup

    return load_plugins_status_at_startup(activate=not sandbox_enabled)


def _log_startup_file_message(core: Any, message: dict[str, Any]) -> None:
    """Log a file-derived startup prompt without making it capture-eligible."""

    envelope = dict(message)
    envelope["attachments"] = True
    core.log_message(envelope)


def run_cli_startup(
    *,
    core,
    cli_workdir,
    env_workdir,
    initial_file_arg,
    non_interactive: bool,
    role_file: str | None = None,
    inject_message: str | None = None,
    inject_message_auto: str | None = None,
    complete_regex: str | None = None,
    decision_provider: str | None = None,
    enable_tools: list[str] | None = None,
    sandbox_initializer: Any = None,
) -> CliStartupState:
    import io
    import os

    startup_cwd = os.getcwd()
    if non_interactive:
        os.environ["UAGENT_NON_INTERACTIVE"] = "1"

    try:
        core.auto_pilot_complete_regex = (
            str(complete_regex).strip() if complete_regex else None
        )
    except Exception:
        pass

    startup_timing_enabled = (
        os.environ.get("UAGENT_STARTUP_TIMING") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    startup_timing_started = time.perf_counter()
    startup_timing_marks: dict[str, float] = {}
    session_store = None
    session_id = None
    sandbox_enabled = False

    def _startup_timing_mark(name: str) -> None:
        if startup_timing_enabled:
            startup_timing_marks[name] = time.perf_counter() - startup_timing_started

    def _startup_timing_emit_detail(name: str, elapsed: float) -> None:
        if startup_timing_enabled:
            print(
                f"[startup-timing] detail.{name}={elapsed:.3f}s",
                file=sys.stderr,
                flush=True,
            )

    def _startup_timing_emit() -> None:
        if not startup_timing_enabled:
            return
        elapsed = time.perf_counter() - startup_timing_started
        lines = [f"[startup-timing] total={elapsed:.3f}s"]
        lines.extend(
            f"[startup-timing] {name}={mark:.3f}s"
            for name, mark in startup_timing_marks.items()
        )
        print(*lines, sep=chr(10), file=sys.stderr, flush=True)

    from .i18n import _, detect_lang, set_thread_lang

    set_thread_lang(detect_lang())

    from . import uagent_llm as llm_util
    from .providers import util_providers as providers
    from . import util_tools as tools_util
    from .decision.laya import preload_laya_torch_on_windows
    from .decision.settings import configure_decision_settings
    from .env_utils import env_get
    from .runtime.runtime_memory import append_long_memory_system_messages
    from .runtime.runtime_init import (
        apply_workdir,
        build_startup_banner,
        decide_workdir,
        reload_dotenv_custom,
        validate_or_exit_startup_env,
    )

    # readme_util removed (README.md/QUICKSTART.md no longer bundled as package-data)
    from .tools import long_memory as personal_long_memory
    from .tools.mcp_servers_shared import ensure_mcp_config_template
    from .welcome import _internal_pager, print_welcome
    from .util_tools import (
        build_initial_messages,
        build_long_memory_system_message,
    )

    tools_util.init_tools_callbacks(core)

    startup_capture_out = io.StringIO()
    startup_capture_err = io.StringIO()

    def _flush_startup_pager_and_continue() -> None:
        combined = startup_capture_out.getvalue() + startup_capture_err.getvalue()
        if combined:
            _internal_pager(combined)

    set_thread_lang(detect_lang())

    try:
        if True:
            # readme/quickstart first-run display removed

            try:
                decision = decide_workdir(
                    cli_workdir=cli_workdir,
                    env_workdir=env_workdir,
                )
                apply_workdir(decision)
                _timing_started = time.perf_counter()
                reload_dotenv_custom()
                selected_role_file = (
                    role_file
                    if role_file is not None
                    else (env_get("UAGENT_ROLE_FILE") or "").strip() or None
                )
                role_prompt = None
                if selected_role_file is not None:
                    try:
                        role_prompt = _read_role_file(
                            selected_role_file, base_dir=startup_cwd
                        )
                    except ValueError as exc:
                        print(f"[FATAL] Invalid role file: {exc}", file=sys.stderr)
                        raise SystemExit(2) from exc

                from .runtime.process_registry import activate_tracking

                activate_tracking("cli")
                _startup_timing_emit_detail(
                    "dotenv", time.perf_counter() - _timing_started
                )
            except Exception as e:
                print(
                    _("[FATAL] Failed to set workdir: %(err)s", err=e),
                    file=sys.stderr,
                )
                sys.exit(1)

            _startup_timing_mark("workdir")
            checkpoint("workdir_ready")

            # Session persistence is deliberately opt-in during rollout.
            try:
                from .runtime.session_store import attach_opt_in_session_store

                session_store, session_id = attach_opt_in_session_store(
                    core,
                    project_path=decision.chosen_expanded,
                    entry_point="cli",
                )
                if session_store is not None:
                    print("[INFO] Session store enabled.")
            except Exception as e:
                session_store = None
                session_id = None
                print(
                    "[WARN] Session store disabled after initialization failure: "
                    + str(e),
                    file=sys.stderr,
                )

            checkpoint("session_store_ready")

            try:
                _timing_started = time.perf_counter()
                validate_or_exit_startup_env(context="cli")
                _startup_timing_emit_detail(
                    "env_validate", time.perf_counter() - _timing_started
                )
            except SystemExit:
                if non_interactive:
                    raise

                setup_cmd = [sys.executable, "-m", "uagent.setup_cli"]
                try:
                    subprocess.run(setup_cmd, check=False)
                except Exception as e:
                    try:
                        combined = (
                            startup_capture_out.getvalue()
                            + startup_capture_err.getvalue()
                        )
                        if combined:
                            sys.__stderr__.write(combined)
                            try:
                                sys.__stderr__.flush()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    print(
                        _("[FATAL] Failed to launch uag_setup: %(err)s", err=e),
                        file=sys.stderr,
                    )
                    raise

                reload_dotenv_custom()
                from .runtime.process_registry import activate_tracking

                activate_tracking("cli")
                configure_decision_settings(cli_provider=decision_provider)
                try:
                    validate_or_exit_startup_env(context="cli")
                except SystemExit:
                    try:
                        combined = (
                            startup_capture_out.getvalue()
                            + startup_capture_err.getvalue()
                        )
                        if combined:
                            sys.__stderr__.write(combined)
                            try:
                                sys.__stderr__.flush()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    raise

            decision_settings = configure_decision_settings(
                cli_provider=decision_provider
            )
            checkpoint("environment_validated")
            if sandbox_initializer is not None:
                sandbox_enabled = bool(
                    sandbox_initializer(
                        decision.chosen_expanded,
                        str(getattr(core, "session_id", "") or session_id or ""),
                    )
                )
            checkpoint("sandbox_status_displayed")
            _preload_laya_torch_for_startup(
                decision_settings,
                sandbox_enabled=sandbox_enabled,
                preload=preload_laya_torch_on_windows,
            )
            _startup_timing_mark("env")
            checkpoint("decision_preload_complete")

            banner = build_startup_banner(
                core=core,
                workdir=decision.chosen_expanded,
                workdir_source=decision.chosen_source,
            )

            _startup_timing_mark("banner")

            print_welcome()
            ensure_mcp_config_template()
            checkpoint("startup_assets_ready")

            # Load and activate enabled plugins (MCP / agents / hooks)
            try:
                _plugins, _plugins_status = _load_cli_startup_plugins(
                    sandbox_enabled=sandbox_enabled
                )
                if _plugins_status:
                    print(_plugins_status, file=sys.stderr)
            except Exception:
                pass

            _startup_timing_mark("plugins")
            checkpoint("plugins_ready")

            try:
                provider, client, depname = providers.make_client(core)
            except (ValueError, RuntimeError) as e:
                print("error: " + _("%(err)s") % {"err": e}, file=sys.stderr)
                sys.exit(2)

            _startup_timing_mark("provider")
            checkpoint("provider_ready")

            if banner:
                print(banner, end="")

            print(
                "[INFO] "
                + _("provider = %(provider)s; model = %(model)s")
                % {"provider": provider, "model": depname or ""}
            )

            if (
                provider == "openrouter"
                and (depname or "").strip() == "openrouter/auto"
            ):
                raw_fb = (
                    env_get("UAGENT_OPENROUTER_FALLBACK_MODELS", "") or ""
                ).strip()
                if raw_fb:
                    print("[INFO] " + _("OpenRouter fallback models enabled."))

            try:
                cwd = os.getcwd()
                print("[INFO] " + _("current workdir = %(cwd)s") % {"cwd": cwd})
            except Exception:
                pass
            _configure_cli_startup_tools(
                sandbox_enabled=sandbox_enabled,
                enable_tools=enable_tools,
            )
            core.set_status(False, "")

            messages = build_initial_messages(
                core=core, role_prompt=role_prompt, provider=provider, depname=depname
            )
            _startup_timing_mark("messages")
            checkpoint("initial_messages_ready")
            print("[INFO] " + _("Loaded long-term memory."))

            try:
                before_len = len(messages)
                append_long_memory_system_messages(
                    core=core,
                    messages=messages,
                    build_long_memory_system_message_fn=build_long_memory_system_message,
                    personal_long_memory_mod=personal_long_memory,
                )

                for m in messages[before_len:]:
                    core.log_message(m)
            except Exception as e:
                print(
                    _(
                        "[WARN] Exception occurred while loading shared long-term memory: %(err)s",
                        err=e,
                    )
                )
    except Exception:
        try:
            combined = startup_capture_out.getvalue() + startup_capture_err.getvalue()
            if combined:
                sys.__stderr__.write(combined)
                try:
                    sys.__stderr__.flush()
                except Exception:
                    pass
        except Exception:
            pass
        raise

    _startup_timing_mark("memory")
    checkpoint("long_memory_ready")
    _flush_startup_pager_and_continue()
    checkpoint("startup_pager_complete")

    def _run_cli_startup_turn(fn, *args, **kwargs):
        return _call_cli_startup_turn(
            fn,
            *args,
            project_path=os.getcwd(),
            session_id=str(getattr(core, "session_id", "") or session_id or ""),
            sandbox_enabled=sandbox_enabled,
            **kwargs,
        )

    file_path = initial_file_arg

    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_text = f.read()
        except Exception:
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    file_text = f.read()
            except Exception as e:
                print(
                    _(
                        "[WARN] Failed to read startup file: %(path)s (%(err)s)",
                        path=file_path,
                        err=e,
                    )
                )
                file_text = ""

        if file_text and file_text.strip():
            max_chars = 10000
            if len(file_text) > max_chars:
                file_text = file_text[:max_chars] + "\n...[truncated]"

            initial_file_msg = {
                "role": "user",
                "content": (_("Startup file provided: %(path)s") % {"path": file_path})
                + "\n\n"
                + file_text,
            }
            messages.append(initial_file_msg)
            _log_startup_file_message(core, initial_file_msg)
            _run_cli_startup_turn(
                llm_util.run_llm_rounds,
                provider,
                client,
                depname,
                messages,
                core=core,
                make_client_fn=providers.make_client,
                append_result_to_outfile_fn=tools_util.append_result_to_outfile,
                try_open_images_from_text_fn=tools_util.try_open_images_from_text,
            )
        else:
            core.set_status(False, "")

    if inject_message:
        inject_msg = {"role": "user", "content": str(inject_message)}
        messages.append(inject_msg)
        core.log_message(inject_msg)
        _run_cli_startup_turn(
            llm_util.run_llm_rounds,
            provider,
            client,
            depname,
            messages,
            core=core,
            make_client_fn=providers.make_client,
            append_result_to_outfile_fn=tools_util.append_result_to_outfile,
            try_open_images_from_text_fn=tools_util.try_open_images_from_text,
        )

    if non_interactive and not inject_message_auto:
        core.set_status(False, "")
        print(
            "[INFO] "
            + _("--non-interactive was specified; exiting without waiting for stdin.")
        )
        _startup_timing_mark("complete")
        _startup_timing_emit()
        checkpoint("startup_state_ready")
        return CliStartupState(
            provider=provider,
            client=client,
            depname=depname,
            banner=banner,
            messages=messages,
            session_store=session_store,
            session_id=session_id,
            inject_message_auto=inject_message_auto,
            should_exit=True,
            startup_timing_enabled=startup_timing_enabled,
            startup_timing_started=(
                startup_timing_started if startup_timing_enabled else None
            ),
            startup_timing_marks=dict(startup_timing_marks),
        )

    _startup_timing_mark("complete")
    _startup_timing_emit()
    checkpoint("startup_state_ready")
    return CliStartupState(
        provider=provider,
        client=client,
        depname=depname,
        banner=banner,
        messages=messages,
        session_store=session_store,
        session_id=session_id,
        inject_message_auto=inject_message_auto,
        should_exit=False,
        startup_timing_enabled=startup_timing_enabled,
        startup_timing_started=(
            startup_timing_started if startup_timing_enabled else None
        ),
        startup_timing_marks=dict(startup_timing_marks),
    )
