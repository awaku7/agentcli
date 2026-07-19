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


@lru_cache(maxsize=None)
def _is_external_data_tool(name: str) -> bool:
    """Check if a tool fetches external/third-party content.

    Results from these tools are wrapped with isolation markers to prevent
    embedded instructions from being interpreted as commands.
    """
    return name in tools.get_external_data_tools()



def _tool_cache_key(name: str, args: dict[str, Any]) -> str:
    canonical_args = json.dumps(args, ensure_ascii=False, sort_keys=True)
    return json.dumps(
        {"name": name, "args": canonical_args},
        ensure_ascii=False,
        sort_keys=True,
    )


def _already_called_tool_result(cached: str) -> str:
    """Prefix a cached tool result when the same call is repeated."""
    return (
        _(
            "[INFO] Already called this tool with the same arguments earlier. "
            "Reusing the previous result. Do NOT call this tool again with the "
            "same arguments. If more work is needed, call a different tool or "
            "answer with what you already have.\n",
            default=(
                "[INFO] Already called this tool with the same arguments earlier. "
                "Reusing the previous result. Do NOT call this tool again with the "
                "same arguments. If more work is needed, call a different tool or "
                "answer with what you already have.\n"
            ),
        )
        + cached
    )


# Tools that may legitimately be re-run with identical args in one session.
_REPEATABLE_TOOL_NAMES = frozenset(
    {
        "bash_exec",
        "pwsh_exec",
        "cmd_exec",
        "cmd_exec_json",
        "python_exec",
        "run_tests",
        "spawn_process",
        "human_ask",
        "finish_skill",
        "tool_catalog",
        "tool_load",
        "unload_tool",
    }
)


def _should_reuse_identical_tool_call(name: str) -> bool:
    return name not in _REPEATABLE_TOOL_NAMES


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
        tool_attachments = tool_msg.get("attachments")
        if isinstance(tool_attachments, list) and tool_attachments:
            auto_user_msg["attachments"] = tool_attachments

    return auto_user_msg


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
            "[WARN] LLM returned an empty assistant message without tool calls.\nprovider=%(provider)s depname=%(depname)s empty_no_tool_rounds=%(empty_no_tool_rounds)s (max=%(empty_no_tool_max)s)\nThis may happen with OpenAI-compatible local providers after tool calls. You can try setting UAGENT_EMPTY_NO_TOOL_MAX to a higher value, or switching provider.",
            default="[WARN] LLM returned an empty assistant message without tool calls.\nprovider=%(provider)s depname=%(depname)s empty_no_tool_rounds=%(empty_no_tool_rounds)s (max=%(empty_no_tool_max)s)\nThis may happen with OpenAI-compatible local providers after tool calls. You can try setting UAGENT_EMPTY_NO_TOOL_MAX to a higher value, or switching provider.",
        ) % {
            "provider": provider,
            "depname": depname,
            "empty_no_tool_rounds": empty_no_tool_rounds,
            "empty_no_tool_max": empty_no_tool_max,
        }
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
    tool_result_cache: dict[str, str],
    use_tool_result_cache: bool,
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
        if not tools.is_parallel_safe(name):
            continue
        arg_str = tc["function"].get("arguments") or "{}"
        try:
            parsed_args = json.loads(arg_str)
            if not isinstance(parsed_args, dict):
                continue
        except Exception:
            continue
        _parallel_batch.append((len(_parallel_batch), name, parsed_args))
        _parallel_tc_ids.append(tc["id"])

    # tc ids whose parallel result came from a fresh execution (not cache reuse)
    _fresh_prefetch_ids: set[str] = set()

    if _parallel_batch:
        # Identical args always short-circuit with the previous result.
        to_run: list[tuple[str, dict[str, Any]]] = []
        run_indices: list[int] = []
        for idx, name, pargs in _parallel_batch:
            ck = _tool_cache_key(name, pargs)
            cached = tool_result_cache.get(ck)
            if cached is not None and _should_reuse_identical_tool_call(name):
                _prefetched[_parallel_tc_ids[idx]] = _already_called_tool_result(
                    cached
                )
            else:
                to_run.append((name, pargs))
                run_indices.append(idx)

        if to_run:
            core.set_status(True, "tool:parallel")
            parallel_results = tools.run_tools_parallel(to_run)
            for (name, pargs, result), orig_idx in zip(parallel_results, run_indices):
                tc_id = _parallel_tc_ids[orig_idx]
                _prefetched[tc_id] = result
                _fresh_prefetch_ids.add(tc_id)
                if getattr(core, "show_tool_output", False):
                    print("[tool output] " + _("name=%(name)s") % {"name": name})
                    print(
                        result
                        if isinstance(result, str)
                        else json.dumps(result, ensure_ascii=False)
                    )
                # Store raw result; reuse path adds the "already called" prefix.
                ck = _tool_cache_key(name, pargs)
                tool_result_cache[ck] = (
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
        tool_cache_key = None
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
            tool_cache_key = f"error:{name}:{arg_str}"
            parsed_args = None

        if parsed_args is not None:
            tool_cache_key = _tool_cache_key(name, parsed_args)

            # Identical tool+args: do not re-execute; tell the model it was
            # already called and return the previous result.
            cached = tool_result_cache.get(tool_cache_key)
            if cached is not None and _should_reuse_identical_tool_call(name):
                tool_result = _already_called_tool_result(cached)
            else:
                # Check if this tool was already executed in the parallel phase
                _tc_id = tc.get("id")
                _prefetched_result = _prefetched.get(_tc_id) if _tc_id else None
                if _prefetched_result is not None:
                    tool_result = _prefetched_result
                    # Parallel phase already cached the raw result when it ran.
                    if _tc_id in _fresh_prefetch_ids:
                        fresh_tool_calls.append(tc)
                else:
                    # Fire PreToolUse hook
                    _fire_tool_hooks("PreToolUse", name)

                    core.set_status(True, f"tool:{name}")
                    try:
                        # ファイルアクセスをキャッシュ管理に記録
                        if name == "read_file" and "filename" in parsed_args:
                            cache_mgr.record_file_access(parsed_args["filename"])

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
                    # Cache raw first/latest executed result only.
                    tool_result_cache[tool_cache_key] = (
                        tool_result
                        if isinstance(tool_result, str)
                        else json.dumps(tool_result, ensure_ascii=False)
                    )
                    fresh_tool_calls.append(tc)
                if getattr(core, "show_tool_output", False):
                    _display = (
                        tool_result
                        if isinstance(tool_result, str)
                        else json.dumps(tool_result, ensure_ascii=False)
                    )
                    print("[tool output] " + _("name=%(name)s") % {"name": name})
                    print(_display)
                executed_new_tool = True

        elif tool_cache_key:
            tool_result_cache[tool_cache_key] = tool_result

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
    # tool result prefix (_already_called_tool_result) only.

    return executed_new_tool, fresh_tool_calls
