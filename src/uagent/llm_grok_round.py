"""Grok-specific round implementation using xai_sdk (gRPC).

Only management tools (tool_catalog, tool_load, unload_tool) are sent to the model.
Supports both streaming and non-streaming via xai_sdk.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Optional

from .env_utils import env_get
from .i18n import _


def _debug_log(prefix: str, **kwargs: Any) -> None:
    if (env_get("UAGENT_DEBUG_GROK") or "").strip() not in ("1", "true", "yes"):
        return
    parts = [f"[GROK_ROUND] {prefix}"]
    for k, v in kwargs.items():
        try:
            vs = json.dumps(v, ensure_ascii=False)[:3000]
        except Exception:
            vs = str(v)[:3000]
        parts.append(f"  {k}={vs}")
    print("\n".join(parts), file=sys.__stderr__, flush=True)


def _resolve_grok_reasoning_effort() -> tuple[str | None, bool]:
    """Resolve Grok reasoning_effort from env.

    Preference:
      1) UAGENT_REASONING (shared UI/CLI: off/auto/minimal/low/medium/high/xhigh/max)
      2) UAGENT_REASONING_EFFORT (legacy Grok-only: none/low/medium/high)

    Returns:
      (effort, is_auto) where effort is one of none/low/medium/high, or None to
      omit the parameter. is_auto is True when the source value was auto (or an
      auto alias), so callers can show LLM:auto-><effort> in the CLI status.
    Unsupported values are rounded to the nearest supported level.
    """
    raw = (env_get("UAGENT_REASONING") or "").strip().lower()
    source = "UAGENT_REASONING"
    if not raw:
        raw = (env_get("UAGENT_REASONING_EFFORT") or "").strip().lower()
        source = "UAGENT_REASONING_EFFORT"
    if not raw:
        return None, False

    # off / disabled => omit (model default), not forced none
    if raw in ("off", "0", "false", "no", "disable", "disabled"):
        return None, False

    # Direct / legacy aliases
    if raw in ("none",):
        return "none", False
    if raw in ("low", "1", "min", "minimal"):
        return "low", False
    if raw in ("auto", "a"):
        # auto: no task-aware heuristic for Grok; use medium
        return "medium", True
    if raw in ("medium", "2", "mid", "middle"):
        return "medium", False
    if raw in ("high", "3"):
        return "high", False
    if raw in ("xhigh", "xh", "x-high", "4", "max", "m", "5"):
        # xhigh/max are above Grok's high; clamp to high
        return "high", False

    # Unknown value: try coarse rounding by keyword, else medium
    if any(k in raw for k in ("max", "xhigh", "ultra", "highest")):
        return "high", False
    if "high" in raw:
        return "high", False
    if "auto" in raw:
        return "medium", True
    if any(k in raw for k in ("med", "mid", "normal", "default")):
        return "medium", False
    if any(k in raw for k in ("low", "min", "light", "small")):
        return "low", False
    if any(k in raw for k in ("none", "off", "disable", "no")):
        return None, False

    _debug_log(
        "unknown_reasoning_rounded",
        source=source,
        raw=raw,
        rounded="medium",
    )
    return "medium", False


def _set_grok_reasoning_status(core: Any, effort: str | None, is_auto: bool) -> None:
    """Mirror OpenAI/Claude status labels for Grok reasoning effort."""
    if not effort:
        return
    label = f"LLM:auto->{effort}" if is_auto else f"LLM:{effort}"
    try:
        core.set_status(True, label)
    except Exception:
        pass


def _call_grok_round(
    *,
    provider: str,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    use_responses_api: bool,  # keep for backward compat; ignored, always gRPC
    stream_responses: bool,
    send_tools_this_round: bool | None = None,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
    messages: list[dict[str, Any]] = None,
    responses_state: Optional[dict] = None,
) -> Any:
    """Run a single Grok (xAI) round using xai_sdk (gRPC).

    Returns (ok, client, assistant_text, tool_calls_list).
    """
    attempt_429 = 0
    assistant_text: str = ""
    tool_calls_list: list[dict[str, Any]] = []

    if send_tools_this_round is None:
        from .llm_helpers import _env_default_on

        send_tools_this_round = _env_default_on("UAGENT_USE_TOOL")

    from .llm_errors import _rate_limit_retry_step
    from .llm_helpers import _maybe_print_certifi_where
    from urllib.error import URLError

    from .providers.llm_grok import (
        build_xai_messages,
        build_xai_tools,
        parse_xai_response,
        parse_xai_stream,
    )

    while True:
        try:
            # --- Build messages and tools ---
            instructions_str, xai_msgs = build_xai_messages(call_messages)
            req_tools = build_xai_tools(
                send_tools_this_round, call_messages=call_messages
            )

            # --- Resolve temperature ---
            default_temp = 0.2
            temp_env = (env_get("UAGENT_GROK_TEMPERATURE") or "").strip()
            if not temp_env:
                temp_env = (env_get("UAGENT_TEMPERATURE") or "").strip()
            resolved_temp = default_temp
            if temp_env:
                try:
                    resolved_temp = float(temp_env)
                except ValueError:
                    pass

            # --- Build create() kwargs ---
            create_kwargs: dict[str, Any] = {
                "model": depname,
                "messages": xai_msgs,
            }
            if send_tools_this_round and req_tools:
                create_kwargs["tools"] = req_tools
                create_kwargs["tool_choice"] = "auto"
            create_kwargs["temperature"] = resolved_temp

            # --- Optional parameters (environment-driven) ---
            max_tokens_env = (env_get("UAGENT_MAX_TOKENS") or "").strip()
            if max_tokens_env:
                try:
                    from .llmcapa_util import clamp_max_tokens

                    create_kwargs["max_tokens"] = clamp_max_tokens(
                        int(max_tokens_env), depname, "grok"
                    )
                except ValueError:
                    pass

            top_p_env = (env_get("UAGENT_TOP_P") or "").strip()
            if top_p_env:
                try:
                    create_kwargs["top_p"] = float(top_p_env)
                except ValueError:
                    pass

            # Map UAGENT_REASONING (preferred) / UAGENT_REASONING_EFFORT (legacy)
            # onto xAI reasoning_effort: none|low|medium|high.
            # Unsupported levels are rounded to the nearest supported value.
            reasoning_effort, reasoning_is_auto = _resolve_grok_reasoning_effort()
            if reasoning_effort is not None:
                create_kwargs["reasoning_effort"] = reasoning_effort
            _set_grok_reasoning_status(core, reasoning_effort, reasoning_is_auto)

            stop_env = (env_get("UAGENT_STOP") or "").strip()
            if stop_env:
                create_kwargs["stop"] = [
                    s.strip() for s in stop_env.split(",") if s.strip()
                ]

            seed_env = (env_get("UAGENT_SEED") or "").strip()
            if seed_env:
                try:
                    create_kwargs["seed"] = int(seed_env)
                except ValueError:
                    pass

            frequency_penalty_env = (env_get("UAGENT_FREQUENCY_PENALTY") or "").strip()
            if frequency_penalty_env:
                try:
                    create_kwargs["frequency_penalty"] = float(frequency_penalty_env)
                except ValueError:
                    pass

            presence_penalty_env = (env_get("UAGENT_PRESENCE_PENALTY") or "").strip()
            if presence_penalty_env:
                try:
                    create_kwargs["presence_penalty"] = float(presence_penalty_env)
                except ValueError:
                    pass

            response_format_env = (
                (env_get("UAGENT_RESPONSE_FORMAT") or "").strip().lower()
            )
            if response_format_env:
                if response_format_env == "json":
                    try:
                        from xai_sdk.proto import chat_pb2

                        create_kwargs["response_format"] = chat_pb2.ResponseFormat(
                            format_type=chat_pb2.FormatType.FORMAT_TYPE_JSON_SCHEMA,
                            json_schema={"type": "object"},
                        )
                    except Exception:
                        create_kwargs["response_format"] = {"type": "json_object"}

            # Add instructions as system message already included in xai_msgs

            _debug_log(
                "request_xai",
                model=depname,
                tools_count=len(req_tools) if req_tools else 0,
                messages_count=len(xai_msgs),
            )

            # --- Call API via xai_sdk ---
            # Create a new chat instance each round (simpler than reusing chat objects)
            chat = client.chat.create(**create_kwargs)

            if stream_responses:
                stream_iter = chat.stream()
                assistant_text, tool_calls_list = parse_xai_stream(
                    stream_iter, core=core
                )
                _debug_log(
                    "stream_xai_done",
                    assistant_text_len=len(assistant_text),
                    tool_calls=len(tool_calls_list),
                )
            else:
                resp = chat.sample()
                assistant_text, tool_calls_list = parse_xai_response(resp, core=core)
                _debug_log(
                    "nonstream_xai_done",
                    assistant_text_len=len(assistant_text),
                    tool_calls=len(tool_calls_list),
                )

            # Management-tool loop detection is handled once in uagent_llm._run_one_round
            # (check_mgmt_tool_loop). Do not count here to avoid double-counting
            # when Grok loads several tools in parallel.

            # Break out of retry loop on success
            break

        except Exception as e:
            # gRPC errors from xai_sdk
            import grpc

            if isinstance(e, grpc.RpcError):
                status_code = e.code() if hasattr(e, "code") else None
                if status_code == grpc.StatusCode.INVALID_ARGUMENT:
                    print("[GROK Error] " + _("400 InvalidArgument"))
                    print("[GROK Error] " + str(e))
                    return False, client, "", []
                elif status_code == grpc.StatusCode.RESOURCE_EXHAUSTED:
                    attempt_429, new_client, action = _rate_limit_retry_step(
                        exception=e,
                        provider=provider,
                        model=depname,
                        attempt=attempt_429,
                        max_retries=max_retries_429,
                        base=retry_base,
                        cap=retry_cap,
                        recreate_client_fn=(lambda: make_client_fn(core)[1]),
                    )
                    if action == "retry":
                        if new_client is not None:
                            client = new_client
                        continue
                    if action == "give_up":
                        print(
                            "[GROK Error] "
                            + _("429 retry limit (%(n)s) reached.")
                            % {"n": max_retries_429}
                        )
                        _maybe_print_certifi_where(e)
                        print(repr(e))
                        return False, client, "", []
                    print("[GROK Error] " + _("Rate limit error."))
                    _maybe_print_certifi_where(e)
                    print(repr(e))
                    return False, client, "", []
                elif status_code == grpc.StatusCode.UNAVAILABLE:
                    from .providers.util_providers import (
                        is_ssl_cert_error,
                        set_ssl_verify_disabled,
                    )

                    if is_ssl_cert_error(e):
                        print(
                            "[GROK Error] "
                            + _(
                                "SSL certificate verification failed. "
                                "Auto-disabling SSL verify and retrying..."
                            )
                        )
                        _maybe_print_certifi_where(e)
                        set_ssl_verify_disabled(True)
                        new_client = make_client_fn(core)[1]
                        if new_client is not None:
                            client = new_client
                        continue
                    print("[GROK Error] " + _("Unavailable"))
                    _maybe_print_certifi_where(e)
                    print(repr(e))
                    return False, client, "", []
                elif status_code == grpc.StatusCode.DEADLINE_EXCEEDED:
                    print("[GROK Error] " + _("Deadline exceeded"))
                    _maybe_print_certifi_where(e)
                    print(repr(e))
                    return False, client, "", []
                else:
                    print(
                        "[GROK Error] "
                        + _("gRPC error (%(code)s)") % {"code": status_code}
                    )
                    _maybe_print_certifi_where(e)
                    print(repr(e))
                    return False, client, "", []

            if isinstance(e, URLError):
                print("[GROK Error] " + _("Network error"))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", []

            attempt_429, new_client, action = _rate_limit_retry_step(
                exception=e,
                provider=provider,
                model=depname,
                attempt=attempt_429,
                max_retries=max_retries_429,
                base=retry_base,
                cap=retry_cap,
                recreate_client_fn=(lambda: make_client_fn(core)[1]),
            )
            if action == "retry":
                if new_client is not None:
                    client = new_client
                continue
            if action == "give_up":
                print(
                    "[GROK Error] "
                    + _("429 retry limit (%(n)s) reached.") % {"n": max_retries_429}
                )
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", []
            import traceback

            print("[GROK Error] " + _("Unexpected exception."))
            traceback.print_exc()
            _maybe_print_certifi_where(e)
            print(repr(e))
            return False, client, "", []

    # Ensure assistant_text ends with newline for clean display
    if assistant_text and not assistant_text.endswith("\n"):
        assistant_text += "\n"
    return True, client, assistant_text, tool_calls_list
