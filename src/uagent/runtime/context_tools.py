"""Budget-aware selection of provider tool definitions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Sequence

from .active_context import ContextCandidate, ContextDecision
from .context_budget import ContextBudget
from .context_decision import ContextDecisionEngine, DecisionPolicy

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]")
_ALWAYS_RELEVANT_TOOL_NAMES = frozenset(
    {"tool_catalog", "tool_load", "unload_tool", "human_ask"}
)


@dataclass(frozen=True)
class ToolDefinitionSelection:
    """Selected tool specs and the decisions that produced the selection."""

    specs: list[dict[str, Any]]
    decisions: list[ContextDecision]
    raw_chars: int
    active_chars: int


def _tool_name(spec: dict[str, Any], index: int) -> str:
    function = spec.get("function")
    if isinstance(function, dict):
        name = function.get("name")
        if name:
            return str(name)
    return f"tool-{index}"


def _tool_text(spec: dict[str, Any]) -> str:
    try:
        return json.dumps(spec, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(spec)


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(text or "")}


def _relevance(
    task: str,
    spec: dict[str, Any],
    *,
    task_tokens: set[str] | None = None,
    tool_tokens: set[str] | None = None,
) -> float:
    function = spec.get("function")
    name = str(function.get("name") or "") if isinstance(function, dict) else ""
    if name in _ALWAYS_RELEVANT_TOOL_NAMES:
        return 1.0
    query = task_tokens if task_tokens is not None else _tokens(task)
    if not query:
        return 0.5
    haystack = tool_tokens if tool_tokens is not None else _tokens(_tool_text(spec))
    overlap = len(query & haystack) / len(query)
    # Keep a no-match fallback above the exclusion threshold so a task with
    # unusual vocabulary still receives a useful, budgeted tool surface.
    return min(1.0, 0.25 + (0.75 * overlap))


def select_tool_definitions(
    tool_specs: Sequence[dict[str, Any]] | None,
    *,
    task: str = "",
    budget: ContextBudget | None = None,
    provider: str = "",
    model: str = "",
    max_tools: int | None = None,
) -> ToolDefinitionSelection:
    """Select whole tool definitions without producing invalid partial JSON.

    Tool schemas are never character-compacted. Low-ranked definitions are
    excluded when the tool-definition section and shared context budget are
    exhausted; the returned decisions explain each exclusion.
    """
    specs = [spec for spec in (tool_specs or []) if isinstance(spec, dict)]
    if max_tools is not None and max_tools < 0:
        raise ValueError("max_tools must be non-negative")
    active_budget = budget or ContextBudget()
    candidates = []
    tool_texts: list[str] = []
    tool_names: list[str] = []
    task_tokens = _tokens(task or "")
    raw_chars = 0
    for index, spec in enumerate(specs):
        text = _tool_text(spec)
        tool_texts.append(text)
        tool_name = _tool_name(spec, index)
        tool_names.append(tool_name)
        raw_chars += len(text)
        tool_tokens = (
            _tokens(text)
            if task_tokens and tool_name not in _ALWAYS_RELEVANT_TOOL_NAMES
            else set()
        )
        candidates.append(
            # ``compact_score`` is above the valid score range: schemas must
            # be kept whole, so a partially fitting schema is excluded.
            ContextCandidate(
                item_id=tool_name,
                source="tool_definition",
                section="tool_definitions",
                content=text,
                relevance=_relevance(
                    task,
                    spec,
                    task_tokens=task_tokens,
                    tool_tokens=tool_tokens,
                ),
            )
        )

    engine = ContextDecisionEngine(
        policy=DecisionPolicy(compact_score=1.01),
    )
    decisions = engine.decide(candidates, budget=active_budget)
    decision_by_id = {decision.item_id: decision for decision in decisions}
    selected_entries = [
        (index, spec, decision_by_id[tool_names[index]])
        for index, spec in enumerate(specs)
        if tool_names[index] in decision_by_id
        and decision_by_id[tool_names[index]].action == "KEEP"
    ]
    if max_tools is not None and len(selected_entries) > max_tools:
        selected_entries = sorted(
            selected_entries,
            key=lambda entry: (-float(entry[2].importance or 0), entry[0]),
        )[:max_tools]
        selected_entries.sort(key=lambda entry: entry[0])
    selected = [spec for _, spec, _ in selected_entries]

    active_chars = sum(len(tool_texts[index]) for index, _, _ in selected_entries)
    return ToolDefinitionSelection(
        specs=selected,
        decisions=decisions,
        raw_chars=raw_chars,
        active_chars=active_chars,
    )


__all__ = ["ToolDefinitionSelection", "select_tool_definitions"]
