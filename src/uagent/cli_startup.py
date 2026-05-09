from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class CliStartupState:
    provider: str
    client: Any
    depname: str
    banner: str
    messages: List[Dict[str, Any]]
    should_exit: bool = False


def run_cli_startup(
    *,
    core,
    cli_workdir,
    env_workdir,
    initial_file_arg,
    non_interactive: bool,
) -> CliStartupState:
    import io
    import os
    from contextlib import redirect_stderr, redirect_stdout

    from .i18n import _, detect_lang, set_thread_lang

    set_thread_lang(detect_lang())

    from . import uagent_llm as llm_util
    from . import util_providers as providers
    from . import util_tools as tools_util
    from .env_utils import env_get
    from .runtime_memory import append_long_memory_system_messages
    from .runtime_init import (
        apply_workdir,
        build_startup_banner,
        decide_workdir,
        validate_or_exit_startup_env,
    )
    from .checks import check_git_installation
    from .readme_util import (
        maybe_print_quickstart_on_first_run,
        maybe_print_readme_on_first_run,
    )
    from .tools import long_memory as personal_long_memory
    from .tools import shared_memory
    from .tools.mcp_servers_shared import ensure_mcp_config_template
    from .welcome import _internal_pager, print_welcome
    from .util_tools import (
        build_initial_messages,
        build_long_memory_system_message,
    )

    startup_capture_out = io.StringIO()
    startup_capture_err = io.StringIO()

    def _flush_startup_pager_and_continue() -> None:
        combined = startup_capture_out.getvalue() + startup_capture_err.getvalue()
        if combined:
            _internal_pager(combined)

    set_thread_lang(detect_lang())

    try:
        with redirect_stdout(startup_capture_out), redirect_stderr(startup_capture_err):
            try:
                maybe_print_readme_on_first_run(open_with_os=True)
                maybe_print_quickstart_on_first_run(open_with_os=True)
            except Exception:
                pass

            try:
                decision = decide_workdir(
                    cli_workdir=cli_workdir,
                    env_workdir=env_workdir,
                )
                apply_workdir(decision)
                # Load .env files in a deterministic order:
                # 1) current workdir .env
                # 2) starting directory .env (if different)
                try:
                    from pathlib import Path
                    from dotenv import load_dotenv

                    workdir_env = Path(os.getcwd()) / ".env"
                    if workdir_env.exists():
                        load_dotenv(workdir_env, override=True)

                    startdir_env = (
                        Path(cli_workdir or env_workdir or os.getcwd()) / ".env"
                    )
                    if startdir_env.exists() and startdir_env != workdir_env:
                        load_dotenv(startdir_env, override=True)
                except ImportError:
                    pass
                banner = build_startup_banner(
                    core=core,
                    workdir=decision.chosen_expanded,
                    workdir_source=decision.chosen_source,
                )
            except Exception as e:
                print(
                    _("[FATAL] Failed to set workdir: %(err)s", err=e),
                    file=sys.stderr,
                )
                sys.exit(1)

            try:
                validate_or_exit_startup_env(context="cli")
            except SystemExit:
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

            print_welcome()
            check_git_installation()
            ensure_mcp_config_template()

            provider, client, depname = providers.make_client(core)

            print("[INFO] " + _("LLM provider = %(provider)s", provider=provider))
            print("[INFO] UAGENT_PROVIDER = %(value)s" % {"value": env_get("UAGENT_PROVIDER", "(not set)")})
            try:
                from .runtime_env import _read_envsec_plaintext as _uagent_read_envsec_plaintext
                from pathlib import Path as _Path
                _uagent_sec_path = _Path.cwd() / ".env.sec"
                _uagent_sec_plain = (
                    _uagent_read_envsec_plaintext(_uagent_sec_path)
                    if _uagent_sec_path.exists()
                    else ""
                )
                _uagent_sec_provider = next(
                    (
                        line.split("=", 1)[1]
                        for line in _uagent_sec_plain.splitlines()
                        if line.startswith("UAGENT_PROVIDER=")
                    ),
                    "(not found)",
                )
                print("[DEBUG] .env.sec UAGENT_PROVIDER = %(value)s" % {"value": _uagent_sec_provider})
            except Exception as e:
                print("[DEBUG] .env.sec UAGENT_PROVIDER = <error: %(err)s>" % {"err": e})
            print("[INFO] " + _("model(deployment) = %(depname)s", depname=depname))
            if banner:
                print(banner, end="")

            if (
                provider == "openrouter"
                and (depname or "").strip() == "openrouter/auto"
            ):
                raw_fb = (
                    env_get("UAGENT_OPENROUTER_FALLBACK_MODELS", "") or ""
                ).strip()
                if raw_fb:
                    print("[INFO] " + _("OpenRouter fallback models enabled."))

            use_responses_api = env_get("UAGENT_RESPONSES", "").lower() in ("1", "true")
            if provider in ("gemini", "claude", "vertexai"):
                if use_responses_api:
                    os.environ["UAGENT_RESPONSES"] = "0"
                print(
                    "[INFO] "
                    + _(
                        "LLM API mode = Native Gemini/Vertex AI/Claude API (UAGENT_RESPONSES is ignored)"
                    )
                )
            elif use_responses_api and provider not in (
                "azure",
                "openai",
                "bedrock",
                "openrouter",
                "ollama",
            ):
                print(
                    _(
                        "[WARN] UAGENT_RESPONSES=1 is set, but provider '%(provider)s' does not support Responses API. Falling back to ChatCompletions.",
                        provider=provider,
                    )
                )
                os.environ["UAGENT_RESPONSES"] = "0"
                print(
                    "[INFO] "
                    + _("LLM API mode = ChatCompletions (UAGENT_RESPONSES is disabled)")
                )
            elif use_responses_api:
                print(
                    "[INFO] "
                    + _("LLM API mode = Responses (UAGENT_RESPONSES is enabled)")
                )
            else:
                print(
                    "[INFO] "
                    + _("LLM API mode = ChatCompletions (UAGENT_RESPONSES is disabled)")
                )

            try:
                cwd = os.getcwd()
                print("[INFO] " + ("current workdir = %(cwd)s" % {"cwd": cwd}))
            except Exception:
                pass

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
    if file_path is None and len(sys.argv) > 1:
        file_path = sys.argv[1]

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
                "content": ("Startup file provided: %(path)s" % {"path": file_path})
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
