from __future__ import annotations

from typing import Any

from . import tools
from .env_utils import env_get
from .tools.context import get_callbacks
from .image_session import build_image_session_message
from .i18n import _
from .providers.llm_gemini import _message_content_text, _sanitize_gemini_parameters

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
    from .providers.gemini_cache_mgr import GeminiCacheManager

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


# Cache for incremental token counting
# key = id(messages_list) -> (total_tokens, last_known_length)
_token_count_cache: dict[int, tuple[int, int]] = {}


def _count_messages_tokens_fallback(messages: list[dict[str, Any]]) -> int:
    """Fallback token counting using tiktoken or character-based heuristic."""
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        total_chars = 0
        for m in messages:
            content = m.get("content")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        total_chars += len(part.get("text", ""))
        return total_chars // 3

    total_tokens = 0
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            total_tokens += len(encoding.encode(content))
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", "")
                    total_tokens += len(encoding.encode(text))
    return total_tokens


def _count_messages_tokens(
    messages: list[dict[str, Any]],
    depname: str | None = None,
) -> int:
    """Count tokens for messages, using incremental cache when possible.

    When ``depname`` is provided and llmcapa is available, uses
    ``llmcapa.count_messages_tokens`` (provider-specific format). Otherwise
    falls back to tiktoken (cl100k_base) or character-based heuristic.

    Cache is keyed by ``id(messages)`` and reset automatically when the
    list shrinks (compression).
    """
    cache_key = id(messages)
    cached_total, cached_len = _token_count_cache.get(cache_key, (0, 0))
    current_len = len(messages)

    # If compression happened (messages were replaced), reset cache
    if current_len < cached_len:
        _token_count_cache.pop(cache_key, None)
        cached_total = 0
        cached_len = 0

    # Incremental: only count newly added messages
    if cached_len > 0 and current_len >= cached_len:
        new_messages = messages[cached_len:]
        if new_messages:
            if depname:
                try:
                    import llmcapa

                    new_tokens = llmcapa.count_messages_tokens(new_messages, depname)
                except Exception:
                    new_tokens = _count_messages_tokens_fallback(new_messages)
            else:
                new_tokens = _count_messages_tokens_fallback(new_messages)
            cached_total += new_tokens
        _token_count_cache[cache_key] = (cached_total, current_len)
        return cached_total

    # First call: full count
    if depname:
        try:
            import llmcapa

            total = llmcapa.count_messages_tokens(messages, depname)
        except Exception:
            total = _count_messages_tokens_fallback(messages)
    else:
        total = _count_messages_tokens_fallback(messages)

    _token_count_cache[cache_key] = (total, current_len)
    return total


def _get_default_shrink_max_tokens(depname: str) -> int:
    try:
        ratio_str = (env_get("UAGENT_SHRINK_RATIO") or "").strip()
        ratio = float(ratio_str) if ratio_str else 0.5
    except Exception:
        ratio = 0.5

    try:
        import llmcapa

        cap = llmcapa.get(depname)
        if cap and cap.context_window > 0:
            return int(cap.context_window * ratio)
    except Exception:
        pass

    return 100000


def _get_shrink_max_tokens(depname: str) -> int:
    # 1. 個別環境変数 (最優先)
    dep_suffix = depname.upper().replace("-", "_").replace(".", "_").replace("/", "_")
    env_specific_key = f"UAGENT_SHRINK_MAX_TOKENS_{dep_suffix}"
    specific_val = (env_get(env_specific_key) or "").strip()
    if specific_val:
        try:
            return int(specific_val)
        except Exception:
            pass

    # 2. 共通環境変数 (JSON辞書 または 単一数値)
    global_val = (env_get("UAGENT_SHRINK_MAX_TOKENS") or "").strip()
    if global_val:
        if global_val.startswith("{") and global_val.endswith("}"):
            try:
                import json

                limits_dict = json.loads(global_val)
                dep_lower = depname.lower()
                for k, v in limits_dict.items():
                    if k.lower() in dep_lower:
                        return int(v)
            except Exception:
                pass
        else:
            try:
                return int(global_val)
            except Exception:
                pass

    # 3. コード内のデフォルト値
    return _get_default_shrink_max_tokens(depname)


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
    use_responses_api: bool = False,
) -> Any:

    # Auto shrink_llm (optional)
    shrink_cnt_raw = (env_get("UAGENT_SHRINK_CNT", "") or "").strip()
    try:
        shrink_cnt = int(shrink_cnt_raw) if shrink_cnt_raw != "" else 0
    except Exception:
        shrink_cnt = 0

    shrink_max_tokens = _get_shrink_max_tokens(depname)

    # Count non-system messages (same rule as core.shrink_messages)
    others_count = 0
    hit_non_system = False
    for m in messages:
        if m.get("role") == "system" and not hit_non_system:
            continue
        hit_non_system = True
        others_count += 1

    keep_last_raw = (env_get("UAGENT_SHRINK_KEEP_LAST", "") or "").strip()
    try:
        keep_last = int(keep_last_raw) if keep_last_raw != "" else 20
    except Exception:
        keep_last = 20

    # 圧縮する余地がない場合はスキップ
    if others_count <= keep_last:
        return gemini_cache_name

    # 件数ベースまたはトークン数ベースのいずれかが上限を超えているか判定
    should_shrink = False
    if shrink_cnt > 0 and others_count >= shrink_cnt:
        should_shrink = True
    elif shrink_max_tokens > 0:
        total_tokens = _count_messages_tokens(messages, depname)
        if total_tokens >= shrink_max_tokens:
            should_shrink = True

    if not should_shrink:
        return gemini_cache_name

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
                use_responses_api=use_responses_api,
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
            _("[WARN] Auto shrink_llm failed: %(err)s")
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
