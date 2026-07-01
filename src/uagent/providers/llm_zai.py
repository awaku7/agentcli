"""Z.AI (Zhipu AI) chat completion helper using the zhipuai SDK.

Compared to the DeepSeek path (llm_deepseek.py):

- ``thinking`` is passed as a **direct** SDK parameter (not via ``extra_body``).
- ``reasoning_effort`` is passed through ``extra_body`` because the zhipuai SDK
  does **not** expose it as a top-level parameter, whereas the Z.AI REST API
  accepts it as a top-level JSON field.
- Exception handling uses ``zhipuai.core`` errors instead of ``openai`` errors.
- Response parsing reuses ``parse_deepseek_stream`` and
  ``parse_deepseek_response`` from ``llm_deepseek`` because the zhipuai SDK
  returns objects with the same attribute names
  (``reasoning_content``, ``tool_calls``, etc.).
"""

from __future__ import annotations

import json
import sys
from typing import Any
from urllib.error import URLError

from .. import tools as _tools
from ..env_utils import env_get
from ..i18n import _
from ..llm_errors import _rate_limit_retry_step
from ..llm_helpers import (
    _choose_auto_effort,
    _extract_latest_user_text,
    _is_thinking_task,
    _maybe_print_certifi_where,
)

# Reuse DeepSeek response parsers (compatible with zhipuai SDK response format)
from .llm_deepseek import (
    parse_deepseek_response,
    parse_deepseek_stream,
    _diagnose_message_structure,
    _repair_incomplete_tool_sequences,
    _strip_reasoning_content_no_tool,
)

# ---------------------------------------------------------------------------
# Thinking-mode effort mapping
# ---------------------------------------------------------------------------
# Z.AI supports: max, xhigh, high, medium, low, minimal, none
# We map our internal values to these.
_EFFORT_MAP: dict[str, str] = {
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "max",
}

_VALID_EFFORTS = frozenset({"max", "xhigh", "high", "medium", "low", "minimal"})

_ENV_PREFIX = "UAGENT_ZAI"
_LABEL = "Z.AI"


def build_zai_chat_kwargs(
    *,
    depname: str,
    call_messages: list[dict[str, Any]],
    send_tools: bool,
    req_tools: list[dict[str, Any]] | None,
    reasoning: str,
    auto_user_text: str,
) -> tuple[dict[str, Any], str | None]:
    """Build the kwargs dict for ``client.chat.completions.create`` (zhipuai SDK).

    Returns ``(chat_kwargs, effort_used)`` where ``effort_used`` is the
    resolved reasoning_effort string (or None if thinking is disabled).
    """
    # Strip reasoning_content from incoming messages to avoid 400.
    clean_messages = _strip_reasoning_content_no_tool(call_messages)

    chat_kwargs: dict[str, Any] = {
        "model": depname,
        "messages": clean_messages,
    }

    if send_tools and req_tools:
        chat_kwargs["tools"] = req_tools
        chat_kwargs["tool_choice"] = "auto"

    # Add stream parameter later in the caller, not here.

    effort_used: str | None = None

    if reasoning == "auto":
        if _is_thinking_task(auto_user_text):
            effort_used = _choose_auto_effort(auto_user_text)
            effort_used = _EFFORT_MAP.get(effort_used, "high")
    elif reasoning in ("off", ""):
        # Explicitly disable thinking via the SDK's thinking parameter
        chat_kwargs["thinking"] = {"type": "disabled"}
    else:
        mapped = _EFFORT_MAP.get(reasoning)
        if mapped:
            effort_used = mapped

    if effort_used in _VALID_EFFORTS:
        # zhipuai SDK's create() has a direct `thinking` parameter
        chat_kwargs["thinking"] = {"type": "enabled"}
        # reasoning_effort is NOT a parameter of zhipuai SDK, but the Z.AI REST
        # API accepts it as a top-level JSON field.  Pass through extra_body.
        chat_kwargs.setdefault("extra_body", {})
        chat_kwargs["extra_body"]["reasoning_effort"] = effort_used
    elif "thinking" not in chat_kwargs:
        # No explicit thinking toggle -> API default
        pass

    # Non-thinking-mode parameters: temperature, top_p, presence_penalty,
    # frequency_penalty.  In thinking mode these are silently ignored or
    # rejected by the API, so we only send them when thinking is disabled.
    if effort_used not in _VALID_EFFORTS:
        # temperature
        temp_env = (
            env_get(f"{_ENV_PREFIX}_TEMPERATURE") or env_get("UAGENT_TEMPERATURE") or ""
        ).strip()
        try:
            resolved_temp = float(temp_env) if temp_env else 0.0
        except ValueError:
            resolved_temp = 0.0
        chat_kwargs["temperature"] = resolved_temp

        # top_p (default: 1.0)
        top_p_env = (env_get(f"{_ENV_PREFIX}_TOP_P") or "").strip()
        try:
            chat_kwargs["top_p"] = float(top_p_env) if top_p_env else 1.0
        except ValueError:
            chat_kwargs["top_p"] = 1.0

        # presence_penalty (default: 0.0)
        pp_env = (env_get(f"{_ENV_PREFIX}_PRESENCE_PENALTY") or "").strip()
        try:
            chat_kwargs["presence_penalty"] = float(pp_env) if pp_env else 0.0
        except ValueError:
            chat_kwargs["presence_penalty"] = 0.0

        # frequency_penalty (default: 0.0)
        fp_env = (env_get(f"{_ENV_PREFIX}_FREQUENCY_PENALTY") or "").strip()
        try:
            chat_kwargs["frequency_penalty"] = float(fp_env) if fp_env else 0.0
        except ValueError:
            chat_kwargs["frequency_penalty"] = 0.0

    return chat_kwargs, effort_used


