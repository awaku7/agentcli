from __future__ import annotations

import json
import sys
import traceback
from functools import lru_cache
from typing import Any

from . import tools
from .env_utils import env_get
from .i18n import _
from .llm_helpers import _effectively_empty_text
from .reasoning_display import show_reasoning
from .runtime.history import (
    materialize_large_tool_result,
    truncate_history_tool_result,
)


@lru_cache(maxsize=None)
def _is_external_data_tool(name: str) -> bool:
    """Check if a tool fetches external/third-party content.

    Results from these tools are wrapped with isolation markers to prevent
    embedded instructions from being interpreted as commands.
    """
    return name in tools.get_external_data_tools()


def _strip_inline_binary_payloads(value: Any) -> Any:
    """Return a tool result copy without inline binary payloads.

    Tool results may keep Base64 data in attachment metadata for the UI or a
    remote client. The same data must not be sent as the textual function
    result to the next LLM turn: generated images and audio can make a
    Responses request invalid or exceed the provider's request limits.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if "base64" in str(key).lower():
                out[key] = "[binary payload omitted from LLM context]"
            else:
                out[key] = _strip_inline_binary_payloads(item)
        return out
    if isinstance(value, list):
        return [_strip_inline_binary_payloads(item) for item in value]
    return value


def _append_assistant_message(
    *,
    messages: list[dict[str, Any]],
    core: Any,
    assistant_text: str,
    tool_calls_list: list[dict[str, Any]],
    gemini_content_dump: Any = None,
    responses_output_items: list[dict[str, Any]] | None = None,
    skip_log_when_web: bool = False,
) -> None:
    assistant_msg: dict[str, Any] = {
        "role": "assistant",
        "content": assistant_text,
    }
    # Keep the server-side Responses API identifier on the assistant log
    # record itself. Previously it was only emitted as a separate
    # ``responses_state`` record, and only when the lifecycle callback ran.
    try:
        response_id = str(
            (getattr(core, "responses_state", {}) or {}).get("previous_response_id", "")
            or ""
        ).strip()
        if response_id.startswith("resp_"):
            assistant_msg["response_id"] = response_id
    except Exception:
        pass
    if tool_calls_list:
        assistant_msg["tool_calls"] = tool_calls_list
    if isinstance(responses_output_items, list) and responses_output_items:
        assistant_msg["_responses_output_items"] = responses_output_items
    if isinstance(gemini_content_dump, dict) and gemini_content_dump:
        assistant_msg["_gemini_content"] = gemini_content_dump

    messages.append(assistant_msg)

    if not (skip_log_when_web and bool(getattr(core, "_is_web", False))):
        core.log_message(assistant_msg)


def _emit_final_answer_if_any(
    *,
    assistant_text: str,
    reasoning_content: str = "",
    use_responses_api: bool,
    stream_responses: bool,
    append_result_to_outfile_fn: Any,
    try_open_images_from_text_fn: Any,
    skip_print: bool = False,
    core: Any = None,
    provider: str = "LLM",
) -> None:
    if not _effectively_empty_text(assistant_text):
        # Responses+Streaming already printed deltas in parse_responses_stream(); avoid double-print.
        if not skip_print and not (use_responses_api and stream_responses):
            if reasoning_content:
                show_reasoning(
                    reasoning_content,
                    provider=provider,
                    is_first=True,
                    core=core,
                )
            print(assistant_text)
        append_result_to_outfile_fn(assistant_text)
        try_open_images_from_text_fn(assistant_text)


def _parse_tool_result_json(tool_result: str) -> dict[str, Any] | None:
    def _load_json(text: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(text)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    parsed = _load_json(tool_result)
    if parsed is not None:
        return parsed

    if isinstance(tool_result, str):
        head, sep, tail = tool_result.partition("\n")
        if sep and head.lstrip().startswith("[INFO]"):
            parsed = _load_json(tail)
            if parsed is not None:
                return parsed

    return None


def _build_auto_user_message_from_next_action(
    *,
    parsed_tool_result: dict[str, Any] | None,
    tool_msg: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(parsed_tool_result, dict):
        return None

    data = parsed_tool_result.get("data")
    if isinstance(data, dict):
        next_action = data.get("next_action")
    else:
        next_action = parsed_tool_result.get("next_action")

    if isinstance(next_action, str):
        next_action = {
            "type": "user_message",
            "content": next_action,
        }

    if not isinstance(next_action, dict):
        return None

    action_type = str(next_action.get("type") or "").strip().lower()
    if action_type != "user_message":
        return None

    content = (
        next_action.get("content")
        or next_action.get("text")
        or next_action.get("prompt")
        or next_action.get("message")
        or ""
    )
    content = str(content).strip()
    if not content:
        return None

    auto_user_msg: dict[str, Any] = {
        "role": "user",
        "content": content,
    }

    attachments = next_action.get("attachments")
    if isinstance(attachments, list) and attachments:
        auto_user_msg["attachments"] = attachments
    else:
        # Generated media is for the client/UI attachment channel. Do not feed
        # its potentially large Base64 payload back into the LLM continuation.
        tool_name = str(tool_msg.get("name") or "")
        if tool_name not in {
            "generate_image",
            "mermaid_render",
            "img2img",
            "forecast",
            "generate_qr_code",
            "screenshot",
            "pdf_export",
            "audio_speech",
        }:
            tool_attachments = tool_msg.get("attachments")
            if isinstance(tool_attachments, list) and tool_attachments:
                auto_user_msg["attachments"] = tool_attachments

    return auto_user_msg


def _default_empty_no_tool_max(provider: str) -> int:
    """Default consecutive empty/no-tool tolerance.

    Grok/xAI sometimes returns empty assistant messages after tool calls more
    often than other providers, so give it a higher default before aborting.
    """
    p = (provider or "").strip().lower()
    if p in ("grok", "xai"):
        return 5
    return 2


def _resolve_empty_no_tool_max(provider: str) -> int:
    """Read UAGENT_EMPTY_NO_TOOL_MAX, falling back to provider-aware default."""
    default = _default_empty_no_tool_max(provider)
    raw = env_get("UAGENT_EMPTY_NO_TOOL_MAX", "")
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(str(raw).strip())
    except Exception:
        return default
    if value < 0:
        return default
    return value


def _drop_trailing_empty_assistant(messages: list[dict[str, Any]]) -> bool:
    """Remove a just-appended empty assistant message (no tool_calls).

    Empty assistant turns pollute the next-turn prompt and make providers more
    likely to emit another empty reply (especially after a short 'continue').
    """
    if not messages:
        return False
    last = messages[-1]
    if not isinstance(last, dict):
        return False
    if last.get("role") != "assistant":
        return False
    if last.get("_uagent_ui_only"):
        messages.pop()
        return True
    tcs = last.get("tool_calls")
    if isinstance(tcs, list) and tcs:
        return False
    if not _effectively_empty_text(last.get("content")):
        return False
    messages.pop()
    return True


def _should_keep_assistant_message(
    assistant_text: str,
    tool_calls_list: list[dict[str, Any]] | None,
) -> bool:
    """Whether an assistant turn should enter model-visible history."""
    if isinstance(tool_calls_list, list) and tool_calls_list:
        return True
    return not _effectively_empty_text(assistant_text)


def _empty_no_tool_recovery_text() -> str:
    return _(
        "The previous model turn ended with an empty reply after tool use. Continue the unfinished task using the most recent tool results. Prefer a concrete next step or final answer over an empty response.",
        default="The previous model turn ended with an empty reply after tool use. Continue the unfinished task using the most recent tool results. Prefer a concrete next step or final answer over an empty response.",
    )


def _consume_empty_no_tool_recovery(
    *,
    messages: list[dict[str, Any]],
    core: Any,
) -> bool:
    """Merge one pending recovery hint into the latest real user message.

    Recovery is intentionally NOT left as a standalone user turn: that caused
    stacked synthetic user messages after repeated empty WARN + 'continue'.
    """
    pending = bool(getattr(core, "_empty_no_tool_recovery_pending", False))
    if not pending:
        return False
    try:
        setattr(core, "_empty_no_tool_recovery_pending", False)
    except Exception:
        pass

    recovery = _empty_no_tool_recovery_text()
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if m.get("role") != "user":
            continue
        if m.get("_uagent_internal") or m.get("_uagent_ui_only"):
            continue
        content = m.get("content")
        if isinstance(content, str):
            body = content.strip()
            if not body:
                m["content"] = recovery
            elif recovery not in body:
                m["content"] = recovery + "\n\n" + content
            return True
        if isinstance(content, list):
            # Prepend a text part for multimodal user turns.
            m["content"] = [{"type": "text", "text": recovery}, *content]
            return True
        m["content"] = recovery
        return True

    messages.append(
        {
            "role": "user",
            "content": recovery,
            "_uagent_internal": "empty_no_tool_recovery",
        }
    )
    return True


def _handle_openai_empty_no_tool(
    *,
    assistant_text: str,
    tool_calls_list: list[dict[str, Any]],
    empty_no_tool_rounds: int,
    empty_no_tool_max: int,
    provider: str,
    depname: str,
    messages: list[dict[str, Any]],
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

        # Safety net: if a provider branch already appended an empty assistant
        # turn, drop it so retries / next user turns do not see blanks.
        try:
            _drop_trailing_empty_assistant(messages)
        except Exception:
            pass

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
                    "content": _(
                        "The previous assistant reply was empty. Please answer based on the most recent tool result.",
                        default="The previous assistant reply was empty. Please answer based on the most recent tool result.",
                    ),
                }
                messages.append(nudge_msg)
                core.log_message(nudge_msg)
            except Exception:
                pass

        if empty_no_tool_rounds <= empty_no_tool_max:
            return "continue", empty_no_tool_rounds

        warn_text = _(
            "[WARN] LLM returned an empty assistant message without tool calls.\nprovider=%(provider)s depname=%(depname)s empty_no_tool_rounds=%(empty_no_tool_rounds)s (max=%(empty_no_tool_max)s)\nThis may happen with some providers (including Grok/xAI and OpenAI-compatible endpoints) after tool calls. You can try setting UAGENT_EMPTY_NO_TOOL_MAX to a higher value, or switching provider.",
            default="[WARN] LLM returned an empty assistant message without tool calls.\nprovider=%(provider)s depname=%(depname)s empty_no_tool_rounds=%(empty_no_tool_rounds)s (max=%(empty_no_tool_max)s)\nThis may happen with some providers (including Grok/xAI and OpenAI-compatible endpoints) after tool calls. You can try setting UAGENT_EMPTY_NO_TOOL_MAX to a higher value, or switching provider.",
        ) % {
            "provider": provider,
            "depname": depname,
            "empty_no_tool_rounds": empty_no_tool_rounds,
            "empty_no_tool_max": empty_no_tool_max,
        }
        # Keep WARN out of model-visible history. Print for CLI; log a UI-only
        # assistant message so Web/GUI can show it without poisoning the prompt.
        try:
            print(warn_text, file=sys.stderr)
        except Exception:
            pass
        try:
            core.log_message(
                {
                    "role": "assistant",
                    "content": warn_text,
                    "_uagent_ui_only": True,
                }
            )
        except Exception:
            pass

        # Defer recovery to the next user turn (merged there once). Appending a
        # synthetic user message here stacked with the real follow-up ("続けて")
        # and repeated WARNs accumulated multiple recovery prompts.
        if env_get("UAGENT_EMPTY_NO_TOOL_RECOVERY", "1") != "0":
            try:
                setattr(core, "_empty_no_tool_recovery_pending", True)
            except Exception:
                pass
        return "break", empty_no_tool_rounds

    return "pass", 0


def _fire_tool_hooks(event: str, tool_name: str) -> None:
    """Fire tool-related hooks (PreToolUse/PostToolUse/PostToolUseFailure)."""
    try:
        from .hooks_engine import (
            get_default_registry_path,
            load_hooks_registry,
            fire_tool_event,
        )

        registry_path = get_default_registry_path()
        hooks = load_hooks_registry(registry_path)
        if hooks:
            fire_tool_event(event, hooks, tool_name=tool_name)
    except Exception:
        pass


def _execute_tool_calls(
    *,
    tool_calls_list: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    core: Any,
    cache_mgr: Any,
) -> tuple[bool, list[dict[str, Any]]]:
    """Execute tool calls.

    Returns:
        executed_new_tool: True if at least one tool ran (not cache-reuse only)
        fresh_tool_calls: tool_call dicts that actually executed (for loop detect)
    """
    executed_new_tool = False
    fresh_tool_calls: list[dict[str, Any]] = []
    pending_auto_user_msgs: list[dict[str, Any]] = []

    # ---- Phase 1: pre-execute parallel-safe tools ----
    # Collect parallel-safe tool calls, run them concurrently, and store results.
    _prefetched: dict[str, str] = {}  # tc_id -> tool_result
    _parallel_batch: list[tuple[int, str, dict[str, Any]]] = (
        []
    )  # (idx_in_list, name, parsed_args)
    _parallel_tc_ids: list[str] = []

    for tc in tool_calls_list:
        name = tc["function"]["name"]
        arg_str = tc["function"].get("arguments") or "{}"
        try:
            parsed_args = json.loads(arg_str)
            if not isinstance(parsed_args, dict):
                continue
        except Exception:
            continue
        if not tools.is_parallel_safe(name, parsed_args):
            continue
        _parallel_batch.append((len(_parallel_batch), name, parsed_args))
        _parallel_tc_ids.append(tc["id"])

    if _parallel_batch:
        to_run = [(name, pargs) for _, name, pargs in _parallel_batch]
        run_indices = list(range(len(_parallel_batch)))

        if to_run:
            core.set_status(True, "tool:parallel")
            parallel_results = tools.run_tools_parallel(to_run)
            for (name, pargs, result), orig_idx in zip(parallel_results, run_indices):
                tc_id = _parallel_tc_ids[orig_idx]
                _prefetched[tc_id] = result
                if getattr(core, "show_tool_output", False):
                    print("[tool output] " + _("name=%(name)s") % {"name": name})
                    print(
                        result
                        if isinstance(result, str)
                        else json.dumps(result, ensure_ascii=False)
                    )
            # Fire PostToolBatch hook
            try:
                _fire_tool_hooks("PostToolBatch", "")
            except Exception:
                pass

            executed_new_tool = bool(to_run)
            core.set_status(True, "LLM")

    # ---- Phase 2: sequential processing (prefetched results merged in) ----
    for tc in tool_calls_list:
        func = tc["function"]
        name = func["name"]
        arg_str = func.get("arguments") or "{}"
        parsed_args = None
        tool_result = ""

        try:
            parsed_args = json.loads(arg_str)
            if not isinstance(parsed_args, dict):
                raise ValueError(
                    _(
                        "arguments must be a JSON object.",
                        default="arguments must be a JSON object.",
                    )
                )
        except Exception as e:
            tb = traceback.format_exc()
            tool_result = _(
                "[tool args error] name=%(name)r raw=%(raw)r err=%(etype)s: %(err)s\nTraceback:\n%(tb)s",
                default=f"[tool args error] name={name!r} raw={arg_str!r} err={type(e).__name__}: {e}\nTraceback:\n{tb}",
            ) % {
                "name": name,
                "raw": arg_str,
                "etype": type(e).__name__,
                "err": e,
                "tb": tb,
            }
            parsed_args = None

        if parsed_args is not None:
            # Check if this tool was already executed in the parallel phase.
            _tc_id = tc.get("id")
            _prefetched_result = _prefetched.get(_tc_id) if _tc_id else None
            if _prefetched_result is not None:
                tool_result = _prefetched_result
                fresh_tool_calls.append(tc)
            else:
                # Fire PreToolUse hook
                _fire_tool_hooks("PreToolUse", name)

                status_label = f"tool:{name}"
                if name in {"computer", "computer_use_preview"}:
                    action_items = parsed_args.get("actions")
                    if not isinstance(action_items, list):
                        action_items = [parsed_args]
                    action_names = []
                    for item in action_items:
                        if not isinstance(item, dict):
                            continue
                        action_name = str(
                            item.get("action") or item.get("type") or "action"
                        )
                        if (
                            action_name
                            in {"click", "double_click", "right_click", "move"}
                            and "x" in item
                            and "y" in item
                        ):
                            action_name += f"@{item['x']},{item['y']}"
                        elif action_name in {"type", "keypress"}:
                            if action_name == "type":
                                action_name += (
                                    f"(len={len(str(item.get('text') or ''))})"
                                )
                            else:
                                action_name += (
                                    f"({item.get('key') or item.get('keys') or ''})"
                                )
                        action_names.append(action_name)
                    if action_names:
                        status_label += ":" + ",".join(action_names[:4])
                core.set_status(True, status_label)
                try:
                    # ファイルアクセスをキャッシュ管理に記録
                    if name == "read_file" and "filename" in parsed_args:
                        cache_mgr.record_file_access(parsed_args["filename"])

                    computer_handler = getattr(core, "computer_use_handler", None)
                    if name in {"computer", "computer_use_preview"} and callable(
                        computer_handler
                    ):
                        tool_result = computer_handler(
                            tool_call=tc,
                            action=parsed_args,
                            messages=messages,
                            core=core,
                        )
                    else:
                        tool_result = tools.run_tool(name, parsed_args)

                    # Fire PostToolUse hook
                    _fire_tool_hooks("PostToolUse", name)
                except Exception as e:
                    # Fire PostToolUseFailure hook
                    _fire_tool_hooks("PostToolUseFailure", name)
                    tb = traceback.format_exc()
                    tool_result = _(
                        "[tool runtime error] name=%(name)r err=%(etype)s: %(err)s\nTraceback:\n%(tb)s",
                        default=f"[tool runtime error] name={name!r} err={type(e).__name__}: {e}\nTraceback:\n{tb}",
                    ) % {
                        "name": name,
                        "etype": type(e).__name__,
                        "err": e,
                        "tb": tb,
                    }
                except SystemExit as e:
                    # Defense in depth: tools.run_tool should already convert this.
                    _fire_tool_hooks("PostToolUseFailure", name)
                    tool_result = (
                        f"[tool runtime error] name={name!r} err=SystemExit: {e}"
                    )
                fresh_tool_calls.append(tc)
            if getattr(core, "show_tool_output", False):
                _display = truncate_history_tool_result(
                    tool_result
                    if isinstance(tool_result, str)
                    else json.dumps(tool_result, ensure_ascii=False)
                )
                print("[tool output] " + _("name=%(name)s") % {"name": name})
                print(_display)
            executed_new_tool = True

        # Ensure content is a string (OpenAI/DeepSeek requires string content for tool role)
        if not isinstance(tool_result, str):
            tool_result = json.dumps(tool_result, ensure_ascii=False)

        tool_msg: dict[str, Any] = {
            "role": "tool",
            "tool_call_id": tc["id"],
            "name": name,
            "content": tool_result,
        }

        # --- Prompt injection defense: wrap external content ---
        if _is_external_data_tool(name):
            wrapped = (
                "---BEGIN_UAGENT_EXTERNAL_CONTENT---\n"
                + tool_msg["content"]
                + "\n---END_UAGENT_EXTERNAL_CONTENT---"
            )
            tool_msg["content"] = wrapped
        try:
            parsed_tool_result = json.loads(tool_result)
        except Exception:
            parsed_tool_result = None
        if isinstance(parsed_tool_result, dict):
            # Keep binary data in attachments for the UI/remote client, but
            # never put inline Base64 into the textual tool result sent to the
            # next LLM turn. Meta rejects the resulting oversized/invalid
            # Responses request after image generation in particular.
            safe_tool_result = _strip_inline_binary_payloads(parsed_tool_result)
            if safe_tool_result != parsed_tool_result:
                safe_content = json.dumps(safe_tool_result, ensure_ascii=False)
                if _is_external_data_tool(name):
                    safe_content = (
                        "---BEGIN_UAGENT_EXTERNAL_CONTENT---\n"
                        + safe_content
                        + "\n---END_UAGENT_EXTERNAL_CONTENT---"
                    )
                tool_msg["content"] = safe_content

            # Responses API can re-capture the current Computer Use screen
            # from the bound runtime. Do not accumulate large base64 screenshots
            # in the conversation history for OpenAI/Azure continuations.
            provider_name = ""
            try:
                provider_name = str(
                    (getattr(core, "responses_state", {}) or {}).get("provider", "")
                ).lower()
            except Exception:
                pass
            if name in {"computer", "computer_use_preview"} and provider_name in {
                "openai",
                "azure",
                "azure-openai",
                "azure_foundry",
                "azure-foundry",
            }:

                def _strip_computer_images(value):
                    if isinstance(value, dict):
                        return {
                            k: _strip_computer_images(v)
                            for k, v in value.items()
                            if k not in {"screenshot_data", "screenshot_media_type"}
                        }
                    if isinstance(value, list):
                        return [_strip_computer_images(v) for v in value]
                    return value

                parsed_tool_result = _strip_computer_images(parsed_tool_result)
                tool_msg["content"] = json.dumps(parsed_tool_result, ensure_ascii=False)

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

        # Keep the full tool result out of the conversation and session
        # history when it exceeds the configured context budget. Attachments
        # and saved paths have already been extracted above.
        tool_msg["content"] = materialize_large_tool_result(
            tool_msg["content"], tool_name=name
        )

        auto_user_msg = _build_auto_user_message_from_next_action(
            parsed_tool_result=(
                parsed_tool_result if isinstance(parsed_tool_result, dict) else None
            ),
            tool_msg=tool_msg,
        )

        messages.append(tool_msg)
        core.log_message(tool_msg)

        if auto_user_msg is not None:
            pending_auto_user_msgs.append(auto_user_msg)

    for auto_user_msg in pending_auto_user_msgs:
        messages.append(auto_user_msg)
        core.log_message(auto_user_msg)

    # NOTE: Do NOT inject a synthetic user message here.
    # With Responses API previous_response_id, a user message inserted after
    # tool results breaks tool-continuation detection and the server rejects
    # the next turn with "no tool output found". Steering text belongs in the

    return executed_new_tool, fresh_tool_calls
