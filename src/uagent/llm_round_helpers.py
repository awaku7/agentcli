from __future__ import annotations

import json
import traceback
from urllib.error import URLError
from typing import Any

try:
    from openai import APIConnectionError, BadRequestError
except Exception:
    APIConnectionError = None
    BadRequestError = None

from . import tools
from .llm_errors import _rate_limit_retry_step
from .providers.llm_gemini import gemini_chat_with_tools
from .providers.llm_claude import (
    claude_chat_with_tools,
    build_claude_output_config_for_effort,
)
from .providers.llm_openai_responses import (
    build_responses_request,
    parse_responses_response,
    parse_responses_stream,
)
from .providers.llm_bedrock_responses import build_bedrock_responses_request
from .tools.llm_tool_narrowing import (
    _is_gpt54_tool_search_target,
    _select_tool_specs_for_gpt54,
)
from .providers.llm_openrouter import (
    apply_openrouter_extra_body,
    apply_openrouter_tool_schema_compat,
    finalize_tool_schema_sync,
    apply_openrouter_fallback_models,
)
from .providers.llm_openrouter_responses import apply_openrouter_responses_compat
from .providers.llm_ollama import apply_ollama_extra_body
from .providers.llm_ollama_responses import apply_ollama_responses_compat
from .providers.llm_deepseek import deepseek_chat_with_tools
from .providers.llm_zai import zai_chat_with_tools
from .llm_helpers import (
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


def _resolve_round_runtime_flags(*, tr_cfg: Any, core: Any) -> Any:
    use_responses_api = (env_get("UAGENT_RESPONSES", "") or "").lower() in (
        "1",
        "true",
    )

    stream_responses = _env_default_true("UAGENT_STREAMING", default=True)

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
        except Exception as e:
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
                recreate_client_fn=(lambda: (make_client_fn(core)[1])),
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
) -> Any:
    attempt_429 = 0
    assistant_text: str = ""
    tool_calls_list: list[dict[str, Any]] = []
    resp = None

    # Respect the caller's send_tools_this_round (which reflects core.tools_enabled).
    # Only fall back to env var if the caller didn't set it.
    if send_tools_this_round is None:
        send_tools_this_round = _env_default_on("UAGENT_USE_TOOL")

    while True:
        try:
            if use_responses_api:
                use_gpt54_tool_search = _is_gpt54_tool_search_target(
                    provider=provider,
                    depname=depname,
                    use_responses_api=use_responses_api,
                )
                responses_tool_specs = (
                    _select_tool_specs_for_gpt54(call_messages)
                    if use_gpt54_tool_search
                    else None
                )

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
                    )

                    resp_kwargs = {
                        "model": depname,
                        "input": input_msgs,
                    }

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
                if instructions_str is not None:
                    resp_kwargs["instructions"] = instructions_str
                if send_tools_this_round and req_tools:
                    resp_kwargs["tools"] = req_tools
                    resp_kwargs["tool_choice"] = "auto"

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

                if stream_responses:
                    assistant_text, tool_calls_list = call_maybe_thread_fn(
                        lambda: parse_responses_stream(
                            client.responses.create(
                                **resp_kwargs,
                                stream=True,
                            ),
                            # In Web mode, parse_responses_stream streams deltas via core.log_message.
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

                    assistant_text, tool_calls_list = call_maybe_thread_fn(
                        lambda: parse_responses_response(
                            _create_responses_with_effort_fallback(),
                            core=core,
                        )
                    )

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
                            assistant_text, tool_calls_list = parse_responses_response(
                                resp,
                                core=core,
                            )
            else:
                req_tools = tools.get_tool_specs() if send_tools_this_round else None

                # Resolve temperature (default 0.2 for deterministic tool use and stable reasoning)
                default_temp = 0.2
                # Allow provider-specific overrides or a global fallback
                temp_env = ""
                if provider == "openai":
                    temp_env = env_get("UAGENT_OPENAI_TEMPERATURE") or ""
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
                    "messages": call_messages,
                    "temperature": resolved_temp,
                }
                if send_tools_this_round and req_tools is not None:
                    chat_kwargs["tools"] = req_tools
                    chat_kwargs["tool_choice"] = "auto"

                # OpenRouter provider routing / extensions (optional)
                apply_openrouter_extra_body(chat_kwargs, provider=provider)

                # Ollama provider routing / extensions (optional)
                apply_ollama_extra_body(chat_kwargs, provider=provider)

                # OpenRouter/Azure-proxy tool schema compatibility workarounds
                apply_openrouter_tool_schema_compat(chat_kwargs, provider=provider)

                # Final OpenRouter/Azure-proxy compatibility sync
                finalize_tool_schema_sync(chat_kwargs, provider=provider)

                # OpenRouter-specific fallback models support (does not affect other providers)
                apply_openrouter_fallback_models(
                    chat_kwargs, provider=provider, depname=depname
                )

                resp = call_maybe_thread_fn(
                    lambda: client.chat.completions.create(**chat_kwargs)
                )
            break
        except Exception as e:
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
                return False, client, "", []

            if BadRequestError is not None and isinstance(e, BadRequestError):
                print("[Azure/OpenAI Error] 400 BadRequest")
                print(f"Error code: 400 - {e}")
                return False, client, "", []
            if APIConnectionError is not None and isinstance(e, APIConnectionError):
                print("[Azure/OpenAI Error] " + _t("Connection error"))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", []
            if isinstance(e, URLError):
                print(_("[Network Error]"))
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
                print(
                    "[Claude Error] "
                    + _("429 retry limit (%(max_retries)s) reached.")
                    % {"max_retries": max_retries_429}
                )
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", []
            print("[LLM Error] " + _t("Unexpected exception."))
            _maybe_print_certifi_where(e)
            print(repr(e))
            return False, client, "", []

    try:
        if use_responses_api:
            # Responses API: assistant_text/tool_calls_list are already parsed above
            # - streaming: parse_responses_stream(resp)
            # - non-streaming: parse_responses_response(resp, core=core)
            pass
        else:
            if resp is None:
                print("[ERROR] " + _("Response error: resp is None."))
                return False, client, "", []
            if resp.choices is None or len(resp.choices) == 0:
                print("[ERROR] " + _("Response error: resp.choices is None or empty."))
                return False, client, "", []
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

                tool_calls_list.append(
                    {
                        "id": tc_id or "",
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

    except Exception as e:
        print("[ERROR] " + _("Error while parsing response: %(err)s") % {"err": e})
        traceback.print_exc()
        return False, client, "", []

    return True, client, assistant_text, tool_calls_list


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
    """Thin wrapper: delegates to providers/llm_zai.py (Z.AI / zhipuai SDK).

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