# ---------------------------------------------------------------------------
# zhipuai SDK error wrappers
# ---------------------------------------------------------------------------

_ZHIPUAI_AVAILABLE = False
_ZhipuaiAPIConnectionError: type[Exception] | None = None
_ZhipuaiAPIStatusError: type[Exception] | None = None
_ZhipuaiAPIReachLimitError: type[Exception] | None = None

try:
    from zhipuai.core import (
        APIConnectionError as _ZhipuaiAPIConnectionError,
        APIStatusError as _ZhipuaiAPIStatusError,
    )

    _ZHIPUAI_AVAILABLE = True
except Exception:
    pass


def _get_zai_client_error_info(e: Exception) -> tuple[int | None, str | None]:
    """Extract (status_code, error_text) from a zhipuai SDK exception."""
    status: int | None = None
    body_str: str | None = None

    # Try common attributes
    if _ZhipuaiAPIStatusError is not None and isinstance(e, _ZhipuaiAPIStatusError):
        status = getattr(e, "status_code", None) or getattr(e, "status", None)
        # zhipuai's APIStatusError has .body or .response
        body = getattr(e, "body", None) or getattr(e, "response", None)
        if body is not None:
            if isinstance(body, (bytes, bytearray)):
                body = body.decode("utf-8", errors="replace")
            if isinstance(body, str):
                body_str = body
            elif isinstance(body, dict):
                body_str = json.dumps(body, ensure_ascii=False)
            elif hasattr(body, "text"):
                try:
                    body_str = body.text
                except Exception:
                    pass

    if status is None:
        status = getattr(e, "status_code", None) or getattr(e, "status", None)

    return status, body_str


# ---------------------------------------------------------------------------
# Main chat completion round
# ---------------------------------------------------------------------------


