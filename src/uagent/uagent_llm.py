import json
import os
import time
from .i18n import _
import traceback
from typing import Any, Dict, List
from urllib.error import URLError

from . import tools
from .llm_errors import (
    _compute_retry_wait_seconds,
    _extract_retry_after,
    _is_rate_limit_error,
    _log_rate_limit_debug,
)
from .llm_gemini import gemini_chat_with_tools, _sanitize_gemini_parameters
from .llm_claude import claude_chat_with_tools
from .llm_openai_responses import (
    build_responses_request,
    parse_responses_response,
    parse_responses_stream,
)

try:
    from google.genai import types as gemini_types
except ImportError:
    gemini_types = None

try:
    from openai import APIConnectionError, BadRequestError
except Exception:
    BadRequestError = None
    APIConnectionError = None


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

    core.set_status(True, "LLM")

    tool_result_cache: Dict[str, str] = {}
    reuse_only_rounds = 0

    from .gemini_cache_mgr import GeminiCacheManager

    cache_mgr = GeminiCacheManager(depname)
    gemini_cache_name = None

    use_cache_env = os.environ.get("UAGENT_GEMINI_CACHE", "1").lower()
    if (
        provider == "gemini"
        and use_cache_env not in ("0", "false", "no")
        and gemini_types
    ):
        clear_on_start = os.environ.get(
            "UAGENT_GEMINI_CACHE_CLEAR_ON_START", "1"
        ).lower() in ("1", "true")
        if clear_on_start:
            try:
                cache_mgr.clear_cache(client)
            except Exception:
                pass
        try:
            system_instruction = "\n".join(
                [m["content"] for m in messages if m["role"] == "system"]
            )
            tool_specs = tools.get_tool_specs() or []

            if cache_mgr.is_cache_valid(system_instruction, tool_specs):
                gemini_cache_name = cache_mgr.get_cache_name()
            else:
                func_decls = []
                for spec in tool_specs:
                    fn = spec.get("function", {})
                    func_decls.append(
                        gemini_types.FunctionDeclaration(
                            name=fn.get("name"),
                            description=fn.get("description", ""),
                            parameters=_sanitize_gemini_parameters(
                                fn.get("parameters", {})
                            ),
                        )
                    )

                # キャッシュにはシステムプロンプトのみを含める。
                # ユーザーの問いかけはリクエスト本体(generate_content)で送る。
                cache_initial_msgs = [m for m in messages if m["role"] == "system"]
                gemini_cache_name = cache_mgr.create_cache(
                    client, system_instruction, func_decls, cache_initial_msgs
                )
        except Exception:
            pass  # print(f"[Gemini] キャッシュ処理中にエラーが発生しました (通常モードで続行): {e}")

    try:
        while True:
            round_count += 1
            if round_count > max_tool_rounds:
                print(_("[WARN] Tool rounds exceeded %(max)d; aborting.") % {"max": max_tool_rounds})
                break

            if provider == "gemini":
                if gemini_cache_name:
                    # キャッシュには System プロンプトが含まれているため、それ以外(User, Assistant, Tool等)を送る。
                    # これにより 1 発目の User プロンプトが確実にリクエストに含まれるようになる。
                    call_messages = [m for m in messages if m["role"] != "system"]
                else:
                    call_messages = messages
            else:
                call_messages = core.sanitize_messages_for_tools(messages)

            tool_calls_list: List[Dict[str, Any]] = []
            assistant_text: str = ""
            use_responses_api = (
                os.environ.get("UAGENT_RESPONSES", "") or ""
            ).lower() in (
                "1",
                "true",
            )

            def _env_default_true(name: str, default: bool = True) -> bool:
                v = (os.environ.get(name, "") or "").strip().lower()
                if v == "":
                    return bool(default)
                return v in ("1", "true", "yes", "on")

            stream_responses = _env_default_true("UAGENT_STREAMING", default=True)

            send_tools_this_round = True
            max_retries_429 = int(os.environ.get("UAGENT_429_MAX_RETRIES", "20"))
            retry_base = float(os.environ.get("UAGENT_429_BACKOFF_BASE", "2"))
            retry_cap = float(os.environ.get("UAGENT_429_BACKOFF_CAP", "65"))

            if provider == "gemini":
                attempt_429 = 0
                gemini_content_dump: Dict[str, Any] = {}
                while True:
                    try:
                        assistant_text, tool_calls_list, gemini_content_dump = (
                            gemini_chat_with_tools(
                                client,
                                depname,
                                call_messages,
                                cached_content=gemini_cache_name,
                            )
                        )
                        break
                    except Exception as e:
                        if _is_rate_limit_error(e):
                            attempt_429 += 1
                            if attempt_429 > max_retries_429:
                                print(
                                    f"[Gemini エラー] 429 Retry limit ({max_retries_429}) reached."
                                )
                                print(repr(e))
                                return
                            _, new_client, _ = make_client_fn(core)
                            client = new_client
                            ra = _extract_retry_after(e)
                            wait_s = _compute_retry_wait_seconds(
                                attempt=attempt_429,
                                retry_after_header=ra,
                                base=retry_base,
                                cap=retry_cap,
                            )
                            _log_rate_limit_debug(
                                provider=provider,
                                model=depname,
                                attempt=attempt_429,
                                max_retries=max_retries_429,
                                exception=e,
                                wait_seconds=wait_s,
                                retry_after=ra,
                            )
                            time.sleep(wait_s)
                            continue
                        print(_("[Gemini Error] An error occurred while generating a response."))
                        print(repr(e))
                        return

                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": assistant_text,
                }
                if tool_calls_list:
                    assistant_msg["tool_calls"] = tool_calls_list
                if isinstance(gemini_content_dump, dict) and gemini_content_dump:
                    assistant_msg["_gemini_content"] = gemini_content_dump
                messages.append(assistant_msg)
                # Web streaming (mode A): do not emit final assistant message to UI to avoid duplicates.
                if not bool(getattr(core, "_is_web", False)):
                    core.log_message(assistant_msg)

                if not tool_calls_list:
                    if assistant_text:
                        # Responses+Streaming already printed deltas in parse_responses_stream(); avoid double-print.
                        if not (use_responses_api and stream_responses):
                            print(assistant_text)
                        append_result_to_outfile_fn(assistant_text)
                        try_open_images_from_text_fn(assistant_text)
                    break

            elif provider == "claude":
                attempt_429 = 0
                while True:
                    try:
                        assistant_text, tool_calls_list = claude_chat_with_tools(
                            client, depname, call_messages
                        )
                        break
                    except Exception as e:
                        if _is_rate_limit_error(e):
                            attempt_429 += 1
                            if attempt_429 > max_retries_429:
                                print(
                                    f"[Claude エラー] 429 Retry limit ({max_retries_429}) reached."
                                )
                                print(repr(e))
                                return
                            _, new_client, _ = make_client_fn(core)
                            client = new_client
                            ra = _extract_retry_after(e)
                            wait_s = _compute_retry_wait_seconds(
                                attempt=attempt_429,
                                retry_after_header=ra,
                                base=retry_base,
                                cap=retry_cap,
                            )
                            _log_rate_limit_debug(
                                provider=provider,
                                model=depname,
                                attempt=attempt_429,
                                max_retries=max_retries_429,
                                exception=e,
                                wait_seconds=wait_s,
                                retry_after=ra,
                            )
                            time.sleep(wait_s)
                            continue
                        print(_("[Claude Error] An error occurred while generating a response."))
                        print(repr(e))
                        return

                assistant_msg = {
                    "role": "assistant",
                    "content": assistant_text,
                }
                if tool_calls_list:
                    assistant_msg["tool_calls"] = tool_calls_list

                messages.append(assistant_msg)
                core.log_message(assistant_msg)

                if not tool_calls_list:
                    if assistant_text:
                        # Responses+Streaming already printed deltas in parse_responses_stream(); avoid double-print.
                        if not (use_responses_api and stream_responses):
                            print(assistant_text)
                        append_result_to_outfile_fn(assistant_text)
                        try_open_images_from_text_fn(assistant_text)
                    break

            else:  # OpenAI / Azure
                attempt_429 = 0
                while True:
                    try:
                        if use_responses_api:
                            instructions_str, input_msgs, req_tools = (
                                build_responses_request(
                                    call_messages,
                                    send_tools_this_round=send_tools_this_round,
                                    provider=provider,
                                )
                            )

                            resp_kwargs: Dict[str, Any] = {
                                "model": depname,
                                "input": input_msgs,
                            }
                            if instructions_str is not None:
                                resp_kwargs["instructions"] = instructions_str
                            if send_tools_this_round and req_tools is not None:
                                resp_kwargs["tools"] = req_tools
                                resp_kwargs["tool_choice"] = "auto"

                            if stream_responses:
                                resp = client.responses.create(
                                    **resp_kwargs,
                                    stream=True,
                                )
                                (
                                    assistant_text,
                                    tool_calls_list,
                                ) = parse_responses_stream(
                                    resp,
                                    # In Web mode, parse_responses_stream streams deltas via core.log_message.
                                    print_delta_fn=(
                                        None
                                        if bool(getattr(core, "_is_web", False))
                                        else (
                                            lambda s: (
                                                print(s, end="", flush=True)
                                                if s
                                                else None
                                            )
                                        )
                                    ),
                                    core=core,
                                )
                                # ensure newline after streaming output
                                if assistant_text and not bool(
                                    getattr(core, "_is_web", False)
                                ):
                                    print("")
                            else:
                                resp = client.responses.create(**resp_kwargs)
                                assistant_text, tool_calls_list = (
                                    parse_responses_response(resp)
                                )
                        else:
                            req_tools = (
                                tools.get_tool_specs()
                                if send_tools_this_round
                                else None
                            )

                            chat_kwargs: Dict[str, Any] = {
                                "model": depname,
                                "messages": call_messages,
                            }
                            if send_tools_this_round and req_tools is not None:
                                chat_kwargs["tools"] = req_tools
                                chat_kwargs["tool_choice"] = "auto"

                            # OpenRouter-specific fallback models support (does not affect other providers)
                            # Enabled only when:
                            # - provider == "openrouter"
                            # - UAGENT_OPENROUTER_DEPNAME == "openrouter/auto" (depname passed here)
                            # - UAGENT_OPENROUTER_FALLBACK_MODELS is set (comma-separated model IDs)
                            if (
                                provider == "openrouter"
                                and (depname or "").strip() == "openrouter/auto"
                            ):
                                raw_fb = (
                                    os.environ.get(
                                        "UAGENT_OPENROUTER_FALLBACK_MODELS", ""
                                    )
                                    or ""
                                ).strip()
                                if raw_fb:
                                    fb_models = [
                                        s.strip()
                                        for s in raw_fb.split(",")
                                        if s.strip()
                                    ]
                                    if fb_models:
                                        chat_kwargs["models"] = fb_models

                            resp = client.chat.completions.create(**chat_kwargs)
                        break
                    except Exception as e:
                        if BadRequestError is not None and isinstance(
                            e, BadRequestError
                        ):
                            print("[Azure/OpenAI エラー] 400 BadRequest")
                            print(f"Error code: 400 - {e}")
                            return
                        if APIConnectionError is not None and isinstance(
                            e, APIConnectionError
                        ):
                            print("[Azure/OpenAI エラー] 接続エラー")
                            print(repr(e))
                            return
                        if isinstance(e, URLError):
                            print("[ネットワークエラー]")
                            print(repr(e))
                            return
                        if _is_rate_limit_error(e):
                            attempt_429 += 1
                            if attempt_429 > max_retries_429:
                                print(
                                    f"[Azure/OpenAI エラー] 429 Retry limit ({max_retries_429}) reached."
                                )
                                print(repr(e))
                                return
                            _, new_client, _ = make_client_fn(core)
                            client = new_client
                            ra = _extract_retry_after(e)
                            wait_s = _compute_retry_wait_seconds(
                                attempt=attempt_429,
                                retry_after_header=ra,
                                base=retry_base,
                                cap=retry_cap,
                            )
                            _log_rate_limit_debug(
                                provider=provider,
                                model=depname,
                                attempt=attempt_429,
                                max_retries=max_retries_429,
                                exception=e,
                                wait_seconds=wait_s,
                                retry_after=ra,
                            )
                            time.sleep(wait_s)
                            continue
                        print("[LLM エラー] 予期しない例外")
                        print(repr(e))
                        return

                try:
                    if use_responses_api:
                        # Responses API: assistant_text/tool_calls_list are already parsed above
                        # - streaming: parse_responses_stream(resp)
                        # - non-streaming: parse_responses_response(resp)
                        pass
                    else:
                        choice = resp.choices[0]
                        msg = choice.message
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                tool_calls_list.append(
                                    {
                                        "id": tc.id,
                                        "type": "function",
                                        "function": {
                                            "name": tc.function.name,
                                            "arguments": tc.function.arguments,
                                        },
                                    }
                                )
                        assistant_text = msg.content or ""

                except Exception as e:
                    print(f"[ERROR] レスポンス解析中にエラー: {e}")
                    traceback.print_exc()
                    return

                assistant_msg = {
                    "role": "assistant",
                    "content": assistant_text,
                }
                if tool_calls_list:
                    assistant_msg["tool_calls"] = tool_calls_list

                messages.append(assistant_msg)
                core.log_message(assistant_msg)

                if not tool_calls_list:
                    if assistant_text:
                        # Responses+Streaming already printed deltas in parse_responses_stream(); avoid double-print.
                        if not (use_responses_api and stream_responses):
                            print(assistant_text)
                        append_result_to_outfile_fn(assistant_text)
                        try_open_images_from_text_fn(assistant_text)
                    break

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
                        raise ValueError(
                            "arguments は JSON object である必要があります。"
                        )
                except Exception as e:
                    tb = traceback.format_exc()
                    tool_result = (
                        f"[tool args error] name={name!r} raw={arg_str!r} "
                        f"err={type(e).__name__}: {e}\nTraceback:\n{tb}"
                    )
                    tool_cache_key = f"error:{name}:{arg_str}"
                    parsed_args = None

                if parsed_args is not None:
                    canonical_args = json.dumps(
                        parsed_args, ensure_ascii=False, sort_keys=True
                    )
                    tool_cache_key = json.dumps(
                        {"name": name, "args": canonical_args},
                        ensure_ascii=False,
                        sort_keys=True,
                    )

                    cached = tool_result_cache.get(tool_cache_key)
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

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": tool_result,
                }
                messages.append(tool_msg)
                core.log_message(tool_msg)

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
