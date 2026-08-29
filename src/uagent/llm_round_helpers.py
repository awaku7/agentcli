from __future__ import annotations

import json
import traceback
import uuid
from urllib.error import URLError
from typing import Any, Optional

try:
    from openai import APIConnectionError, APIResponseValidationError, BadRequestError
except Exception:
    APIConnectionError = None
    APIResponseValidationError = None
    BadRequestError = None

from . import tools
from .llm_errors import _rate_limit_retry_step
from .reasoning_display import show_reasoning
from .llm_message_helpers import _get_shrink_max_tokens
from .providers.llm_gemini import gemini_chat_with_tools
from .providers.llm_claude import (
    claude_chat_with_tools,
    build_claude_output_config_for_effort,
)
from .providers.llm_openai_responses import build_responses_request
from .providers.responses_common import (
    parse_responses_response,
    parse_responses_stream,
    parse_assistant_text_tool_calls,
)
from .providers.llm_bedrock_responses import build_bedrock_responses_request
from .tools.llm_tool_narrowing import (
    _is_gpt54_tool_search_target,
    _is_legacy_mode,
    _select_tool_specs_legacy,
)
from .providers.llm_openrouter import (
    apply_openrouter_extra_body,
    apply_openrouter_tool_schema_compat,
    finalize_tool_schema_sync,
    apply_openrouter_fallback_models,
)
from .providers.llm_openrouter_responses import apply_openrouter_responses_compat
from .providers.llm_ollama import apply_ollama_extra_body
from .providers.llm_llama_cpp import apply_llama_cpp_extra_body
from .providers.structured_output import (
    apply_openai_chat_structured_output,
    apply_openai_responses_structured_output,
    structured_output_request,
)
from .providers.llm_ollama_responses import apply_ollama_responses_compat
from .providers.llm_deepseek import (
    _normalize_chat_image_content,
    deepseek_chat_with_tools,
)
from .providers.llm_pfn import pfn_chat_with_tools
from .providers.llm_deepseek_responses import apply_deepseek_responses_compat
from .providers.llm_zai import zai_chat_with_tools
from .providers.llm_novita import novita_chat_with_tools
from .providers.llm_together import together_chat_with_tools
from .providers.llm_vercel import vercel_chat_with_tools
from .llm_helpers import (
    LLMWaitInterrupted,
    _auto_low_quality,
    _bump_effort,
    _choose_auto_effort,
    _env_default_on,
    _extract_latest_user_text,
    _is_thinking_task,
    _maybe_print_certifi_where,
)
from .env_utils import env_get
from .i18n import _
from .llm_helpers import _env_default_true
from .translate import translate_text


def _openai_fast_mode_enabled() -> bool:
    """Return whether OpenAI Fast mode should be requested.

    Fast mode is an OpenAI-only request option. Keep the switch provider
    specific so OpenAI-compatible gateways and Azure do not receive an
    unsupported ``service_tier`` parameter.
    """
    raw = (env_get("UAGENT_OPENAI_FAST_MODE") or "").strip().lower()
    return raw in {"1", "true", "yes", "on", "fast"}


def _apply_llama_cpp_reasoning_kwargs(chat_kwargs: dict[str, Any]) -> None:
    """Map the shared reasoning preference to llama.cpp chat-template kwargs.

    llama-server's Qwen-style templates use ``enable_thinking`` rather than
    provider-neutral reasoning effort values.  Leave unset/``auto`` alone so
    the model/template default remains in control.  This is llama.cpp-only;
    Ollama has a separate, model-dependent thinking API.
    """
    # These are llama-server fields, not parameters declared by the OpenAI
    # Python SDK. Put them in extra_body so Completions.create does not reject
    # the request before it reaches llama-server (notably with Qwen).
    extra_body = chat_kwargs.get("extra_body")
    if not isinstance(extra_body, dict):
        extra_body = {}
    extra_body["reasoning_format"] = "deepseek"
    reasoning = (env_get("UAGENT_REASONING") or "").strip().lower()
    if reasoning == "off":
        extra_body["chat_template_kwargs"] = {"enable_thinking": False}
    elif reasoning in {"minimal", "low", "medium", "high", "xhigh", "max"}:
        extra_body["chat_template_kwargs"] = {"enable_thinking": True}
    chat_kwargs["extra_body"] = extra_body


def _translate_call_messages(
    call_messages: list[dict[str, Any]], tr_cfg: Any
) -> list[dict[str, Any]]:
    translated_call_messages = call_messages
    if tr_cfg is not None:
        try:
            translated_call_messages = []
            for m in call_messages:
                role = m.get("role")
                if role in ("system", "user", "assistant"):
                    content = m.get("content")
                    if isinstance(content, str) and content.strip():
                        src_lang = ""
                        out, diag = translate_text(
                            content,
                            direction="to_llm",
                            src_lang=src_lang,
                            cfg=tr_cfg,
                        )
                        nm = dict(m)
                        nm["content"] = out
                        translated_call_messages.append(nm)
                        continue
                translated_call_messages.append(m)
        except Exception:
            pass

    return translated_call_messages


