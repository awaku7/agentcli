import json
import sys
import re
import threading
from .env_utils import env_get
from .i18n import _, detect_lang, set_thread_lang

set_thread_lang(detect_lang())

from .translate import load_translate_config
import traceback
from typing import Any, Dict, List
from urllib.error import URLError

try:
    import certifi
except Exception:
    certifi = None

from . import tools
from .llm_errors import (
    _rate_limit_retry_step,
)
from .llm_gemini import gemini_chat_with_tools
from .llm_claude import claude_chat_with_tools, build_claude_output_config_for_effort
from .llm_openai_responses import (
    build_responses_request,
    parse_responses_response,
    parse_responses_stream,
)
from .llm_bedrock_responses import build_bedrock_responses_request

try:
    from google.genai import types as gemini_types
except ImportError:
    gemini_types = None

try:
    from openai import APIConnectionError, BadRequestError
except Exception:
    BadRequestError = None
    APIConnectionError = None

from .llm_tool_narrowing import (
    _is_gpt54_tool_search_target,
    _select_tool_specs_for_gpt54,
)

from .llm_openrouter import (
    apply_openrouter_extra_body,
    apply_openrouter_tool_schema_compat,
    finalize_tool_schema_sync,
    apply_openrouter_fallback_models,
)
from .llm_openrouter_responses import apply_openrouter_responses_compat
from .llm_ollama import apply_ollama_extra_body
from .llm_ollama_responses import apply_ollama_responses_compat
from .llm_message_helpers import (
    _build_call_messages,
    _init_gemini_cache,
    _maybe_auto_shrink_messages,
)
from .llm_helpers import (
    _AUTO_EFFORT_LADDER,
    _auto_low_quality,
    _bump_effort,
    _call_maybe_thread,
    _choose_auto_effort,
    _effectively_empty_text,
    _env_default_on,
    _env_default_true,
    _extract_latest_user_text,
    _is_thinking_task,
    _maybe_print_certifi_where,
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

def _append_assistant_message(
    *,
    messages: List[Dict[str, Any]],
    core: Any,
    assistant_text: str,
    tool_calls_list: List[Dict[str, Any]],
    gemini_content_dump: Any = None,
    skip_log_when_web: bool = False,
) -> None:
    assistant_msg: Dict[str, Any] = {
        "role": "assistant",
        "content": assistant_text,
    }
    if tool_calls_list:
        assistant_msg["tool_calls"] = tool_calls_list
    if isinstance(gemini_content_dump, dict) and gemini_content_dump:
        assistant_msg["_gemini_content"] = gemini_content_dump

    messages.append(assistant_msg)

    if not (skip_log_when_web and bool(getattr(core, "_is_web", False))):
        core.log_message(assistant_msg)


def _emit_final_answer_if_any(
    *,
    assistant_text: str,
    use_responses_api: bool,
    stream_responses: bool,
    append_result_to_outfile_fn: Any,
    try_open_images_from_text_fn: Any,
) -> None:
    if not _effectively_empty_text(assistant_text):
        # Responses+Streaming already printed deltas in parse_responses_stream(); avoid double-print.
        if not (use_responses_api and stream_responses):
            print(assistant_text)
        append_result_to_outfile_fn(assistant_text)
        try_open_images_from_text_fn(assistant_text)


def _handle_openai_empty_no_tool(
    *,
    assistant_text: str,
    tool_calls_list: List[Dict[str, Any]],
    empty_no_tool_rounds: int,
    empty_no_tool_max: int,
    provider: str,
    depname: str,
    messages: List[Dict[str, Any]],
    core: Any,
) -> Any:
    eff_empty = _effectively_empty_text(assistant_text)

    if env_get("UAGENT_DEBUG_FLOW") == "1":
        try:
            _t = (
                assistant_text
                if isinstance(assistant_text, str)
                else str(assistant_text)
            )
            _u = _t.encode("utf-8", errors="backslashreplace").decode(
                "utf-8", errors="replace"
            )
            _tool_names = []
            try:
                _tool_names = [
                    tc.get("function", {}).get("name") for tc in tool_calls_list
                ][:5]
            except Exception:
                pass
            print(
                "[debug] llm_resp: "
                f"tool_calls={len(tool_calls_list)} names={_tool_names} "
                f"eff_empty={eff_empty} len={len(_t)} repr={_u!r}",
                file=sys.stderr,
            )
        except Exception:
            pass

    if tool_calls_list and eff_empty:
        return "pass", 0

    if not tool_calls_list and eff_empty:
        empty_no_tool_rounds += 1

        # Optional debug for empty assistant responses (no tool calls).
        if env_get("UAGENT_DEBUG_EMPTY") == "1":
            try:
                _t = (
                    assistant_text
                    if isinstance(assistant_text, str)
                    else str(assistant_text)
                )
                _u = _t.encode("utf-8", errors="backslashreplace").decode(
                    "utf-8", errors="replace"
                )
                print(
                    "[debug] empty assistant_text (no tool_calls): "
                    f"round={empty_no_tool_rounds}/{empty_no_tool_max} "
                    f"len={len(_t)} repr={_u!r}",
                    file=sys.stderr,
                )
            except Exception:
                pass

        # Optional nudge to recover from providers that sometimes emit an empty message
        # right after tool calls.
        if (
            empty_no_tool_rounds == 1
            and env_get("UAGENT_EMPTY_NO_TOOL_NUDGE", "1") != "0"
        ):
            try:
                nudge_msg = {
                    "role": "user",
                    "content": "前回のアシスタント返答が空でした。直前のツール結果を踏まえて回答してください。",
                }
                messages.append(nudge_msg)
                core.log_message(nudge_msg)
            except Exception:
                pass

        if empty_no_tool_rounds <= empty_no_tool_max:
            return "continue", empty_no_tool_rounds

        warn_text = (
            "[WARN] LLM returned an empty assistant message without tool calls.\n"
            f"provider={provider} depname={depname} "
            f"empty_no_tool_rounds={empty_no_tool_rounds} (max={empty_no_tool_max})\n"
            "This may happen with OpenAI-compatible local providers after tool calls. "
            "You can try setting UAGENT_EMPTY_NO_TOOL_MAX to a higher value, or switching provider."
        )
        try:
            warn_msg = {"role": "assistant", "content": warn_text}
            messages.append(warn_msg)
            core.log_message(warn_msg)
        except Exception:
            pass
        try:
            print(warn_text, file=sys.stderr)
        except Exception:
            pass
        return "break", empty_no_tool_rounds

    return "pass", 0


def _execute_tool_calls(
    *,
    tool_calls_list: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
    core: Any,
    cache_mgr: Any,
    tool_result_cache: Dict[str, str],
    use_tool_result_cache: bool,
) -> bool:
    executed_new_tool = False

    for tc in tool_calls_list:
        func = tc["function"]
        name = func["name"]
        arg_str = func.get("arguments") or "{}"
        tool_cache_key = None
        parsed_args = None
        tool_result = ""

        try:
            parsed_args = json.loads(arg_str)
            if not isinstance(parsed_args, dict):
                raise ValueError("arguments は JSON object である必要があります。")
        except Exception as e:
            tb = traceback.format_exc()
            tool_result = (
                f"[tool args error] name={name!r} raw={arg_str!r} "
                f"err={type(e).__name__}: {e}\nTraceback:\n{tb}"
            )
            tool_cache_key = f"error:{name}:{arg_str}"
            parsed_args = None

        if parsed_args is not None:
            canonical_args = json.dumps(parsed_args, ensure_ascii=False, sort_keys=True)
            tool_cache_key = json.dumps(
                {"name": name, "args": canonical_args},
                ensure_ascii=False,
                sort_keys=True,
            )

            cached = (
                tool_result_cache.get(tool_cache_key) if use_tool_result_cache else None
            )
            if cached is not None:
                tool_result = (
                    "[INFO] 同一内容のツール呼び出しのため、前回の結果を再利用します。\n"
                    + cached
                )
            else:
                core.set_status(True, f"tool:{name}")
                try:
                    # ファイルアクセスをキャッシュ管理に記録
                    if name == "read_file" and "filename" in parsed_args:
                        cache_mgr.record_file_access(parsed_args["filename"])

                    tool_result = tools.run_tool(name, parsed_args)
                except Exception as e:
                    tb = traceback.format_exc()
                    tool_result = (
                        f"[tool runtime error] name={name!r} "
                        f"err={type(e).__name__}: {e}\nTraceback:\n{tb}"
                    )
                tool_result_cache[tool_cache_key] = tool_result
                executed_new_tool = True

        elif tool_cache_key:
            tool_result_cache[tool_cache_key] = tool_result

        tool_msg: Dict[str, Any] = {
            "role": "tool",
            "tool_call_id": tc["id"],
            "name": name,
            "content": tool_result,
        }
        try:
            parsed_tool_result = json.loads(tool_result)
        except Exception:
            parsed_tool_result = None
        if isinstance(parsed_tool_result, dict):
            data = parsed_tool_result.get("data")
            if isinstance(data, dict):
                attachments = data.get("attachments")
                if isinstance(attachments, list) and attachments:
                    tool_msg["attachments"] = attachments
                if data.get("saved_files"):
                    tool_msg["saved_files"] = data.get("saved_files")
                if data.get("meta_path"):
                    tool_msg["saved_path"] = data.get("meta_path")
            else:
                attachments = parsed_tool_result.get("attachments")
                if isinstance(attachments, list) and attachments:
                    tool_msg["attachments"] = attachments
                if parsed_tool_result.get("saved_files"):
                    tool_msg["saved_files"] = parsed_tool_result.get("saved_files")
                if parsed_tool_result.get("saved_path"):
                    tool_msg["saved_path"] = parsed_tool_result.get("saved_path")

        messages.append(tool_msg)

        core.log_message(tool_msg)

    return executed_new_tool


def run_llm_rounds(
    provider: str,
    client: Any,
    depname: str,
    messages: List[Dict[str, Any]],
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

    core.set_status(True, "LLM")

    use_llm_thread = _env_default_on("UAGENT_LLM_IN_THREAD")

    def _call_maybe_thread_fn(fn: Any) -> Any:
        return _call_maybe_thread(fn, use_llm_thread=use_llm_thread)

    tool_result_cache: Dict[str, str] = {}
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

            send_tools_this_round = True
            max_retries_429 = int(env_get("UAGENT_429_MAX_RETRIES", "20"))
            retry_base = float(env_get("UAGENT_429_BACKOFF_BASE", "2"))
            retry_cap = float(env_get("UAGENT_429_BACKOFF_CAP", "300"))

            tool_calls_list: List[Dict[str, Any]] = []
            assistant_text: str = ""

            if provider in ("gemini", "vertexai"):
                ok, client, assistant_text, tool_calls_list, gemini_content_dump = (
                    _call_gemini_round(
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

                if not tool_calls_list:
                    _emit_final_answer_if_any(
                        assistant_text=assistant_text,
                        use_responses_api=use_responses_api,
                        stream_responses=stream_responses,
                        append_result_to_outfile_fn=append_result_to_outfile_fn,
                        try_open_images_from_text_fn=try_open_images_from_text_fn,
                    )
                    break

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

            core.set_status(True, "LLM")

            if executed_new_tool:
                reuse_only_rounds = 0
            else:
                reuse_only_rounds += 1
                if reuse_only_rounds >= 3:
                    print(
                        "[WARN] 3 ラウンド連続で同一ツール結果の再利用のみとなったため、"
                        "ループ防止のため処理を終了しました。"
                    )
                    break

    finally:
        # セッション中（プログラム終了まで）キャッシュを保持するため、ここでは削除しない。
        # クリーンアップは cli.py のメインループを抜けた際の finally で行う。
        core.set_status(False, "")
