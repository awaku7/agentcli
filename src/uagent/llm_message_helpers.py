from __future__ import annotations

from typing import Any

from . import tools
from .env_utils import env_get
from .tools.context import get_callbacks
from .image_session import build_image_session_message
from .i18n import \_
from .llm_gemini import \_message_content_text, \_sanitize_gemini_parameters

try:
from google.genai import types as gemini_types
except Exception:
gemini_types = None

def \_init_gemini_cache(
\*,
provider: str,
client: Any,
depname: str,
messages: list\[dict[str, Any]\],
) -> Any:
from .gemini_cache_mgr import GeminiCacheManager

```
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
```

def \_maybe_auto_shrink_messages(
\*,
provider: str,
client: Any,
depname: str,
messages: list\[dict[str, Any]\],
core: Any,
cache_mgr: Any,
gemini_cache_name: Any,
call_maybe_thread_fn: Any,
) -> Any:
\# Determine character limit based on provider
if provider in ("gemini", "vertexai"):
default_char_limit = (
600000 # Safe limit for Gemini (approx 730k tokens in Japanese)
)
elif provider == "claude":
default_char_limit = (
120000 # Safe limit for Claude (approx 84k tokens in Japanese)
)
else:
default_char_limit = (
80000 # Safe limit for OpenAI/Azure (approx 56k tokens in Japanese)
)

```
try:
    char_limit_raw = (env_get("UAGENT_SHRINK_CHAR_LIMIT", "") or "").strip()
    char_limit = int(char_limit_raw) if char_limit_raw else default_char_limit
except Exception:
    char_limit = default_char_limit

# Calculate total characters in message history
total_chars = 0
for m in messages:
    content = m.get("content") or ""
    if isinstance(content, (dict, list)):
        import json

        content = json.dumps(content, ensure_ascii=False)
    total_chars += len(str(content))

# Count-based shrink (disabled by default, enabled only if UAGENT_SHRINK_CNT > 0)
shrink_cnt_raw = (env_get("UAGENT_SHRINK_CNT", "") or "").strip()
try:
    shrink_cnt = int(shrink_cnt_raw) if shrink_cnt_raw != "" else 0
except Exception:
    shrink_cnt = 0

others_count = 0
hit_non_system = False
for m in messages:
    if m.get("role") == "system" and not hit_non_system:
        continue
    hit_non_system = True
    others_count += 1

# Trigger shrink if either limit is exceeded
should_shrink = False
trigger_reason = ""
if char_limit > 0 and total_chars > char_limit:
    should_shrink = True
    trigger_reason = f"character limit exceeded ({total_chars} > {char_limit})"
elif shrink_cnt > 0 and others_count >= shrink_cnt:
    should_shrink = True
    trigger_reason = (
        f"message count limit exceeded ({others_count} >= {shrink_cnt})"
    )

if not should_shrink:
    return gemini_cache_name

import sys as _sys

print(
    _("[INFO] Auto-shrinking conversation history (reason: %(reason)s)...")
    % {"reason": trigger_reason},
    file=_sys.stderr,
)

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

    # Try LLM-based compression first
    try:
        print(
            _(
                "[INFO] Attempting LLM-based compression (keep_last=%(keep_last)d)..."
            )
            % {"keep_last": keep_last},
            file=_sys.stderr,
        )
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
        print(
            _("[INFO] LLM-based compression succeeded."),
            file=_sys.stderr,
        )
    except Exception as compress_err:
        # Fallback to simple truncation if LLM compression fails
        print(
            _(
                "[WARN] LLM compression failed, falling back to simple truncation: %(err)s"
            )
            % {"err": f"{type(compress_err).__name__}: {compress_err}"},
            file=_sys.stderr,
        )
        from .core import shrink_messages

        new_messages = shrink_messages(messages, keep_last=keep_last)
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
        % {"err": f"{type(e).__name__}: {e}"},
        file=_sys.stderr,
    )

return gemini_cache_name
```

def \_build_call_messages(
\*,
provider: str,
messages: list\[dict[str, Any]\],
core: Any,
depname: str,
gemini_cache_name: Any,
) -> list\[dict[str, Any]\]:
if provider in ("gemini", "vertexai"):
src_messages = (
[m for m in messages if m.get("role") != "system"]
if gemini_cache_name
else list(messages)
)

```
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
```