def _resolve_round_runtime_flags(
    *, tr_cfg: Any, core: Any, provider: str = "", depname: str = ""
) -> Any:
    lmstudio_transport = (
        (env_get("UAGENT_LMSTUDIO_TRANSPORT", "") or "").lower().strip()
    )
    if provider == "lmstudio" and lmstudio_transport in {
        "sdk",
        "chat",
        "chat_completions",
    }:
        # The LM Studio Python SDK exposes native chat prediction, not the
        # OpenAI Responses client surface.
        responses_env = "0"
    elif provider == "lmstudio" and lmstudio_transport in {"responses", "response"}:
        responses_env = "1"
    else:
        responses_env = (env_get("UAGENT_RESPONSES", "") or "").lower().strip()

    if responses_env in ("1", "true"):
        if provider == "lmstudio":
            from .providers.llm_lmstudio import responses_endpoint_available

            use_responses_api = responses_endpoint_available(core)
        else:
            use_responses_api = True
    elif responses_env in ("0", "false", "no", "off"):
        use_responses_api = False
    else:
        # LM Studio defaults to Responses, but only when the running server
        # actually exposes the endpoint (added in LM Studio v0.3.29).
        if provider == "lmstudio":
            from .providers.llm_lmstudio import responses_endpoint_available

            use_responses_api = responses_endpoint_available(core)
        else:
            # Auto-enable when provider/model can use Responses API
            from .llmcapa_util import provider_allows_responses_api

            use_responses_api = provider_allows_responses_api(provider, depname or None)

    stream_responses = _env_default_true("UAGENT_STREAMING", default=True)

    # LM Studio SDK's ``act()`` owns the tool-call loop and returns a completed
    # result rather than an OpenAI-compatible delta iterator. Avoid passing a
    # completed SDK result through the outer streaming parser when tools are on.
    if (
        provider == "lmstudio"
        and lmstudio_transport == "sdk"
        and bool(getattr(core, "tools_enabled", False))
    ):
        stream_responses = False

    # If translation is enabled, disable streaming to avoid mismatched partial outputs.
    # (We translate per-call, not per-delta.)
    if tr_cfg is not None and (
        (tr_cfg.to_llm or "").strip() or (tr_cfg.from_llm or "").strip()
    ):
        stream_responses = False

    # If using Responses API and reasoning=auto, disable streaming so we can retry once
    # (and avoid mixed partial outputs that cannot be "taken back").
    if use_responses_api and stream_responses:
        _r0 = (env_get("UAGENT_REASONING") or "").strip().lower()
        if _r0 == "auto":
            stream_responses = False
            try:
                core.set_status(True, "LLM:auto")
            except Exception:
                pass

    return use_responses_api, stream_responses


def _translate_assistant_if_needed(
    *,
    assistant_text: str,
    tr_cfg: Any,
    use_responses_api: bool,
    stream_responses: bool,
) -> str:
    # Translate assistant output (if enabled; avoid responses+streaming double output)
    if (
        tr_cfg is not None
        and isinstance(assistant_text, str)
        and assistant_text.strip()
        and not (use_responses_api and stream_responses)
    ):
        out, diag = translate_text(
            assistant_text,
            direction="from_llm",
            src_lang="",
            cfg=tr_cfg,
        )
        if diag:
            # Non-fatal: keep original output and show diagnostics.
            print(_("[Translate Error] %(diag)s") % {"diag": diag})
        else:
            assistant_text = out

    return assistant_text


def _call_gemini_round(
    *,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    gemini_cache_name: Any,
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
    stream_responses: bool,
    force_thinking_level: str | None = None,
    send_tools: bool = True,
    provider: str = "gemini",
) -> Any:
    attempt_429 = 0
    gemini_content_dump: dict[str, Any] = {}
    assistant_text = ""
    tool_calls_list: list[dict[str, Any]] = []

    while True:
        try:
            assistant_text, tool_calls_list, gemini_content_dump = call_maybe_thread_fn(
                lambda: gemini_chat_with_tools(
                    client,
                    depname,
                    call_messages,
                    cached_content=gemini_cache_name,
                    stream=stream_responses,
                    core=core,
                    force_thinking_level=force_thinking_level,
                    send_tools=send_tools,
                    provider=provider,
                )
            )
            break
        except LLMWaitInterrupted:
            # Keep the interrupt flag set so _run_one_round() performs the
            # common stop-prompt/RS_BREAK handling.
            return True, client, "", [], {}
        except Exception as e:
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
                    "[Claude Error] "
                    + _("429 retry limit (%(max_retries)s) reached.")
                    % {"max_retries": max_retries_429}
                )
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", [], {}
            msg = str(e)
            if force_thinking_level is None and (
                "Thinking level MINIMAL is not supported for this model" in msg
                or "thinking level minimal is not supported for this model"
                in msg.lower()
            ):
                try:
                    from .util_tools import set_reasoning_mode

                    set_reasoning_mode("medium")
                except Exception:
                    pass
                force_thinking_level = "medium"
                try:
                    core.set_status(True, "LLM:medium")
                except Exception:
                    pass
                continue
            print(_("[Gemini Error] An error occurred while generating a response."))
            _maybe_print_certifi_where(e)
            print(repr(e))
            return False, client, "", [], {}

    return True, client, assistant_text, tool_calls_list, gemini_content_dump


def _call_claude_round(
    *,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
    send_tools: bool = True,
    provider: str = "claude",
) -> Any:
    attempt_429 = 0
    assistant_text = ""
    tool_calls_list: list[dict[str, Any]] = []

    while True:
        try:
            # Map UAGENT_REASONING -> Claude output_config.effort (best-effort)
            _reasoning = (env_get("UAGENT_REASONING") or "").strip().lower()
            _auto_user_text = ""
            _effort_used = None

            if _reasoning in ("minimal", "low", "medium", "high", "xhigh"):
                _effort_used = _reasoning
            elif _reasoning == "auto":
                _auto_user_text = _extract_latest_user_text(call_messages)
                if _is_thinking_task(_auto_user_text):
                    _effort_used = _choose_auto_effort(_auto_user_text)

            _claude_out_cfg = (
                build_claude_output_config_for_effort(depname, _effort_used)
                if _effort_used
                else None
            )
            _claude_structured = structured_output_request(call_messages)
            if _claude_structured is not None:
                try:
                    from .llmcapa_util import supports_json_schema

                    if supports_json_schema(depname, provider) is not True:
                        _claude_structured = None
                except Exception:
                    _claude_structured = None
            if _claude_structured is not None:
                if not isinstance(_claude_out_cfg, dict):
                    _claude_out_cfg = {}
                if _claude_structured.get("type") == "json_schema":
                    _claude_out_cfg["format"] = {
                        "type": "json_schema",
                        "schema": _claude_structured["json_schema"]["schema"],
                    }
                else:
                    _claude_out_cfg["format"] = {
                        "type": "json_schema",
                        "schema": {"type": "object"},
                    }
            if _claude_out_cfg is not None:
                try:
                    if _reasoning == "auto":
                        core.set_status(True, f"LLM:auto->{_effort_used}")
                    else:
                        core.set_status(True, f"LLM:{_effort_used}")
                except Exception:
                    pass

            def _on_output_config_info(m: str) -> None:
                if getattr(core, "_last_claude_outcfg_info", None) != m:
                    print(m)
                setattr(core, "_last_claude_outcfg_info", m)

            assistant_text, tool_calls_list = call_maybe_thread_fn(
                lambda: claude_chat_with_tools(
                    client,
                    depname,
                    call_messages,
                    output_config=_claude_out_cfg,
                    on_output_config_info=_on_output_config_info,
                    on_output_config_fallback=lambda m: print(m),
                    send_tools=send_tools,
                    core=core,
                )
            )
            break
        except Exception as e:
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
                    "[Claude Error] "
                    + _("429 retry limit (%(max_retries)s) reached.")
                    % {"max_retries": max_retries_429}
                )
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", []
            print(_("[Claude Error] An error occurred while generating a response."))
            _maybe_print_certifi_where(e)
            print(repr(e))
            return False, client, "", []

    return True, client, assistant_text, tool_calls_list


