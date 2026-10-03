"""Auto-pilot (:auto) command implementation (moved from util_tools.py)."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from .decision import (
    DecisionQuestion,
    DecisionRequest,
    create_decision_provider,
    get_decision_settings,
)
from .env_utils import env_get
from .i18n import _, get_locale
from .runtime.observability.auto_pilot import (
    record_auto_pilot_judgment,
    record_auto_pilot_run_finished,
)
from .util_common import CommandResult, append_result_to_outfile
from .util_image import try_open_images_from_text
from .utils.secret_mask import _mask_inline_secrets, mask_message

# Default translation function used when core.tr is not provided.
tr = _
tr_ = _

_SENTINEL_INSTRUCTION = _(
    "\n\nAuto-pilot protocol: finish your response with exactly one line: "
    "<AUTO_CONTINUE> if work remains, or <AUTO_COMPLETE> if the goal is complete. "
    "If neither marker is present, auto-pilot stops safely."
)


def _sentinel_mode_enabled() -> bool:
    raw = (env_get("UAGENT_AUTO_SENTINEL", "0") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _with_sentinel_instruction(prompt: str) -> str:
    return str(prompt) + _SENTINEL_INSTRUCTION


def _sentinel_judgment(messages: list[dict[str, Any]]) -> str | None:
    """Read a normalized sentinel from the latest assistant response.

    Models occasionally vary capitalization or omit the angle brackets. Keep
    the protocol conservative by accepting only a sentinel-shaped final line,
    while tolerating those harmless formatting differences.
    """
    for message in reversed(messages or []):
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        # A tool-call-only assistant message is not a text-only sentinel turn.
        # Tool execution still has to be accounted for, so continue safely
        # instead of stopping because ``content`` is empty.
        if message.get("tool_calls"):
            return "CONTINUE"

        content = message.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in content
            )
        lines = [line.strip() for line in str(content).splitlines() if line.strip()]
        if not lines:
            return None
        marker = lines[-1].strip().upper()
        if re.fullmatch(r"(?:<AUTO_COMPLETE>|AUTO_COMPLETE)", marker):
            return "COMPLETE"
        if re.fullmatch(r"(?:<AUTO_CONTINUE>|AUTO_CONTINUE)", marker):
            return "CONTINUE"
        return None
    return None


def _completion_regex_matches(messages: list[dict[str, Any]], pattern: Any) -> bool:
    """Check the latest assistant text against the optional CLI completion regex."""
    raw_pattern = str(pattern or "").strip()
    if not raw_pattern:
        return False
    latest_text = ""
    for message in reversed(messages or []):
        if isinstance(message, dict) and message.get("role") == "assistant":
            content = message.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(item.get("text", "")) if isinstance(item, dict) else str(item)
                    for item in content
                )
            latest_text = str(content or "")
            break
    try:
        return re.search(raw_pattern, latest_text, flags=re.MULTILINE) is not None
    except re.error as exc:
        print(f"[WARN] Invalid --complete-regex: {exc}", flush=True)
        return False


def _get_followup_prompt(goal: str, feedback: str = "") -> str:
    """Generate continuation prompt for the main query (i18n)."""
    prompt = _("Continue. Goal: %(goal)s") % {"goal": goal}
    if feedback:
        prompt += "\n\n" + _("Reviewer notes: %(feedback)s") % {"feedback": feedback}
    return prompt


def _tool_result_for_judgment(message: dict[str, Any]) -> dict[str, str]:
    name = str(message.get("name") or "tool")
    call_id = str(message.get("tool_call_id") or "")
    raw_content = message.get("content", "")
    try:
        raw_parsed = json.loads(str(raw_content))
    except Exception:
        raw_parsed = None
    if isinstance(raw_parsed, (dict, list)):
        masked = json.dumps(mask_message(raw_parsed), ensure_ascii=False)
    else:
        masked = mask_message({"content": raw_content}).get("content", "")
    status = "success"
    summary = str(masked or "")
    try:
        parsed = json.loads(str(masked))
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        if parsed.get("ok") is False or parsed.get("error"):
            status = "failed"
            error = parsed.get("error")
            if isinstance(error, dict):
                summary = str(error.get("message") or error.get("code") or error)
            else:
                summary = str(error or parsed)
        else:
            result = parsed.get("result", parsed.get("data", parsed))
            if isinstance(result, dict):
                summary = str(
                    result.get("text")
                    or result.get("summary")
                    or result.get("message")
                    or result
                )
            else:
                summary = str(result)
    return {
        "tool": _mask_inline_secrets(name)[:100],
        "call_id": _mask_inline_secrets(call_id)[:100],
        "status": status,
        "summary": _mask_inline_secrets(" ".join(summary.split()))[:400],
    }


def _tool_result_summary_for_judgment(message: dict[str, Any]) -> str:
    item = _tool_result_for_judgment(message)
    call_suffix = f" call_id={item['call_id']}" if item["call_id"] else ""
    return (
        f"[TOOL-RESULT] tool={item['tool']} status={item['status']}"
        f"{call_suffix} summary={item['summary']}"
    )


def _decision_text_content(content: Any) -> str:
    if isinstance(content, list):
        content = " ".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
    return _mask_inline_secrets(" ".join(str(content or "").split()))[:500]


def _build_auto_pilot_decision_state(
    messages: list[dict[str, Any]],
    core: Any,
) -> dict[str, Any]:
    recent_conversation: list[dict[str, str]] = []
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role not in ("user", "assistant"):
            continue
        content = _decision_text_content(message.get("content", ""))
        if not content:
            continue
        recent_conversation.append({"role": str(role), "content": content})
        if len(recent_conversation) >= 6:
            break
    recent_conversation.reverse()

    recent_tool_results: list[dict[str, str]] = []
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        recent_tool_results.append(_tool_result_for_judgment(message))
        if len(recent_tool_results) >= 4:
            break
    recent_tool_results.reverse()

    max_rounds = getattr(core, "auto_pilot_max_rounds", None)
    return {
        "goal": _mask_inline_secrets(str(core.auto_pilot_goal or ""))[:2000],
        "round": int(getattr(core, "auto_pilot_round", 0) or 0),
        "max_rounds": max_rounds,
        "recent_conversation": recent_conversation,
        "recent_tool_results": recent_tool_results,
    }


def _decision_failure_detail(exc: BaseException) -> str:
    """Return a bounded, secret-masked one-line provider failure detail."""

    detail = " ".join(str(exc).split())
    if not detail:
        return ""
    return _mask_inline_secrets(detail)[:300]


def _decision_provider_supports_choice(decision_provider: Any) -> bool | None:
    model = str(getattr(decision_provider, "model", "") or "").strip()
    provider = str(getattr(decision_provider, "name", "") or "").strip()
    if not model or not provider:
        return None
    try:
        import llmcapa

        capability = llmcapa.get(model, provider=provider)
    except Exception:
        return None
    if capability is None:
        return None
    try:
        if capability.supports("decision_output") is False:
            return False
    except Exception:
        pass
    decision = getattr(capability, "decision", None)
    kinds = getattr(decision, "question_kinds", None)
    if kinds is None:
        return None
    return "choice" in set(kinds)


def _build_auto_pilot_decision_request(
    state: dict[str, Any],
    *,
    reverse_choices: bool = False,
) -> DecisionRequest:
    criteria_items = [
        (
            "COMPLETE",
            "The required work is fully finished and no material work remains.",
        ),
        (
            "CONTINUE",
            "Additional material work remains, or completion is uncertain.",
        ),
    ]
    if reverse_choices:
        criteria_items.reverse()

    return DecisionRequest(
        state=state,
        questions=(
            DecisionQuestion(
                id="auto_pilot_goal_status",
                kind="choice",
                instruction=(
                    "Determine whether the auto-pilot goal is fully complete. "
                    "Choose COMPLETE only when the required work is finished and no "
                    "material work remains. Choose CONTINUE when additional work is "
                    "required or completion is uncertain."
                ),
                choices=tuple(label for label, _description in criteria_items),
                metadata={
                    "criteria": {
                        label: description for label, description in criteria_items
                    }
                },
            ),
        ),
        metadata={"site": "auto_pilot_review"},
    )


def _ask_auto_pilot_decision(
    messages: list[dict[str, Any]],
    core: Any,
    *,
    decision_provider: Any,
) -> tuple[str, str] | None:
    question_id = "auto_pilot_goal_status"
    state = _build_auto_pilot_decision_state(messages, core)
    request = _build_auto_pilot_decision_request(state)
    provider_name = str(getattr(decision_provider, "name", "") or "")
    provider_model = str(getattr(decision_provider, "model", "") or "")

    def run_attempt(
        attempt_request: DecisionRequest,
        *,
        attempt: str = "",
    ) -> tuple[str, Any, Any] | None:
        started = time.perf_counter()
        try:
            result = decision_provider.decide(attempt_request)
            answer = result.answers.get(question_id)
            if answer is None:
                raise ValueError("missing auto_pilot_goal_status answer")
            judgment = str(answer.value or "").strip().upper()
            if judgment not in {"COMPLETE", "CONTINUE"}:
                raise ValueError(f"invalid auto-pilot judgment: {answer.value!r}")
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            record_auto_pilot_judgment(
                source="decision_provider",
                round_number=getattr(core, "auto_pilot_round", 0),
                fallback=False,
                provider=provider_name,
                model=provider_model,
                latency_ms=latency_ms,
                error_type=type(exc).__name__,
                additional_call=True,
            )
            detail = _decision_failure_detail(exc)
            detail_text = f" detail={detail!r}" if detail else ""
            attempt_text = f" attempt={attempt}" if attempt else ""
            print(
                "[AUTO:judge:decision] "
                f"provider={provider_name or 'unknown'}{attempt_text} "
                f"failed={type(exc).__name__}{detail_text}; "
                "falling back to LLM reviewer",
                flush=True,
            )
            return None

        model = str(result.model or provider_model)
        record_auto_pilot_judgment(
            source="decision_provider",
            round_number=getattr(core, "auto_pilot_round", 0),
            answer=judgment,
            fallback=False,
            provider=str(result.provider or provider_name),
            model=model,
            confidence=answer.confidence,
            latency_ms=result.latency_ms,
            additional_call=True,
        )
        return judgment, result, answer

    primary = run_attempt(request, attempt="primary" if provider_name == "laya" else "")
    if primary is None:
        return None

    judgment, result, answer = primary
    model = str(result.model or provider_model)
    confidence = answer.confidence
    latency_ms = float(result.latency_ms)

    if provider_name.strip().lower() == "laya":
        reversed_request = _build_auto_pilot_decision_request(
            state,
            reverse_choices=True,
        )
        reversed_attempt = run_attempt(reversed_request, attempt="reversed")
        if reversed_attempt is None:
            return None

        reversed_judgment, reversed_result, reversed_answer = reversed_attempt
        latency_ms += float(reversed_result.latency_ms)
        if reversed_judgment != judgment:
            print(
                "[AUTO:judge:decision] "
                f"provider={provider_name} model={model} "
                f"order_inconsistent primary={judgment} "
                f"reversed={reversed_judgment}; "
                "falling back to LLM reviewer",
                flush=True,
            )
            return None

        confidence_values = [
            float(value)
            for value in (confidence, reversed_answer.confidence)
            if value is not None
        ]
        confidence = min(confidence_values) if confidence_values else None

    confidence_text = "none" if confidence is None else f"{float(confidence):.4f}"
    consistency_text = (
        " order_consistent=true" if provider_name.strip().lower() == "laya" else ""
    )
    print(
        "[AUTO:judge:decision] "
        f"provider={result.provider} model={model} judgment={judgment} "
        f"confidence={confidence_text} latency_ms={latency_ms:.1f}"
        f"{consistency_text}",
        flush=True,
    )
    return judgment, ""


def _review_language() -> str:
    configured = (env_get("UAGENT_AUTO_REVIEW_LANGUAGE", "") or "").strip()
    if configured:
        return configured
    try:
        return str(get_locale() or "en")
    except Exception:
        return "en"


def _build_judgment_messages(
    messages: list[dict[str, Any]],
    goal: str,
) -> list[dict[str, Any]]:
    """Build messages for the reviewer judgment query.

    The explanatory text is localized through gettext. The COMPLETE/CONTINUE
    tokens and output format remain unchanged because they are protocol values.
    """
    system_prompt = _(
        "auto.review_judgment_system_prompt",
        default=(
            "You are a reviewer. Evaluate the conversation below and "
            "determine whether the goal '%(goal)s' has been achieved.\n"
            "Achieved    \u2192 COMPLETE\n"
            "More needed \u2192 CONTINUE\n"
            "Reply with COMPLETE or CONTINUE.\n"
            "If CONTINUE, briefly state what is still missing.\n"
            "Format: CONTINUE: <reason>"
        ),
    ) % {"goal": goal}
    system_prompt += (
        "\nWrite any CONTINUE reason only in the requested review language: "
        + _review_language()
        + ". Do not mix languages. Keep COMPLETE/CONTINUE unchanged."
    )

    msgs: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    # Recent conversation history (max 6 messages = 3 turns)
    history: list[dict[str, Any]] = []
    for m in reversed(messages):
        if m.get("role") in ("user", "assistant"):
            content = m.get("content", "")
            if isinstance(content, str) and content.strip():
                history.append({"role": m["role"], "content": content[:500]})
                if len(history) >= 6:
                    break

    for h in reversed(history):
        msgs.append(h)

    tool_summaries: list[str] = []
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        tool_summaries.append(_tool_result_summary_for_judgment(message))
        if len(tool_summaries) >= 4:
            break
    if tool_summaries:
        msgs.append(
            {
                "role": "user",
                "content": "Recent tool results (bounded summaries):\n"
                + "\n".join(reversed(tool_summaries)),
            }
        )

    msgs.append({"role": "user", "content": "COMPLETE or CONTINUE?"})
    return msgs


def _parse_reviewer_judgment(raw: str) -> tuple[str, str]:
    """Parse reviewer output; word matches are accepted and CONTINUE wins."""
    text = raw or ""
    upper = text.upper()
    # Accept punctuation and explanatory text (for example ``COMPLETE.``),
    # while avoiding substrings such as ``INCOMPLETE``.  CONTINUE is checked
    # first so mixed or contradictory output remains conservative.
    if re.search(r"\bCONTINUE\b", upper):
        return "CONTINUE", text
    if re.search(r"\bNOT\s+COMPLETE\b", upper):
        return "CONTINUE", text
    if re.search(r"\bCOMPLETE\b", upper):
        return "COMPLETE", ""
    return "CONTINUE", text


def _ask_reviewer_judgment(
    provider: str,
    client: Any,
    depname: str,
    messages: list[dict[str, Any]],
    core: Any,
    *,
    make_client_fn: Any,
    fallback: bool = False,
) -> tuple[str, str]:
    """Ask the LLM as a reviewer whether the goal is achieved.

    Uses run_llm_rounds() in judgment_mode=True so that the same code path
    (Responses API included) is used for the judgment query.
    Returns ("COMPLETE"|"CONTINUE", feedback_text).
    """
    from . import uagent_llm as llm_util

    judgment_msgs = _build_judgment_messages(messages, core.auto_pilot_goal)

    core.set_status(True, "AUTO:judge")

    import warnings

    started = time.perf_counter()
    error_type = ""
    try:
        result_text = llm_util.run_llm_rounds(
            provider=provider,
            client=client,
            depname=depname,
            messages=messages,
            core=core,
            make_client_fn=make_client_fn,
            append_result_to_outfile_fn=append_result_to_outfile,
            try_open_images_from_text_fn=try_open_images_from_text,
            judgment_mode=True,
            judgment_messages=judgment_msgs,
            preserve_tool_loop_state=True,
        )
    except Exception as e:
        error_type = type(e).__name__
        warnings.warn(
            _("[AUTO] Judgment call failed: %(etype)s: %(error)s")
            % {"etype": error_type, "error": e}
        )
        raw = "CONTINUE"
    else:
        raw = (result_text or "").strip()

    # Only an explicit decision token may stop auto-pilot.  Substring matching
    # incorrectly treated phrases such as "not COMPLETE" or "INCOMPLETE" as
    # successful completion.
    judgment, feedback = _parse_reviewer_judgment(raw)
    if judgment != "COMPLETE":
        # Extract feedback after "CONTINUE:" or the whole text minus "CONTINUE"
        feedback = raw
        for prefix in ("CONTINUE:", "continue:", "CONTINUE", "continue"):
            if prefix in raw:
                parts = raw.split(prefix, 1)
                if len(parts) > 1:
                    feedback = parts[1].strip().lstrip(":")
                    break
        feedback = feedback.strip().strip(" -\n").strip("\"'")

    latency_ms = (time.perf_counter() - started) * 1000.0
    record_auto_pilot_judgment(
        source="llm_reviewer",
        round_number=getattr(core, "auto_pilot_round", 0),
        answer=judgment,
        fallback=fallback,
        provider=provider,
        model=depname,
        latency_ms=latency_ms,
        error_type=error_type,
        additional_call=True,
    )

    print(_("\n[AUTO:judge] %(judgment)s") % {"judgment": judgment})
    if feedback:
        print(_("  feedback: %(feedback)s") % {"feedback": feedback})
    return judgment, feedback


def _run_auto_pilot_loop(
    provider: str,
    client: Any,
    depname: str,
    messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    append_result_to_outfile_fn: Any,
    try_open_images_from_text_fn: Any,
) -> None:
    """Auto-pilot main loop.

    Step B (judgment) is performed FIRST to check the initial goal execution
    done by the caller. If COMPLETE, the loop exits immediately -- no extra round.
    Only if CONTINUE does Step A (followup refinement) run.

    1 round = 2 LLM calls:
      Step B: Reviewer judgment (evaluates previous work / initial goal)
      Step A: Main query (continuation of review/analysis if not yet done)
    """
    # Lazy import to avoid circular imports at module level
    from . import uagent_llm as llm_util

    # Allow separate LLM for reviewer (created once before the loop)
    _judge_provider = provider
    _judge_client = client
    _judge_depname = depname
    _judge_override = env_get("UAGENT_AP_PROVIDER", "").strip()
    if _judge_override:
        _saved = {}
        try:
            _prefix = "UAGENT_AP_"
            _std_prefix = "UAGENT_"
            for _key, _val in os.environ.items():
                if _key.startswith(_prefix):
                    _std_key = _std_prefix + _key[len(_prefix) :]
                    _saved[_std_key] = os.environ.get(_std_key, "")
                    os.environ[_std_key] = _val
            _judge_provider, _judge_client, _judge_depname = make_client_fn(core)
        except Exception:
            pass
        finally:
            for _std_key, _orig_val in _saved.items():
                if _orig_val:
                    os.environ[_std_key] = _orig_val
                else:
                    os.environ.pop(_std_key, None)

    feedback = ""
    decision_provider = None
    decision_provider_initialized = False
    decision_provider_choice_checked = False
    last_judgment_source = ""
    run_outcome_recorded = False

    def record_run_outcome(
        reason: str,
        *,
        judgment_source: str = "",
        max_rounds_reached: bool = False,
        rounds: int | None = None,
    ) -> None:
        nonlocal run_outcome_recorded
        if run_outcome_recorded:
            return
        run_outcome_recorded = True
        record_auto_pilot_run_finished(
            reason=reason,
            rounds=(getattr(core, "auto_pilot_round", 0) if rounds is None else rounds),
            judgment_source=judgment_source,
            max_rounds_reached=max_rounds_reached,
        )

    try:
        while True:
            # The flag can be cleared by the GUI stop button or another
            # controller.  Do not require a keyboard event in that case.
            if not core.auto_pilot_active:
                record_run_outcome("stopped", judgment_source=last_judgment_source)
                print(_("[AUTO] Stopped."))
                return

            # F11 requests an auto-pilot stop; F12 is reserved for stopping
            # the current LLM response.
            with core.auto_pilot_exit_lock:
                if core.auto_pilot_exit_requested:
                    core.auto_pilot_exit_requested = False
                    core.auto_pilot_active = False
                    record_run_outcome(
                        "user_exit",
                        judgment_source=last_judgment_source,
                    )
                    print(_("[AUTO] Exited by user (F11)."))
                    return

            # Check the deterministic completion path before spending another
            # reviewer LLM call. This is useful for batch runs whose final
            # answer contains a known marker.
            if _completion_regex_matches(
                messages, getattr(core, "auto_pilot_complete_regex", None)
            ):
                core.auto_pilot_active = False
                if not getattr(core, "_last_completion_reason", None):
                    core._last_completion_reason = "regex"
                    print(
                        '[COMPLETE] {"reason":"regex","source":"auto"}',
                        flush=True,
                    )
                record_run_outcome("completion_regex")
                print(_("[AUTO] Completion regex matched."))
                return

            # === Step B first: Reviewer judgment ===
            # Sentinel mode is an opt-in single-LLM path: the target model's
            # exact final marker replaces the extra reviewer LLM call.
            if _sentinel_mode_enabled():
                sentinel_started = time.perf_counter()
                judgment = _sentinel_judgment(messages)
                sentinel_latency_ms = (time.perf_counter() - sentinel_started) * 1000.0
                feedback = ""
                last_judgment_source = "sentinel"
                if judgment is None:
                    record_auto_pilot_judgment(
                        source="sentinel",
                        round_number=getattr(core, "auto_pilot_round", 0),
                        fallback=False,
                        provider=provider,
                        model=depname,
                        latency_ms=sentinel_latency_ms,
                        error_type="InvalidSentinel",
                        additional_call=False,
                    )
                    record_run_outcome(
                        "sentinel_invalid",
                        judgment_source=last_judgment_source,
                    )
                    print(
                        _("[AUTO] Missing or invalid auto sentinel; stopping safely.")
                    )
                    return
                record_auto_pilot_judgment(
                    source="sentinel",
                    round_number=getattr(core, "auto_pilot_round", 0),
                    answer=judgment,
                    fallback=False,
                    provider=provider,
                    model=depname,
                    latency_ms=sentinel_latency_ms,
                    additional_call=False,
                )
                print(_("\n[AUTO:sentinel] %(judgment)s") % {"judgment": judgment})
            else:
                decision_result = None
                settings = get_decision_settings()
                if settings.enabled:
                    if not decision_provider_initialized:
                        decision_provider_initialized = True
                        try:
                            decision_provider = create_decision_provider(settings)
                        except Exception as exc:
                            record_auto_pilot_judgment(
                                source="decision_provider",
                                round_number=getattr(core, "auto_pilot_round", 0),
                                fallback=False,
                                provider=settings.provider,
                                error_type=type(exc).__name__,
                                additional_call=False,
                            )
                            detail = _decision_failure_detail(exc)
                            detail_text = f" detail={detail!r}" if detail else ""
                            print(
                                "[AUTO:judge:decision] "
                                f"provider={settings.provider} "
                                f"init_failed={type(exc).__name__}{detail_text}; "
                                "falling back to LLM reviewer",
                                flush=True,
                            )
                            decision_provider = None

                    if (
                        decision_provider is not None
                        and not decision_provider_choice_checked
                    ):
                        decision_provider_choice_checked = True
                        supports_choice = _decision_provider_supports_choice(
                            decision_provider
                        )
                        if supports_choice is False:
                            record_auto_pilot_judgment(
                                source="decision_provider",
                                round_number=getattr(core, "auto_pilot_round", 0),
                                fallback=False,
                                provider=settings.provider,
                                model=str(
                                    getattr(decision_provider, "model", "") or ""
                                ),
                                error_type="UnsupportedChoice",
                                additional_call=False,
                            )
                            print(
                                "[AUTO:judge:decision] "
                                f"provider={settings.provider} model="
                                f"{getattr(decision_provider, 'model', '')} "
                                "does_not_support=choice; "
                                "falling back to LLM reviewer",
                                flush=True,
                            )
                            try:
                                decision_provider.close()
                            except Exception:
                                pass
                            decision_provider = None

                    if decision_provider is not None:
                        decision_result = _ask_auto_pilot_decision(
                            messages,
                            core,
                            decision_provider=decision_provider,
                        )
                        if decision_result is None:
                            print(
                                "[AUTO:judge:decision] "
                                f"provider={settings.provider} disabled_for_run=true; "
                                "using LLM reviewer for remaining rounds",
                                flush=True,
                            )
                            try:
                                decision_provider.close()
                            except Exception:
                                pass
                            decision_provider = None

                if decision_result is None:
                    # On the first iteration this judges the initial goal execution.
                    # On subsequent iterations this judges the followup from Step A.
                    last_judgment_source = "llm_reviewer"
                    judgment, feedback = _ask_reviewer_judgment(
                        _judge_provider,
                        _judge_client,
                        _judge_depname,
                        messages,
                        core,
                        make_client_fn=make_client_fn,
                        fallback=settings.enabled,
                    )
                else:
                    last_judgment_source = "decision_provider"
                    judgment, feedback = decision_result

            if judgment == "COMPLETE":
                core.auto_pilot_active = False
                core._last_round_outcome = {
                    "status": "completed",
                    "reason": "reviewer",
                }
                record_run_outcome(
                    "complete",
                    judgment_source=last_judgment_source,
                )
                print(_("[AUTO] Review/analysis completed."))
                return

            # 2. Max rounds check (after judgment to count actual followup rounds)
            core.auto_pilot_round += 1
            max_rounds = core.auto_pilot_max_rounds
            if max_rounds is not None and core.auto_pilot_round > max_rounds:
                core.auto_pilot_active = False
                core._last_round_outcome = {
                    "status": "failed",
                    "reason": "max_rounds",
                }
                record_run_outcome(
                    "max_rounds",
                    judgment_source=last_judgment_source,
                    max_rounds_reached=True,
                    rounds=max_rounds,
                )
                print(
                    _("[AUTO] Max rounds (%(max)d) reached. Stopping.")
                    % {"max": max_rounds}
                )
                return

            # === Step A: Main query (refinement followup) ===
            next_prompt = _get_followup_prompt(core.auto_pilot_goal, feedback)
            if _sentinel_mode_enabled():
                next_prompt = _with_sentinel_instruction(next_prompt)

            core.set_status(True, "AUTO")
            if core.auto_pilot_max_rounds is None:
                print(
                    _("[AUTO] Round %(round)d/INFINITE")
                    % {"round": core.auto_pilot_round}
                )
            else:
                print(
                    _("[AUTO] Round %(round)d/%(max)d")
                    % {
                        "round": core.auto_pilot_round,
                        "max": core.auto_pilot_max_rounds,
                    }
                )

            user_msg = {"role": "user", "content": next_prompt}
            messages.append(user_msg)
            core.log_message(user_msg)

            # Reset interrupt flag for each round
            with core.interrupt_lock:
                core.interrupt_requested = False

            llm_util.run_llm_rounds(
                provider,
                client,
                depname,
                messages,
                core=core,
                make_client_fn=make_client_fn,
                append_result_to_outfile_fn=append_result_to_outfile_fn,
                try_open_images_from_text_fn=try_open_images_from_text_fn,
                preserve_tool_loop_state=True,
            )

            core.set_status(True, "AUTO")

    finally:
        if not run_outcome_recorded:
            record_run_outcome(
                "aborted",
                judgment_source=last_judgment_source,
            )
        if decision_provider is not None:
            try:
                decision_provider.close()
            except Exception:
                pass
        # Never leave auto mode latched after completion or an exception.
        core.auto_pilot_active = False


def _parse_auto_goal_options(
    raw: str,
) -> tuple[str, int | None, bool, str | None]:
    """Parse auto options without tokenizing or rewriting the goal text.

    ``--inject-message-auto`` passes a complete goal as one argv value. The
    goal may contain newlines, quotes, or apostrophes, so shell tokenization is
    deliberately avoided. Options are recognized only as suffixes, matching
    the documented command form.
    """
    value = str(raw or "").strip()
    max_rounds: int | None = 10
    infinite_mode = False

    if re.match(r"^INFINITE(?:\s+|$)", value, flags=re.IGNORECASE):
        infinite_mode = True
        value = value[len("INFINITE") :].lstrip()

    max_match = re.search(
        r"(?:\s+)--max-rounds\s+(?P<value>INFINITE|[+-]?\d+)\s*$",
        value,
        flags=re.IGNORECASE,
    )
    if max_match:
        raw_max = max_match.group("value")
        if raw_max.upper() == "INFINITE":
            infinite_mode = True
        else:
            try:
                max_rounds = int(raw_max)
            except ValueError:
                return value, max_rounds, infinite_mode, raw_max
            if max_rounds <= 0:
                return value, max_rounds, infinite_mode, raw_max
        value = value[: max_match.start()].rstrip()
    else:
        infinite_match = re.search(r"(?:\s+)--infinite\s*$", value, flags=re.IGNORECASE)
        if infinite_match:
            infinite_mode = True
            value = value[: infinite_match.start()].rstrip()

    if re.search(r"(?:^|\s)--max-rounds\s*$", value, flags=re.IGNORECASE):
        return value, max_rounds, infinite_mode, ""

    if infinite_mode:
        max_rounds = None
    return value, max_rounds, infinite_mode, None


def _handle_cmd_auto(
    arg: str,
    messages_ref: list[dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
    tr: Any,
) -> CommandResult | bool:
    """Handle the :auto command.

    Usage:
      :auto <goal> [--max-rounds N|INFINITE]
      :auto <goal> --infinite
      :auto INFINITE <goal>
      :auto off
    """
    a = (arg or "").strip()

    if a.lower() == "off":
        core.auto_pilot_active = False
        core.auto_pilot_exit_requested = False
        print(_("[AUTO] Auto-pilot turned off."))
        return CommandResult()

    if not a:
        print(tr("Usage: :auto <goal> [--max-rounds N]"))
        print(tr("       :auto off"))
        return CommandResult()

    # Parse only documented suffix options. Preserve the goal as one string so
    # newlines, quotes, apostrophes, and non-ASCII text reach the model intact.
    goal, max_rounds, _infinite_mode, parse_error = _parse_auto_goal_options(a)
    if parse_error is not None:
        print(
            tr("Invalid value for --max-rounds: %(val)s")
            % {"val": parse_error or "<missing>"}
        )
        return CommandResult()
    if not goal:
        print(tr("Goal cannot be empty."))
        return CommandResult()

    # Set auto-pilot state
    core.auto_pilot_goal = goal
    core.auto_pilot_max_rounds = max_rounds
    core.auto_pilot_round = 0
    core.auto_pilot_exit_requested = False
    core.auto_pilot_active = True

    print(_("[AUTO] Started. Goal: %(goal)s") % {"goal": goal})
    if max_rounds is None:
        print(_("[AUTO] Max rounds: INFINITE"))
    else:
        print(_("[AUTO] Max rounds: %(max)d") % {"max": max_rounds})

    # Return CommandResult with run_llm=True to trigger the first LLM call.
    # In opt-in sentinel mode, the target model itself supplies continuation.
    prompt = _with_sentinel_instruction(goal) if _sentinel_mode_enabled() else goal
    return CommandResult(run_llm=True, prompt=prompt)
