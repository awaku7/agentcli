"""OpenAI/Azure Responses API: request builder."""

from __future__ import annotations

import base64
import copy
import json
import os
import sys

from typing import Any, Optional

from .. import tools
from ..i18n import _
from ..llm_image_helpers import build_image_default_prompt

from .responses_common import (
    as_str,
    attachment_to_content_item,
    normalize_content_items,
)
from .responses_web_search_openai import (
    normalize_openai_builtin_tool,
    openai_web_search_tool_for_provider,
)
from ..runtime.history import truncate_history_tool_result
from .provider_caps import supports_responses_output_item_replay

# Module-level constants (reused across calls, avoids re-allocation).
_TOOL_CALLING_RULES: str = _("""[Tool calling rules]
        - When calling a tool/function, you MUST provide function_call.arguments as a JSON object.
        - The JSON object MUST include all required parameters defined by the tool schema.
        - Never call a tool with an empty object {} unless the tool has no required parameters.
        - If you do not have a required parameter, ask the user for it using human_ask instead of guessing.
        """)

_OPENROUTER_EAGER_TOOL_NAMES = frozenset(
    {"human_ask", "calculator", "fetch_url", "search_web", "python_exec"}
)
_OPENROUTER_MANAGEMENT_TOOL_NAMES = frozenset(
    {"tool_catalog", "tool_load", "unload_tool"}
)
_DEEPSEEK_TOOL_SEARCH_EAGER_NAMES = _OPENROUTER_EAGER_TOOL_NAMES | frozenset(
    {"computer"}
)

_WEB_SEARCH_RULES: str = _("""[Web search rules]
        - Use web search only when fresh or external information is necessary.
        - Do not use web search for local or stable information.
        - Prefer answering without web search when the answer is already sufficient.
        """)

# ---------------------------------------------------------------------------
# Request builder
# ---------------------------------------------------------------------------


