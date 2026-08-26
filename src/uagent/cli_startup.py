from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CliStartupState:
    provider: str
    client: Any
    depname: str
    banner: str
    messages: list[dict[str, Any]]
    session_store: Any = None
    session_id: str | None = None
    should_exit: bool = False


def _prompt_startup_tool_genre_mask() -> int:
    """Prompt for the startup tool-genre bitmask, using a TTY dialog when available."""
    if (
        getattr(sys.stdin, "isatty", lambda: False)()
        and getattr(sys.stdout, "isatty", lambda: False)()
    ):
        try:
            from prompt_toolkit.shortcuts import checkboxlist_dialog

            values = [
                ("basic", "basic"),
                ("comm", "comm"),
                ("office", "office"),
                ("devel", "devel"),
            ]
            selected = checkboxlist_dialog(
                title="Tool genres", text="Select tool genres", values=values
            ).run()
            bits = {"basic": 1, "comm": 1, "office": 2, "devel": 4}
            return sum(bits.get(str(item), 0) for item in (selected or []))
        except Exception:
            pass
    try:
        return int(input().strip() or "0")
    except (TypeError, ValueError, EOFError):
        return 0


def _apply_startup_tool_genre_mask(mask: int) -> None:
    if mask <= 0:
        return

    from .i18n import _
    from .tools.genre_control_tool import (
        _set_basic_tools_enabled,
        _set_comm_tools_enabled,
        _set_devel_tools_enabled,
        _set_exec_tools_enabled,
        _set_external_tools_enabled,
        _set_file_tools_enabled,
        _set_index_tools_enabled,
        _set_iot_tools_enabled,
        _set_media_tools_enabled,
        _set_office_tools_enabled,
    )

    enabled_specs = [
        (1, _set_basic_tools_enabled),
        (2, _set_comm_tools_enabled),
        (4, _set_office_tools_enabled),
        (8, _set_devel_tools_enabled),
    ]
    if _set_iot_tools_enabled is not None:
        enabled_specs.append((16, _set_iot_tools_enabled))
    if _set_exec_tools_enabled is not None:
        enabled_specs.append((32, _set_exec_tools_enabled))
    if _set_external_tools_enabled is not None:
        enabled_specs.append((64, _set_external_tools_enabled))
    if _set_media_tools_enabled is not None:
        enabled_specs.append((128, _set_media_tools_enabled))
    if _set_file_tools_enabled is not None:
        enabled_specs.append((256, _set_file_tools_enabled))
    if _set_index_tools_enabled is not None:
        enabled_specs.append((512, _set_index_tools_enabled))

    for bit, setter in enabled_specs:
        if not (mask & bit):
            continue
        try:
            msg = setter(True)
            if msg:
                print(msg)
        except Exception as e:
            print(
                _("[WARN] Failed to apply startup tool selection: %(err)s", err=e),
                file=sys.stderr,
            )


def run_cli_startup(
    *,
    core,
    cli_workdir,
    env_workdir,
    initial_file_arg,
    non_interactive: bool,
    tool_genre_mask: int | None = None,
    inject_message: str | None = None,
    enable_tools: list[str] | None = None,
) -> CliStartupState:
    import io
    import os

    if non_interactive:
        os.environ["UAGENT_NON_INTERACTIVE"] = "1"

    startup_timing_enabled = (
        os.environ.get("UAGENT_STARTUP_TIMING") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    startup_timing_started = time.perf_counter()
    startup_timing_marks: dict[str, float] = {}
    session_store = None
    session_id = None

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
    from .tools import shared_memory
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

            _startup_timing_mark("env")

            banner = build_startup_banner(
                core=core,
                workdir=decision.chosen_expanded,
                workdir_source=decision.chosen_source,
            )

            _startup_timing_mark("banner")

            print_welcome()
            ensure_mcp_config_template()

            # Load and activate enabled plugins (MCP / agents / hooks)
            try:
                from .runtime.runtime_plugins import load_plugins_status_at_startup

                _plugins, _plugins_status = load_plugins_status_at_startup(
                    activate=True
                )
                if _plugins_status:
                    print(_plugins_status, file=sys.stderr)
            except Exception:
                pass

            _startup_timing_mark("plugins")

            try:
                provider, client, depname = providers.make_client(core)
            except (ValueError, RuntimeError) as e:
                print("error: " + _("%(err)s") % {"err": e}, file=sys.stderr)
                sys.exit(2)

            _startup_timing_mark("provider")

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
            if tool_genre_mask is not None:
                _apply_startup_tool_genre_mask(tool_genre_mask)
            if enable_tools:
                from .tools._genre_control_util import enable_single_tool
                from .tools import _EMBEDDED_EXCLUDED_TOOLS, _is_embedded_mode

                # enable_single_tool() registers single-loaded tools newest-first
                # (smallest x_single_load_seq sorts to the front), so iterate in
                # reverse to preserve the user-specified order: the first tool
                # given on the command line is presented to the LLM first.
                for tname in reversed(enable_tools):
                    try:
                        ok = enable_single_tool(tname)
                        if (
                            not ok
                            and _is_embedded_mode()
                            and tname in _EMBEDDED_EXCLUDED_TOOLS
                        ):
                            print(
                                "[WARN] "
                                + _(
                                    "Tool '%(name)s' is unavailable in embedded mode and was not enabled."
                                )
                                % {"name": tname},
                                file=sys.stderr,
                            )
                    except Exception as e:
                        print(
                            "[WARN] "
                            + _("Failed to enable tool '%(name)s': %(err)s")
                            % {"name": tname, "err": e},
                            file=sys.stderr,
                        )
            core.set_status(False, "")

            messages = build_initial_messages(
                core=core, provider=provider, depname=depname
            )
            _startup_timing_mark("messages")
            print("[INFO] " + _("Loaded long-term memory."))

            try:
                before_len = len(messages)
                flags = append_long_memory_system_messages(
                    core=core,
                    messages=messages,
                    build_long_memory_system_message_fn=build_long_memory_system_message,
                    personal_long_memory_mod=personal_long_memory,
                    shared_memory_mod=shared_memory,
                )

                if flags.get("shared_enabled"):
                    print("[INFO] " + _("Loaded shared long-term memory."))

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
    _flush_startup_pager_and_continue()

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
            core.log_message(initial_file_msg)
            llm_util.run_llm_rounds(
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
        llm_util.run_llm_rounds(
            provider,
            client,
            depname,
            messages,
            core=core,
            make_client_fn=providers.make_client,
            append_result_to_outfile_fn=tools_util.append_result_to_outfile,
            try_open_images_from_text_fn=tools_util.try_open_images_from_text,
        )

    if non_interactive:
        core.set_status(False, "")
        print(
            "[INFO] "
            + _("--non-interactive was specified; exiting without waiting for stdin.")
        )
        _startup_timing_mark("complete")
        _startup_timing_emit()
        return CliStartupState(
            provider=provider,
            client=client,
            depname=depname,
            banner=banner,
            messages=messages,
            session_store=session_store,
            session_id=session_id,
            should_exit=True,
        )

    _startup_timing_mark("complete")
    _startup_timing_emit()
    return CliStartupState(
        provider=provider,
        client=client,
        depname=depname,
        banner=banner,
        messages=messages,
        session_store=session_store,
        session_id=session_id,
        should_exit=False,
    )
