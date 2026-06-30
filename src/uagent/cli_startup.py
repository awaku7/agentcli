from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class CliStartupState:
    provider: str
    client: Any
    depname: str
    banner: str
    messages: list[dict[str, Any]]
    should_exit: bool = False


def _prompt_startup_tool_genre_mask_fallback() -> int:
    from .i18n import _

    print(_("[INFO] startup genre prompt = numeric-input"), file=sys.stderr)

    prompt = _(
        "Enter the sum of numbers (1=basic,2=comm,4=office,8=devel,16=iot,32=exec,64=external,128=media,256=file,512=index,1023=all, Enter=basic only):"
    )
    out = getattr(sys, "__stdout__", None) or sys.stdout
    while True:
        try:
            out.write(prompt + "\n")
            out.flush()
        except Exception:
            pass
        try:
            raw = input().strip()
        except EOFError:
            return 1
        except Exception:
            return 1
        if not raw:
            return 1
        try:
            value = int(raw, 10)
        except Exception:
            try:
                out.write("[WARN] 0〜127 の整数を入力してください。\n")
                out.flush()
            except Exception:
                pass
            continue
        if 0 <= value <= 511:
            return value
        try:
            out.write("[WARN] 0〜127 の整数を入力してください。\n")
            out.flush()
        except Exception:
            pass


def _prompt_startup_tool_genre_mask() -> int:
    from .i18n import _

    try:
        from prompt_toolkit.shortcuts import checkboxlist_dialog
    except Exception:
        return _prompt_startup_tool_genre_mask_fallback()

    choices = [
        ("basic", _("Basic (env, time, prompts, skills, memory, tools control)")),
        (
            "file",
            _(
                "File (create, delete, read, write, search, zip, rename, hash, grep, list dir)"
            ),
        ),
        ("comm", _("Communication (Teams, Discord, Bluesky)")),
        ("office", _("Office (Excel, Word, PDF, PPT, document extraction)")),
        (
            "devel",
            _(
                "Development (lint, test, git, DB, screenshot, browser, binary, compile)"
            ),
        ),
        (
            "iot",
            _("IoT (Bluetooth/BLE, ECHONET, Matter, SwitchBot, UPnP, camera, geo-IP)"),
        ),
        ("exec", _("Execution (cmd, python, pwsh, bash, sub-agent)")),
        ("external", _("External (A2A, MCP, fetch, search web)")),
        ("media", _("Media (image gen/edit/analyze, audio, QR code)")),
        (
            "file",
            _(
                "File (create, delete, read, write, search, zip, rename, hash, grep, list dir)"
            ),
        ),
        (
            "index",
            _(
                "Index (source code navigation: py2idx, ts2idx, jv2idx, cs2idx, dart2idx, cpp2idx, rs2idx, go2idx, swift2idx, kt2idx)"
            ),
        ),
    ]

    stdin_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
    stdout_tty = bool(
        getattr(
            getattr(sys, "__stdout__", None) or sys.stdout, "isatty", lambda: False
        )()
    )
    if not (stdin_tty and stdout_tty):
        return _prompt_startup_tool_genre_mask_fallback()

    print(_("[INFO] startup genre prompt = prompt_toolkit"), file=sys.stderr)
    try:
        result = checkboxlist_dialog(
            title=_("Tool genre selection"),
            text=_("Use Space to toggle, Arrow keys to move, Enter to confirm."),
            ok_text=_("OK"),
            cancel_text=_("Default"),
            values=choices,
            default_values=["basic"],
        ).run()
    except Exception:
        print(
            _("[INFO] startup genre prompt = numeric-input (prompt_toolkit fallback)"),
            file=sys.stderr,
        )
        return _prompt_startup_tool_genre_mask_fallback()

    if result is None:
        return 1

    mask = 0
    for key in result:
        if key == "basic":
            mask |= 1
        elif key == "comm":
            mask |= 2
        elif key == "office":
            mask |= 4
        elif key == "devel":
            mask |= 8
        elif key == "iot":
            mask |= 16
        elif key == "exec":
            mask |= 32
        elif key == "external":
            mask |= 64
        elif key == "media":
            mask |= 128
        elif key == "file":
            mask |= 256
        elif key == "index":
            mask |= 512
    return mask


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
                reload_dotenv_custom()
            except Exception as e:
                print(
                    _("[FATAL] Failed to set workdir: %(err)s", err=e),
                    file=sys.stderr,
                )
                sys.exit(1)

            try:
                validate_or_exit_startup_env(context="cli")
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

            banner = build_startup_banner(
                core=core,
                workdir=decision.chosen_expanded,
                workdir_source=decision.chosen_source,
            )

            print_welcome()
            ensure_mcp_config_template()

            provider, client, depname = providers.make_client(core)

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
            else:
                # Default: basic only
                _apply_startup_tool_genre_mask(0)
                # Default: none
            if enable_tools:
                from .tools._genre_control_util import enable_single_tool

                for tname in enable_tools:
                    try:
                        enable_single_tool(tname)
                    except Exception as e:
                        print(
                            f"[WARN] Failed to enable tool '{tname}': {e}",
                            file=sys.stderr,
                        )
            core.set_status(False, "")

            messages = build_initial_messages(core=core)
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
        return CliStartupState(
            provider=provider,
            client=client,
            depname=depname,
            banner=banner,
            messages=messages,
            should_exit=True,
        )

    return CliStartupState(
        provider=provider,
        client=client,
        depname=depname,
        banner=banner,
        messages=messages,
        should_exit=False,
    )