def zai_chat_with_tools(
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    *,
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    send_tools_this_round: bool,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
    stream: bool = True,
) -> tuple[bool, Any, str, str, list[dict[str, Any]]]:
    """Run one Z.AI (zhipuai SDK) chat completion round.

    Returns ``(ok, client, assistant_text, reasoning_content, tool_calls_list)``.
    """
    attempt_429 = 0
    tool_repair_attempted = False

    _reasoning = (env_get("UAGENT_REASONING") or "").strip().lower()
    _auto_user_text = (
        _extract_latest_user_text(call_messages) if _reasoning == "auto" else ""
    )

    req_tools = _tools.get_tool_specs() if send_tools_this_round else None

    while True:
        try:
            chat_kwargs, effort_used = build_zai_chat_kwargs(
                depname=depname,
                call_messages=call_messages,
                send_tools=send_tools_this_round,
                req_tools=req_tools,
                reasoning=_reasoning,
                auto_user_text=_auto_user_text,
            )

            if effort_used:
                label = (
                    f"LLM:auto->{effort_used}"
                    if _reasoning == "auto"
                    else f"LLM:{effort_used}"
                )
                try:
                    core.set_status(True, label)
                except Exception:
                    pass

            if stream:
                assistant_text, reasoning_content, tool_calls_list = (
                    call_maybe_thread_fn(
                        lambda: parse_deepseek_stream(
                            client.chat.completions.create(**chat_kwargs, stream=True),
                            print_delta_fn=(
                                None
                                if bool(getattr(core, "_is_web", False))
                                else (
                                    lambda s: (
                                        print(s, end="", flush=True) if s else None
                                    )
                                )
                            ),
                            core=core,
                        )
                    )
                )
            else:
                resp = call_maybe_thread_fn(
                    lambda: client.chat.completions.create(**chat_kwargs)
                )
                assistant_text, reasoning_content, tool_calls_list = (
                    parse_deepseek_response(resp)
                )

            return True, client, assistant_text, reasoning_content, tool_calls_list

        except Exception as e:
            attempt_429, new_client, action = _rate_limit_retry_step(
                exception=e,
                provider="zai",
                model=depname,
                attempt=attempt_429,
                max_retries=max_retries_429,
                base=retry_base,
                cap=retry_cap,
                recreate_client_fn=(lambda: (make_client_fn(core)[1])),
            )
            if action == "retry":
                if new_client is not None:
                    client = new_client
                continue
            if action == "give_up":
                print(
                    f"[{_LABEL} Error] "
                    + _("429 retry limit (%(max_retries)s) reached.")
                    % {"max_retries": max_retries_429}
                )
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []

            err = str(e)
            # Context window
            if "context window" in err.lower() or "exceeds the context" in err.lower():
                print(f"[{_LABEL} Error] " + _("Input exceeds the context window."))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []

            # 400 BadRequest (zhipuai SDK raises APIStatusError)
            status, body_str = _get_zai_client_error_info(e)
            if status == 400 or (
                _ZhipuaiAPIStatusError is not None
                and isinstance(e, _ZhipuaiAPIStatusError)
                and status in (None, 400)
            ):
                err_text_lower = err.lower()
                if "does not support tools" in err_text_lower:
                    print(
                        f"[{_LABEL} Error] Model does not support tools. "
                        "Auto-disabling tools and retrying..."
                    )
                    from .. import core as _core_module
                    _core_module.tools_enabled = False
                    send_tools_this_round = False
                    req_tools = None
                    continue
                if "does not support thinking" in err_text_lower:
                    print(
                        f"[{_LABEL} Error] Model does not support thinking. "
                        "Disabling thinking via UAGENT_REASONING=off and retrying..."
                    )
                    import os
                    os.environ["UAGENT_REASONING"] = "off"
                    continue
                if (
                    "insufficient tool messages" in err_text_lower
                    and not tool_repair_attempted
                ):
                    print(
                        f"[{_LABEL} Error] 400 BadRequest - 'insufficient tool messages'"
                    )
                    _diagnose_message_structure(call_messages)
                    if _repair_incomplete_tool_sequences(call_messages):
                        tool_repair_attempted = True
                        print(
                            f"[{_LABEL}] Repaired incomplete tool sequences, retrying...",
                            file=sys.stderr,
                        )
                        continue
                    print(
                        f"[{_LABEL}] " + _("Repair did not change messages, giving up."),
                        file=sys.stderr,
                    )
                print(f"[{_LABEL} Error] " + _("400 BadRequest"))
                if body_str:
                    print(f"[{_LABEL} Error] " + _("Response body: %(body)s") % {"body": body_str[:500]})
                print(repr(e))
                return False, client, "", "", []

            # Connection error
            if _ZhipuaiAPIConnectionError is not None and isinstance(
                e, _ZhipuaiAPIConnectionError
            ):
                print(f"[{_LABEL} Error] " + _("Connection error"))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []

            if isinstance(e, URLError):
                print(_("[Network Error]"))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []

            print(
                f"[{_LABEL} Error] "
                + _("An error occurred while generating a response.")
            )
            _maybe_print_certifi_where(e)
            print(repr(e))
            return False, client, "", "", []
