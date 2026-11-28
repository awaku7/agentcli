from __future__ import annotations

import copy
import json
import re
from typing import Any, Optional

from ..env_utils import env_get
from ..i18n import _
from .. import tools
from ..reasoning_display import show_reasoning

_ANTHROPIC_EAGER_TOOL_NAMES = (
    "human_ask",
    "calculator",
    "fetch_url",
    "search_web",
    "python_exec",
)


def _anthropic_block_to_dict(block: Any) -> dict[str, Any] | None:
    """Convert an Anthropic SDK content block to its API-shaped mapping."""
    if isinstance(block, dict):
        return copy.deepcopy(block)
    dump = getattr(block, "model_dump", None)
    if callable(dump):
        try:
            value = dump(mode="json", exclude_none=True)
        except TypeError:
            try:
                value = dump(exclude_none=True)
            except Exception:
                value = None
        except Exception:
            value = None
        if isinstance(value, dict):
            return value
    to_dict = getattr(block, "to_dict", None)
    if callable(to_dict):
        try:
            value = to_dict()
            if isinstance(value, dict):
                return value
        except Exception:
            pass
    try:
        value = vars(block)
    except Exception:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        return None
    return {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if not key.startswith("_") and item is not None
    }


def _parse_claude_model(
    model_name: str,
) -> tuple[Optional[str], Optional[int], Optional[int]]:
    """Best-effort parse Claude model name.

    Examples:
      - claude-opus-4-6   -> ("opus", 4, 6)
      - claude-opus-4.6   -> ("opus", 4, 6)
      - claude-sonnet-4-6 -> ("sonnet", 4, 6)
      - claude-3-7-sonnet -> ("sonnet", 3, 7)
      - claude-fable-5    -> ("fable", 5, 0)

    Returns: (family, major, minor) where family is one of {"opus","sonnet","fable"}, or None.
    """

    s = (model_name or "").strip().lower()

    # 1. claude-fable-5 or similar (family-major-minor or family-major)
    m_fable = re.search(r"claude-(fable|opus|sonnet|haiku)-(\d+)(?:[\.-](\d+))?", s)
    if m_fable:
        fam = m_fable.group(1)
        try:
            major = int(m_fable.group(2))
            minor = int(m_fable.group(3)) if m_fable.group(3) else 0
            return fam, major, minor
        except Exception:
            pass

    # 2. claude-3-7-sonnet or similar (major-minor-family)
    m_num_first = re.search(r"claude-(\d+)[\.-](\d+)-(sonnet|opus|haiku|fable)", s)
    if m_num_first:
        try:
            major = int(m_num_first.group(1))
            minor = int(m_num_first.group(2))
            fam = m_num_first.group(3)
            return fam, major, minor
        except Exception:
            pass

    # 3. Fallback for simple major version like claude-3-sonnet
    m_simple = re.search(r"claude-(\d+)-(sonnet|opus|haiku|fable)", s)
    if m_simple:
        try:
            major = int(m_simple.group(1))
            fam = m_simple.group(2)
            return fam, major, 0
        except Exception:
            pass

    # 4. Classic format
    m = re.search(r"claude-(opus|sonnet|haiku|fable)-(\d+)[\.-](\d+)", s)
    if not m:
        return None, None, None
    fam = m.group(1)
    try:
        major = int(m.group(2))
        minor = int(m.group(3))
    except Exception:
        return fam, None, None
    return fam, major, minor


# Models that rejected thinking.type=enabled in this session (per-process memo).
# These require thinking.type=adaptive + output_config.effort.
_ADAPTIVE_THINKING_MODELS: set[str] = set()


def _claude_requires_adaptive_thinking(model_name: str) -> bool:
    """Return True if the model requires thinking.type=adaptive.

    Per API documentation, Claude 4.6+ and newer models (including Fable 5+)
    reject thinking.type=enabled and require adaptive + output_config.effort.
    Also returns True if the model was memoized after a runtime rejection.
    """

    if model_name in _ADAPTIVE_THINKING_MODELS:
        return True
    fam, major, minor = _parse_claude_model(model_name)
    if fam == "fable":
        return True
    if major is not None and major >= 5:
        return True
    # Anthropic's Claude 4.6+ models use adaptive thinking; Claude 4.5
    # remains on the enabled/budget_tokens path.
    if fam in ("opus", "sonnet") and major == 4 and minor is not None and minor >= 6:
        return True
    return False


