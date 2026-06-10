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


def _count_messages_tokens(messages: list[dict[str, Any]]) -> int:
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        # tiktoken が使えない場合は簡易文字数ベースで概算
        total_chars = 0
        for m in messages:
            content = m.get("content")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        total_chars += len(part.get("text", ""))
        return total_chars // 3  # 簡易的な概算（1トークン ≒ 3文字）

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


DEFAULT_SHRINK_LIMITS = {
    "gemini": {
        "pro": 200000,
        "flash": 150000,
        "default": 150000,
    },
    "claude": {
        "default": 100000,
    },
    "deepseek": {
        "v4": 200000,
        "default": 100000,
    },
    "gpt-5.5": {
        "pro": 200000,
        "default": 200000,
    },
    "gpt-5": {
        "mini": 60000,
        "default": 100000,
    },
    "gpt-4.1": {
        "default": 150000,
    },
    "gpt-4o": {
        "default": 60000,
    },
    "o1-": {
        "default": 60000,
    },
    "o3-": {
        "default": 60000,
    },
    "o4-": {
        "default": 60000,
    },
    "grok": {
        "default": 200000,
    },
    "mistral": {
        "default": 60000,
    },
    "nemotron": {
        "default": 120000,
    },
    "llama-3": {
        "default": 60000,
    },
    "llama3": {
        "default": 60000,
    },
    "qwen3.5": {
        "default": 200000,
    },
    "qwen": {
        "max": 120000,
        "plus": 200000,
        "flash": 200000,
        "coder": 120000,
        "default": 120000,
    },
    "gemma-4": {
        "default": 200000,
    },
    "gemma4": {
        "default": 200000,
    },
    "gemma": {
        "e2b": 24000,
        "e4b": 24000,
        "default": 100000,
    },
    "gpt-oss": {
        "default": 60000,
    },
}


def _get_default_shrink_max_tokens(depname: str) -> int:
    dep_lower = depname.lower()
    for brand, sub_dict in DEFAULT_SHRINK_LIMITS.items():
        if brand in dep_lower:
            for sub_key, val in sub_dict.items():
                if sub_key != "default" and sub_key in dep_lower:
                    return val
            return sub_dict.get("default", 100000)
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
        total_tokens = _count_messages_tokens(messages)
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
