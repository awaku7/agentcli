from __future__ import annotations

import json
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

                # 繧ｭ繝｣繝・す繝･縺ｫ縺ｯ繧ｷ繧ｹ繝・Β繝励Ο繝ｳ繝励ヨ縺ｮ縺ｿ繧貞性繧√ｋ縲・
                # 繝ｦ繝ｼ繧ｶ繝ｼ縺ｮ蝠上＞縺九￠縺ｯ繝ｪ繧ｯ繧ｨ繧ｹ繝域悽菴・generate_content)縺ｧ騾√ｋ縲・
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
    """Fallback token counting using a simple character-based heuristic."""
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


def _count_auxiliary_tokens(value: Any, depname: str | None = None) -> int:
    """Count JSON-shaped request data not represented by message content.

    Tool schemas and tool-call fields are sent alongside the conversation, so
    counting only message content can substantially under-report the request.
    This helper is local-only and never calls a provider API.
    """
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        text = str(value)

    if depname:
        try:
            import llmcapa

            n = llmcapa.count_tokens(text, depname)
            if n is not None:
                return int(n)
        except Exception:
            pass

    return len(text) // 3


def _count_request_extras_tokens(
    messages: list[dict[str, Any]],
    tool_specs: list[dict[str, Any]] | None = None,
    depname: str | None = None,
) -> int:
    """Count non-content message fields and separately supplied tool schemas."""
    total = 0
    for message in messages:
        if not isinstance(message, dict):
            total += _count_auxiliary_tokens(message, depname)
            continue
        # The model-aware message counter already accounts for role framing;
        # only count fields it cannot see through content-only fallbacks.
        extras = {k: v for k, v in message.items() if k not in ("role", "content")}
        if extras:
            total += _count_auxiliary_tokens(extras, depname)
    if tool_specs:
        total += _count_auxiliary_tokens(tool_specs, depname)
    return total


def _count_messages_tokens(
    messages: list[dict[str, Any]],
    depname: str | None = None,
) -> int:
    """Count tokens for messages, using incremental cache when possible.

    When ``depname`` is provided and llmcapa is available, uses
    ``llmcapa.count_messages_tokens`` with a resolved model id (provider
    aliases applied). Otherwise falls back to a character-based heuristic.

    Cache is keyed by ``id(messages)`` and reset automatically when the
    list shrinks (compression).
    """
    cache_key = id(messages)
    cached_total, cached_len = _token_count_cache.get(cache_key, (0, 0))
    current_len = len(messages)

    def _count_chunk(chunk: list[dict[str, Any]]) -> int:
        if depname:
            try:
                from .llmcapa_util import count_messages_tokens, current_provider

                n = count_messages_tokens(chunk, depname, current_provider() or None)
                if n is not None:
                    return n
            except Exception:
                pass
        return _count_messages_tokens_fallback(chunk)

    # If compression happened (messages were replaced), reset cache
    if current_len < cached_len:
        _token_count_cache.pop(cache_key, None)
        cached_total = 0
        cached_len = 0

    # Incremental: only count newly added messages
    if cached_len > 0 and current_len >= cached_len:
        new_messages = messages[cached_len:]
        if new_messages:
            cached_total += _count_chunk(new_messages)
        _token_count_cache[cache_key] = (cached_total, current_len)
        return cached_total

    # First call: full count
    total = _count_chunk(messages)
    _token_count_cache[cache_key] = (total, current_len)
    return total


def _get_default_shrink_max_tokens(depname: str) -> int:
    try:
        ratio_str = (env_get("UAGENT_SHRINK_RATIO") or "").strip()
        ratio = float(ratio_str) if ratio_str else 0.5
    except Exception:
        ratio = 0.5

    try:
        from .llmcapa_util import current_model, current_provider, get_context_window

        provider = current_provider() or None
        ctx = get_context_window(depname, provider)
        if ctx is None:
            actual = current_model(provider)
            if actual and actual != depname:
                ctx = get_context_window(actual, provider)
        if ctx is not None and ctx > 0:
            return max(1, int(ctx * ratio))
    except Exception:
        pass

    return 100000