def _claude_supports_max_effort(model_name: str) -> bool:
    """Check if model supports "max" effort using llmcapa data."""

    try:
        from uagent.llmcapa_util import get_capability, current_provider

        cap = get_capability(model_name, current_provider() or None)
        if cap is not None and getattr(cap, "supports_reasoning_effort", False):
            return "max" in (cap.get_reasoning_effort_values() or [])
    except Exception:
        pass

    # Fallback: hardcoded check
    fam, major, minor = _parse_claude_model(model_name)
    if fam != "opus":
        return False
    if major is None or minor is None:
        return False
    return (major, minor) >= (4, 6)


def _claude_supports_effort(model_name: str) -> bool:
    """Per docs, effort is supported on:

    - Claude Fable 5+
    - Claude 3.7+ (Sonnet, Opus, etc.)
    - Claude Opus 4.6
    - Claude Sonnet 4.6
    - Claude Opus 4.5
    - Claude Haiku 5.5

    Prefer llmcapa's model-specific capability data; the family/version checks
    below are conservative fallbacks for catalogs that do not provide it.
    """
    try:
        from uagent.llmcapa_util import get_capability, current_provider

        cap = get_capability(model_name, current_provider() or None)
        if cap is not None and getattr(cap, "supports_reasoning_effort", False):
            return True
    except Exception:
        pass

    fam, major, minor = _parse_claude_model(model_name)
    if fam is None or major is None or minor is None:
        # Fallback: if model name contains "3-7", "3.7", "claude-4", "fable", "claude-5", assume it supports effort
        s = (model_name or "").strip().lower()
        if any(x in s for x in ("3-7", "3.7", "claude-4", "fable", "claude-5")):
            return True
        return False

    if fam == "fable":
        return major >= 5
    if fam == "opus":
        return (major, minor) >= (4, 5)
    if fam == "sonnet":
        return (major, minor) >= (4, 6)
    if major == 3 and minor >= 7:
        return True
    return False


def _claude_supports_manual_thinking_budget(model_name: str) -> bool:
    """Whether a non-adaptive Claude model supports budget-based thinking."""
    if _claude_requires_adaptive_thinking(model_name):
        return False
    try:
        from uagent.llmcapa_util import current_provider, get_capability

        cap = get_capability(model_name, current_provider() or "claude")
        return bool(cap and getattr(cap, "supports_thinking_budget", False))
    except Exception:
        return False


def build_claude_output_config_for_effort(
    model_name: str,
    effort: str | None,
) -> Optional[dict[str, Any]]:
    """Convert UAG effort to an Anthropic effort or manual-budget hint.

    Adaptive-thinking models receive ``output_config.effort``. Models that
    expose only ``thinking.budget_tokens`` receive an internal effort hint
    that the request builder converts to ``thinking.type=enabled``.

    UAG levels are minimal|low|medium|high|xhigh; Anthropic effort levels are
    low|medium|high|max. llmcapa determines which controls the model supports.
    """

    e = (effort or "").strip().lower()
    if not e:
        return None

    supports_effort = _claude_supports_effort(model_name)
    supports_manual_budget = (
        not supports_effort and _claude_supports_manual_thinking_budget(model_name)
    )

    # Older models such as Claude Haiku 4.5 support manual thinking budgets,
    # not output_config.effort. Return an internal effort hint; the request
    # builder translates it to thinking.type=enabled + budget_tokens.
    if supports_manual_budget:
        if e in ("minimal", "low"):
            return {"effort": "low"}
        if e == "medium":
            return {"effort": "medium"}
        if e in ("high", "xhigh", "max"):
            return {"effort": "high"}
        return None

    # If the model supports neither effort nor manual budget thinking, omit it.
    if not supports_effort:
        return None

    try:
        from uagent.llmcapa_util import get_capability, current_provider

        cap = get_capability(model_name, current_provider() or None)
        if cap is not None and getattr(cap, "supports_reasoning_effort", False):
            valid = cap.get_reasoning_effort_values() or []
            if e in valid:
                # Map xhigh/max based on model support
                if e in ("xhigh", "max"):
                    if _claude_supports_max_effort(model_name):
                        return {"effort": "max"}
                    return {"effort": "high"}
                # For other values, map minimal->low, otherwise pass through
                if e == "minimal":
                    return {"effort": "low"}
                return {"effort": e}
    except Exception:
        pass

    # Fallback: hardcoded mapping
    if e in ("minimal", "low"):
        return {"effort": "low"}
    if e == "medium":
        return {"effort": "medium"}
    if e == "high":
        return {"effort": "high"}
    if e == "xhigh":
        if _claude_supports_max_effort(model_name):
            return {"effort": "max"}
        return {"effort": "high"}
    return None


