"""Claude compatibility adapter extracted from legacy round helpers."""

from __future__ import annotations

from typing import Any

from ..env_utils import env_get
from ..i18n import _
from ..llm_helpers import (
    _choose_auto_effort,
    _extract_latest_user_text,
    _is_thinking_task,
    _maybe_print_certifi_where,
)
from ..providers.llm_claude import (
    build_claude_output_config_for_effort,
    claude_chat_with_tools,
)
from ..providers.structured_output import structured_output_request
from ..runtime.error_renderer import exception_text
from .retry_coordinator import RoundRetryCoordinator


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
    claude_chat_fn: Any = None,
    retry_coordinator: RoundRetryCoordinator | None = None,
) -> Any:
    retry_coordinator = retry_coordinator or RoundRetryCoordinator(max_retries_429)
    retry_coordinator.expose_budget(core)
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
                    from ..llmcapa_util import supports_json_schema

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
                lambda: (claude_chat_fn or claude_chat_with_tools)(
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
            attempt_429, new_client, action = retry_coordinator.rate_limit_step(
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
                print(exception_text(e))
                return False, client, "", []
            print(_("[Claude Error] An error occurred while generating a response."))
            _maybe_print_certifi_where(e)
            print(exception_text(e))
            return False, client, "", []

    return True, client, assistant_text, tool_calls_list


__all__ = ["_call_claude_round"]
