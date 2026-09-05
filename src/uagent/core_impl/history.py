"""Message history helpers (split from core.py)."""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Optional

from ..env_utils import env_get
from ..i18n import _
from .. import core as _core
from ..runtime.spinner import stop_quietly as _stop_spinner_quietly
from .logs import log_message


def normalize_message_from_log(obj: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Normalize a single line dict from past logs into a minimal message dict
    that can be passed to the current ChatCompletion API.
    - Remove unnecessary keys.
    - Skip broken formats by returning None.
    """
    role = obj.get("role")
    if role not in ("system", "user", "assistant", "tool"):
        return None

    msg: dict[str, Any] = {"role": role}

    if role == "tool":
        msg["content"] = str(obj.get("content") or "")
        if "tool_call_id" in obj:
            msg["tool_call_id"] = obj["tool_call_id"]
        if "name" in obj:
            msg["name"] = obj["name"]
        for key in ("attachments", "saved_path", "saved_files"):
            if key in obj:
                msg[key] = obj.get(key)
        return msg

    # Common for system / user / assistant
    msg["content"] = obj.get("content") or ""

    # OpenRouter (and compatible stacks) may include assistant.reasoning_details.
    # Preserve it so a loaded conversation can continue the chain.
    if role == "assistant" and "reasoning_details" in obj:
        try:
            msg["reasoning_details"] = obj.get("reasoning_details")
        except Exception:
            pass

    # Keep future structured fields such as image attachments
    for key in ("attachments", "saved_path", "saved_files"):
        if key in obj:
            msg[key] = obj.get(key)

    # If tool_calls was present in past logs, keep it aligned with the current format
    tcs = obj.get("tool_calls")
    if isinstance(tcs, list):
        new_tcs: list[dict[str, Any]] = []
        for tc in tcs:
            if not isinstance(tc, dict):
                continue

            fn = tc.get("function") or {}
            if not isinstance(fn, dict):
                fn = {}

            name = fn.get("name") or tc.get("name")
            arguments = fn.get("arguments") or "{}"

            if not name or not isinstance(arguments, str):
                continue

            new_tcs.append(
                {
                    "id": tc.get("id") or "",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": arguments,
                    },
                }
            )

        if new_tcs:
            msg["tool_calls"] = new_tcs

    return msg


def sanitize_messages_for_tools(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove "isolated tool messages that do not have a corresponding assistant.tool_calls" from messages.
    Also strip tool_calls from assistant messages whose tool_call_ids have no matching tool response
    (e.g. after :load of a session that was interrupted mid-tool-call).
    """
    cleaned: list[dict[str, Any]] = []
    pending_tool_ids: set[str] = set()
    pending_tool_block_start: int | None = None

    def _drop_pending_tool_block() -> None:
        nonlocal pending_tool_block_start
        if pending_tool_block_start is not None:
            del cleaned[pending_tool_block_start:]
        pending_tool_ids.clear()
        pending_tool_block_start = None

    for m in messages:
        if not isinstance(m, dict):
            continue
        # Never send UI-only / internal control messages to the model.
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
                cleaned.append(m)
                if tool_ids:
                    pending_tool_ids = tool_ids
                    pending_tool_block_start = len(cleaned) - 1
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

                cleaned.append(m)
                pending_tool_ids.discard(tcid)
                if not pending_tool_ids:
                    pending_tool_block_start = None
                break

            cleaned.append(m)
            break

    if pending_tool_block_start is not None:
        del cleaned[pending_tool_block_start:]

    return cleaned


def load_conversation_from_log(
    path: str,
    system_prompt: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Read conversation history from log file (JSONL) and reconstruct messages:
    - Normalize messages.
    - Discard normal system messages but maintain skill/hook-injected system messages.
    - Re-insert the specified system_prompt at the beginning
      (use the current SYSTEM_PROMPT if not specified).
    """
    raw_messages: list[dict[str, Any]] = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                # Skip broken lines
                continue
            if not isinstance(obj, dict) or "role" not in obj:
                continue
            raw_messages.append(obj)

    # First, normalize
    messages: list[dict[str, Any]] = [
        nm
        for obj in raw_messages
        if (nm := normalize_message_from_log(obj)) is not None
    ]

    # Keep skill/hook-injected system messages; discard other system messages
    skill_prefix = "[SKILL] "
    hook_prefix = "[HOOK] "
    preserved_system_messages = [
        m
        for m in messages
        if m.get("role") == "system"
        and isinstance(m.get("content"), str)
        and (
            m.get("content").startswith(skill_prefix)
            or m.get("content").startswith(hook_prefix)
        )
    ]
    messages = [m for m in messages if m.get("role") != "system"]

    # Use the current SYSTEM_PROMPT if the argument is None
    if system_prompt is None:
        system_prompt = _core.SYSTEM_PROMPT

    # Re-insert the specified system_prompt at the beginning
    system_msg = {"role": "system", "content": system_prompt}
    messages.insert(0, system_msg)

    # Put skill/hook system messages back immediately after system_prompt
    if preserved_system_messages:
        messages[1:1] = preserved_system_messages

    return list(messages)


def shrink_messages(
    messages: list[dict[str, Any]], keep_last: int = 40
) -> list[dict[str, Any]]:
    """
    Simply compress messages in memory:
    - Keep the leading system messages as they are.
    - Keep only the last keep_last messages for others (user/assistant/tool) and discard the rest.
    """
    # system is assumed to be at the beginning (SYSTEM_PROMPT, long-term memory notes, etc.)
    system_msgs: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []

    hit_non_system = False
    for m in messages:
        if m.get("role") == "system" and not hit_non_system:
            system_msgs.append(m)
        else:
            hit_non_system = True
            others.append(m)

    if len(others) <= keep_last:
        _stop_spinner_quietly()
        print(
            _(
                "[INFO] There were %(count)d messages to compress, so nothing was changed."
            )
            % {"count": len(others)},
            file=sys.stderr,
        )
        return list(messages)

    trimmed_others = others[-keep_last:]
    trimmed_others = _fix_tool_call_boundaries(trimmed_others)
    _stop_spinner_quietly()
    print(
        _(
            "[INFO] Compressed in-memory conversation history: %(old_n)d -> %(new_n)d messages (keep_last=%(keep_last)d)"
        )
        % {
            "old_n": len(others),
            "new_n": len(trimmed_others),
            "keep_last": keep_last,
        },
        file=sys.stderr,
    )

    new_messages = system_msgs + trimmed_others
    return new_messages


def _fix_tool_call_boundaries(
    msgs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fix message list boundaries so it doesn't start or end mid-tool-call.

    - Drop leading ``tool`` messages whose corresponding assistant tool_calls
      were truncated away.
    - Drop trailing assistant messages that have ``tool_calls`` but whose
      ``tool`` responses were truncated away.
    - Also drop leading assistant messages that have ``tool_calls`` but whose
      ``tool`` responses were truncated away.
    """
    if not msgs:
        return msgs

    result = list(msgs)

    # ---- Fix leading edge ----
    # Remove leading tool messages that have no preceding assistant with tool_calls.
    while result:
        first = result[0]
        if first.get("role") == "tool":
            result.pop(0)
            continue
        # If the first message is an assistant with tool_calls but the
        # following tool responses are missing, drop it too.
        if first.get("role") == "assistant" and first.get("tool_calls"):
            # Check if all tool_call IDs have matching tool messages.
            tc_ids = set()
            for tc in first.get("tool_calls") or []:
                tc_id = tc.get("id") if isinstance(tc, dict) else None
                if tc_id:
                    tc_ids.add(tc_id)
            if tc_ids:
                # Find matching tool messages in the next few messages.
                found_ids = set()
                for m in result[1:]:
                    if m.get("role") == "tool" and m.get("tool_call_id") in tc_ids:
                        found_ids.add(m["tool_call_id"])
                    elif m.get("role") != "tool":
                        break
                missing = tc_ids - found_ids
                if missing:
                    # Drop the assistant message and any partial tool responses.
                    result.pop(0)
                    while result and result[0].get("role") == "tool":
                        result.pop(0)
                    continue
        break

    # ---- Fix trailing edge ----
    # Remove trailing assistant messages with tool_calls that have no tool responses.
    while result:
        last = result[-1]
        if last.get("role") == "assistant" and last.get("tool_calls"):
            tc_ids = set()
            for tc in last.get("tool_calls") or []:
                tc_id = tc.get("id") if isinstance(tc, dict) else None
                if tc_id:
                    tc_ids.add(tc_id)
            if tc_ids:
                # Check if there are matching tool messages after this assistant.
                found_ids = set()
                for m in reversed(result[:-1]):
                    if m.get("role") == "tool" and m.get("tool_call_id") in tc_ids:
                        found_ids.add(m["tool_call_id"])
                missing = tc_ids - found_ids
                if missing:
                    result.pop()
                    continue
        # Remove trailing tool messages whose assistant was removed.
        if last.get("role") == "tool":
            # Check if there's a preceding assistant with matching tool_call_id.
            tool_id = last.get("tool_call_id")
            has_match = False
            for m in reversed(result[:-1]):
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    for tc in m.get("tool_calls") or []:
                        tc_id = tc.get("id") if isinstance(tc, dict) else None
                        if tc_id == tool_id:
                            has_match = True
                            break
                    if has_match:
                        break
                if m.get("role") != "tool":
                    break
            if not has_match:
                result.pop()
                continue
        break

    return result


def compress_history_with_llm(
    client: Any,
    depname: str,
    messages: list[dict[str, Any]],
    keep_last: int = 20,
    use_responses_api: bool = False,
    emit_log: bool = True,
) -> list[dict[str, Any]]:
    """
    Launch another LLM context to summarize old user/assistant/tool messages
    step-by-step in chunks of around 20 messages, compressing them into a single system message.
    If a context length error occurs, retry by halving the chunk size.
    """
    try:
        from ..profile_manager import run_profiling_async
        import sys as _sys

        _core_mod = _sys.modules[__name__]
        run_profiling_async(messages, _core_mod)
    except Exception:
        pass

    try:
        from ..providers.gemini_cache_mgr import GeminiCacheManager

        mgr = GeminiCacheManager(depname)
        mgr.clear_cache(client)
    except Exception:
        pass

    from ..llm_message_helpers import (
        _is_history_summary_message,
        _strip_history_summary_prefix,
    )

    system_msgs: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []
    prior_summary_bodies: list[str] = []

    hit_non_system = False
    for m in messages:
        # History-compression summaries are system-role but must not be treated
        # as permanent system instructions: fold them into the rolling summary
        # and keep only one summary message in the result.
        if _is_history_summary_message(m):
            body = _strip_history_summary_prefix(str(m.get("content") or ""))
            if body:
                prior_summary_bodies.append(body)
            hit_non_system = True
            continue
        if m.get("role") == "system" and not hit_non_system:
            system_msgs.append(m)
        else:
            hit_non_system = True
            others.append(m)

    old_part = others[:-keep_last]
    tail_part = others[-keep_last:]

    chunk_size_raw = (env_get("UAGENT_SHRINK_CHUNK_SIZE", "") or "").strip()
    try:
        initial_chunk_size = int(chunk_size_raw) if chunk_size_raw else 100
    except Exception:
        initial_chunk_size = 100
    if initial_chunk_size <= 0:
        initial_chunk_size = 100

    # Single-shot mode: send all old messages in one LLM call (UAGENT_SHRINK_SINGLE_SHOT=1)
    single_shot_raw = (env_get("UAGENT_SHRINK_SINGLE_SHOT", "") or "").strip().lower()
    if single_shot_raw in ("1", "true", "yes", "on"):
        if len(old_part) > 0:
            initial_chunk_size = len(old_part)

    max_retries_429 = int(env_get("UAGENT_429_MAX_RETRIES", "20"))
    retry_base = float(env_get("UAGENT_429_BACKOFF_BASE", "2"))
    retry_cap = float(env_get("UAGENT_429_BACKOFF_CAP", "300"))

    from ..llm_errors import _rate_limit_retry_step

    def _recreate_client() -> Any:
        try:
            from ..providers import util_providers
            import sys as _sys

            _core_mod = _sys.modules[__name__]
            _unused_p, new_client, _unused_m = util_providers.make_client(_core_mod)
            return new_client
        except Exception:
            return None

    from ..providers import util_providers

    try:
        provider = util_providers.detect_provider()
    except Exception:
        provider = (env_get("UAGENT_PROVIDER") or "").strip().lower() or "openai"
    translator = globals().get("_")
    try:
        from ..i18n import get_locale

        active_locale = get_locale()
    except Exception:
        active_locale = "en"

    def _t(s: str) -> str:
        try:
            return translator(s) if callable(translator) else s
        except Exception:
            return s

    def _message_to_text(m: dict[str, Any]) -> tuple[str | None, str]:
        role = str(m.get("role") or "")
        content = m.get("content") or ""
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False)
        content = str(content).strip()
        if not content:
            return None, role

        if role == "user":
            return f"User: {content}", role
        if role == "assistant":
            return f"Assistant: {content}", role
        if role == "tool":
            tname = m.get("name") or "(unknown_tool)"
            return f"Tool: {tname} {content}", role
        return None, role

    def _is_context_length_exceeded(err: Exception) -> bool:
        s = f"{type(err).__name__}: {err}".lower()
        return (
            "context_length_exceeded" in s
            or "exceeds the context window" in s
            or "input exceeds the context window" in s
        )

    def _is_openai_module_deadlock(err: Exception) -> bool:
        """Return whether a lazy OpenAI resource import hit a module deadlock."""
        text = f"{type(err).__name__}: {err}".lower()
        return "_modulelock" in text and "openai.resources" in text

    def _is_temperature_rejected(err: Exception) -> bool:
        """Return whether the provider rejected the temperature parameter."""
        s = f"{type(err).__name__}: {err}".lower()
        if "temperature" not in s:
            return False
        return any(
            marker in s
            for marker in (
                "unsupported value",
                "unsupported parameter",
                "does not support",
                "not support",
                "only the default",
                "unknown parameter",
                "unexpected keyword",
            )
        )

    def _summarize_with_llm(
        summary_messages: list[dict[str, Any]],
    ) -> tuple[str | None, Exception | None]:
        nonlocal client
        summary_content = ""
        attempt_429 = 0
        module_deadlock_retries = 0
        while True:
            try:
                if provider in ("gemini", "vertexai") or "genai.Client" in str(
                    type(client)
                ):
                    from ..providers.llm_gemini import gemini_chat_with_tools

                    summary_content, _summary_unused1, _summary_unused2 = (
                        gemini_chat_with_tools(
                            client=client,
                            model_name=depname,
                            messages=summary_messages,
                            core=sys.modules[__name__],
                            # Preserve the active provider during history
                            # compression. Otherwise this helper defaults to
                            # "gemini" and sends the Developer API-only
                            # server-side tool flag to Vertex AI.
                            provider=provider,
                        )
                    )
                elif provider == "claude":
                    from ..providers.llm_claude import claude_chat_with_tools

                    claude_result = claude_chat_with_tools(
                        client=client,
                        model_name=depname,
                        messages=summary_messages,
                        core=sys.modules[__name__],
                    )
                    if isinstance(claude_result, tuple):
                        summary_content = (
                            claude_result[0] if len(claude_result) >= 1 else ""
                        )
                    else:
                        summary_content = str(claude_result)
                else:
                    # Shared max tokens for history-summary generation.
                    _sum_max = 2048
                    try:
                        from ..llmcapa_util import clamp_max_tokens

                        _sum_max = clamp_max_tokens(_sum_max, depname, provider)
                    except Exception:
                        pass

                    if use_responses_api:
                        resp = client.responses.create(
                            model=depname,
                            instructions=summary_messages[0]["content"],
                            input=[
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "input_text",
                                            "text": summary_messages[1]["content"],
                                        },
                                    ],
                                }
                            ],
                            max_output_tokens=_sum_max,
                        )
                        if hasattr(resp, "output") and resp.output:
                            for item in resp.output:
                                if item.type == "message":
                                    for c in item.content:
                                        if c.type == "output_text":
                                            summary_content += c.text
                    elif (
                        hasattr(client, "chat")
                        and hasattr(client.chat, "create")
                        and not hasattr(client.chat, "completions")
                    ):
                        # xai_sdk (gRPC): convert OpenAI-format messages first
                        from ..providers.llm_grok import simple_xai_chat

                        summary_content = simple_xai_chat(
                            client,
                            depname,
                            summary_messages,
                            max_tokens=_sum_max,
                            temperature=0.0,
                        )
                    elif hasattr(client, "chat") and hasattr(
                        client.chat, "completions"
                    ):
                        _summary_kwargs = {
                            "model": depname,
                            "messages": summary_messages,
                            "temperature": 0.0,
                        }
                        _summary_model = str(depname or "").lower()
                        if provider in ("openai", "azure") and (
                            _summary_model.startswith("gpt-5")
                            or _summary_model.startswith(("o1", "o2", "o3", "o4"))
                        ):
                            _summary_kwargs["max_completion_tokens"] = _sum_max
                        else:
                            _summary_kwargs["max_tokens"] = _sum_max
                        try:
                            resp = client.chat.completions.create(**_summary_kwargs)
                        except Exception as temperature_error:
                            if not _is_temperature_rejected(temperature_error):
                                raise
                            # Some reasoning models require their default
                            # temperature and reject any explicit value.
                            _summary_kwargs.pop("temperature", None)
                            resp = client.chat.completions.create(**_summary_kwargs)
                        summary_content = resp.choices[0].message.content or ""
                    else:
                        raise AttributeError(
                            f"Client {type(client)} has no attribute 'chat' and is not recognized as Gemini."
                        )
                return summary_content, None
            except Exception as e:
                if _is_openai_module_deadlock(e) and module_deadlock_retries < 3:
                    module_deadlock_retries += 1
                    time.sleep(0.25 * module_deadlock_retries)
                    continue
                if _is_context_length_exceeded(e):
                    return None, e

                attempt_429, new_client, action = _rate_limit_retry_step(
                    exception=e,
                    provider="summarize",
                    model=depname,
                    attempt=attempt_429,
                    max_retries=max_retries_429,
                    base=retry_base,
                    cap=retry_cap,
                    recreate_client_fn=_recreate_client,
                )

                if action == "retry":
                    if new_client is not None:
                        client = new_client
                    continue

                if action == "give_up":
                    _stop_spinner_quietly()
                    print(
                        "[WARN] "
                        + _t(
                            "429 retry limit (%(max_retries)s) reached while history compression."
                        )
                        % {"max_retries": max_retries_429},
                        file=sys.stderr,
                    )
                    print(repr(e), file=sys.stderr)
                    return None, e

                _stop_spinner_quietly()
                print(
                    "[WARN] "
                    + _t("Error while calling LLM for history compression: %(err)r")
                    % {"err": e},
                    file=sys.stderr,
                )
                return None, e

    def _compress_once(
        current_chunk_size: int,
    ) -> tuple[list[dict[str, Any]] | None, Exception | None]:
        if current_chunk_size <= 0:
            current_chunk_size = 1

        chunks = [
            old_part[i : i + current_chunk_size]
            for i in range(0, len(old_part), current_chunk_size)
        ]

        total_chunks = len(chunks)
        chunk_index = 0
        # Seed rolling summary from any prior compressions so we merge instead
        # of stacking multiple "Summary of the conversation so far" system msgs.
        rolling_summary = "\n\n".join(prior_summary_bodies).strip()
        for chunk in chunks:
            lines = [
                rendered
                for m in chunk
                if (rendered := _message_to_text(m)[0]) is not None
            ]

            if not lines:
                continue

            chunk_text = "\n\n".join(lines)

            if not rolling_summary:
                summary_system_prompt = (
                    _t(
                        "- Write the summary in the same language as the user messages; "
                        "prefer the active UI locale (%(locale)s).\n"
                    )
                    % {"locale": active_locale}
                    + _t(
                        "- Keep the summary concise but include key decisions, constraints, and pending items.\n"
                    )
                    + _t("- Output should be directly usable as a system message.")
                )
                summary_user_content = (
                    _t("Conversation chunk:\n")
                    + f"{chunk_text}\n\n"
                    + _t("Write a concise summary of this chunk.")
                )
            else:
                summary_system_prompt = (
                    _t("- You are updating an existing conversation summary.\n")
                    + _t("- Preserve important facts from the previous summary.\n")
                    + _t(
                        "- Merge in the new chunk without losing constraints, decisions, or pending items.\n"
                    )
                    + _t("- Keep the result concise and suitable for a system message.")
                )
                summary_user_content = (
                    _t("Previous summary:\n")
                    + f"{rolling_summary}\n\n"
                    + _t("New chunk:\n")
                    + f"{chunk_text}\n\n"
                    + _t("Update the summary while keeping the prior context intact.")
                )

            summary_messages = [
                {"role": "system", "content": summary_system_prompt},
                {"role": "user", "content": summary_user_content},
            ]

            chunk_index += 1
            if emit_log and total_chunks > 1:
                _stop_spinner_quietly()
                print(
                    _t("[shrink_llm] Summarizing chunk %(i)d/%(n)d...")
                    % {"i": chunk_index, "n": total_chunks},
                    file=sys.stderr,
                )

            summary_content, error = _summarize_with_llm(summary_messages)
            if error is not None:
                return None, error
            if summary_content is None:
                return None, RuntimeError("history compression returned no summary")

            rolling_summary = summary_content.strip()

        if not rolling_summary:
            # No new summary text and no prior summary body to keep.
            return system_msgs + tail_part, None

        summary_msg = {
            "role": "system",
            "content": _t("Summary of the conversation so far:\n") + rolling_summary,
        }

        new_messages = system_msgs + [summary_msg] + tail_part

        if emit_log:
            _stop_spinner_quietly()
            print(
                _t(
                    "[INFO] shrink_llm: {old_n} -> {new_n} messages "
                    "(compressed {old_part_n} older messages into 1 summary; kept {tail_n} tail)"
                ).format(
                    old_n=len(messages),
                    new_n=len(new_messages),
                    old_part_n=len(old_part),
                    tail_n=len(tail_part),
                ),
                file=sys.stderr,
            )

        if emit_log:
            log_message(summary_msg)
        return new_messages, None

    current_chunk_size = initial_chunk_size
    while True:
        compressed_messages, error = _compress_once(current_chunk_size)
        if error is None:
            return (
                compressed_messages
                if compressed_messages is not None
                else list(messages)
            )

        if _is_context_length_exceeded(error):
            if current_chunk_size <= 1:
                _stop_spinner_quietly()
                print(
                    _(
                        "[WARN] history compression hit context length at the minimum chunk size; history was left unchanged."
                    ),
                    file=sys.stderr,
                )
                return list(messages)

            next_chunk_size = max(1, current_chunk_size // 2)
            if next_chunk_size == current_chunk_size:
                _stop_spinner_quietly()
                print(
                    _(
                        "[WARN] history compression could not reduce the chunk size; history was left unchanged."
                    ),
                    file=sys.stderr,
                )
                return list(messages)

            _stop_spinner_quietly()
            print(
                _(
                    "[WARN] history compression context length exceeded; retrying with chunk_size=%(chunk_size)d"
                )
                % {"chunk_size": next_chunk_size},
                file=sys.stderr,
            )
            current_chunk_size = next_chunk_size
            continue

        _stop_spinner_quietly()
        print(
            _t(
                "[WARN] history compression failed due to an LLM error; history was left unchanged."
            ),
            file=sys.stderr,
        )
        return list(messages)
