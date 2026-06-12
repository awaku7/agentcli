from __future__ import annotations

from .env_utils import env_get
from .i18n import _, detect_lang, set_thread_lang

set_thread_lang(detect_lang())

from .translate import load_translate_config
from typing import Any

try:
    import certifi
except Exception:
    certifi = None

try:
    from google.genai import types as gemini_types
except ImportError:
    gemini_types = None

try:
    from openai import APIConnectionError, BadRequestError
except Exception:
    BadRequestError = None
    APIConnectionError = None

from .llm_message_helpers import (
    _build_call_messages,
    _init_gemini_cache,
    _maybe_auto_shrink_messages,
)
from .llm_helpers import (
    _call_maybe_thread,
    _env_default_on,
)
from .llm_round_helpers import (
    _translate_call_messages,
    _resolve_round_runtime_flags,
    _translate_assistant_if_needed,
    _call_gemini_round,
    _call_claude_round,
    _call_openai_azure_round,
)
from .llm_flow_helpers import (
    _append_assistant_message,
    _emit_final_answer_if_any,
    _handle_openai_empty_no_tool,
    _execute_tool_calls,
)
from .tools.context import get_callbacks
from .tools.skill_history import make_finish_skill_handler
from .tools import llm_tool_narrowing as _llm_tool_narrowing

_is_gpt54_tool_search_target = _llm_tool_narrowing._is_gpt54_tool_search_target
_select_tool_specs_for_gpt54 = _llm_tool_narrowing._select_tool_specs_for_gpt54