def _call_openai_azure_round(
    *,
    provider: str,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    use_responses_api: bool,
    stream_responses: bool,
    send_tools_this_round: bool | None = None,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
    messages: list[dict[str, Any]] = None,
    responses_state: Optional[dict] = None,
) -> Any:
    # PLaMo is OpenAI-compatible at the transport level, but its documented
    # tool schema/streaming contract differs. Keep its request/response path
    # isolated from the generic OpenAI/Azure implementation.
    if provider == "pfn":
        return pfn_chat_with_tools(
            client=client,
            depname=depname,
            call_messages=call_messages,
            core=core,
            make_client_fn=make_client_fn,
            call_maybe_thread_fn=call_maybe_thread_fn,
            send_tools_this_round=bool(send_tools_this_round),
            max_retries_429=max_retries_429,
            retry_base=retry_base,
            retry_cap=retry_cap,
        )

    attempt_429 = 0
    assistant_text: str = ""
    reasoning_content: str = ""
    tool_calls_list: list[dict[str, Any]] = []
    if core is not None:
        try:
            setattr(core, "_last_responses_output_items", None)
            if use_responses_api and provider in ("openai", "azure", "lmstudio"):
                setattr(core, "_responses_client", client)
                setattr(core, "_responses_provider", provider)
                setattr(core, "_responses_model", depname)
        except Exception:
            pass
    resp = None
    resp_kwargs: dict[str, Any] = {}
    chat_kwargs: dict[str, Any] = {}

    # Respect the caller's send_tools_this_round (which reflects core.tools_enabled).
    # Only fall back to env var if the caller didn't set it.
    if send_tools_this_round is None:
        send_tools_this_round = _env_default_on("UAGENT_USE_TOOL")

    # Track whether thinking/reasoning has been disabled due to model rejection
    _thinking_disabled = False
    # Track whether previous_response_id caused a stale error; if so, stop using it
    _stale_rid_retried = False

    def _clear_stale_rid_after_success() -> None:
        """Allow Responses API continuation again after a successful retry."""
        if not isinstance(responses_state, dict):
            return
        if responses_state.pop("_stale_rid_occurred", None) is not None:
            from .core import _save_responses_state

            _save_responses_state()

    while True:
        try:
            if use_responses_api:
                # Extract previous_response_id from shared state (if any)
                _prev_rid: Optional[str] = None
                if isinstance(responses_state, dict):
                    # xAI (Grok) Responses API does not reliably support
                    # previous_response_id with tools; disable it.
                    # OpenRouter Responses schema expects previous_response_id=null.
                    # DeepSeek Responses API is stateless (previous_response_id not supported).
                    if provider in ("grok", "openrouter", "deepseek"):
                        responses_state.pop("previous_response_id", None)
                    _prev_rid = responses_state.get("previous_response_id")
                    # Empty / non-resp ids are invalid for continuation.
                    if not (
                        isinstance(_prev_rid, str) and _prev_rid.startswith("resp_")
                    ):
                        _prev_rid = None
                    # Once a stale error occurred, stop using previous_response_id.
                    if responses_state.get("_stale_rid_occurred"):
                        _prev_rid = None

                # Keep previous_response_id during tool loops. The Responses
                # API expects the matching function_call_output items to be
                # submitted as the continuation of the assistant response.
                _should_track_rid = True

                use_gpt54_tool_search = _is_gpt54_tool_search_target(
                    provider=provider,
                    depname=depname,
                    use_responses_api=use_responses_api,
                )
                if use_gpt54_tool_search and _is_legacy_mode():
                    # Legacy mode: narrow tools via tool_catalog (client-side)
                    responses_tool_specs = _select_tool_specs_legacy(call_messages)
                elif use_gpt54_tool_search:
                    # Native mode: scan all tool modules from disk (bypass genre),
                    # exclude management tools. Server-side tool_search does narrowing.
                    _excluded = {"tool_catalog", "tool_load", "unload_tool"}
                    _all_tools: list[dict[str, Any]] = []
                    try:
                        from .tools._genre_control_util import _find_tool_modules
                        from .tools import is_computer_use_conflict

                        for _mname, _mod in _find_tool_modules():
                            _spec = getattr(_mod, "TOOL_SPEC", None)
                            if not isinstance(_spec, dict):
                                continue
                            if is_computer_use_conflict(_spec):
                                continue
                            _fn = _spec.get("function", {})
                            if not isinstance(_fn, dict):
                                continue
                            if _fn.get("name") in _excluded:
                                continue
                            _all_tools.append(_spec)
                    except Exception:
                        pass
                    if not _all_tools:
                        # Fallback: use already-registered tools
                        _all_tools = tools.get_tool_specs()
                    responses_tool_specs = _all_tools
                else:
                    # Standard Responses API path (non-GPT-5.4): genre-filtered + tool_catalog
                    responses_tool_specs = None
                if provider == "bedrock":
                    _bedrock_req = build_bedrock_responses_request(
                        call_messages,
                        send_tools_this_round=send_tools_this_round,
                        tool_specs=responses_tool_specs,
                    )
                    instructions_str = None
                    req_tools = _bedrock_req.get("tools")
                    resp_kwargs: dict[str, Any] = {
                        "model": depname,
                        "input": _bedrock_req.get("input", ""),
                    }
                else:
                    instructions_str, input_msgs, req_tools = build_responses_request(
                        call_messages,
                        send_tools_this_round=send_tools_this_round,
                        provider=provider,
                        tool_specs=responses_tool_specs,
                        previous_response_id=_prev_rid,
                        core=core,
                    )

                    resp_kwargs = {
                        "model": depname,
                        "input": input_msgs,
                    }

                # OpenAI Fast mode is intentionally not applied to Azure or
                # other OpenAI-compatible providers.
                if provider == "openai" and _openai_fast_mode_enabled():
                    resp_kwargs["service_tier"] = "fast"

                # Use previous_response_id for multi-turn continuity
                if _prev_rid is not None:
                    resp_kwargs["previous_response_id"] = _prev_rid

                # Server-side compaction (Responses API)
                # Uses the same threshold as local auto-shrink to trigger compaction
                # at the same point where local context would be compressed.
                _compact_threshold = _get_shrink_max_tokens(depname)
                resp_kwargs["context_management"] = [
                    {"type": "compaction", "compact_threshold": _compact_threshold}
                ]

                # Optional Responses API knobs via env (OpenAI SDK >= 2.x)
                # - UAGENT_REASONING: auto|minimal|low|medium|high|xhigh|off (unset/off => do not send)
                # - UAGENT_VERBOSITY: low|medium|high|off (unset/off => do not send)
                _reasoning = (env_get("UAGENT_REASONING") or "").strip().lower()
                _auto_user_text = ""
                _effort_used = None

                if _reasoning in ("minimal", "low", "medium", "high", "xhigh"):
                    _effort_used = _reasoning
                elif _reasoning == "auto":
                    _auto_user_text = _extract_latest_user_text(call_messages)
                    if _is_thinking_task(_auto_user_text):
                        _effort_used = _choose_auto_effort(_auto_user_text)

                if _effort_used in ("minimal", "low", "medium", "high", "xhigh"):
                    if _thinking_disabled:
                        # Model rejected thinking; skip reasoning params.
                        _effort_used = None
                    else:
                        # DeepSeek Responses API only accepts effort
                        # high/max (minimal/low/medium -> high, xhigh -> max).
                        if provider == "deepseek":
                            try:
                                from .providers.llm_deepseek import (
                                    _get_valid_deepseek_efforts,
                                    _resolve_deepseek_effort,
                                )

                                _mapped = _resolve_deepseek_effort(_effort_used)
                                if _mapped:
                                    # Validate against llmcapa model capability
                                    # (reasoning_effort_values). If the mapped
                                    # value is not accepted by the model, fall
                                    # back to the lowest valid effort.
                                    _valid = _get_valid_deepseek_efforts(depname)
                                    if _valid and _mapped not in _valid:
                                        _mapped = (
                                            "high"
                                            if "high" in _valid
                                            else sorted(_valid)[0]
                                        )
                                    _effort_used = _mapped
                            except Exception:
                                pass
                        # Send the requested effort as-is. If the backend rejects
                        # minimal/xhigh for a specific model, retry once with a
                        # fallback value below.
                        resp_kwargs["reasoning"] = {"effort": _effort_used}
                    try:
                        if _reasoning == "auto":
                            core.set_status(True, f"LLM:auto->{_effort_used}")
                        else:
                            core.set_status(True, f"LLM:{_effort_used}")
                    except Exception:
                        pass

                _verbosity = (env_get("UAGENT_VERBOSITY") or "").strip().lower()
                if _verbosity in ("low", "medium", "high"):
                    _text_cfg = resp_kwargs.get("text")
                    if not isinstance(_text_cfg, dict):
                        _text_cfg = {}
                    _text_cfg["verbosity"] = _verbosity
                    resp_kwargs["text"] = _text_cfg

                # Shared max tokens for Responses API (OpenAI/Azure/OpenRouter/etc.)
                _max_tokens_env = (env_get("UAGENT_MAX_TOKENS") or "").strip()
                if _max_tokens_env:
                    try:
                        from .llmcapa_util import clamp_max_tokens

                        resp_kwargs["max_output_tokens"] = clamp_max_tokens(
                            int(_max_tokens_env), depname, provider
                        )
                    except ValueError:
                        pass
                if instructions_str is not None:
                    resp_kwargs["instructions"] = instructions_str
                if send_tools_this_round and req_tools:
                    resp_kwargs["tools"] = req_tools
                    resp_kwargs["tool_choice"] = "auto"

                apply_openai_responses_structured_output(
                    resp_kwargs,
                    provider=provider,
                    messages=call_messages,
                    model_id=depname,
                )

                apply_openrouter_responses_compat(
                    resp_kwargs,
                    provider=provider,
                    depname=depname,
                )

                # Ollama Responses-API compatibility workarounds
                apply_ollama_responses_compat(
                    resp_kwargs,
                    provider=provider,
                    depname=depname,
                )

                # DeepSeek Responses-API compatibility workarounds
                apply_deepseek_responses_compat(
                    resp_kwargs,
                    provider=provider,
                    depname=depname,
                )

                # When using previous_response_id, the instructions from the
                # first turn are already retained by the server. Sending them
                # again is redundant and some providers (e.g. xAI) reject it.
                if _prev_rid is not None:
                    resp_kwargs.pop("instructions", None)

                if provider == "lmstudio":
                    from .providers.llm_lmstudio import apply_lmstudio_transport

                    apply_lmstudio_transport(resp_kwargs, responses=True)

                if stream_responses:
                    _stream_result = call_maybe_thread_fn(
                        lambda: parse_responses_stream(
                            client.responses.create(
                                **resp_kwargs,
                                stream=True,
                            ),
                            provider=provider,
                            # In Web mode, parse_responses_stream streams deltas via core.log_message.
                            print_delta_fn=(
                                None
                                if bool(getattr(core, "_is_web", False))
                                else (
                                    getattr(core, "print_stream_delta", None)
                                    or (
                                        lambda s: (
                                            print(s, end="", flush=True) if s else None
                                        )
                                    )
                                )
                            ),
                            core=core,
                        )
                    )
                    (
                        assistant_text,
                        reasoning_content,
                        tool_calls_list,
                        _stream_rid,
                        _stream_output_items,
                    ) = _stream_result
                    if core is not None:
                        try:
                            setattr(
                                core,
                                "_last_responses_output_items",
                                _stream_output_items,
                            )
                        except Exception:
                            pass
                    if (
                        _should_track_rid
                        and _stream_rid
                        and isinstance(responses_state, dict)
                    ):
                        responses_state["previous_response_id"] = _stream_rid
                        from .core import _save_responses_state, set_active_response

                        set_active_response(_stream_rid, status="completed")

                        _save_responses_state()
                    # A successful streaming Responses API request also clears
                    # the stale marker set by an earlier fallback.
                    _clear_stale_rid_after_success()
                    # ensure newline after streaming output
                    if (
                        assistant_text
                        and not bool(getattr(core, "_is_web", False))
                        and not assistant_text.endswith("\n")
                    ):
                        print("")
                else:

                    def _create_responses_with_effort_fallback() -> Any:
                        try:
                            return client.responses.create(**resp_kwargs)
                        except Exception as e:
                            err_text = str(e).lower()
                            effort = None
                            if isinstance(resp_kwargs.get("reasoning"), dict):
                                effort = resp_kwargs["reasoning"].get("effort")

                            # Only fall back for effort-related rejections.
                            if effort == "minimal" and (
                                "reasoning.effort" in err_text
                                or "invalid value" in err_text
                                or "unsupported" in err_text
                            ):
                                resp_kwargs["reasoning"] = {"effort": "low"}
                                return client.responses.create(**resp_kwargs)
                            if effort == "xhigh" and (
                                "reasoning.effort" in err_text
                                or "invalid value" in err_text
                                or "unsupported" in err_text
                            ):
                                resp_kwargs["reasoning"] = {"effort": "high"}
                                return client.responses.create(**resp_kwargs)
                            raise

                    _resp_result = call_maybe_thread_fn(
                        lambda: parse_responses_response(
                            _create_responses_with_effort_fallback(),
                            core=core,
                        )
                    )
                    (
                        assistant_text,
                        reasoning_content,
                        tool_calls_list,
                        _resp_rid,
                        _resp_output_items,
                    ) = _resp_result
                    if core is not None:
                        try:
                            setattr(
                                core, "_last_responses_output_items", _resp_output_items
                            )
                        except Exception:
                            pass
                    if (
                        _should_track_rid
                        and _resp_rid
                        and isinstance(responses_state, dict)
                    ):
                        responses_state["previous_response_id"] = _resp_rid
                        from .core import _save_responses_state, set_active_response

                        set_active_response(_resp_rid, status="completed")

                        _save_responses_state()

                    # Auto retry (non-streaming only): if output looks unusable, retry once with higher effort.
                    if (
                        _reasoning == "auto"
                        and _effort_used
                        in ("minimal", "low", "medium", "high", "xhigh")
                        and not tool_calls_list
                        and _auto_low_quality(_auto_user_text, assistant_text)
                    ):
                        _next_effort = _bump_effort(_effort_used)
                        if _next_effort in (
                            "minimal",
                            "low",
                            "medium",
                            "high",
                            "xhigh",
                        ):
                            try:
                                core.set_status(True, f"LLM:auto->{_next_effort}")
                            except Exception:
                                pass
                            resp_kwargs["reasoning"] = {"effort": _next_effort}
                            resp = call_maybe_thread_fn(
                                lambda: client.responses.create(**resp_kwargs)
                            )
                            (
                                assistant_text,
                                _retry_reasoning,
                                tool_calls_list,
                                _retry_rid,
                                _retry_output_items,
                            ) = parse_responses_response(
                                resp,
                                core=core,
                            )
                            if core is not None:
                                try:
                                    setattr(
                                        core,
                                        "_last_responses_output_items",
                                        _retry_output_items,
                                    )
                                except Exception:
                                    pass
                            if (
                                _should_track_rid
                                and _retry_rid
                                and isinstance(responses_state, dict)
                            ):
                                responses_state["previous_response_id"] = _retry_rid
                                from .core import (
                                    _save_responses_state,
                                    set_active_response,
                                )

                                set_active_response(_retry_rid, status="completed")

                                _save_responses_state()

                    # A successful Responses API request (including a retry)
                    # means the stale marker is no longer needed.
                    _clear_stale_rid_after_success()
            else:
                req_tools = tools.get_tool_specs() if send_tools_this_round else None

                # Resolve temperature (default 0.2 for deterministic tool use and stable reasoning)
                default_temp = 0.2
                # Allow provider-specific overrides or a global fallback
                temp_env = ""
                if provider == "openai":
                    temp_env = env_get("UAGENT_OPENAI_TEMPERATURE") or ""
                elif provider == "pfn":
                    temp_env = env_get("UAGENT_PFN_TEMPERATURE") or ""
                elif provider == "azure":
                    temp_env = env_get("UAGENT_AZURE_TEMPERATURE") or ""
                elif provider == "openrouter":
                    temp_env = env_get("UAGENT_OPENROUTER_TEMPERATURE") or ""
                elif provider == "bedrock":
                    temp_env = env_get("UAGENT_BEDROCK_TEMPERATURE") or ""
                elif provider == "nvidia":
                    temp_env = env_get("UAGENT_NVIDIA_TEMPERATURE") or ""
                elif provider == "grok":
                    temp_env = env_get("UAGENT_GROK_TEMPERATURE") or ""
                elif provider == "zai":
                    temp_env = env_get("UAGENT_ZAI_TEMPERATURE") or ""
                elif provider == "sakana":
                    temp_env = env_get("UAGENT_SAKANA_TEMPERATURE") or ""
                elif provider == "sakura":
                    temp_env = env_get("UAGENT_SAKURA_TEMPERATURE") or ""
                elif provider == "novita":
                    temp_env = env_get("UAGENT_NOVITA_TEMPERATURE") or ""
                elif provider == "together":
                    temp_env = env_get("UAGENT_TOGETHER_TEMPERATURE") or ""
                elif provider == "vercel":
                    temp_env = env_get("UAGENT_VERCEL_TEMPERATURE") or ""

                if not temp_env:
                    temp_env = env_get("UAGENT_TEMPERATURE") or ""

                resolved_temp = default_temp
                if temp_env.strip():
                    try:
                        resolved_temp = float(temp_env.strip())
                    except ValueError:
                        pass

                chat_kwargs: dict[str, Any] = {
                    "model": depname,
                    "messages": _normalize_chat_image_content(call_messages),
                    "temperature": resolved_temp,
                }
                if provider == "llama_cpp":
                    _apply_llama_cpp_reasoning_kwargs(chat_kwargs)
                # OpenAI Fast mode is intentionally not applied to Azure or
                # other OpenAI-compatible providers.
                if provider == "openai" and _openai_fast_mode_enabled():
                    chat_kwargs["service_tier"] = "fast"
                # Common generation knobs (optional). Provider-specific envs win
                # when already handled above; these are shared fallbacks.
                max_tokens_env = (env_get("UAGENT_MAX_TOKENS") or "").strip()
                if max_tokens_env:
                    try:
                        from .llmcapa_util import clamp_max_tokens

                        _chat_token_limit = clamp_max_tokens(
                            int(max_tokens_env), depname, provider
                        )
                        _model_lower = str(depname or "").lower()
                        if provider in ("openai", "azure") and (
                            _model_lower.startswith("gpt-5")
                            or _model_lower.startswith(("o1", "o2", "o3", "o4"))
                        ):
                            chat_kwargs["max_completion_tokens"] = _chat_token_limit
                        else:
                            chat_kwargs["max_tokens"] = _chat_token_limit
                    except ValueError:
                        pass
                top_p_env = (env_get("UAGENT_TOP_P") or "").strip()
                if top_p_env:
                    try:
                        chat_kwargs["top_p"] = float(top_p_env)
                    except ValueError:
                        pass
                if send_tools_this_round and req_tools is not None:
                    chat_kwargs["tools"] = req_tools
                    chat_kwargs["tool_choice"] = "auto"
                    if provider == "llama_cpp":
                        # llama-server and the uagent executor both support
                        # parallel calls; unsafe tools are still serialized by
                        # _execute_tool_calls based on their safety policy.
                        chat_kwargs["parallel_tool_calls"] = True

                apply_openai_chat_structured_output(
                    chat_kwargs,
                    provider=provider,
                    messages=call_messages,
                    model_id=depname,
                )

                # OpenRouter provider routing / extensions (optional)
                apply_openrouter_extra_body(chat_kwargs, provider=provider)

                # Ollama provider routing / extensions (optional)
                apply_ollama_extra_body(
                    chat_kwargs, provider=provider, messages=call_messages
                )

                # llama-server sampling extensions (optional)
                apply_llama_cpp_extra_body(
                    chat_kwargs, provider=provider, messages=call_messages
                )

                # OpenRouter/Azure-proxy tool schema compatibility workarounds
                apply_openrouter_tool_schema_compat(chat_kwargs, provider=provider)

                # Final OpenRouter/Azure-proxy compatibility sync
                finalize_tool_schema_sync(chat_kwargs, provider=provider)

                # OpenRouter-specific fallback models support (does not affect other providers)
                apply_openrouter_fallback_models(
                    chat_kwargs, provider=provider, depname=depname
                )

                # OpenAI/Azure Chat Completions require an explicit
                # non-reasoning effort when function tools are used with
                # models whose default reasoning mode is enabled.
                if provider in ("openai", "azure") and send_tools_this_round:
                    chat_kwargs.pop("reasoning", None)
                    chat_kwargs["reasoning_effort"] = "none"

                if provider == "lmstudio":
                    from .providers.llm_lmstudio import apply_lmstudio_transport

                    apply_lmstudio_transport(chat_kwargs, responses=False)

                resp = call_maybe_thread_fn(
                    lambda: client.chat.completions.create(**chat_kwargs)
                )
            break
        except Exception as e:
            # Clear previous_response_id on any error (may be stale)
            if isinstance(responses_state, dict):
                responses_state.pop("previous_response_id", None)
                from .core import _save_responses_state

                _save_responses_state()

            # NOTE: i18n function _ is a global import, but some exception paths
            # previously triggered UnboundLocalError: '_' due to local-scope issues.
            # Use a safe fallback translator to avoid crashing while reporting errors.
            def _t(s: str) -> str:
                return s

            try:
                _t = _
            except Exception:
                pass

            # Context-window overflow (OpenAI Responses streaming can raise APIError)
            # We handle it explicitly to avoid the generic error path.
            if (
                "context window" in str(e).lower()
                or "exceeds the context" in str(e).lower()
            ):
                print("[Azure/OpenAI Error] " + _t("Input exceeds the context window."))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []

            def _err_text_of(exc: BaseException) -> str:
                parts = [str(exc)]
                body = getattr(exc, "body", None)
                if body is not None:
                    parts.append(str(body))
                raw = getattr(exc, "response", None)
                if raw is not None:
                    try:
                        parts.append(str(getattr(raw, "text", "") or ""))
                    except Exception:
                        pass
                return "\n".join(parts).lower()

            def _is_stale_previous_response_error(exc: BaseException) -> bool:
                err_text = _err_text_of(exc)
                markers = (
                    "no tool call found",
                    "no tool output found",
                    "previous_response_id",
                    "invalid_prompt",
                    "expected null, received string",
                )
                return any(m in err_text for m in markers)

            def _retry_without_previous_response_id(exc: BaseException) -> bool:
                """One-shot full-history retry after a bad previous_response_id."""
                nonlocal _stale_rid_retried
                if _stale_rid_retried:
                    print(
                        "[Azure/OpenAI Error] "
                        + _(
                            "The Responses API rejected the full-history "
                            "retry; starting a new session is required."
                        )
                    )
                    try:
                        from .core import clear_responses_continuation

                        clear_responses_continuation()
                    except Exception:
                        if isinstance(responses_state, dict):
                            responses_state.pop("previous_response_id", None)
                            responses_state["_stale_rid_occurred"] = True
                    return False
                _stale_rid_retried = True
                if isinstance(responses_state, dict):
                    responses_state.pop("previous_response_id", None)
                    responses_state["_stale_rid_occurred"] = True
                    from .core import _save_responses_state

                    _save_responses_state()
                _used_rid = bool(_prev_rid) if "_prev_rid" in locals() else True
                if _used_rid:
                    print(
                        "[Azure/OpenAI Error] "
                        + _(
                            "Stale previous_response_id. "
                            "Retrying with full history..."
                        )
                    )
                else:
                    print(
                        "[Azure/OpenAI Error] "
                        + _(
                            "Responses tool chain rejected. "
                            "Retrying with sanitized full history..."
                        )
                    )
                return True

            _is_bad_request = BadRequestError is not None and isinstance(
                e, BadRequestError
            )
            _is_resp_validation = APIResponseValidationError is not None and isinstance(
                e, APIResponseValidationError
            )
            if _is_bad_request or _is_resp_validation:
                err_text = _err_text_of(e)
                if _is_bad_request and "does not support tools" in err_text:
                    print(
                        "[Azure/OpenAI Error] "
                        + _(
                            "Model does not support tools. "
                            "Auto-disabling tools and retrying..."
                        )
                    )
                    from . import core as _core_module

                    _core_module.tools_enabled = False
                    send_tools_this_round = False
                    continue
                if _is_bad_request and "does not support thinking" in err_text:
                    print(
                        "[Azure/OpenAI Error] "
                        + _(
                            "Model does not support thinking. "
                            "Disabling thinking and retrying..."
                        )
                    )
                    _thinking_disabled = True
                    resp_kwargs.pop("reasoning", None)
                    continue
                # A Responses continuation can fail when the stored
                # previous_response_id is stale, incomplete, or unsupported
                # (e.g. OpenRouter expects null and may return invalid_prompt
                # with a non-integer error.code that surfaces as
                # APIResponseValidationError).
                if _is_stale_previous_response_error(e):
                    if _retry_without_previous_response_id(e):
                        continue
                    return False, client, "", "", []
                print("[Azure/OpenAI Error] " + _("400 BadRequest"))
                print(
                    "[Azure/OpenAI Error] "
                    + _("Error code: %(code)s - %(err)s")
                    % {"code": getattr(e, "status_code", 400) or 400, "err": e}
                )
                return False, client, "", "", []
            if APIConnectionError is not None and isinstance(e, APIConnectionError):
                from .providers.util_providers import (
                    is_ssl_cert_error,
                    set_ssl_verify_disabled,
                )

                if is_ssl_cert_error(e):
                    print(
                        "[Azure/OpenAI Error] "
                        + _t(
                            "SSL certificate verification failed. Auto-disabling SSL verify and retrying..."
                        )
                    )
                    _maybe_print_certifi_where(e)
                    set_ssl_verify_disabled(True)
                    new_client = make_client_fn(core)[1]
                    if new_client is not None:
                        client = new_client
                    continue
                print("[Azure/OpenAI Error] " + _t("Connection error"))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []
            if isinstance(e, URLError):
                print(_("[Network Error]"))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []
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
                    "[Azure/OpenAI Error] "
                    + _("429 retry limit (%(max_retries)s) reached.")
                    % {"max_retries": max_retries_429}
                )
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []
            print("[LLM Error] " + _t("Unexpected exception."))
            _maybe_print_certifi_where(e)
            print(repr(e))
            return False, client, "", "", []

    try:
        if use_responses_api:
            # Responses API: assistant_text/tool_calls_list are already parsed above
            # - streaming: parse_responses_stream(resp)
            # - non-streaming: parse_responses_response(resp, core=core)
            pass
        else:
            if resp is None:
                print("[ERROR] " + _("Response error: resp is None."))
                return False, client, "", "", []
            if resp.choices is None or len(resp.choices) == 0:
                print("[ERROR] " + _("Response error: resp.choices is None or empty."))
                return False, client, "", "", []
            choice = resp.choices[0]
            msg = choice.message

            raw_tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in raw_tool_calls:
                tc_id = getattr(tc, "id", None)
                fn_obj = getattr(tc, "function", None)

                if fn_obj is None and isinstance(tc, dict):
                    tc_id = tc.get("id")
                    fn_obj = tc.get("function") or {}

                fn_name = getattr(fn_obj, "name", None)
                fn_args = getattr(fn_obj, "arguments", None)

                if isinstance(fn_obj, dict):
                    fn_name = fn_obj.get("name")
                    fn_args = fn_obj.get("arguments")

                if not isinstance(fn_name, str) or not fn_name:
                    continue

                if isinstance(fn_args, dict):
                    fn_args = json.dumps(fn_args, ensure_ascii=False)
                elif fn_args is None:
                    fn_args = "{}"
                elif not isinstance(fn_args, str):
                    fn_args = str(fn_args)

                # Generate synthetic ID when the API returns empty/missing tool_call_id.
                # This prevents sanitize_messages_for_tools from dropping tool results
                # as orphans, which would cause the model to repeat the same tool call.
                _tid = tc_id if tc_id else uuid.uuid4().hex[:12]
                tool_calls_list.append(
                    {
                        "id": _tid,
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": fn_args,
                        },
                    }
                )

            raw_content = getattr(msg, "content", "")
            if isinstance(raw_content, str):
                assistant_text = raw_content
            elif raw_content is None:
                assistant_text = ""
            elif isinstance(raw_content, list):
                parts = []
                for item in raw_content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        if isinstance(item.get("text"), str):
                            parts.append(item["text"])
                        elif isinstance(item.get("content"), str):
                            parts.append(item["content"])
                        elif isinstance(item.get("value"), str):
                            parts.append(item["value"])
                    else:
                        txt = getattr(item, "text", None)
                        if isinstance(txt, str):
                            parts.append(txt)
                assistant_text = "".join(parts)
            else:
                assistant_text = str(raw_content)

            # Extract reasoning_content if present (e.g. o1/o3, OpenRouter reasoning models)
            # Official OpenRouter SDK returns reasoning in `reasoning` (not `reasoning_content`).
            _rc = getattr(msg, "reasoning_content", None)
            if not (isinstance(_rc, str) and _rc):
                _rc = getattr(msg, "reasoning", None)
            if isinstance(_rc, str) and _rc:
                reasoning_content = _rc
                show_reasoning(
                    _rc,
                    provider=provider.capitalize(),
                    is_first=True,
                    print_fn=getattr(core, "print_stream_delta", None)
                    or (lambda s: print(s, end="", flush=True)),
                    core=core,
                )

            if not tool_calls_list:
                assistant_text, recovered_tool_calls = parse_assistant_text_tool_calls(
                    assistant_text
                )
                if recovered_tool_calls:
                    tool_calls_list = recovered_tool_calls

    except Exception as e:
        print("[ERROR] " + _("Error while parsing response: %(err)s") % {"err": e})
        traceback.print_exc()
        return False, client, "", "", []

    return True, client, assistant_text, reasoning_content, tool_calls_list


