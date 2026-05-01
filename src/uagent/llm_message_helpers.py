from typing import Any, Dict, List

from . import tools
from .env_utils import env_get
from .image_session import build_image_session_message
from .i18n import _
from .llm_gemini import _message_content_text, _sanitize_gemini_parameters

try:
    from google.genai import types as gemini_types
except Exception:
    gemini_types = None


def _init_gemini_cache(
    *,
    provider: str,
    client: Any,
    depname: str,
    messages: List[Dict[str, Any]],
) -> Any:
    from .gemini_cache_mgr import GeminiCacheManager

    cache_mgr = GeminiCacheManager(depname)
    gemini_cache_name = None

    use_cache_env = env_get("UAGENT_GEMINI_CACHE", "1").lower()
    if (
        provider in ("gemini", "vertexai")
        and use_cache_env not in ("0", "false", "no")
        and gemini_types
    ):
        clear_on_start = env_get("UAGENT_GEMINI_CACHE_CLEAR_ON_START", "1").lower() in (
            "1",
            "true",
        )
        if clear_on_start:
            try:
                cache_mgr.clear_cache(client)
            except Exception:
                pass
        try:
            system_instruction = "\n".join(
                [_message_content_text(m) for m in messages if m["role"] == "system"]
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
            pass

    return cache_mgr, gemini_cache_name


def _maybe_auto_shrink_messages(
    *,
    provider: str,
    client: Any,
    depname: str,
    messages: List[Dict[str, Any]],
    core: Any,
    cache_mgr: Any,
    gemini_cache_name: Any,
    call_maybe_thread_fn: Any,
) -> Any:
    # Gemini の場合は自動圧縮を行わない
    if provider in ("gemini", "vertexai"):
        return gemini_cache_name
    # Auto shrink_llm (optional)
    shrink_cnt_raw = (env_get("UAGENT_SHRINK_CNT", "") or "").strip()
    try:
        shrink_cnt = int(shrink_cnt_raw) if shrink_cnt_raw != "" else 100
    except Exception:
        shrink_cnt = 100

    if shrink_cnt <= 0:
        return gemini_cache_name

    # Count non-system messages (same rule as core.shrink_messages)
    others_count = 0
    hit_non_system = False
    for m in messages:
        if m.get("role") == "system" and not hit_non_system:
            continue
        hit_non_system = True
        others_count += 1

    if others_count < shrink_cnt:
        return gemini_cache_name

    keep_last_raw = (env_get("UAGENT_SHRINK_KEEP_LAST", "") or "").strip()
    try:
        keep_last = int(keep_last_raw) if keep_last_raw != "" else 20
    except Exception:
        keep_last = 20

    try:
        # If Gemini cache is enabled, clear it on auto shrink_llm
        # to avoid mismatched cached system instructions.
        if provider in ("gemini", "vertexai"):
            try:
                cache_mgr.clear_cache(client)
            except Exception:
                pass
            gemini_cache_name = None

        new_messages = call_maybe_thread_fn(
            lambda: core.compress_history_with_llm(
                client=client,
                depname=depname,
                messages=messages,
                keep_last=keep_last,
            )
        )
        messages.clear()
        messages.extend(new_messages)

        # Persist into current session log
        try:
            core.rewrite_current_log_from_messages(messages)
        except Exception:
            pass

    except Exception as e:
        print(
            _("[WARN] Auto shrink_llm failed: %(err)s")
            % {"err": f"{type(e).__name__}: {e}"}
        )

    return gemini_cache_name


def _build_call_messages(
    *,
    provider: str,
    messages: List[Dict[str, Any]],
    core: Any,
    depname: str,
    gemini_cache_name: Any,
) -> List[Dict[str, Any]]:
    if provider in ("gemini", "vertexai"):
        src_messages = (
            [m for m in messages if m.get("role") != "system"]
            if gemini_cache_name
            else list(messages)
        )

        call_messages: List[Dict[str, Any]] = []
        expecting_tool = False
        saw_tool_in_block = False
        last_kept_role = None

        for m in src_messages:
            if not isinstance(m, dict):
                continue

            role = m.get("role")
            tool_calls = m.get("tool_calls") or []
            has_tool_calls = isinstance(tool_calls, list) and bool(tool_calls)

            if role == "assistant" and has_tool_calls:
                # Gemini requires function_call turns to come directly after user/function response.
                if last_kept_role not in ("user", "tool"):
                    break
                if expecting_tool and not saw_tool_in_block:
                    break
                if expecting_tool and saw_tool_in_block:
                    expecting_tool = False
                    saw_tool_in_block = False

                # Preserve the original assistant turn as-is.
                # Gemini-native dumps are consumed later by llm_gemini.py.
                call_messages.append(m)
                expecting_tool = True
                saw_tool_in_block = False
                last_kept_role = "assistant"
                continue

            if role == "tool":
                if not expecting_tool:
                    break
                call_messages.append(m)
                saw_tool_in_block = True
                last_kept_role = "tool"
                continue

            if expecting_tool and not saw_tool_in_block:
                break

            if expecting_tool and saw_tool_in_block:
                expecting_tool = False
                saw_tool_in_block = False

            call_messages.append(m)
            last_kept_role = role

        if expecting_tool and not saw_tool_in_block:
            while call_messages:
                last = call_messages[-1]
                if (
                    isinstance(last, dict)
                    and last.get("role") == "assistant"
                    and (last.get("tool_calls") or [])
                ):
                    call_messages.pop()
                    break
                call_messages.pop()

        return call_messages

    call_messages = core.sanitize_messages_for_tools(messages)

    image_session_msg = build_image_session_message(call_messages, depname)
    if image_session_msg is not None:
        call_messages = [image_session_msg] + call_messages
    return call_messages