def run_llm_rounds(
    provider: str,
    client: Any,
    depname: str,
    messages: list[dict[str, Any]],
    *,
    core: Any,
    make_client_fn: Any,
    append_result_to_outfile_fn: Any,
    try_open_images_from_text_fn: Any,
) -> None:
    max_tool_rounds = 200
    round_count = 0

    empty_no_tool_rounds = 0

    # Some OpenAI-compatible local providers may return empty assistant messages after tool calls.
    # Tolerate a few consecutive empty/no-tool rounds, then abort with an explicit warning.
    try:
        empty_no_tool_max = int(env_get("UAGENT_EMPTY_NO_TOOL_MAX", "2"))
    except Exception:
        empty_no_tool_max = 2
    if empty_no_tool_max < 0:
        empty_no_tool_max = 2

    cb = get_callbacks()
    prev_finish_skill = cb.finish_skill
    cb.finish_skill = make_finish_skill_handler(messages, core)

    core.set_status(True, "LLM")

    use_llm_thread = _env_default_on("UAGENT_LLM_IN_THREAD")

    def _call_maybe_thread_fn(fn: Any) -> Any:
        return _call_maybe_thread(fn, use_llm_thread=use_llm_thread)

    tool_result_cache: dict[str, str] = {}
    use_tool_result_cache = env_get(
        "UAGENT_TOOL_RESULT_CACHE", "0"
    ).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    reuse_only_rounds = 0

    cache_mgr, gemini_cache_name = _init_gemini_cache(
        provider=provider,
        client=client,
        depname=depname,
        messages=messages,
    )

    try:
        while True:
            round_count += 1

            gemini_cache_name = _maybe_auto_shrink_messages(
                provider=provider,
                client=client,
                depname=depname,
                messages=messages,
                core=core,
                cache_mgr=cache_mgr,
                gemini_cache_name=gemini_cache_name,
                call_maybe_thread_fn=_call_maybe_thread_fn,
            )

            if round_count > max_tool_rounds:
                print(
                    _("[WARN] Tool rounds exceeded %(max)d; aborting.")
                    % {"max": max_tool_rounds}
                )
                break

            # Optional translation layer (off by default).
            # We keep the original `messages` history unchanged and create a translated
            # copy only for the LLM call.
            tr_cfg = load_translate_config()

            call_messages = _build_call_messages(
                provider=provider,
                messages=messages,
                core=core,
                depname=depname,
                gemini_cache_name=gemini_cache_name,
            )
            call_messages = _translate_call_messages(call_messages, tr_cfg)

            use_responses_api, stream_responses = _resolve_round_runtime_flags(
                tr_cfg=tr_cfg,
                core=core,
            )
            # Responses API is only supported on OpenAI, Azure, and OpenRouter providers.
            # Force use_responses_api to False for other providers (like Claude) to prevent skipping final output.
            if provider not in ("openai", "azure", "openrouter"):
                use_responses_api = False

            send_tools_this_round = True
            max_retries_429 = int(env_get("UAGENT_429_MAX_RETRIES", "20"))
            retry_base = float(env_get("UAGENT_429_BACKOFF_BASE", "2"))
            retry_cap = float(env_get("UAGENT_429_BACKOFF_CAP", "300"))

            tool_calls_list: list[dict[str, Any]] = []
            assistant_text: str = ""

            if provider in ("gemini", "vertexai"):
                (
                    ok,
                    client,
                    assistant_text,
                    tool_calls_list,
                    gemini_content_dump,
                ) = _call_gemini_round(
                    client=client,
                    depname=depname,
                    call_messages=call_messages,
                    gemini_cache_name=gemini_cache_name,
                    core=core,
                    make_client_fn=make_client_fn,
                    call_maybe_thread_fn=_call_maybe_thread_fn,
                    max_retries_429=max_retries_429,
                    retry_base=retry_base,
                    retry_cap=retry_cap,
                    stream_responses=stream_responses,
                )
                if not ok:
                    return

                assistant_text = _translate_assistant_if_needed(
                    assistant_text=assistant_text,
                    tr_cfg=tr_cfg,
                    use_responses_api=use_responses_api,
                    stream_responses=stream_responses,
                )

                # Web streaming (mode A): do not emit final assistant message to UI to avoid duplicates.
                _append_assistant_message(
                    messages=messages,
                    core=core,
                    assistant_text=assistant_text,
                    tool_calls_list=tool_calls_list,
                    gemini_content_dump=gemini_content_dump,
                    skip_log_when_web=True,
                )

                action, empty_no_tool_rounds = _handle_openai_empty_no_tool(
                    assistant_text=assistant_text,
                    tool_calls_list=tool_calls_list,
                    empty_no_tool_rounds=empty_no_tool_rounds,
                    empty_no_tool_max=empty_no_tool_max,
                    provider=provider,
                    depname=depname,
                    messages=messages,
                    core=core,
                )

                if action == "continue":
                    continue
                if action == "break":
                    break

                if not tool_calls_list:
                    # Gemini streaming already emitted the text; avoid double-printing.
                    if not (provider in ("gemini", "vertexai") and stream_responses):
                        _emit_final_answer_if_any(
                            assistant_text=assistant_text,
                            use_responses_api=use_responses_api,
                            stream_responses=stream_responses,
                            append_result_to_outfile_fn=append_result_to_outfile_fn,
                            try_open_images_from_text_fn=try_open_images_from_text_fn,
                        )
                    break

                empty_no_tool_rounds = 0

            elif provider == "claude":
                ok, client, assistant_text, tool_calls_list = _call_claude_round(
                    client=client,
                    depname=depname,
                    call_messages=call_messages,
                    core=core,
                    make_client_fn=make_client_fn,
                    call_maybe_thread_fn=_call_maybe_thread_fn,
                    max_retries_429=max_retries_429,
                    retry_base=retry_base,
                    retry_cap=retry_cap,
                )
                if not ok:
                    return

                assistant_text = _translate_assistant_if_needed(
                    assistant_text=assistant_text,
                    tr_cfg=tr_cfg,
                    use_responses_api=use_responses_api,
                    stream_responses=stream_responses,
                )

                _append_assistant_message(
                    messages=messages,
                    core=core,
                    assistant_text=assistant_text,
                    tool_calls_list=tool_calls_list,
                )

                action, empty_no_tool_rounds = _handle_openai_empty_no_tool(
                    assistant_text=assistant_text,
                    tool_calls_list=tool_calls_list,
                    empty_no_tool_rounds=empty_no_tool_rounds,
                    empty_no_tool_max=empty_no_tool_max,
                    provider=provider,
                    depname=depname,
                    messages=messages,
                    core=core,
                )

                if action == "continue":
                    continue
                if action == "break":
                    break

                if not tool_calls_list:
                    _emit_final_answer_if_any(
                        assistant_text=assistant_text,
                        use_responses_api=use_responses_api,
                        stream_responses=stream_responses,
                        append_result_to_outfile_fn=append_result_to_outfile_fn,
                        try_open_images_from_text_fn=try_open_images_from_text_fn,
                    )
                    break

                empty_no_tool_rounds = 0

            else:  # OpenAI / Azure
                ok, client, assistant_text, tool_calls_list = _call_openai_azure_round(
                    provider=provider,
                    client=client,
                    depname=depname,
                    call_messages=call_messages,
                    core=core,
                    make_client_fn=make_client_fn,
                    call_maybe_thread_fn=_call_maybe_thread_fn,
                    use_responses_api=use_responses_api,
                    stream_responses=stream_responses,
                    send_tools_this_round=send_tools_this_round,
                    max_retries_429=max_retries_429,
                    retry_base=retry_base,
                    retry_cap=retry_cap,
                    messages=messages,
                )
                if not ok:
                    return

                _append_assistant_message(
                    messages=messages,
                    core=core,
                    assistant_text=assistant_text,
                    tool_calls_list=tool_calls_list,
                )

                action, empty_no_tool_rounds = _handle_openai_empty_no_tool(
                    assistant_text=assistant_text,
                    tool_calls_list=tool_calls_list,
                    empty_no_tool_rounds=empty_no_tool_rounds,
                    empty_no_tool_max=empty_no_tool_max,
                    provider=provider,
                    depname=depname,
                    messages=messages,
                    core=core,
                )

                if action == "continue":
                    continue
                if action == "break":
                    break

                if not tool_calls_list:
                    _emit_final_answer_if_any(
                        assistant_text=assistant_text,
                        use_responses_api=use_responses_api,
                        stream_responses=stream_responses,
                        append_result_to_outfile_fn=append_result_to_outfile_fn,
                        try_open_images_from_text_fn=try_open_images_from_text_fn,
                    )
                    break

                empty_no_tool_rounds = 0

            executed_new_tool = _execute_tool_calls(
                tool_calls_list=tool_calls_list,
                messages=messages,
                core=core,
                cache_mgr=cache_mgr,
                tool_result_cache=tool_result_cache,
                use_tool_result_cache=use_tool_result_cache,
            )

            if any(
                isinstance(tc, dict)
                and (tc.get("function") or {}).get("name") == "generate_image"
                for tc in tool_calls_list
            ):
                # Image generation is terminal for the current turn.
                # Avoid a follow-up Responses round that can request generate_image again.
                break

            # Re-check before the next LLM call in case a large tool result
            # pushed the conversation near the context limit.
            gemini_cache_name = _maybe_auto_shrink_messages(
                provider=provider,
                client=client,
                depname=depname,
                messages=messages,
                core=core,
                cache_mgr=cache_mgr,
                gemini_cache_name=gemini_cache_name,
                call_maybe_thread_fn=_call_maybe_thread_fn,
            )

            core.set_status(True, "LLM")

            if executed_new_tool:
                reuse_only_rounds = 0
            else:
                reuse_only_rounds += 1
                if reuse_only_rounds >= 3:
                    print(
                        "[WARN] The same tool result was reused for 3 consecutive rounds, so "
                        "processing was stopped to prevent a loop."
                    )
                    break

    finally:
        cb.finish_skill = prev_finish_skill
        # セッション中（プログラム終了まで）キャッシュを保持するため、ここでは削除しない。
        # クリーンアップは cli.py のメインループを抜けた際の finally で行う。
        core.set_status(False, "")