def _responses_tool_output(
    call_id: str,
    content: Any,
    tool_name: str,
    core: Any = None,
    provider: str = "openai",
) -> dict[str, Any]:
    """Convert a normalized tool result to a Responses input item."""
    # A local runtime exposes ``computer`` as a normal function tool. Native
    # Responses computer calls are identified by the native tool metadata,
    # not by whether a local runtime has already been created.
    native_active = bool(getattr(core, "computer_use_native_active", False))
    try:
        payload = json.loads(content) if isinstance(content, str) else content
    except Exception:
        payload = {}
    candidates = payload.get("results", []) if isinstance(payload, dict) else []
    if not candidates and isinstance(payload, dict):
        candidates = [payload]
    has_screenshot = any(
        isinstance(item, dict) and item.get("screenshot_data") for item in candidates
    )
    provider_name = (provider or "").strip().lower()
    native_provider = (
        str(getattr(core, "computer_use_native_provider", "") or "").strip().lower()
    )
    if provider_name == "meta":
        is_native_computer = (
            native_active and native_provider == "meta" and tool_name == "computer"
        )
    else:
        is_native_computer = (
            tool_name in {"computer", "computer_use_preview"} and native_active
        ) or (not tool_name and native_active)
    if not is_native_computer:
        return {
            "type": "function_call_output",
            "call_id": call_id,
            "output": as_str(content),
        }
    screenshot = next(
        (
            item
            for item in reversed(candidates)
            if isinstance(item, dict) and item.get("screenshot_data")
        ),
        None,
    )
    output = {"type": "computer_screenshot"}
    if provider_name != "meta":
        output["detail"] = "original"
    if screenshot:
        output["image_url"] = (
            f"data:{screenshot.get('screenshot_media_type', 'image/png')};base64,"
            + str(screenshot["screenshot_data"])
        )
    elif core is not None:
        # Keep the Responses payload valid even when a legacy handler omitted
        # screenshot_data from its serialized result.
        try:
            runtime = getattr(core, "computer_use_runtime", None)
            shot = runtime.screenshot() if runtime is not None else None
            if shot is not None:
                output["image_url"] = (
                    f"data:{shot.media_type};base64,"
                    + base64.b64encode(shot.data).decode("ascii")
                )
        except Exception:
            pass
    if not output.get("image_url"):
        raise RuntimeError(
            f"{provider_name.title() or 'OpenAI'} Computer Use requires a screenshot, "
            "but none could be captured"
        )
    if provider_name == "meta":
        try:
            image_header, encoded_image = str(output["image_url"]).split(",", 1)
            media_type = image_header.removeprefix("data:").removesuffix(";base64")
            image_bytes = base64.b64decode(encoded_image, validate=True)
        except Exception as exc:
            raise RuntimeError(
                "Meta Computer Use screenshot data URL is invalid"
            ) from exc
        if media_type not in {"image/png", "image/jpeg"}:
            raise RuntimeError(
                f"Meta Computer Use does not support screenshot media type: {media_type}"
            )
        if not image_bytes or len(image_bytes) > 25 * 1024 * 1024:
            raise RuntimeError(
                "Meta Computer Use screenshot is empty or exceeds 25 MiB"
            )
    if (os.environ.get("UAGENT_DEBUG_COMPUTER") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        image_url = output.get("image_url")
        print(
            "[computer-debug] "
            f"tool_name={tool_name!r} native={is_native_computer} "
            f"native_active={native_active} has_screenshot={has_screenshot} "
            f"screenshot_data_len={sum(len(str(item.get('screenshot_data') or '')) for item in candidates if isinstance(item, dict))} "
            f"output_keys={sorted(output.keys())} "
            f"image_url_present={bool(image_url)} "
            f"image_url_len={len(str(image_url or ''))}",
            file=sys.stderr,
            flush=True,
        )
    if provider_name == "meta":
        from ..computer_use.adapters.meta import MetaComputerAdapter

        if not isinstance(payload, dict):
            payload = {}
        return MetaComputerAdapter().build_tool_result(
            call_id=call_id,
            image_url=str(output["image_url"]),
            acknowledged_safety_checks=payload.get("acknowledged_safety_checks", []),
            meta_safety_replay_receipt=payload.get("meta_safety_replay_receipt"),
        )
    return {"type": "computer_call_output", "call_id": call_id, "output": output}


def _deepseek_tool_search_result_tools(
    query: str,
    tool_specs: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> list[dict[str, Any]]:
    """Resolve a client-side DeepSeek search query to flat Responses tools."""
    query = (query or "").strip()
    if not query:
        return []
    raw_specs = list(tool_specs) if tool_specs is not None else tools.get_tool_specs()
    try:
        matches = tools.get_tool_catalog(
            query=query,
            max_results=12,
            tool_specs=raw_specs,
        )
    except Exception:
        matches = []
    names = {
        str(item.get("name") or "").strip()
        for item in matches or []
        if isinstance(item, dict)
    }
    names.discard("")
    names.difference_update(_OPENROUTER_MANAGEMENT_TOOL_NAMES)
    names.difference_update(_DEEPSEEK_TOOL_SEARCH_EAGER_NAMES)
    selected = []
    for spec in raw_specs:
        if not isinstance(spec, dict):
            continue
        function = spec.get("function")
        if not isinstance(function, dict):
            continue
        name = str(function.get("name") or "").strip()
        if name in names:
            selected.append(
                {
                    "type": "function",
                    "name": name,
                    "description": function.get("description") or "",
                    "parameters": function.get("parameters")
                    or {"type": "object", "properties": {}},
                }
            )
    return selected


def build_responses_request(
    call_messages: list[dict[str, Any]],
    *,
    send_tools_this_round: bool,
    provider: str = "openai",
    tool_specs: Optional[list[dict[str, Any]]] = None,
    previous_response_id: Optional[str] = None,
    core: Any = None,
    model_name: str = "",
    openrouter_tool_search_variant: str | None = None,
    deepseek_tool_search_enabled: bool | None = None,
) -> tuple[Optional[str], list[dict[str, Any]], Optional[list[dict[str, Any]]]]:
    """Build payload for OpenAI/Azure Responses API.

    Returns:
      (instructions_str_or_none, input_msgs, tools_or_none)
    """
    provider_name = (provider or "").strip().lower()
    if provider_name == "openrouter" and model_name:
        if openrouter_tool_search_variant is None:
            from ..runtime.tool_discovery import (
                openrouter_responses_tool_search_variant as _openrouter_search_variant,
            )

            openrouter_tool_search_variant = _openrouter_search_variant(
                provider_name, model_name
            )
    native_openrouter_search = bool(
        provider_name == "openrouter"
        and send_tools_this_round
        and openrouter_tool_search_variant == "regex"
    )
    if (
        provider_name == "deepseek"
        and model_name
        and deepseek_tool_search_enabled is None
    ):
        from ..runtime.tool_discovery import (
            deepseek_responses_tool_search_enabled,
        )

        deepseek_tool_search_enabled = deepseek_responses_tool_search_enabled(
            provider_name, model_name
        )
    native_deepseek_search = bool(
        provider_name == "deepseek"
        and send_tools_this_round
        and deepseek_tool_search_enabled
    )

    # OpenRouter Responses is stateless. Native tool search also signs the
    # deferred-tool state into the returned output items, so full-history
    # replay must retain each assistant output and matching function result.
    if native_openrouter_search:
        if previous_response_id is not None:
            previous_response_id = None
        expected_call_ids: set[str] = set()
        raw_call_ids: set[str] = set()
        result_call_ids: set[str] = set()
        for message in call_messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") == "assistant" and message.get("tool_calls"):
                tool_calls = message.get("tool_calls")
                if not isinstance(tool_calls, list):
                    native_openrouter_search = False
                    break
                output_items = message.get("_responses_output_items")
                if (
                    not isinstance(output_items, list)
                    or not output_items
                    or any(not isinstance(item, dict) for item in output_items)
                ):
                    native_openrouter_search = False
                    break
                for tool_call in tool_calls:
                    call_id = (
                        tool_call.get("id") or tool_call.get("call_id")
                        if isinstance(tool_call, dict)
                        else None
                    )
                    if not isinstance(call_id, str) or not call_id:
                        native_openrouter_search = False
                        break
                    expected_call_ids.add(call_id)
                raw_call_ids.update(
                    str(item.get("call_id") or item.get("id"))
                    for item in output_items
                    if item.get("type") == "function_call"
                    and isinstance(item.get("call_id") or item.get("id"), str)
                    and (item.get("call_id") or item.get("id"))
                )
                if not native_openrouter_search:
                    break
            elif message.get("role") == "tool":
                call_id = message.get("tool_call_id") or message.get("id")
                if not isinstance(call_id, str) or not call_id:
                    native_openrouter_search = False
                    break
                result_call_ids.add(call_id)
        if native_openrouter_search and (
            expected_call_ids != raw_call_ids or expected_call_ids != result_call_ids
        ):
            native_openrouter_search = False

    deepseek_search_calls: dict[str, dict[str, Any]] = {}
    if native_deepseek_search:
        # DeepSeek's client-side search is stateless: every subsequent request
        # must replay the call and its matching tool_search_output item.
        previous_response_id = None
        search_result_ids: set[str] = set()
        for message in call_messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") == "assistant":
                output_items = message.get("_responses_output_items")
                for item in output_items if isinstance(output_items, list) else ():
                    if (
                        not isinstance(item, dict)
                        or item.get("type") != "tool_search_call"
                    ):
                        continue
                    call_id = item.get("call_id")
                    if (
                        item.get("execution") != "client"
                        or not isinstance(call_id, str)
                        or not call_id
                        or not isinstance(item.get("arguments"), (dict, str))
                    ):
                        native_deepseek_search = False
                        break
                    deepseek_search_calls[call_id] = item
            elif message.get("role") == "tool":
                call_id = message.get("tool_call_id") or message.get("id")
                if isinstance(call_id, str) and call_id in deepseek_search_calls:
                    search_result_ids.add(call_id)
            if not native_deepseek_search:
                break
        if native_deepseek_search and set(deepseek_search_calls) != search_result_ids:
            native_deepseek_search = False
        if not native_deepseek_search:
            deepseek_search_calls.clear()

    if core is not None and (native_openrouter_search or native_deepseek_search):
        # Deferred-tool protocols bind their continuation state to the full
        # history. The round preparer must not compact/reorder that history
        # after this request has begun.
        try:
            core._responses_tool_search_history_provider = provider_name
        except (AttributeError, TypeError):
            pass

    instructions_list: list[str] = []
    input_msgs: list[dict[str, Any]] = []
    _latest_user: Optional[dict[str, Any]] = None
    _latest_user_index: int = -1
    _last_tool_call_assistant_index: int = -1
    _pending_call_ids: set[str] = set()

    # Pre-scan for tool-continuation detection
    for _idx, _msg in enumerate(call_messages):
        if not isinstance(_msg, dict):
            continue
        _role = _msg.get("role")
        if _role == "user":
            _latest_user_index = _idx
        elif _role == "assistant":
            _tcs = _msg.get("tool_calls")
            if isinstance(_tcs, list) and _tcs:
                _last_tool_call_assistant_index = _idx
                _pending_call_ids.clear()
                for _tc in _tcs:
                    if not isinstance(_tc, dict):
                        continue
                    _tcid = _tc.get("id") or _tc.get("call_id")
                    if isinstance(_tcid, str) and _tcid:
                        _pending_call_ids.add(_tcid)

    _tool_continuation = (
        _last_tool_call_assistant_index >= 0
        and _latest_user_index < _last_tool_call_assistant_index
    )

    instructions_list.append(_TOOL_CALLING_RULES)
    instructions_list.append(_WEB_SEARCH_RULES)

    for _idx, m in enumerate(call_messages):
        role = m.get("role")

        # -- previous_response_id mode --
        if previous_response_id is not None:
            if role == "system":
                instructions_list.append(as_str(m.get("content", "")))
            elif role == "tool":
                if _tool_continuation and _idx > _last_tool_call_assistant_index:
                    tm = dict(m)
                    for _k in ("attachments", "saved_path", "saved_files"):
                        tm.pop(_k, None)
                    call_id = tm.pop("tool_call_id", None) or tm.get("id", "")
                    if isinstance(call_id, str) and call_id in _pending_call_ids:
                        output = as_str(tm.get("content", ""))
                        input_msgs.append(
                            _responses_tool_output(
                                call_id, output, tm.get("name", ""), core, provider
                            )
                        )
            elif role == "user":
                if not _tool_continuation:
                    _latest_user = dict(m)
                    _latest_user_index = _idx
                    for _k in ("attachments", "saved_path", "saved_files"):
                        if _k in _latest_user:
                            try:
                                del _latest_user[_k]
                            except Exception:
                                pass
            continue

        # -- Full history mode --
        if role == "system":
            instructions_list.append(as_str(m.get("content", "")))
            continue

        m_clean: dict[str, Any] = dict(m)

        # ``response_id`` is local conversation metadata, not a valid field
        # on a Responses API input item. It is attached to persisted
        # assistant messages for UI/state display, but Azure/OpenAI rejects
        # it when forwarded as input[n].response_id.
        m_clean.pop("response_id", None)

        # ``reasoning_content`` is a Chat Completions extension used by some
        # reasoning providers (for example DeepSeek).  It is retained in
        # local history, but is not a valid field on a Responses API input
        # item; Azure OpenAI rejects it as an unknown parameter.  Responses
        # reasoning is represented by typed output items instead.
        m_clean.pop("reasoning_content", None)

        # Gemini/Vertex history stores a serialized native Content object for
        # replay by those providers. It is local metadata, not a Responses API
        # input field (OpenAI rejects unknown parameters).
        m_clean.pop("_gemini_content", None)

        attachment_items: list[dict[str, Any]] = []
        if role == "user":
            raw_attachments = m_clean.get("attachments")
            if isinstance(raw_attachments, list):
                for att in raw_attachments:
                    item = attachment_to_content_item(att)
                    if item is not None:
                        attachment_items.append(item)
            elif isinstance(raw_attachments, dict):
                item = attachment_to_content_item(raw_attachments)
                if item is not None:
                    attachment_items.append(item)

            saved_path = m_clean.get("saved_path")
            if isinstance(saved_path, str) and saved_path.strip():
                item = attachment_to_content_item(
                    {"type": "image", "saved_path": saved_path.strip()}
                )
                if item is not None:
                    attachment_items.append(item)

            saved_files = m_clean.get("saved_files")
            if isinstance(saved_files, list):
                for sf in saved_files:
                    if isinstance(sf, str) and sf.strip():
                        item = attachment_to_content_item(
                            {"type": "image", "saved_path": sf.strip()}
                        )
                        if item is not None:
                            attachment_items.append(item)
                    elif isinstance(sf, dict):
                        item = attachment_to_content_item(sf)
                        if item is not None:
                            attachment_items.append(item)

            content_text = as_str(m_clean.get("content", ""))
            if attachment_items and not content_text.strip():
                attachment_items.insert(
                    0,
                    {
                        "type": "input_text",
                        "text": build_image_default_prompt("describe"),
                    },
                )

        for _k in ("attachments", "saved_path", "saved_files"):
            if _k in m_clean:
                try:
                    del m_clean[_k]
                except Exception:
                    pass

        if role == "assistant" and native_deepseek_search:
            raw_items = m_clean.get("_responses_output_items")
            if isinstance(raw_items, list) and any(
                isinstance(item, dict) and item.get("type") == "tool_search_call"
                for item in raw_items
            ):
                for item in raw_items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "tool_search_call":
                        call_id = item.get("call_id")
                        if not isinstance(call_id, str) or not call_id:
                            continue
                        arguments = item.get("arguments")
                        if isinstance(arguments, str):
                            try:
                                arguments = json.loads(arguments)
                            except (TypeError, ValueError):
                                arguments = {}
                        input_msgs.append(
                            {
                                "type": "tool_search_call",
                                "call_id": call_id,
                                "execution": "client",
                                "arguments": (
                                    arguments if isinstance(arguments, dict) else {}
                                ),
                            }
                        )
                    else:
                        input_msgs.append(copy.deepcopy(item))
                continue

        if role == "assistant" and native_deepseek_search:
            raw_items = m_clean.get("_responses_output_items")
            if (
                isinstance(raw_items, list)
                and raw_items
                and all(isinstance(item, dict) for item in raw_items)
            ):
                # DeepSeek thinking responses require reasoning state to be
                # replayed along with ordinary function_call items.
                input_msgs.extend(copy.deepcopy(raw_items))
                continue

        if role == "assistant" and m_clean.get("tool_calls"):
            from .llm_deepseek_responses import assistant_tool_turn_items

            _deepseek_items = assistant_tool_turn_items(m, provider=provider)
            if _deepseek_items is not None:
                m_clean.pop("tool_calls", None)
                m_clean["content"] = normalize_content_items(
                    m_clean.get("content"), role="assistant"
                )
                # Full-history Responses input messages are intentionally
                # rebuilt from API-supported fields only; session metadata
                # (for example actor_id or provider-specific keys) must stay local.
                input_msgs.append({"role": "assistant", "content": m_clean["content"]})
                input_msgs.extend(_deepseek_items)
                continue

        _responses_items = m_clean.pop("_responses_output_items", None)
        if (
            native_openrouter_search
            and isinstance(_responses_items, list)
            and _responses_items
        ):
            input_msgs.extend(copy.deepcopy(_responses_items))
            continue
        # Meta does not accept prior Responses output objects as input items.
        # Rebuild its fallback from the normalized assistant/tool text below.
        if (
            isinstance(_responses_items, list)
            and _responses_items
            and supports_responses_output_item_replay(provider)
        ):
            # Full-history fallback must not replay bare function_call items:
            # without matching function_call_output the Responses API rejects
            # the request ("no tool output found"). Keep only non-tool items
            # (message/reasoning/etc.) and fall through to the text summary
            # path for tool calls.
            _safe_items: list[dict[str, Any]] = []
            _has_function_call = False
            for _item in _responses_items:
                if not isinstance(_item, dict) or not _item.get("type"):
                    continue
                _itype = str(_item.get("type") or "")
                if _itype in (
                    "function_call",
                    "function_call_output",
                    "custom_tool_call",
                    "custom_tool_call_output",
                ):
                    _has_function_call = True
                    continue
                _safe_items.append(dict(_item))
            if _safe_items and not _has_function_call:
                input_msgs.extend(_safe_items)
                continue
            if _safe_items:
                input_msgs.extend(_safe_items)
            # If there were function_call items, continue into tool_calls /
            # content conversion below instead of replaying them raw.
            if _has_function_call:
                pass
            else:
                continue

        if "tool_calls" in m_clean:
            tc_info: list[str] = []
            tcs = m_clean.get("tool_calls")
            if isinstance(tcs, list):
                for tc in tcs:
                    if isinstance(tc, dict):
                        fn = (
                            (tc.get("function") or {})
                            if isinstance(tc.get("function"), dict)
                            else {}
                        )
                        name = fn.get("name", "unknown")
                        args = fn.get("arguments", "{}")
                        tc_info.append(f"{name}({args})")
            try:
                del m_clean["tool_calls"]
            except Exception:
                pass
            if tc_info:
                instructions_list.append(
                    "[System: The assistant previously executed tools: "
                    + ", ".join(tc_info)
                    + "]"
                )

        if role == "tool":
            tool_name = m_clean.pop("name", "unknown")
            deepseek_search_call_id = m.get("tool_call_id") or m.get("id")
            if (
                native_deepseek_search
                and isinstance(deepseek_search_call_id, str)
                and deepseek_search_call_id in deepseek_search_calls
            ):
                search_item = deepseek_search_calls[deepseek_search_call_id]
                search_arguments = search_item.get("arguments")
                if isinstance(search_arguments, str):
                    try:
                        search_arguments = json.loads(search_arguments)
                    except (TypeError, ValueError):
                        search_arguments = {}
                query = (
                    str(search_arguments.get("query") or "").strip()
                    if isinstance(search_arguments, dict)
                    else ""
                )
                raw_specs = tools.get_tool_specs() if tool_specs is None else tool_specs
                input_msgs.append(
                    {
                        "type": "tool_search_output",
                        "call_id": deepseek_search_call_id,
                        "execution": "client",
                        "tools": _deepseek_tool_search_result_tools(query, raw_specs),
                    }
                )
                continue
            if native_openrouter_search:
                call_id = m.get("tool_call_id") or m.get("id")
                output = truncate_history_tool_result(m_clean.get("content", ""))
                input_msgs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": as_str(output),
                    }
                )
                continue
            if "tool_call_id" in m_clean:
                try:
                    del m_clean["tool_call_id"]
                except Exception:
                    pass
            from .llm_deepseek_responses import tool_turn_item

            _tool_message_for_responses = dict(m)
            _tool_message_for_responses["content"] = truncate_history_tool_result(
                m.get("content", "")
            )
            _deepseek_handled, _deepseek_output = tool_turn_item(
                _tool_message_for_responses, provider=provider
            )
            if _deepseek_handled:
                if _deepseek_output is not None:
                    input_msgs.append(_deepseek_output)
                continue
            original_content = truncate_history_tool_result(m_clean.get("content", ""))
            prefix = f"[System: Tool '{tool_name}' returned result]\n"
            merged = prefix + as_str(original_content).lstrip("\r\n")
            m_clean["role"] = "user"
            m_clean["content"] = normalize_content_items(merged, role="user")
            input_msgs.append(
                {
                    "role": "user",
                    "content": normalize_content_items(merged, role="user"),
                }
            )
            continue

        if role not in ("user", "assistant"):
            role = "user"
            m_clean["role"] = "user"

        normalized_content = normalize_content_items(m_clean.get("content"), role=role)
        if role == "user" and attachment_items:
            normalized_content.extend(attachment_items)
        m_clean["content"] = normalized_content

        if "tool_call_id" in m_clean:
            try:
                del m_clean["tool_call_id"]
            except Exception:
                pass
        if "name" in m_clean and m_clean.get("role") != "tool":
            try:
                del m_clean["name"]
            except Exception:
                pass

        # Only role/content belong on a standard Responses input message.
        # Never forward local session fields or provider-specific metadata.
        input_msgs.append({"role": role, "content": normalized_content})

    if previous_response_id is not None and _latest_user is not None:
        _latest_user["content"] = normalize_content_items(
            _latest_user.get("content"), role="user"
        )
        for _k in ("attachments", "saved_path", "saved_files"):
            _latest_user.pop(_k, None)
        # The continuation request also accepts only the canonical user item;
        # discard any metadata copied from restored session history.
        input_msgs.append({"role": "user", "content": _latest_user["content"]})

    instructions_str: Optional[str] = None
    if instructions_list:
        tmp = "\n".join([s for s in instructions_list if s is not None])
        if tmp.strip() != "":
            instructions_str = tmp

    req_tools: Optional[list[dict[str, Any]]] = None
    if send_tools_this_round:
        raw_specs = tools.get_tool_specs() if tool_specs is None else tool_specs
        from ..runtime.execution_broker import (
            computer_use_allowed,
            is_computer_use_tool_spec,
        )

        _computer_use_allowed = computer_use_allowed()
        if not _computer_use_allowed:
            raw_specs = [
                spec for spec in raw_specs or [] if not is_computer_use_tool_spec(spec)
            ]
        flat_tools: list[dict[str, Any]] = []

        env_web_search_tool = openai_web_search_tool_for_provider(provider)
        if env_web_search_tool is not None:
            flat_tools.append(env_web_search_tool)

        _excluded_local: set[str] = set()
        if env_web_search_tool is not None:
            _excluded_local.add("search_web")

        for t in raw_specs or []:
            if not isinstance(t, dict):
                continue
            builtin_tool = normalize_openai_builtin_tool(t)
            if builtin_tool is not None:
                flat_tools.append(builtin_tool)
                continue
            fn = t.get("function") or {}
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not name:
                continue
            if native_openrouter_search and name in _OPENROUTER_MANAGEMENT_TOOL_NAMES:
                continue
            if name in _excluded_local:
                continue
            flat_tools.append(
                {
                    "type": "function",
                    "name": name,
                    "description": fn.get("description") or "",
                    "parameters": fn.get("parameters")
                    or {"type": "object", "properties": {}},
                }
            )
        native_tool = (
            getattr(core, "computer_use_native_tool", None)
            if core is not None and _computer_use_allowed
            else None
        )
        native_provider = (
            str(getattr(core, "computer_use_native_provider", "") or "").strip().lower()
        )
        meta_native_candidate = (
            provider == "meta"
            and native_provider == "meta"
            and isinstance(native_tool, dict)
            and native_tool.get("type") == "computer"
        )
        meta_native_added = False
        native_active = bool(
            _computer_use_allowed and getattr(core, "computer_use_native_active", False)
            if core is not None
            else False
        )
        if (
            core is not None
            and _computer_use_allowed
            and getattr(core, "computer_use_runtime", None) is not None
            and not native_active
            and not meta_native_candidate
        ):
            from ..computer_use.native import local_computer_tool_spec

            if not any(
                item.get("name") == "computer"
                for item in flat_tools
                if isinstance(item, dict)
            ):
                local = local_computer_tool_spec()["function"]
                flat_tools.append({"type": "function", **local})
        if (
            (
                getattr(core, "computer_use_runtime", None) is None
                or native_active
                or meta_native_candidate
            )
            and provider
            in {
                "openai",
                "azure",
                "azure-openai",
                "azure_foundry",
                "azure-foundry",
                "meta",
            }
            and isinstance(native_tool, dict)
            and native_tool.get("type") in {"computer", "computer_use_preview"}
            and (provider != "meta" or meta_native_candidate)
        ):
            flat_tools.append(dict(native_tool))
            try:
                core.computer_use_native_active = True
            except Exception:
                pass
            meta_native_added = provider == "meta"
        if native_openrouter_search:
            deferred_any = False
            for item in flat_tools:
                if item.get("type") != "function":
                    continue
                name = str(item.get("name") or "")
                if name in _OPENROUTER_EAGER_TOOL_NAMES:
                    continue
                item["defer_loading"] = True
                deferred_any = True
            if deferred_any:
                flat_tools.insert(0, {"type": "openrouter:tool_search"})
            else:
                native_openrouter_search = False
        if native_deepseek_search:
            eager_tools = [
                item
                for item in flat_tools
                if item.get("type") == "function"
                and str(item.get("name") or "") in _DEEPSEEK_TOOL_SEARCH_EAGER_NAMES
            ]
            flat_tools = [
                {
                    "type": "tool_search",
                    "execution": "client",
                    "description": "Search for tools that can help with the user's request.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
                *eager_tools,
            ]
        req_tools = flat_tools

        if meta_native_added and previous_response_id is None:
            if any(
                isinstance(message, dict)
                and (
                    (
                        message.get("role") == "tool"
                        and message.get("name") == "computer"
                    )
                    or (
                        message.get("role") == "assistant"
                        and any(
                            isinstance(call, dict)
                            and isinstance(call.get("function"), dict)
                            and call["function"].get("name") == "computer"
                            for call in (message.get("tool_calls") or [])
                        )
                    )
                )
                for message in call_messages
            ):
                raise RuntimeError(
                    "Meta native Computer Use continuation requires previous_response_id; "
                    "stateless replay is disabled"
                )
            initial_screen_attached = False
            for user_item in reversed(input_msgs):
                if not isinstance(user_item, dict) or user_item.get("role") != "user":
                    continue
                content_items = user_item.get("content")
                if not isinstance(content_items, list):
                    content_items = normalize_content_items(content_items, role="user")
                    user_item["content"] = content_items
                has_user_image = any(
                    isinstance(item, dict)
                    and item.get("type") in {"input_image", "image_url"}
                    for item in content_items
                )
                if has_user_image:
                    initial_screen_attached = True
                else:
                    runtime = getattr(core, "computer_use_runtime", None)
                    try:
                        screenshot = (
                            runtime.screenshot() if runtime is not None else None
                        )
                    except Exception as exc:
                        raise RuntimeError(
                            "Meta Computer Use could not capture its initial screenshot"
                        ) from exc
                    if screenshot is None:
                        raise RuntimeError(
                            "Meta Computer Use requires an initial screenshot and a local Runtime"
                        )
                    image_bytes = bytes(screenshot.data)
                    if not image_bytes or len(image_bytes) > 25 * 1024 * 1024:
                        raise RuntimeError(
                            "Meta Computer Use initial screenshot is empty or exceeds 25 MiB"
                        )
                    media_type = str(screenshot.media_type or "")
                    if media_type not in {"image/png", "image/jpeg"}:
                        raise RuntimeError(
                            f"Meta Computer Use does not support screenshot media type: {media_type}"
                        )
                    image_url = f"data:{media_type};base64," + base64.b64encode(
                        image_bytes
                    ).decode("ascii")
                    content_items.append(
                        {"type": "input_image", "image_url": image_url}
                    )
                    initial_screen_attached = True
                break
            if not initial_screen_attached:
                raise RuntimeError(
                    "Meta Computer Use requires a user turn and initial screenshot"
                )

    return instructions_str, input_msgs, req_tools
