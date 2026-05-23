from __future__ import annotations

from typing import Any

from . import tools
from .env_utils import env_get
from .tools.context import get_callbacks
from .image_session import build_image_session_message
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
    messages: list[dict[str, Any]],
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
    messages: list[dict[str, Any]],
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
            cb = get_callbacks()
            rewrite_current_log = getattr(cb, "rewrite_current_log_from_messages", None)
            if rewrite_current_log is not None:
                rewrite_current_log(messages)
            else:
                core.rewrite_current_log_from_messages(messages)
        except Exception:
            pass

    except Exception as e:
        print(
            "[WARN] Auto shrink_llm failed: %(err)s"
            % {"err": f"{type(e).__name__}: {e}"}
        )

    return gemini_cache_name


def _build_call_messages(
    *,
    provider: str,
    messages: list[dict[str, Any]],
    core: Any,
    depname: str,
    gemini_cache_name: Any,
) -> list[dict[str, Any]]:
    if provider in ("gemini", "vertexai"):
        src_messages = (
            [m for m in messages if m.get("role") != "system"]
            if gemini_cache_name
            else list(messages)
        )

        call_messages: list[dict[str, Any]] = []
        pending_tool_ids: set[str] = set()
        pending_tool_block_start: int | None = None

        def _drop_pending_tool_block() -> None:
            nonlocal pending_tool_block_start
            if pending_tool_block_start is not None:
                del call_messages[pending_tool_block_start:]
            pending_tool_ids.clear()
            pending_tool_block_start = None

        for m in src_messages:
            if not isinstance(m, dict):
                continue

            while True:
                role = m.get("role")
                tool_calls = m.get("tool_calls") or []
                has_tool_calls = isinstance(tool_calls, list) and bool(tool_calls)

                # If a tool-call block is interrupted by any non-tool message, drop the
                # incomplete block and keep later history instead of truncating the tail.
                if pending_tool_block_start is not None and role != "tool":
                    _drop_pending_tool_block()
                    continue

                if role == "assistant" and has_tool_calls:
                    tool_ids: set[str] = set()
                    for tc in tool_calls:
                        if not isinstance(tc, dict):
                            continue
                        tcid = tc.get("id")
                        if isinstance(tcid, str) and tcid:
                            tool_ids.add(tcid)

                    # Keep the assistant turn even when tool IDs are missing, but do not
                    # enter pending-tool mode because we cannot reliably match tool results.
                    call_messages.append(m)
                    if tool_ids:
                        pending_tool_ids = tool_ids
                        pending_tool_block_start = len(call_messages) - 1
                    break

                if role == "tool":
                    tcid = m.get("tool_call_id")
                    if pending_tool_block_start is None:
                        # Orphan tool result: ignore it and continue with later history.
                        break

                    if not (isinstance(tcid, str) and tcid in pending_tool_ids):
                        # Mismatched tool result: ignore it. The pending block will be
                        # dropped later if it is interrupted by a non-tool message.
                        break

                    call_messages.append(m)
                    pending_tool_ids.discard(tcid)
                    if not pending_tool_ids:
                        pending_tool_block_start = None
                    break

                call_messages.append(m)
                break

        if pending_tool_block_start is not None:
            del call_messages[pending_tool_block_start:]

        return call_messages

    call_messages = core.sanitize_messages_for_tools(messages)

    image_session_msg = build_image_session_message(call_messages, depname)
    if image_session_msg is not None:
        call_messages = [image_session_msg] + call_messages
    return call_messages
