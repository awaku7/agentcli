# ruff: noqa: F401  (re-export facade)

"""Host-side command processing and tool helpers.

Historically a single large module, now split into focused util_* modules:
  util_common / util_image / util_mode / util_help / util_message /
  util_model / util_cmd_files / util_cmd_session / util_cmd_auto

This module keeps ``handle_command`` (the dispatch hub) and re-exports the
split names for backward compatibility.
"""

from __future__ import annotations

from typing import Any

from .i18n import _, detect_lang, set_thread_lang

set_thread_lang(detect_lang())

from . import tools

from .env_utils import env_get

from .util_common import (
    strip_surrogates,
    CommandResult,
    init_tools_callbacks,
    parse_startup_args,
    iter_backup_files,
    load_agents_md,
    append_result_to_outfile,
)
from .util_image import (
    _IMAGE_PATH_RE,
    extract_image_paths,
    extract_video_paths,
    open_image_with_default_app,
    image_file_to_data_url,
    media_file_to_data_url,
    provider_allows_chat_vision,
    build_multimodal_user_message,
    try_open_images_from_text,
)
from .util_mode import (
    _REASONING_LEVELS,
    _VERBOSITY_LEVELS,
    get_reasoning_mode,
    get_verbosity_mode,
    _normalize_off_arg,
    _normalize_reasoning_level_arg,
    _normalize_verbosity_level_arg,
    _cycle_level,
    set_reasoning_mode,
    set_verbosity_mode,
    _REASONING_HISTORY,
    _DISPLAY_REASONING,
    get_display_reasoning,
    extract_last_assistant_text,
    apply_reasoning_arg,
    apply_verbosity_arg,
    _handle_cmd_reasoning,
    _handle_cmd_verbosity,
)
from .util_help import (
    format_help,
    _static_help_catalog,
    format_help_detail,
)
from .util_message import (
    _cwd_marker_prefix,
    _format_cwd_system_content,
    _insert_cwd_system_message,
    _extract_last_cwd_from_messages,
    _read_raw_log_messages,
    _skills_marker_prefix,
    _format_skill_system_content,
    _has_any_user_message,
    _trim_messages_after_last_user,
    _clear_skill_messages,
    insert_tools_system_message,
    build_initial_messages,
    build_long_memory_system_message,
)
from .util_model import (
    _uagent_env_names,
    _uagent_format_env_value,
    _handle_cmd_env,
    _get_env,
    _format_capa,
    _fetch_model_capa,
    _model_provider_note,
    _model_value_note,
    _append_resolved_model_section,
    _image_analysis_model_keys,
    _image_generation_model_keys,
    _audio_model_keys,
    _handle_cmd_model,
)
from .util_cmd_files import (
    _handle_cmd_cd,
    _handle_cmd_reload,
    _handle_cmd_ls,
    _handle_cmd_logs,
    _handle_cmd_tools,
    _strip_outer_quotes,
    _normalize_cp_mv_args,
    _resolve_copy_move_target,
    _remove_existing_path,
    _handle_cmd_cp,
    _handle_cmd_mv,
    _handle_cmd_head,
    _handle_cmd_tail,
    _handle_cmd_rm,
)
from .util_cmd_auto import (
    _get_followup_prompt,
    _build_judgment_messages,
    _ask_reviewer_judgment,
    _run_auto_pilot_loop,
    _handle_cmd_auto,
)
from .util_cmd_credentials import handle_credential_command
from .util_cmd_responses import _handle_cmd_response
from .util_cmd_session import (
    _handle_cmd_skills,
    _handle_cmd_sessions,
    _default_clean_threshold,
    _count_user_turns,
    _parse_clean_threshold,
    _collect_clean_targets,
    _confirm_clean_delete,
    _delete_clean_targets,
    _maybe_discard_short_session_log,
    _sweep_short_session_logs,
    _handle_cmd_clean,
    _prepend_loaded_log_to_current,
    _handle_cmd_load,
    _persist_messages_with_warn,
    _handle_cmd_shrink,
    _handle_cmd_shrink_llm,
    _handle_cmd_tokens,
    _handle_cmd_mem_list,
    _handle_cmd_mem_del,
    _handle_cmd_shared_mem_list,
    _handle_cmd_profile_show,
    _handle_cmd_profile_clear,
    _handle_cmd_shared_mem_del,
)

# Default translation function used when core.tr is not provided.
# Kept as a separate name for backward-compatibility.
tr = _
tr_ = _


