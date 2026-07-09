"""Grok-specific round implementation using xai_sdk (gRPC).

Only management tools (tool_catalog, tool_load, unload_tool) are sent to the model.
Supports both streaming and non-streaming via xai_sdk.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Optional

from .env_utils import env_get


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
    print("\n".join(parts), file=sys.stderr, flush=True)


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
                    create_kwargs["max_tokens"] = int(max_tokens_env)
                except ValueError:
                    pass

            top_p_env = (env_get("UAGENT_TOP_P") or "").strip()
            if top_p_env:
                try:
                    create_kwargs["top_p"] = float(top_p_env)
                except ValueError:
                    pass

            reasoning_effort_env = (env_get("UAGENT_REASONING_EFFORT") or "").strip().lower()
            if reasoning_effort_env:
                effort_map = {
                    "none": 4,
                    "low": 1,
                    "medium": 2,
                    "high": 3,
                }
                effort_val = effort_map.get(reasoning_effort_env)
                if effort_val is not None:
                    try:
                        from xai_sdk.proto import chat_pb2
                        create_kwargs["reasoning_effort"] = chat_pb2.ReasoningEffort.Name(effort_val)
                    except Exception:
                        create_kwargs["reasoning_effort"] = reasoning_effort_env

            stop_env = (env_get("UAGENT_STOP") or "").strip()
            if stop_env:
                create_kwargs["stop"] = [s.strip() for s in stop_env.split(",") if s.strip()]

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

            response_format_env = (env_get("UAGENT_RESPONSE_FORMAT") or "").strip().lower()
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
                assistant_text, tool_calls_list = parse_xai_stream(stream_iter)
                _debug_log(
                    "stream_xai_done",
                    assistant_text_len=len(assistant_text),
                    tool_calls=len(tool_calls_list),
                )
            else:
                resp = chat.sample()
                assistant_text, tool_calls_list = parse_xai_response(resp)
                _debug_log(
                    "nonstream_xai_done",
                    assistant_text_len=len(assistant_text),
                    tool_calls=len(tool_calls_list),
                )

            # --- Loop detection for management tools ---
            if tool_calls_list:
                mgmt_tools = {"tool_catalog", "tool_load", "unload_tool"}
                mgmt_count = sum(
                    1
                    for tc in tool_calls_list
                    if tc.get("function", {}).get("name") in mgmt_tools
                )
                if mgmt_count == len(tool_calls_list) and len(tool_calls_list) > 0:
                    _debug_log(
                        "mgmt_only_tool_calls",
                        names=[tc["function"]["name"] for tc in tool_calls_list],
                    )
                    from .uagent_llm import _TOOL_CALL_FINGERPRINTS

                    _LOOP_THRESHOLD = 4
                    for tc in tool_calls_list:
                        _fn = tc.get("function", {})
                        _name = _fn.get("name", "")
                        _args_raw = _fn.get("arguments", "{}")
                        try:
                            _args_parsed = (
                                json.loads(_args_raw)
                                if isinstance(_args_raw, str)
                                else _args_raw
                            )
                        except Exception:
                            _args_parsed = _args_raw
                        _fp = json.dumps(
                            {"name": _name, "args": _args_parsed},
                            sort_keys=True,
                            ensure_ascii=False,
                        )
                        _TOOL_CALL_FINGERPRINTS[_fp] = (
                            _TOOL_CALL_FINGERPRINTS.get(_fp, 0) + 1
                        )
                        if _TOOL_CALL_FINGERPRINTS[_fp] >= _LOOP_THRESHOLD:
                            print(
                                "[GROK] Management tool call '%(name)s' repeated %(n)d times; "
                                "aborting to prevent loop."
                                % {"name": _name, "n": _TOOL_CALL_FINGERPRINTS[_fp]}
                            )
                            return True, client, "", []

            # Break out of retry loop on success
            break

        except Exception as e:
            # gRPC errors from xai_sdk
            import grpc

            if isinstance(e, grpc.RpcError):
                status_code = e.code() if hasattr(e, "code") else None
                if status_code == grpc.StatusCode.INVALID_ARGUMENT:
                    print("[GROK Error] 400 InvalidArgument")
                    print(f"[GROK Error] {e}")
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
                        recreate_client_fn=(lambda: (make_client_fn(core)[1])),
                    )
                    if action == "retry":
                        if new_client is not None:
                            client = new_client
                        continue
                    if action == "give_up":
                        print(
                            f"[GROK Error] 429 retry limit ({max_retries_429}) reached."
                        )
                        _maybe_print_certifi_where(e)
                        print(repr(e))
                        return False, client, "", []
                    print("[GROK Error] Rate limit error.")
                    _maybe_print_certifi_where(e)
                    print(repr(e))
                    return False, client, "", []
                elif status_code == grpc.StatusCode.UNAVAILABLE:
                    print("[GROK Error] Unavailable")
                    _maybe_print_certifi_where(e)
                    print(repr(e))
                    return False, client, "", []
                elif status_code == grpc.StatusCode.DEADLINE_EXCEEDED:
                    print("[GROK Error] Deadline exceeded")
                    _maybe_print_certifi_where(e)
                    print(repr(e))
                    return False, client, "", []
                else:
                    print(f"[GROK Error] gRPC error ({status_code})")
                    _maybe_print_certifi_where(e)
                    print(repr(e))
                    return False, client, "", []

            if isinstance(e, URLError):
                print("[GROK Error] Network error")
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
                recreate_client_fn=(lambda: (make_client_fn(core)[1])),
            )
            if action == "retry":
                if new_client is not None:
                    client = new_client
                continue
            if action == "give_up":
                print(f"[GROK Error] 429 retry limit ({max_retries_429}) reached.")
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", []
            import traceback

            print("[GROK Error] Unexpected exception.")
            traceback.print_exc()
            _maybe_print_certifi_where(e)
            print(repr(e))
            return False, client, "", []

    # Ensure assistant_text ends with newline for clean display
    if assistant_text and not assistant_text.endswith("\n"):
        assistant_text += "\n"
    return True, client, assistant_text, tool_calls_list