def _get_shrink_max_tokens(depname: str) -> int:
    # 1. 蛟句挨迺ｰ蠅・､画焚 (譛蜆ｪ蜈・
    dep_suffix = depname.upper().replace("-", "_").replace(".", "_").replace("/", "_")
    env_specific_key = f"UAGENT_SHRINK_MAX_TOKENS_{dep_suffix}"
    specific_val = (env_get(env_specific_key) or "").strip()
    if specific_val:
        try:
            return int(specific_val)
        except Exception:
            pass

    # 2. 蜈ｱ騾夂腸蠅・､画焚 (JSON霎樊嶌 縺ｾ縺溘・ 蜊倅ｸ謨ｰ蛟､)
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

    # 3. 繧ｳ繝ｼ繝牙・縺ｮ繝・ヵ繧ｩ繝ｫ繝亥､
    return _get_default_shrink_max_tokens(depname)


# Prefix used for LLM history-compression summary system messages (msgid).
_HISTORY_SUMMARY_MSGID = "Summary of the conversation so far:" + chr(10)


def _history_summary_prefixes(translator: Any | None = None) -> list[str]:
    """Return candidate summary prefixes (English msgid + optional translation)."""
    prefixes: set[str] = set()
    candidates = [_HISTORY_SUMMARY_MSGID]
    tr = translator if callable(translator) else _
    try:
        translated = tr(_HISTORY_SUMMARY_MSGID)
        if isinstance(translated, str) and translated:
            candidates.append(translated)
    except Exception:
        pass
    for c in candidates:
        if not isinstance(c, str) or not c:
            continue
        prefixes.add(c)
        stripped = c.rstrip(chr(10))
        prefixes.add(stripped)
        prefixes.add(stripped + chr(10))
    # Longest first so strip prefers the full prefix.
    return sorted((p for p in prefixes if p), key=len, reverse=True)


def _is_history_summary_content(content: Any, translator: Any | None = None) -> bool:
    if not isinstance(content, str) or not content:
        return False
    for prefix in _history_summary_prefixes(translator):
        if content.startswith(prefix):
            return True
    return False


def _strip_history_summary_prefix(content: str, translator: Any | None = None) -> str:
    for prefix in _history_summary_prefixes(translator):
        if content.startswith(prefix):
            return content[len(prefix) :].strip()
    return content.strip()


def _is_history_summary_message(
    m: dict[str, Any], translator: Any | None = None
) -> bool:
    if not isinstance(m, dict) or m.get("role") != "system":
        return False
    return _is_history_summary_content(m.get("content"), translator)


def _messages_have_history_summary(
    messages: list[dict[str, Any]], translator: Any | None = None
) -> bool:
    for m in messages:
        if _is_history_summary_message(m, translator):
            return True
    return False


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
    # History-summary system messages are excluded: they are rolling context,
    # not permanent instructions, and must not inflate others_count / hysteresis.
    others_count = 0
    hit_non_system = False
    for m in messages:
        if _is_history_summary_message(m):
            hit_non_system = True
            continue
        if m.get("role") == "system" and not hit_non_system:
            continue
        hit_non_system = True
        others_count += 1

    keep_last_raw = (env_get("UAGENT_SHRINK_KEEP_LAST", "") or "").strip()
    try:
        keep_last = int(keep_last_raw) if keep_last_raw != "" else 20
    except Exception:
        keep_last = 20

    # Nothing compressible beyond the protected tail.
    if others_count <= keep_last:
        return gemini_cache_name

    # After a prior LLM summary exists, require enough NEW tail growth
    # (hysteresis) so we do not re-shrink immediately on the next tool round.
    should_shrink = False
    has_summary = _messages_have_history_summary(messages)
    if has_summary:
        # Need more than keep_last messages after the previous compress.
        # Default hysteresis: re-trigger only when others_count >= keep_last * 2
        # or when token budget is exceeded again.
        re_cnt = max(keep_last * 2, keep_last + 10)
        if shrink_cnt > 0:
            re_cnt = max(re_cnt, shrink_cnt)
        if others_count >= re_cnt:
            should_shrink = True
        elif shrink_max_tokens > 0:
            total_tokens = _count_messages_tokens(messages, depname)
            if total_tokens >= shrink_max_tokens:
                should_shrink = True
    else:
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
            if m.get("_uagent_ui_only") or m.get("_uagent_internal"):
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