def handle_command(
    line: str,
    messages_ref: list[dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
) -> bool | CommandResult:
    """\u30b3\u30de\u30f3\u30c9\u884c(:help, :logs, :load ...)\u3092\u51e6\u7406\u3059\u308b

    \u623b\u308a\u5024: False \u3092\u8fd4\u3059\u3068\u30e1\u30a4\u30f3\u30eb\u30fc\u30d7\u7d42\u4e86(:exit / :quit)\u3002
    CommandResult(run_llm=True) \u3092\u8fd4\u3059\u3068\u3001\u30b3\u30de\u30f3\u30c9\u51e6\u7406\u5f8c\u306b LLM \u3092\u5b9f\u884c\u3059\u308b\u3002
    """
    tr = getattr(core, "tr", tr_)

    line = line.lstrip(":").strip()
    if not line:
        return True

    parts = line.split(maxsplit=1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    # Plugin namespaced form: :plugin:subcommand [args]
    # (Claude-style /plugin:cmd mapped onto uag ":")
    if ":" in cmd:
        head, tail = cmd.split(":", 1)
        if head and tail:
            # ":genshijin:commit" -> cmd=genshijin, arg="commit ..."
            cmd = head
            arg = f"{tail} {arg}".strip() if arg else tail

    if cmd in ("help", "h", "?"):
        topic = (arg or "").strip() or None
        core.print_help(topic)
        return True

    if cmd in ("r", "reasoning"):
        return _handle_cmd_reasoning(arg, tr=tr)

    if cmd in ("v", "verbosity"):
        return _handle_cmd_verbosity(arg, tr=tr)

    if cmd == "cd":
        return _handle_cmd_cd(arg, messages_ref, core=core, tr=tr)

    if cmd == "reload":
        return _handle_cmd_reload(arg, messages_ref, core=core, tr=tr)

    if cmd == "ls":
        return _handle_cmd_ls(arg, tr=tr)

    if cmd == "logs":
        return _handle_cmd_logs(arg, core=core, tr=tr)

    if cmd == "tools":
        if arg and arg.strip():
            parts = arg.strip().split()
            sub = parts[0].lower()
            # ":tools on" / ":tools off" (no extra args) => global tool toggle.
            # ":tools on iot" / ":tools off comm" etc. => genre enable/disable + global sync.
            if sub in ("on", "off") and len(parts) == 1:
                core.tools_enabled = sub == "on"
                state = "ON" if core.tools_enabled else "OFF"
                print(
                    _("[tools] Tool sending to LLM is now %(state)s") % {"state": state}
                )
                return CommandResult()
            # ":tools on <genre>" => enable genre, also re-enable global tool sending.
            if sub == "on" and len(parts) >= 2:
                core.tools_enabled = True
            # Try dynamic subcommands (e.g., on comm, off comm, list)
            res = tools.handle_dynamic_command(
                "tools",
                arg,
                messages_ref=messages_ref,
                client=client,
                depname=depname,
                core=core,
                tr=tr,
            )
            if res is not None:
                if isinstance(res, str):
                    print(res)
                if type(res).__name__ == "CommandResult":
                    return res
                return CommandResult()
        print(_("Usage: :tools [list|on|off|output] [args...]"))
        return CommandResult()

    if cmd == "env":
        return _handle_cmd_env(arg, tr=tr)

    if cmd in {"credential", "credentials"}:
        return handle_credential_command(arg, core=core, tr=tr)

    if cmd == "skills":
        return _handle_cmd_skills(arg, messages_ref, client, depname, core=core, tr=tr)

    if cmd in {"sessions", "session"}:
        return _handle_cmd_sessions(
            arg, messages_ref=messages_ref, client=client, depname=depname,
            core=core, tr=tr
        )

    if cmd == "clean":
        return _handle_cmd_clean(arg, core=core, tr=tr)

    if cmd == "cont":
        return _handle_cmd_load("0", messages_ref, core=core, tr=tr)

    if cmd == "load":
        return _handle_cmd_load(arg, messages_ref, core=core, tr=tr)

    if cmd == "shrink":
        return _handle_cmd_shrink(arg, messages_ref, core=core)

    if cmd == "shrink_llm":
        return _handle_cmd_shrink_llm(arg, messages_ref, client, depname, core=core)

    if cmd == "response":
        return _handle_cmd_response(
            arg, messages_ref, client, depname, core=core, tr=tr
        )

    if cmd == "tokens":
        return _handle_cmd_tokens(messages_ref, core=core, depname=depname)

    if cmd == "mem-list":
        return _handle_cmd_mem_list(tr=tr)

    if cmd == "mem-del":
        return _handle_cmd_mem_del(arg, tr=tr)

    if cmd in ("profile", "profile-show"):
        return _handle_cmd_profile_show(arg, core=core, tr=tr)

    if cmd == "profile-fromlog":
        # Pass optional max_log_files as "fromlog N"
        profile_arg = "fromlog 100"
        if arg and arg.strip():
            try:
                n = int(arg.strip())
                profile_arg = f"fromlog {n}"
            except (ValueError, TypeError):
                pass
        return _handle_cmd_profile_show(profile_arg, core=core, tr=tr)

    if cmd == "profile-clear":
        return _handle_cmd_profile_clear(tr=tr)

    if cmd == "cp":
        return _handle_cmd_cp(arg, tr=tr)

    if cmd == "mv":
        return _handle_cmd_mv(arg, tr=tr)

    if cmd == "head":
        return _handle_cmd_head(arg, tr=tr)

    if cmd == "tail":
        return _handle_cmd_tail(arg, tr=tr)

    if cmd == "rm":
        return _handle_cmd_rm(arg, tr=tr)

    if cmd == "auto":
        return _handle_cmd_auto(
            arg,
            messages_ref,
            client,
            depname,
            core=core,
            tr=tr,
        )

    if cmd == "model":
        return _handle_cmd_model(arg, core=core, tr=tr)

    # Try dynamic commands registered by tool modules
    res = tools.handle_dynamic_command(
        cmd,
        arg,
        messages_ref=messages_ref,
        client=client,
        depname=depname,
        core=core,
        tr=tr,
    )
    if res is not None:
        if isinstance(res, str):
            print(res)
            return CommandResult()
        return res

    if cmd in ("exit", "quit"):
        print(tr("Exiting."))
        return False

    print(tr("Unknown command: :%(cmd)s") % {"cmd": cmd})
    return True
