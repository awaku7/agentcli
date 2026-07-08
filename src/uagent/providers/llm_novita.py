"""Novita AI chat completion helper.

Compared to the DeepSeek path (llm_deepseek.py):

- Novita's reasoning models use a standard OpenAI-compatible Chat Completions
  API with no extra_body / thinking.type / reasoning_effort parameters.
- ``reasoning_content`` is returned in the same format as DeepSeek's API,
  so we reuse ``parse_deepseek_response`` and ``parse_deepseek_stream``.
- ``build_assistant_message_with_reasoning`` is also reused.
- No temperature suppression in thinking mode (Novita handles it server-side).
- No tool repair complexity (Novita uses standard OpenAI tool format).
"""

from __future__ import annotations

import json
import sys
from typing import Any
from urllib.error import URLError

try:
    from openai import APIConnectionError, BadRequestError
except Exception:
    APIConnectionError = None
    BadRequestError = None

from .. import tools as _tools
from ..env_utils import env_get
from ..i18n import _
from ..llm_errors import _rate_limit_retry_step
from ..llm_helpers import _maybe_print_certifi_where

# Reuse DeepSeek response parsers (same OpenAI SDK response format)
from .llm_deepseek import (
    parse_deepseek_response,
    parse_deepseek_stream,
    _strip_reasoning_content_no_tool,
)

_LABEL = "Novita"
_ENV_PREFIX = "UAGENT_NOVITA"


# ---------------------------------------------------------------------------
# chat_kwargs builder
# ---------------------------------------------------------------------------


def build_novita_chat_kwargs(
    *,
    depname: str,
    call_messages: list[dict[str, Any]],
    send_tools: bool,
    req_tools: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Build the kwargs dict for ``client.chat.completions.create``.

    Novita uses a standard OpenAI-compatible API. No special parameters
    like extra_body, reasoning_effort, or thinking.type are needed.
    """
    # Strip reasoning_content from incoming messages to avoid issues.
    clean_messages = _strip_reasoning_content_no_tool(call_messages)

    chat_kwargs: dict[str, Any] = {
        "model": depname,
        "messages": clean_messages,
    }

    if send_tools and req_tools:
        chat_kwargs["tools"] = req_tools
        chat_kwargs["tool_choice"] = "auto"

    # temperature
    temp_env = (
        env_get(f"{_ENV_PREFIX}_TEMPERATURE") or env_get("UAGENT_TEMPERATURE") or ""
    ).strip()
    try:
        resolved_temp = float(temp_env) if temp_env else 0.0
    except ValueError:
        resolved_temp = 0.0
    chat_kwargs["temperature"] = resolved_temp

    return chat_kwargs


# ---------------------------------------------------------------------------
# Main chat completion round
# ---------------------------------------------------------------------------


def novita_chat_with_tools(
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
    """Run one Novita AI chat completion round.

    Returns ``(ok, client, assistant_text, reasoning_content, tool_calls_list)``.
    """
    attempt_429 = 0

    req_tools = _tools.get_tool_specs() if send_tools_this_round else None

    while True:
        try:
            chat_kwargs = build_novita_chat_kwargs(
                depname=depname,
                call_messages=call_messages,
                send_tools=send_tools_this_round,
                req_tools=req_tools,
            )

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
                provider="novita",
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
            # 400 BadRequest
            if BadRequestError is not None and isinstance(e, BadRequestError):
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
                print(f"[{_LABEL} Error] " + _("400 BadRequest"))
                print(
                    f"[{_LABEL} Error] "
                    + _("Error code: %(code)d - %(err)s") % {"code": 400, "err": e}
                )
                return False, client, "", "", []
            if APIConnectionError is not None and isinstance(e, APIConnectionError):
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