def _call_deepseek_round(
    *,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    send_tools_this_round: bool,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
    provider: str = "deepseek",
) -> tuple[bool, Any, str, str, list[dict[str, Any]]]:
    """Thin wrapper: delegates to providers/llm_deepseek.py (DeepSeek/MiMo).

    Returns ``(ok, client, assistant_text, reasoning_content, tool_calls_list)``.
    """
    stream = _env_default_true("UAGENT_STREAMING", default=True)
    return deepseek_chat_with_tools(
        client,
        depname,
        call_messages,
        core=core,
        make_client_fn=make_client_fn,
        call_maybe_thread_fn=call_maybe_thread_fn,
        send_tools_this_round=send_tools_this_round,
        max_retries_429=max_retries_429,
        retry_base=retry_base,
        retry_cap=retry_cap,
        stream=stream,
        provider=provider,
    )


def _call_zai_round(
    *,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    send_tools_this_round: bool,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
) -> tuple[bool, Any, str, str, list[dict[str, Any]]]:
    """Thin wrapper: delegates to providers/llm_zai.py (Z.AI / zai-sdk).

    Returns ``(ok, client, assistant_text, reasoning_content, tool_calls_list)``.
    """
    stream = _env_default_true("UAGENT_STREAMING", default=True)
    return zai_chat_with_tools(
        client,
        depname,
        call_messages,
        core=core,
        make_client_fn=make_client_fn,
        call_maybe_thread_fn=call_maybe_thread_fn,
        send_tools_this_round=send_tools_this_round,
        max_retries_429=max_retries_429,
        retry_base=retry_base,
        retry_cap=retry_cap,
        stream=stream,
    )


