"""Autonomous completion policy for Sub-Agents.

This module mirrors Auto-pilot's completion precedence while keeping Sub-Agent
execution policy independent:

1. optional deterministic completion regex
2. optional sentinel protocol
3. configured Decision Provider (Jev/Laya)
4. conservative LLM reviewer fallback

Decision Provider failures disable that provider for the remainder of the
current Sub-Agent run, matching Auto-pilot's run-local circuit breaker.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from ..decision import create_decision_provider, get_decision_settings
from ..decision.goal_completion import (
    GoalCompletionError,
    evaluate_goal_completion,
    provider_supports_goal_completion,
)
from ..runtime.agent_loop import AgentLoopJudgment
from ..utils.secret_mask import _mask_inline_secrets, mask_message


SUB_AGENT_SENTINEL_INSTRUCTION = (
    "\n\nSub-Agent completion protocol: finish your response with exactly one "
    "line: <SUB_AGENT_CONTINUE> if material work remains, or "
    "<SUB_AGENT_COMPLETE> if the task is complete. If sentinel mode is enabled "
    "and neither marker is present, the autonomous loop stops safely."
)


@dataclass(frozen=True)
class SubAgentJudgeEvent:
    source: str
    judgment: str = ""
    provider: str = ""
    model: str = ""
    detail: str = ""


ReviewCallback = Callable[[dict[str, Any]], tuple[str, str]]
EventCallback = Callable[[SubAgentJudgeEvent], None]


def completion_regex_matches(text: str, pattern: str | None) -> bool:
    raw_pattern = str(pattern or "").strip()
    if not raw_pattern:
        return False
    try:
        return re.search(raw_pattern, str(text or ""), flags=re.MULTILINE) is not None
    except re.error:
        return False


def sentinel_judgment(text: str) -> str | None:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return None
    marker = lines[-1].upper()
    if re.fullmatch(r"(?:<SUB_AGENT_COMPLETE>|SUB_AGENT_COMPLETE)", marker):
        return "COMPLETE"
    if re.fullmatch(r"(?:<SUB_AGENT_CONTINUE>|SUB_AGENT_CONTINUE)", marker):
        return "CONTINUE"
    return None


def strip_sentinel(text: str) -> str:
    lines = str(text or "").splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and re.fullmatch(
        r"(?:<SUB_AGENT_(?:COMPLETE|CONTINUE)>|SUB_AGENT_(?:COMPLETE|CONTINUE))",
        lines[-1].strip(),
        flags=re.IGNORECASE,
    ):
        lines.pop()
    return "\n".join(lines).rstrip()


def parse_reviewer_judgment(raw: str) -> tuple[str, str]:
    text = str(raw or "")
    upper = text.upper()
    if re.search(r"\bCONTINUE\b", upper) or re.search(
        r"\bNOT\s+COMPLETE\b", upper
    ):
        judgment = "CONTINUE"
    elif re.search(r"\bCOMPLETE\b", upper):
        return "COMPLETE", ""
    else:
        return "CONTINUE", text.strip()

    feedback = text
    for prefix in ("CONTINUE:", "continue:", "CONTINUE", "continue"):
        if prefix in feedback:
            feedback = feedback.split(prefix, 1)[1]
            break
    return judgment, feedback.strip().strip(" -\n").strip("\"'")


def _masked_summary(value: Any, limit: int) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(mask_message(value), ensure_ascii=False)
    else:
        value = mask_message({"content": value}).get("content", "")
    return _mask_inline_secrets(" ".join(str(value or "").split()))[:limit]


def build_sub_agent_completion_state(
    goal: str,
    latest_answer: str,
    *,
    prior_answers: Iterable[str] = (),
    tool_evidence: Iterable[dict[str, Any]] = (),
    max_prior_answers: int = 4,
    max_tool_evidence: int = 4,
) -> dict[str, Any]:
    evidence: list[dict[str, str]] = []

    prior = list(prior_answers)[-max_prior_answers:]
    for answer in prior:
        summary = _masked_summary(strip_sentinel(answer), 2000)
        if summary:
            evidence.append(
                {
                    "source": "assistant",
                    "status": "reported",
                    "summary": summary,
                }
            )

    tools = list(tool_evidence)[-max_tool_evidence:]
    for item in tools:
        if not isinstance(item, dict):
            continue
        evidence.append(
            {
                "source": "tool",
                "tool": _masked_summary(item.get("tool", "tool"), 100),
                "status": _masked_summary(item.get("status", "observed"), 40),
                "summary": _masked_summary(item.get("summary", ""), 400),
            }
        )

    return {
        "goal": _masked_summary(goal, 2000),
        "latest_answer": _masked_summary(strip_sentinel(latest_answer), 12000),
        "evidence": evidence,
    }


def build_followup_prompt(
    goal: str,
    previous_output: str,
    feedback: str = "",
) -> str:
    prompt = (
        "Continue working on the same Sub-Agent task until every explicit "
        "requirement is satisfied.\n\n"
        f"[Goal]\n{goal}\n\n"
        f"[Previous result]\n{strip_sentinel(previous_output)}"
    )
    if feedback:
        prompt += f"\n\n[Completion review]\n{feedback}"
    prompt += (
        "\n\nRe-check the goal against the available evidence. Use tools when "
        "needed, then produce a revised final result."
    )
    return prompt


def build_llm_review_prompt(state: dict[str, Any]) -> tuple[str, str]:
    system_prompt = (
        "You are a conservative completion reviewer for a Sub-Agent. Determine "
        "whether every explicit requirement in the goal is actually satisfied by "
        "the latest answer and evidence.\n"
        "Satisfied and no material work remains -> COMPLETE\n"
        "Anything material missing or uncertain -> CONTINUE\n"
        "Reply with COMPLETE or CONTINUE. If CONTINUE, briefly state the concrete "
        "missing work. Format: CONTINUE: <reason>"
    )
    user_prompt = json.dumps(state, ensure_ascii=False, indent=2)
    return system_prompt, user_prompt


class SubAgentCompletionJudge:
    """Run-local multi-method completion judge."""

    def __init__(
        self,
        *,
        reviewer: ReviewCallback,
        sentinel_enabled: bool = False,
        event_callback: EventCallback | None = None,
    ) -> None:
        self._reviewer = reviewer
        self._sentinel_enabled = bool(sentinel_enabled)
        self._event_callback = event_callback
        self._settings = get_decision_settings()
        self._decision_provider: Any = None
        self._provider_initialized = False
        self._provider_disabled = False

    def _emit(self, event: SubAgentJudgeEvent) -> None:
        if self._event_callback is None:
            return
        try:
            self._event_callback(event)
        except Exception:
            pass

    def _disable_provider(self, detail: str = "") -> None:
        provider = self._decision_provider
        self._decision_provider = None
        self._provider_disabled = True
        if provider is not None:
            try:
                provider.close()
            except Exception:
                pass
        self._emit(
            SubAgentJudgeEvent(
                source="decision_provider",
                provider=str(getattr(provider, "name", "") or self._settings.provider),
                model=str(getattr(provider, "model", "") or ""),
                detail=detail,
            )
        )

    def _ensure_provider(self) -> Any:
        if (
            not self._settings.enabled
            or self._provider_disabled
            or self._decision_provider is not None
        ):
            return self._decision_provider
        if self._provider_initialized:
            return None

        self._provider_initialized = True
        try:
            provider = create_decision_provider(self._settings)
        except Exception as exc:
            self._disable_provider(type(exc).__name__)
            return None

        if provider is None:
            self._provider_disabled = True
            return None

        supports = provider_supports_goal_completion(provider)
        if supports is False:
            self._decision_provider = provider
            self._disable_provider("unsupported_completion_questions")
            return None

        self._decision_provider = provider
        return provider

    def judge(
        self,
        state: dict[str, Any],
        *,
        raw_output: str,
    ) -> AgentLoopJudgment:
        if self._sentinel_enabled:
            judgment = sentinel_judgment(raw_output)
            if judgment is None:
                self._emit(
                    SubAgentJudgeEvent(
                        source="sentinel",
                        detail="invalid_or_missing_sentinel",
                    )
                )
                return AgentLoopJudgment(
                    complete=False,
                    source="sentinel",
                    terminal_reason="sentinel_invalid",
                )
            self._emit(SubAgentJudgeEvent(source="sentinel", judgment=judgment))
            return AgentLoopJudgment(
                complete=judgment == "COMPLETE",
                feedback=(
                    ""
                    if judgment == "COMPLETE"
                    else "The Sub-Agent reported that material work remains."
                ),
                source="sentinel",
            )

        provider = self._ensure_provider()
        if provider is not None:
            try:
                evaluation = evaluate_goal_completion(
                    provider,
                    state,
                    site="sub_agent_review",
                    choice_question_id="sub_agent_goal_status",
                    choice_subject="sub-agent task",
                )
            except GoalCompletionError as exc:
                self._disable_provider(exc.reason)
            else:
                self._emit(
                    SubAgentJudgeEvent(
                        source="decision_provider",
                        judgment=evaluation.judgment,
                        provider=evaluation.provider,
                        model=evaluation.model,
                    )
                )
                return AgentLoopJudgment(
                    complete=evaluation.judgment == "COMPLETE",
                    feedback=(
                        ""
                        if evaluation.judgment == "COMPLETE"
                        else (
                            "The completion judge found material work remaining. "
                            "Re-check every explicit requirement and the evidence."
                        )
                    ),
                    source="decision_provider",
                )

        judgment, feedback = self._reviewer(state)
        normalized = "COMPLETE" if str(judgment).upper() == "COMPLETE" else "CONTINUE"
        self._emit(
            SubAgentJudgeEvent(
                source="llm_reviewer",
                judgment=normalized,
                detail=feedback,
            )
        )
        return AgentLoopJudgment(
            complete=normalized == "COMPLETE",
            feedback=feedback,
            source="llm_reviewer",
        )

    def close(self) -> None:
        provider = self._decision_provider
        self._decision_provider = None
        if provider is not None:
            try:
                provider.close()
            except Exception:
                pass