def claude_chat_with_tools(
    client: Any,
    model_name: str,
    messages: list[dict[str, Any]],
    *,
    provider: str = "claude",
    output_config: Optional[dict[str, Any]] = None,
    on_output_config_info: Optional[Any] = None,
    on_output_config_fallback: Optional[Any] = None,
    send_tools: bool = True,
    core: Any = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Anthropic Messages API compatible routeで tool_calls 付き応答を生成する。

    OpenAI 形式の messages を Anthropic 形式に変換してからリクエストする。

    Returns:
        assistant_text: アシスタントのテキスト応答
        tool_calls_list: OpenAI 互換の tool_calls リスト
    """

    try:
        from anthropic import Anthropic  # lazy
    except ImportError:
        Anthropic = None
    if Anthropic is None:
        raise RuntimeError(_("anthropic package is not installed."))
    if core is not None:
        try:
            core._last_claude_content_blocks = None
        except (AttributeError, TypeError):
            pass

    from ..runtime.tool_discovery import (
        MANAGEMENT_TOOL_NAMES,
        anthropic_messages_tool_search_variant,
        deepseek_messages_tool_search_enabled,
    )

    tool_search_variant = (
        anthropic_messages_tool_search_variant(provider, model_name)
        if send_tools
        else None
    )
    deepseek_client_tool_search = (
        deepseek_messages_tool_search_enabled(provider, model_name)
        if send_tools
        else False
    )
    messages_tool_search_active = bool(
        tool_search_variant is not None or deepseek_client_tool_search
    )
    tool_catalog_call_ids = {
        str(tool_call.get("id") or "")
        for message in messages
        if isinstance(message, dict) and message.get("role") == "assistant"
        for tool_call in (message.get("tool_calls") or [])
        if isinstance(tool_call, dict)
        and str(((tool_call.get("function") or {}).get("name") or "")) == "tool_catalog"
        and str(tool_call.get("id") or "")
    }
    has_prior_server_search = any(
        isinstance(message, dict)
        and message.get("role") == "assistant"
        and isinstance(message.get("_anthropic_content_blocks"), list)
        and any(
            isinstance(block, dict)
            and block.get("type") in {"server_tool_use", "tool_search_tool_result"}
            for block in message["_anthropic_content_blocks"]
        )
        for message in messages
    )

    anthropic_messages: list[dict[str, Any]] = []
    system_content = ""

    # OpenAI 形式のメッセージ履歴を Anthropic 形式に変換
    # - System は system パラメータへ
    # - User/Tool -> User role (Tool は tool_result ブロック)
    # - Assistant -> Assistant role (tool_calls は tool_use ブロック)
    # - 同一ロールの連続は 1 つのメッセージに結合する

    for m in messages:
        role = m.get("role")
        content = m.get("content") or ""

        if role == "system":
            system_content += content + "\n"
            continue

        new_role = None
        new_content_blocks: list[dict[str, Any]] = []

        if role == "user":
            new_role = "user"
            if isinstance(content, str):
                new_content_blocks.append({"type": "text", "text": content})
            elif isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    item_type = item.get("type")
                    if item_type == "text":
                        new_content_blocks.append(
                            {"type": "text", "text": item.get("text", "")}
                        )
                    elif item_type == "image_url":
                        img_url_obj = item.get("image_url") or {}
                        url = img_url_obj.get("url") or ""
                        if url.startswith("data:"):
                            try:
                                header, data = url.split(",", 1)
                                mime_type = header.split(";")[0].split(":")[1]
                                new_content_blocks.append(
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": mime_type,
                                            "data": data,
                                        },
                                    }
                                )
                            except Exception:
                                pass
                        else:
                            new_content_blocks.append(
                                {"type": "text", "text": f"[Image URL: {url}]"}
                            )

        elif role == "assistant":
            new_role = "assistant"
            native_blocks = m.get("_anthropic_content_blocks")
            if (
                isinstance(native_blocks, list)
                and native_blocks
                and all(isinstance(block, dict) for block in native_blocks)
                and messages_tool_search_active
            ):
                # Messages endpoints require native blocks (including provider
                # deferred-load state) to be replayed unchanged.
                new_content_blocks.extend(copy.deepcopy(native_blocks))
            else:
                if content:
                    new_content_blocks.append({"type": "text", "text": content})

                tool_calls = m.get("tool_calls", [])
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    t_name = fn.get("name", "")
                    t_args = fn.get("arguments", "{}")
                    t_id = tc.get("id")
                    try:
                        t_input = json.loads(t_args)
                    except Exception:
                        t_input = {}
                    member = tc.get("computer_member_tool")
                    if tc.get("computer_toolset_name") == "computer" and member:
                        original_member_input = tc.get("computer_member_input")
                        if isinstance(original_member_input, dict):
                            t_input = dict(original_member_input)
                        elif isinstance(t_input, dict):
                            t_input = dict(t_input)
                            t_input.pop("action", None)
                        new_content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": t_id,
                                "name": str(member),
                                "toolset_name": "computer",
                                "input": t_input,
                            }
                        )
                    else:
                        new_content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": t_id,
                                "name": t_name,
                                "input": t_input,
                            }
                        )

        elif role == "tool":
            new_role = "user"
            result_content: Any = content
            try:
                result_json = json.loads(content) if isinstance(content, str) else {}
                screenshot_data = result_json.get("screenshot_data")
                if screenshot_data:
                    result_content = [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": result_json.get(
                                    "screenshot_media_type", "image/png"
                                ),
                                "data": screenshot_data,
                            },
                        }
                    ]
                    if result_json.get("error"):
                        result_content.append(
                            {"type": "text", "text": result_json["error"]}
                        )
            except Exception:
                pass
            member = m.get("computer_member_tool")
            if m.get("computer_toolset_name") == "computer" and member:
                try:
                    result_json = (
                        json.loads(content) if isinstance(content, str) else {}
                    )
                except Exception:
                    result_json = {}
                if not isinstance(result_json, dict):
                    result_json = {}
                screenshot_data = result_json.get("screenshot_data")
                succeeded = bool(result_json.get("success"))
                result_error = str(result_json.get("error") or "Computer action failed")
                result_blocks: list[dict[str, Any]] = []
                if not succeeded:
                    result_blocks.append({"type": "text", "text": result_error})
                elif member == "screenshot":
                    if screenshot_data:
                        result_blocks.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": result_json.get(
                                        "screenshot_media_type", "image/png"
                                    ),
                                    "data": screenshot_data,
                                },
                            }
                        )
                    else:
                        succeeded = False
                        result_blocks.append(
                            {
                                "type": "text",
                                "text": "Error: failed to capture screenshot.",
                            }
                        )
                else:
                    result_blocks.append({"type": "text", "text": "OK"})
                    is_last_batch_member = (
                        m.get("computer_batch_index") is not None
                        and m.get("computer_batch_size") is not None
                        and int(m["computer_batch_index"]) + 1
                        == int(m["computer_batch_size"])
                    )
                    if is_last_batch_member and screenshot_data:
                        result_blocks.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": result_json.get(
                                        "screenshot_media_type", "image/png"
                                    ),
                                    "data": screenshot_data,
                                },
                            }
                        )
                new_content_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": m.get("tool_call_id"),
                        "toolset_name": "computer",
                        "content": result_blocks,
                        "is_error": not succeeded,
                    }
                )
            else:
                if (
                    deepseek_client_tool_search
                    and str(m.get("tool_call_id") or "") in tool_catalog_call_ids
                    and isinstance(result_content, str)
                ):
                    try:
                        catalog_result = json.loads(result_content)
                    except Exception:
                        catalog_result = None
                    rows = (
                        catalog_result.get("tools")
                        if isinstance(catalog_result, dict)
                        else None
                    )
                    declared_names = {
                        str((spec.get("function") or {}).get("name") or "")
                        for spec in (tools.get_tool_specs() or [])
                        if isinstance(spec, dict)
                        and isinstance(spec.get("function"), dict)
                    }
                    references = [
                        {
                            "type": "tool_reference",
                            "tool_name": str(row.get("name") or ""),
                        }
                        for row in (rows or [])
                        if isinstance(row, dict)
                        and str(row.get("name") or "") in declared_names
                    ]
                    if references:
                        result_content = references + [
                            {"type": "text", "text": "Continue."}
                        ]
                new_content_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": m.get("tool_call_id"),
                        "content": result_content,
                    }
                )

        if new_role:
            if anthropic_messages and anthropic_messages[-1]["role"] == new_role:
                # 直前のメッセージと同じロールなら結合 (content は常に list)
                anthropic_messages[-1]["content"].extend(new_content_blocks)
            else:
                # 新規メッセージ
                anthropic_messages.append(
                    {"role": new_role, "content": new_content_blocks}
                )

    anthropic_tools = []
    native_tool = None
    if send_tools:
        context_tool_specs = getattr(core, "context_tool_specs", None)
        _tool_specs_iter = list(
            context_tool_specs
            if context_tool_specs is not None
            else (tools.get_tool_specs() or [])
        )
        if messages_tool_search_active:
            # Native server search and DeepSeek's client-side reference loading
            # both require the complete execution-policy-filtered inventory.
            _tool_specs_iter = list(tools.get_tool_specs() or [])
        from ..runtime.execution_broker import (
            computer_use_allowed,
            is_computer_use_tool_spec,
        )

        _computer_use_allowed = computer_use_allowed()
        if not _computer_use_allowed:
            _tool_specs_iter = [
                spec for spec in _tool_specs_iter if not is_computer_use_tool_spec(spec)
            ]
        native_tool = (
            getattr(core, "computer_use_native_tool", None)
            if core is not None and _computer_use_allowed
            else None
        )
        native_toolset_active = (
            isinstance(native_tool, dict)
            and native_tool.get("type") == "computer_toolset_20260801"
        )
        if (
            core is not None
            and _computer_use_allowed
            and getattr(core, "computer_use_runtime", None) is not None
            and not native_toolset_active
        ):
            from ..computer_use.native import local_computer_tool_spec

            if not any(
                (spec.get("function", {}).get("name") == "computer")
                for spec in _tool_specs_iter
                if isinstance(spec, dict)
            ):
                _tool_specs_iter.append(local_computer_tool_spec())
    else:
        _tool_specs_iter = []
    unfiltered_tool_specs = _tool_specs_iter
    if tool_search_variant is not None:
        # Native server-side search replaces the local catalog/load bootstrap.
        # Do not expose those management tools as searchable callable tools.
        _tool_specs_iter = [
            spec
            for spec in _tool_specs_iter
            if str((spec.get("function") or {}).get("name") or "")
            not in MANAGEMENT_TOOL_NAMES
        ]
    if (
        (
            getattr(core, "computer_use_runtime", None) is None
            or (
                isinstance(native_tool, dict)
                and native_tool.get("type") == "computer_toolset_20260801"
            )
        )
        and native_tool
        and isinstance(native_tool, dict)
    ):
        # Native tools use Anthropic's top-level tool shape, not JSON Schema.
        anthropic_tools.append(dict(native_tool))

    function_tool_names = [
        str(spec.get("function", {}).get("name") or "")
        for spec in _tool_specs_iter
        if isinstance(spec, dict) and isinstance(spec.get("function"), dict)
    ]
    eager_tool_names: set[str] = set()
    if tool_search_variant is not None:
        eager_tool_names = {
            name for name in _ANTHROPIC_EAGER_TOOL_NAMES if name in function_tool_names
        }
        # Keep a small direct-call surface even when this environment has
        # different built-ins loaded than the usual CLI set.
        for name in function_tool_names:
            if len(eager_tool_names) >= min(3, len(function_tool_names)):
                break
            eager_tool_names.add(name)
        if not has_prior_server_search and not any(
            name not in eager_tool_names for name in function_tool_names
        ):
            tool_search_variant = None
            messages_tool_search_active = False
            # Once native search is abandoned, use the catalog bootstrap rather
            # than exposing the full inventory directly.
            _tool_specs_iter = [
                spec
                for spec in unfiltered_tool_specs
                if str((spec.get("function") or {}).get("name") or "")
                in MANAGEMENT_TOOL_NAMES
            ]
            function_tool_names = [
                str(spec.get("function", {}).get("name") or "")
                for spec in _tool_specs_iter
                if isinstance(spec, dict) and isinstance(spec.get("function"), dict)
            ]
            eager_tool_names = set()
    elif deepseek_client_tool_search:
        from ..runtime.tool_discovery import MANAGEMENT_TOOL_NAMES

        eager_tool_names = {
            name
            for name in (
                *MANAGEMENT_TOOL_NAMES,
                "human_ask",
                *_ANTHROPIC_EAGER_TOOL_NAMES,
            )
            if name in function_tool_names
        }
        # DeepSeek's client-side Messages protocol needs a callable catalog
        # tool whose result UAG converts to tool_reference blocks.
        can_defer = "tool_catalog" in eager_tool_names and any(
            name not in eager_tool_names for name in function_tool_names
        )
        if not can_defer:
            deepseek_client_tool_search = False
            messages_tool_search_active = tool_search_variant is not None
            eager_tool_names = set()

    if tool_search_variant is not None:
        anthropic_tools.append(
            {
                "type": f"tool_search_tool_{tool_search_variant}_20251119",
                "name": f"tool_search_tool_{tool_search_variant}",
            }
        )

    for spec in _tool_specs_iter:
        fn = spec.get("function", {})
        name = fn.get("name", "")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})
        anthropic_tool = {
            "name": name,
            "description": desc,
            "input_schema": params,
        }
        if "input_examples" in fn:
            anthropic_tool["input_examples"] = fn["input_examples"]
        if fn.get("strict") is not None:
            anthropic_tool["strict"] = fn["strict"]
        if messages_tool_search_active and name not in eager_tool_names:
            anthropic_tool["defer_loading"] = True
        anthropic_tools.append(anthropic_tool)

    # Anthropic prompt-cache directives are provider-specific. Compatible
    # gateways use their own cache policy and may reject this extension.
    system_blocks = []
    if system_content.strip():
        system_block = {"type": "text", "text": system_content.strip()}
        if provider == "claude":
            system_block["cache_control"] = {"type": "ephemeral"}
        system_blocks.append(system_block)

    # The cache directive is only supported on the direct Anthropic route.
    first_user_msg = next((m for m in anthropic_messages if m["role"] == "user"), None)
    if (
        provider == "claude"
        and first_user_msg
        and isinstance(first_user_msg["content"], list)
    ):
        for block in first_user_msg["content"]:
            if block.get("type") == "text":
                block["cache_control"] = {"type": "ephemeral"}
                break

    # Normalize output_config (best-effort)
    out_cfg = None
    if isinstance(output_config, dict) and output_config:
        out_cfg = output_config

    # Resolve temperature: UAGENT_CLAUDE_TEMPERATURE, then UAGENT_TEMPERATURE.
    # Only set when explicitly configured (thinking mode may force omit later).
    claude_temp = None
    temp_env = (
        env_get("UAGENT_CLAUDE_TEMPERATURE") or env_get("UAGENT_TEMPERATURE") or ""
    ).strip()
    if temp_env:
        try:
            claude_temp = float(temp_env)
        except ValueError:
            pass

    # Parse both family-first IDs (claude-haiku-4-5) and version-first IDs
    # (claude-3-7-sonnet) so modern-model behavior applies to every family.
    model_family, major, minor = _parse_claude_model(model_name)
    is_modern_claude = bool(
        (major is not None and major >= 4)
        or (major == 3 and minor is not None and minor >= 7)
        or re.search(r"3[\.-][7-9]", model_name)
        or re.search(r"claude-[4-9]", model_name)
        or model_family == "fable"
        or "fable" in model_name.lower()
    )

    # Resolve max_tokens (dynamic based on environment variable or model/thinking)
    max_tokens = 4096
    max_tokens_env = (env_get("UAGENT_MAX_TOKENS") or "").strip()
    if max_tokens_env:
        try:
            max_tokens = int(max_tokens_env)
        except ValueError:
            pass
    else:
        # If model is modern Claude or output_config (thinking) is enabled, default to 8192
        if is_modern_claude or out_cfg is not None:
            max_tokens = 8192
    try:
        from uagent.llmcapa_util import clamp_max_tokens, current_provider

        max_tokens = clamp_max_tokens(
            max_tokens, model_name, current_provider() or "claude"
        )
    except Exception:
        pass

    # Resolve thinking parameter for modern Claude models (Claude 3.7+, Claude 4+, Fable 5+)
    thinking_param = None
    use_adaptive_thinking = False
    if (
        is_modern_claude
        and out_cfg is not None
        and _claude_requires_adaptive_thinking(model_name)
    ):
        # Newer models (Fable 5+ / Claude 5+) reject thinking.type=enabled.
        # Send thinking.type=adaptive and keep output_config.effort.
        use_adaptive_thinking = True
        thinking_param: dict[str, Any] = {"type": "adaptive"}
        claude_temp = None
    elif is_modern_claude and out_cfg is not None:
        eff = out_cfg.get("effort", "medium")
        # Map effort to budget_tokens
        budget = 4096
        if eff == "low":
            budget = 1024
        elif eff == "medium":
            budget = 4096
        elif eff in ("high", "max"):
            budget = 6144

        # Anthropic requires max_tokens > thinking.budget_tokens.
        # If UAGENT_MAX_TOKENS is set too small, shrink the budget; if it
        # cannot be at least 1024 (API minimum), disable thinking entirely.
        if max_tokens <= budget:
            budget = max_tokens - 1024

        if budget >= 1024:
            thinking_param = {"type": "enabled", "budget_tokens": budget}
            # When thinking is enabled, temperature must be omitted or set to 1.0.
            # We omit it by setting claude_temp to None.
            claude_temp = None

    req_kwargs: dict[str, Any] = {
        "model": model_name,
        "max_tokens": max_tokens,
        "messages": anthropic_messages,
    }
    # If output_config (thinking/effort) is used, temperature must be omitted.
    # Otherwise, only set temperature if explicitly configured.
    if claude_temp is not None and out_cfg is None and thinking_param is None:
        req_kwargs["temperature"] = claude_temp

    if system_blocks:
        req_kwargs["system"] = system_blocks
    if anthropic_tools:
        req_kwargs["tools"] = anthropic_tools
    native_headers = (
        getattr(core, "computer_use_native_headers", None) if core is not None else None
    )
    if native_headers:
        req_kwargs["extra_headers"] = {"anthropic-beta": ",".join(native_headers)}

    if use_adaptive_thinking and thinking_param is not None:
        req_kwargs["thinking"] = thinking_param
        if out_cfg is not None:
            req_kwargs["output_config"] = out_cfg
        try:
            eff = out_cfg.get("effort") if isinstance(out_cfg, dict) else None
            msg = f"[Claude] using thinking.type=adaptive, output_config.effort: {eff}"
            if callable(on_output_config_info):
                on_output_config_info(msg)
            else:
                print(msg)
        except Exception:
            pass
    elif thinking_param is not None:
        req_kwargs["thinking"] = thinking_param
        try:
            msg = f"[Claude] using thinking.budget_tokens: {thinking_param.get('budget_tokens')}"
            if callable(on_output_config_info):
                on_output_config_info(msg)
            else:
                print(msg)
        except Exception:
            pass
    elif out_cfg is not None:
        # In the legacy budget path, "effort" is only an internal hint and
        # must never be sent as output_config.effort. Keep any independent
        # output_config fields (for example, structured-output format).
        direct_out_cfg = out_cfg
        if is_modern_claude and not use_adaptive_thinking:
            direct_out_cfg = {k: v for k, v in out_cfg.items() if k != "effort"}
        if direct_out_cfg:
            req_kwargs["output_config"] = direct_out_cfg
            try:
                eff = direct_out_cfg.get("effort")
                msg = f"[Claude] using output_config.effort: {eff or direct_out_cfg}"
                if callable(on_output_config_info):
                    on_output_config_info(msg)
                else:
                    print(msg)
            except Exception:
                pass

    try:
        response = client.messages.create(**req_kwargs)
    except Exception as e:
        msg = str(e)
        ml = msg.lower()

        # Case 1: Temperature is rejected/deprecated
        if "temperature" in ml and "temperature" in req_kwargs:
            try:
                try:
                    if callable(on_output_config_fallback):
                        on_output_config_fallback(
                            "[Claude] "
                            + _("temperature rejected; retrying without temperature")
                        )
                    else:
                        print(
                            "[Claude] "
                            + _("temperature rejected; retrying without temperature")
                        )
                except Exception:
                    pass
                req_kwargs.pop("temperature", None)
                response = client.messages.create(**req_kwargs)
            except Exception as retry_exc:
                retry_msg = str(retry_exc)
                retry_ml = retry_msg.lower()
                if out_cfg is not None and (
                    "output_config" in retry_ml or "output config" in retry_ml
                ):
                    try:
                        req_kwargs.pop("output_config", None)
                        response = client.messages.create(**req_kwargs)
                    except Exception:
                        raise e from retry_exc
                else:
                    raise e from retry_exc

        # Case 1.5: thinking.type "enabled" is not supported (newer models
        # require thinking.type "adaptive" + output_config.effort).
        elif "thinking" in req_kwargs and (
            "thinking.type.enabled" in ml
            or ("thinking.type" in ml and "adaptive" in ml)
        ):
            try:
                # Memoize: this model needs adaptive from the first request next time.
                _ADAPTIVE_THINKING_MODELS.add(model_name)
                fb_msg = "[Claude] " + _(
                    "thinking.type=enabled rejected; "
                    "retrying with thinking.type=adaptive + output_config.effort"
                )
                try:
                    if callable(on_output_config_fallback):
                        on_output_config_fallback(fb_msg)
                    else:
                        print(fb_msg)
                except Exception:
                    pass
                req_kwargs["thinking"] = {"type": "adaptive"}
                if out_cfg is not None:
                    req_kwargs["output_config"] = out_cfg
                try:
                    response = client.messages.create(**req_kwargs)
                except Exception as retry_exc:
                    retry_ml = str(retry_exc).lower()
                    # If output_config is also rejected, drop it and retry once more.
                    if "output_config" in retry_ml or "output config" in retry_ml:
                        req_kwargs.pop("output_config", None)
                        response = client.messages.create(**req_kwargs)
                    else:
                        raise e from retry_exc
            except Exception as retry_exc:
                raise e from retry_exc

        # Case 2: output_config is rejected
        elif out_cfg is not None and ("output_config" in ml or "output config" in ml):
            try:
                try:
                    if callable(on_output_config_fallback):
                        on_output_config_fallback(
                            "[Claude] "
                            + _(
                                "output_config rejected; retrying without output_config"
                            )
                        )
                    else:
                        print(
                            "[Claude] "
                            + _(
                                "output_config rejected; retrying without output_config"
                            )
                        )
                except Exception:
                    pass
                req_kwargs.pop("output_config", None)
                # If we removed output_config, we can restore temperature if it wasn't rejected
                if claude_temp is not None:
                    req_kwargs["temperature"] = claude_temp
                try:
                    response = client.messages.create(**req_kwargs)
                except Exception as retry_exc:
                    retry_msg = str(retry_exc)
                    retry_ml = retry_msg.lower()
                    if "temperature" in retry_ml:
                        req_kwargs.pop("temperature", None)
                        response = client.messages.create(**req_kwargs)
                    else:
                        raise e from retry_exc
            except Exception as retry_exc:
                raise e from retry_exc
        else:
            raise

    assistant_text = ""
    tool_calls_list: list[dict[str, Any]] = []
    thinking_text = ""
    _thinking_blocks = 0
    if core is not None and messages_tool_search_active:
        raw_blocks = [
            serialized
            for block in (getattr(response, "content", None) or [])
            if (serialized := _anthropic_block_to_dict(block)) is not None
        ]
        if raw_blocks:
            try:
                core._last_claude_content_blocks = raw_blocks
            except (AttributeError, TypeError):
                pass
    _computer_tool_uses = [
        block
        for block in (getattr(response, "content", None) or [])
        if getattr(block, "type", None) == "tool_use"
        and getattr(block, "toolset_name", None) == "computer"
    ]
    _batch_id = str(
        getattr(response, "id", None) or f"{provider}-messages:{id(response)}"
    )
    _batch_positions = {
        id(block): index for index, block in enumerate(_computer_tool_uses)
    }

    for block in response.content:
        if block.type == "text":
            assistant_text += block.text
        elif block.type == "thinking":
            _t = getattr(block, "thinking", None) or ""
            thinking_text += _t
            # 思考プロセスをコンソールに表示する（空ブロックは見出しを出さない）
            if _t.strip():
                show_reasoning(
                    _t, provider="Claude", is_first=(_thinking_blocks == 0), core=core
                )
                _thinking_blocks += 1
            elif (env_get("UAGENT_DEBUG") or "").strip():
                try:
                    print(f"\n[Claude Thinking] (empty thinking block) raw={block!r}\n")
                except Exception:
                    pass
        elif block.type == "redacted_thinking":
            # 暗号化された思考ブロック（内容は表示不可）
            if (env_get("UAGENT_DEBUG") or "").strip():
                print("\n[Claude Thinking] (redacted_thinking block)\n")
        elif block.type == "tool_use":
            input_payload = block.input if isinstance(block.input, dict) else {}
            tool_call = {
                "id": block.id,
                "type": "function",
                "function": {
                    "name": block.name,
                    "arguments": json.dumps(input_payload),
                },
            }
            if getattr(block, "toolset_name", None) == "computer":
                from ..computer_use.adapters.anthropic import (
                    ANTHROPIC_COMPUTER_MEMBERS,
                    AnthropicComputerAdapter,
                )

                member = str(block.name or "")
                if member not in ANTHROPIC_COMPUTER_MEMBERS:
                    raise ValueError(
                        f"unsupported Anthropic computer toolset member: {member or '<empty>'}"
                    )
                normalized_input = AnthropicComputerAdapter._normalize_member_input(
                    member, input_payload
                )
                tool_call["function"] = {
                    "name": "computer",
                    "arguments": json.dumps(normalized_input),
                }
                batch_index = _batch_positions[id(block)]
                tool_call.update(
                    {
                        "computer_toolset_name": "computer",
                        "computer_member_tool": member,
                        "computer_member_input": dict(input_payload),
                        "computer_batch_id": _batch_id,
                        "computer_batch_index": batch_index,
                        "computer_batch_size": len(_computer_tool_uses),
                    }
                )
            tool_calls_list.append(tool_call)

    # 思考プロセスが検出された場合、assistant_text の先頭に埋め込むことで
    # 上位モジュールや会話履歴に思考プロセスを正しく伝播させる
    if thinking_text:
        assistant_text = f"<thinking>\n{thinking_text}\n</thinking>\n" + assistant_text

    # Preserve the successfully completed API response's usage as a new
    # per-request snapshot. The fallback chat span maps it to standard GenAI
    # attributes; a rejected API attempt never contributes a second count.
    if core is not None:
        from ..runtime.telemetry import anthropic_usage_to_dict

        measured = anthropic_usage_to_dict(getattr(response, "usage", None))
        if measured:
            try:
                core._last_responses_usage = measured
            except (AttributeError, TypeError):
                pass

    return assistant_text, tool_calls_list