def _call_vercel_round(
    *,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    send_tools_this_round: bool,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
) -> tuple[bool, Any, str, str, list[dict[str, Any]]]:
    """Thin wrapper: delegates to providers/llm_vercel.py (Vercel AI Gateway).

    Returns ``(ok, client, assistant_text, reasoning_content, tool_calls_list)``.
    """
    stream = _env_default_true("UAGENT_STREAMING", default=True)
    return vercel_chat_with_tools(
        client,
        depname,
        call_messages,
        core=core,
        make_client_fn=make_client_fn,
        call_maybe_thread_fn=call_maybe_thread_fn,
        send_tools_this_round=send_tools_this_round,
        max_retries_429=max_retries_429,
        retry_base=retry_base,
        retry_cap=retry_cap,
        stream=stream,
    )


def _call_together_round(
    *,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    send_tools_this_round: bool,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
) -> tuple[bool, Any, str, str, list[dict[str, Any]]]:
    """Thin wrapper: delegates to providers/llm_together.py (Together AI).

    Returns ``(ok, client, assistant_text, reasoning_content, tool_calls_list)``.
    """
    stream = _env_default_true("UAGENT_STREAMING", default=True)
    return together_chat_with_tools(
        client,
        depname,
        call_messages,
        core=core,
        make_client_fn=make_client_fn,
        call_maybe_thread_fn=call_maybe_thread_fn,
        send_tools_this_round=send_tools_this_round,
        max_retries_429=max_retries_429,
        retry_base=retry_base,
        retry_cap=retry_cap,
        stream=stream,
    )


def _call_novita_round(
    *,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    send_tools_this_round: bool,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
) -> tuple[bool, Any, str, str, list[dict[str, Any]]]:
    """Thin wrapper: delegates to providers/llm_novita.py (Novita AI).

    Returns ``(ok, client, assistant_text, reasoning_content, tool_calls_list)``.
    """
    stream = _env_default_true("UAGENT_STREAMING", default=True)
    return novita_chat_with_tools(
        client,
        depname,
        call_messages,
        core=core,
        make_client_fn=make_client_fn,
        call_maybe_thread_fn=call_maybe_thread_fn,
        send_tools_this_round=send_tools_this_round,
        max_retries_429=max_retries_429,
        retry_base=retry_base,
        retry_cap=retry_cap,
        stream=stream,
    )
