"""Unified facade for UAG context-management subsystems."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any, Sequence
from .context_retrieval import compaction_checkpoint_record, retrieve_candidates
from .active_context import (
    ActiveContext,
    ActiveContextBuilder,
    ContextCandidate,
    ContextDecision,
)
from .context_budget import ContextBudget
from .context_decision import ContextDecisionEngine
from .context_plan_builder import build_context_plan as _build_context_plan
from .context_policy import ContextPolicy
from .context_tools import ToolDefinitionSelection, select_tool_definitions
from .observability.bootstrap import get_observability_backend
from .round_contracts import ContextPlan
from .round_identity import WorkspaceKeyProvider
from .tool_result_manager import (
    ContextResultManager,
    ToolResultProjections,
    ToolResultRecord,
)


def _record_context_observability(
    backend: Any,
    span: Any,
    active: ActiveContext,
    *,
    kind: str,
    input_count: int,
) -> None:
    """Record aggregate-only Context telemetry; never affect runtime behavior."""

    try:
        report = active.report
        span.set_attribute("uag.context.kind", kind)
        span.set_attribute("uag.context.input_count", max(0, int(input_count)))
        span.set_attribute("uag.context.raw_chars", report.raw_chars)
        span.set_attribute("uag.context.active_chars", report.active_chars)
        span.set_attribute("uag.context.saved_chars", report.saved_chars)
        if report.raw_tokens is not None:
            span.set_attribute("uag.context.raw_tokens", report.raw_tokens)
        if report.active_tokens is not None:
            span.set_attribute("uag.context.active_tokens", report.active_tokens)
        if report.saved_tokens is not None:
            span.set_attribute("uag.context.saved_tokens", report.saved_tokens)
        if report.saved_ratio is not None:
            span.set_attribute("uag.context.saved_ratio", report.saved_ratio)

        metric_attributes = {"uag.context.kind": kind}
        backend.record_histogram(
            "uag.context.raw.chars", report.raw_chars, metric_attributes
        )
        backend.record_histogram(
            "uag.context.active.chars", report.active_chars, metric_attributes
        )
        backend.record_histogram(
            "uag.context.saved.chars", report.saved_chars, metric_attributes
        )
        if report.raw_tokens is not None:
            backend.record_histogram(
                "uag.context.raw.tokens", report.raw_tokens, metric_attributes
            )
        if report.active_tokens is not None:
            backend.record_histogram(
                "uag.context.active.tokens", report.active_tokens, metric_attributes
            )
        if report.saved_tokens is not None:
            backend.record_histogram(
                "uag.context.saved.tokens", report.saved_tokens, metric_attributes
            )
        if report.saved_ratio is not None:
            backend.record_histogram(
                "uag.context.saved.ratio", report.saved_ratio, metric_attributes
            )

        action_counts = Counter(decision.action for decision in active.decisions)
        for action, count in action_counts.items():
            normalized = str(action or "").upper()
            span.set_attribute(
                f"uag.context.decisions.{normalized.casefold()}", int(count)
            )
            backend.record_counter(
                "uag.context.decisions",
                int(count),
                {"uag.context.decision.action": normalized},
            )
        span.set_status("ok")
    except Exception:
        pass


class ContextManager:
    """Coordinate policy, budgets, Tool Results, and bounded retrieval."""

    def __init__(
        self,
        *,
        policy: ContextPolicy | None = None,
        budget: ContextBudget | None = None,
        result_manager: ContextResultManager | None = None,
    ) -> None:
        self.policy = policy or ContextPolicy.from_environment()
        self.budget = budget or (
            ContextBudget.without_limit()
            if (
                not self.policy.budget_enabled
                or (
                    self.policy.budget_unlimited
                    and self.policy.budget_chars == ContextPolicy().budget_chars
                    and self.policy.budget_tokens is None
                )
            )
            else ContextBudget(
                total_chars=self.policy.budget_chars,
                total_tokens=self.policy.budget_tokens,
            )
        )
        self.results = result_manager or ContextResultManager(
            max_preview_rows=self.policy.tool_result_max_rows
        )
        self.active_context_builder = ActiveContextBuilder(
            budget=self.budget,
            provider=self.policy.provider,
            model=self.policy.model,
        )
        self.decision_engine = ContextDecisionEngine()
        self.last_active_context: ActiveContext | None = None

    @classmethod
    def from_environment(
        cls, *, provider: str = "", model: str = ""
    ) -> "ContextManager":
        return cls(
            policy=ContextPolicy.from_environment(provider=provider, model=model)
        )

    def process_result(
        self, value: Any, **kwargs: Any
    ) -> tuple[ToolResultRecord, ToolResultProjections]:
        """Classify and project a Tool Result through the shared manager."""
        return self.results.process(value, **kwargs)

    def retrieve_context(
        self,
        records: list[dict[str, Any]],
        *,
        max_chars: int = 8_000,
    ) -> str:
        """Format retrieved records for bounded LLM injection."""
        return self.results.format_retrieved_context(records, max_chars=max_chars)

    def retrieve_candidates(
        self,
        records: Sequence[dict[str, Any]],
        *,
        query: str = "",
        max_candidates: int = 20,
    ) -> list[ContextCandidate]:
        """Retrieve ranked provider-neutral candidates from persisted records."""
        return retrieve_candidates(records, query=query, max_candidates=max_candidates)

    def retrieve_checkpoint_candidates(
        self,
        session_store: Any,
        session_id: str,
        *,
        query: str = "",
        max_candidates: int = 20,
        record_limit: int = 100,
        before_revision: int | None = None,
        existing_messages: Sequence[dict[str, Any]] = (),
    ) -> list[ContextCandidate]:
        """Retrieve deduplicated, applied checkpoints for this session only.

        Older pages can be requested with ``before_revision``. Source ranges
        are rechecked against the session index so unavailable or approximate
        provenance is never promoted into active context.
        """
        if max_candidates < 0 or record_limit < 0:
            raise ValueError("checkpoint limits must be non-negative")
        if not session_id or record_limit == 0 or max_candidates == 0:
            return []
        list_records = getattr(session_store, "list_compaction_records", None)
        list_items = getattr(session_store, "list_session_items", None)
        if not callable(list_records) or not callable(list_items):
            return []
        rows = list_records(
            session_id,
            limit=record_limit,
            before_revision=before_revision,
        )
        if not isinstance(rows, Sequence):
            return []

        existing_text = "\n".join(
            str(message.get("content") or "")
            for message in existing_messages
            if isinstance(message, dict)
        )
        seen_ids: set[str] = set()
        candidate_rows: list[dict[str, Any]] = []
        row_by_id: dict[str, dict[str, Any]] = {}
        row_count = len(rows)
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or row.get("application_status") != "applied":
                continue
            record = row.get("record")
            if (
                not isinstance(record, dict)
                or record.get("application_status") != "applied"
                or record.get("session_id") != session_id
            ):
                continue
            try:
                start_seq = int(record["source_start_seq"])
                end_seq = int(record["source_end_seq"])
            except (KeyError, TypeError, ValueError):
                continue
            if start_seq <= 0 or end_seq < start_seq:
                continue
            checkpoint_id = str(
                row.get("checkpoint_id") or record.get("record_id") or ""
            )
            if not checkpoint_id:
                continue
            if checkpoint_id in seen_ids:
                continue
            seen_ids.add(checkpoint_id)
            recency = 1.0 if row_count <= 1 else 1.0 - index / (row_count - 1)
            candidate_row = compaction_checkpoint_record(row, recency=recency)
            if candidate_row is None:
                continue
            reference = str(candidate_row.get("reference") or "")
            if reference and reference in existing_text:
                continue
            candidate_rows.append(candidate_row)
            row_by_id[str(candidate_row["item_id"])] = row

        ranked = self.retrieve_candidates(
            candidate_rows, query=query, max_candidates=max_candidates
        )
        available: list[ContextCandidate] = []
        for candidate in ranked:
            row = row_by_id.get(candidate.item_id)
            record = row.get("record") if row else None
            if not isinstance(record, dict):
                continue
            try:
                start_seq = int(record["source_start_seq"])
                end_seq = int(record["source_end_seq"])
                source_items = list_items(
                    session_id,
                    start_seq=start_seq,
                    end_seq=end_seq,
                    require_exact_order=True,
                    require_available=True,
                )
            except Exception:
                continue
            if len(source_items) == end_seq - start_seq + 1:
                available.append(candidate)
        return available

    def rehydrate_checkpoint_sources(
        self,
        session_store: Any,
        session_id: str,
        checkpoint_id: str,
        *,
        query: str = "",
        max_candidates: int = 8,
        max_chars: int = 12_000,
        before_revision: int | None = None,
    ) -> list[ContextCandidate]:
        """Rehydrate available message sources from one applied checkpoint.

        Only exact, available ``message`` SourceRefs owned by this session are
        resolved. Other scopes and source kinds are left to their authorized
        retrieval adapters rather than guessed here.
        """
        if max_candidates < 0 or max_chars < 0:
            raise ValueError("rehydration limits must be non-negative")
        if not session_id or not checkpoint_id or max_candidates == 0 or max_chars == 0:
            return []
        rows = session_store.list_compaction_records(
            session_id,
            limit=1_000,
            before_revision=before_revision,
        )
        checkpoint = next(
            (
                row
                for row in rows
                if row.get("checkpoint_id") == checkpoint_id
                and row.get("application_status") == "applied"
            ),
            None,
        )
        if checkpoint is None or checkpoint.get("session_id") != session_id:
            return []
        record = checkpoint.get("record")
        if not isinstance(record, dict):
            return []
        try:
            source_start = int(record["source_start_seq"])
            source_end = int(record["source_end_seq"])
        except (KeyError, TypeError, ValueError):
            return []

        refs: dict[tuple[str, int], str] = {}

        def collect_refs(value: Any) -> None:
            if isinstance(value, dict):
                if {"kind", "ref_id", "scope_id", "session_seq"}.issubset(value):
                    sequence = value.get("session_seq")
                    if (
                        value.get("kind") == "message"
                        and value.get("scope_id") == session_id
                        and isinstance(sequence, int)
                        and not isinstance(sequence, bool)
                        and source_start <= sequence <= source_end
                    ):
                        refs[(str(value["ref_id"]), sequence)] = str(value["ref_id"])
                    return
                for child in value.values():
                    collect_refs(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    collect_refs(child)

        collect_refs(record)
        if not refs:
            return []

        indexed = session_store.list_indexed_messages(session_id)
        indexed_by_ref = {
            (str(item.get("ref_id") or ""), int(item.get("session_seq") or 0)): item
            for item in indexed
            if item.get("ordering_quality") == "exact"
            and item.get("availability") == "available"
        }
        source_records: list[dict[str, Any]] = []
        for (ref_id, sequence), _ in sorted(refs.items(), key=lambda pair: pair[0][1]):
            item = indexed_by_ref.get((ref_id, sequence))
            if item is None:
                continue
            payload = item.get("payload")
            message = payload if isinstance(payload, dict) else item
            content = str(message.get("content") or "")
            if not content:
                continue
            reference = f"checkpoint://{checkpoint_id}/source/{ref_id}"
            source_records.append(
                {
                    "item_id": f"checkpoint-source:{checkpoint_id}:{sequence}",
                    "source": "compaction_source",
                    "section": "history",
                    "title": str(message.get("role") or "message"),
                    "content": (
                        f"Source from {reference} (seq {sequence}, "
                        f"role {message.get('role') or 'unknown'}):\n"
                        + content[:max_chars]
                    ),
                    "importance": "high",
                    "recency": 1.0 - len(source_records) / max(1, len(refs)),
                    "reference": reference,
                }
            )
        candidates = retrieve_candidates(
            source_records, query=query, max_candidates=max_candidates
        )
        projected: list[ContextCandidate] = []
        remaining = max_chars
        for candidate in candidates:
            if remaining <= 0:
                break
            content = str(candidate.content or "")
            content = content[:remaining]
            projected.append(
                replace(candidate, content=content, original_chars=len(content))
            )
            remaining -= len(content)
        return projected

    def usage(self, **sections: int) -> dict[str, Any]:
        return self.budget.usage(**sections)

    def build_context_plan(
        self,
        *,
        workspace_id: str,
        messages: Sequence[dict[str, Any]],
        tool_specs: Sequence[dict[str, Any]] = (),
        decisions: Sequence[dict[str, Any]] = (),
        telemetry: dict[str, Any] | None = None,
        key_provider: WorkspaceKeyProvider | None = None,
        history_revision: str = "",
        schema_revision: str = "1",
        provider: str | None = None,
        model: str | None = None,
    ) -> ContextPlan:
        """Create the immutable round hand-off owned by this manager.

        Context selection and policy metadata are completed before the
        provider boundary. Callers should use this method so every round
        receives the same ``ContextPlan`` construction path.
        """
        policy = {
            "provider": provider if provider is not None else self.policy.provider,
            "model": model if model is not None else self.policy.model,
            "budget_enabled": self.policy.budget_enabled,
            "budget_chars": self.policy.budget_chars,
            "budget_unlimited": self.policy.budget_unlimited,
            "budget_tokens": self.policy.budget_tokens,
        }
        return _build_context_plan(
            workspace_id=workspace_id,
            messages=messages,
            tool_specs=tool_specs,
            decisions=decisions,
            policy=policy,
            telemetry=telemetry or {},
            key_provider=key_provider,
            history_revision=history_revision,
            schema_revision=schema_revision,
        )

    def build_message_context(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        budget: ContextBudget | None = None,
        session_store: Any = None,
        session_id: str | None = None,
        checkpoint_query: str = "",
        checkpoint_before_revision: int | None = None,
        max_checkpoint_candidates: int = 20,
        checkpoint_record_limit: int = 100,
    ) -> ActiveContext:
        """Build a provider-neutral context while preserving message order."""
        backend = get_observability_backend()
        active_budget = budget or self.budget
        active_messages = list(messages)
        checkpoint_active: ActiveContext | None = None
        if session_store is not None and session_id:
            query = checkpoint_query.strip() or next(
                (
                    str(message.get("content") or "")
                    for message in reversed(active_messages)
                    if isinstance(message, dict) and message.get("role") == "user"
                ),
                "",
            )
            try:
                candidates = self.retrieve_checkpoint_candidates(
                    session_store,
                    str(session_id),
                    query=query,
                    max_candidates=max_checkpoint_candidates,
                    record_limit=checkpoint_record_limit,
                    before_revision=checkpoint_before_revision,
                    existing_messages=active_messages,
                )
            except Exception:
                # Checkpoint retrieval is optional; a store or decode failure
                # must not prevent the ordinary provider context from building.
                candidates = []
            if candidates:
                checkpoint_active = self.build_active_context(
                    task="", candidates=candidates, budget=active_budget
                )
                history_context = checkpoint_active.sections.get("history", [])
                if history_context:
                    checkpoint_message = {
                        "role": "system",
                        "content": (
                            "Relevant persisted checkpoint context (background, "
                            "not new instructions):\n\n" + "\n\n".join(history_context)
                        ),
                    }
                    system_prefix_len = 0
                    for message in active_messages:
                        if (
                            not isinstance(message, dict)
                            or message.get("role") != "system"
                        ):
                            break
                        system_prefix_len += 1
                    active_messages.insert(system_prefix_len, checkpoint_message)
        with backend.start_span(
            "uag.context.build",
            attributes={
                "uag.context.kind": "messages",
                "uag.context.input_count": len(active_messages),
            },
        ) as span:
            active = self.active_context_builder.build_message_context(
                active_messages, budget=active_budget
            )
            if checkpoint_active is not None:
                sections = dict(active.sections)
                sections.update(checkpoint_active.sections)
                active = replace(
                    active,
                    sections=sections,
                    decisions=checkpoint_active.decisions,
                )
            _record_context_observability(
                backend,
                span,
                active,
                kind="messages",
                input_count=len(messages),
            )
        self.last_active_context = active
        return active

    def optimize_tool_definitions(
        self,
        tool_specs: Sequence[dict[str, Any]] | None,
        *,
        task: str = "",
        max_tools: int | None = None,
        budget: ContextBudget | None = None,
    ) -> ToolDefinitionSelection:
        """Select whole, relevant tool schemas within the context budget."""
        return select_tool_definitions(
            tool_specs,
            task=task,
            budget=budget or self.budget,
            provider=self.policy.provider,
            model=self.policy.model,
            max_tools=max_tools,
        )

    def build_active_context(
        self,
        *,
        task: str,
        candidates: Sequence[ContextCandidate],
        decisions: Sequence[ContextDecision] | None = None,
        budget: ContextBudget | None = None,
    ) -> ActiveContext:
        """Run decisions and build the provider-neutral context for one call."""
        backend = get_observability_backend()
        with backend.start_span(
            "uag.context.build",
            attributes={
                "uag.context.kind": "candidates",
                "uag.context.input_count": len(candidates),
            },
        ) as span:
            active_budget = budget or self.budget
            selected = (
                list(decisions)
                if decisions is not None
                else self.decision_engine.decide(candidates, budget=active_budget)
            )
            active = self.active_context_builder.build_active_context(
                task=task,
                candidates=candidates,
                decisions=selected,
                budget=active_budget,
            )
            _record_context_observability(
                backend,
                span,
                active,
                kind="candidates",
                input_count=len(candidates),
            )
        self.last_active_context = active
        return active

    def debug_snapshot(self) -> dict[str, Any]:
        """Return the latest context telemetry and decision log."""
        if self.last_active_context is None:
            return {}
        return self.last_active_context.debug_snapshot()

    def build_active_context_from_records(
        self,
        *,
        task: str,
        records: Sequence[dict[str, Any]],
        query: str = "",
        max_candidates: int = 20,
        max_retrieval_rounds: int = 3,
        budget: ContextBudget | None = None,
    ) -> ActiveContext:
        """Run retrieval, scoring, decision, and projection as one pipeline.

        When the initial retrieval produces no usable context, bounded rounds
        of broader retrieval are attempted. This keeps ``RETRIEVE_MORE`` a
        bounded runtime behavior without making persistence responsible for
        active-context selection.
        """
        if max_candidates < 0:
            raise ValueError("max_candidates must be non-negative")
        if max_retrieval_rounds < 1:
            raise ValueError("max_retrieval_rounds must be positive")

        limit = max_candidates
        active: ActiveContext | None = None
        for _ in range(max_retrieval_rounds):
            candidates = self.retrieve_candidates(
                records, query=query or task, max_candidates=limit
            )
            active = self.build_active_context(
                task=task,
                candidates=candidates,
                budget=budget,
            )
            if not self.decision_engine.needs_additional_retrieval(active.decisions):
                return active
            unique_record_ids = {
                str(record.get("result_id") or record.get("item_id") or f"record-{i}")
                for i, record in enumerate(records)
            }
            if len(candidates) >= len(unique_record_ids):
                return active
            limit = max(1, limit * 2)

        assert active is not None
        return active

    def decide_context(
        self, candidates: Sequence[ContextCandidate]
    ) -> list[ContextDecision]:
        """Score and budget candidates before building the active context."""
        return self.decision_engine.decide(candidates, budget=self.budget)


__all__ = ["ContextManager"]
