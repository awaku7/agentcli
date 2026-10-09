from __future__ import annotations

from uagent.runtime.active_context import ActiveContext
from uagent.runtime.context_budget import ContextBudget
from uagent.runtime.compaction_record import (
    CompactionRecord,
    GoalDelta,
    ProvenancedObservation,
    SourceRef,
)
from uagent.runtime.context_manager import ContextManager
from uagent.runtime.context_policy import ContextPolicy
from uagent.runtime.session_store import SessionStore


def _commit_checkpoint(
    store: SessionStore,
    session_id: str,
    *,
    message_id: int,
    title: str,
    operation_id: str,
    base_revision: int,
    application_status: str = "applied",
) -> str:
    indexed = next(
        item
        for item in store.list_indexed_messages(session_id)
        if int(item["message_id"]) == message_id
    )
    source = SourceRef(
        kind="message",
        ref_id=str(indexed["ref_id"]),
        scope_id=session_id,
        session_seq=int(indexed["session_seq"]),
    )
    delta = GoalDelta(
        goal_delta_id=f"delta-{operation_id}",
        association="new",
        title_hint=title,
        progress_events=(
            ProvenancedObservation(text=f"Completed {title}.", source_refs=(source,)),
        ),
        source_refs=(source,),
    )
    record = CompactionRecord(
        record_id=f"checkpoint-{operation_id}",
        operation_id=operation_id,
        application_status=application_status,
        session_id=session_id,
        actor_kind="runtime",
        actor_id="test-context",
        source_start_id=source.ref_id,
        source_end_id=source.ref_id,
        source_start_seq=source.session_seq,
        source_end_seq=source.session_seq,
        source_message_count=1,
        source_chars=len(title),
        base_revision=base_revision,
        goal_deltas=(delta,),
    )
    saved = store.commit_compaction_record(record)
    return str(saved["checkpoint_id"])


def _seed_checkpoints(store: SessionStore) -> tuple[str, str, str]:
    session = store.create_session(project="context", entry_point="test")
    first_message_id = store.append_message(
        session.session_id,
        "user",
        "database migration",
        payload={"role": "user", "content": "database migration"},
    )
    first_id = _commit_checkpoint(
        store,
        session.session_id,
        message_id=first_message_id,
        title="Database migration completed",
        operation_id="cp-first",
        base_revision=0,
    )
    second_message_id = store.append_message(
        session.session_id,
        "user",
        "weather report",
        payload={"role": "user", "content": "weather report"},
    )
    second_id = _commit_checkpoint(
        store,
        session.session_id,
        message_id=second_message_id,
        title="Weather report completed",
        operation_id="cp-second",
        base_revision=1,
    )
    _commit_checkpoint(
        store,
        session.session_id,
        message_id=second_message_id,
        title="Comparison-only weather branch",
        operation_id="cp-comparison",
        base_revision=2,
        application_status="comparison_only",
    )
    return session.session_id, first_id, second_id


def test_checkpoint_candidates_are_scored_injected_and_deduplicated(tmp_path):
    with SessionStore(tmp_path / "context-checkpoints.sqlite3") as store:
        session_id, first_id, second_id = _seed_checkpoints(store)
        manager = ContextManager(policy=ContextPolicy(budget_enabled=False))
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Please verify the database migration."},
        ]

        active = manager.build_message_context(
            messages,
            session_store=store,
            session_id=session_id,
            max_checkpoint_candidates=2,
        )

        assert isinstance(active, ActiveContext)
        assert len(messages) == 2
        checkpoint_message = next(
            message
            for message in active.messages
            if message.get("role") == "assistant"
            and "Relevant persisted checkpoint context" in str(message.get("content"))
        )
        injected = checkpoint_message["content"]
        assert f"checkpoint://{first_id}" in injected
        assert f"checkpoint://{second_id}" in injected
        assert "Database migration completed" in injected
        assert "Comparison-only weather branch" not in injected
        assert {decision.source for decision in active.decisions} == {"compaction"}
        assert active.sections["history"]

        repeated = manager.build_message_context(
            active.messages,
            session_store=store,
            session_id=session_id,
            max_checkpoint_candidates=2,
        )
        repeated_content = "\n".join(
            str(message.get("content") or "") for message in repeated.messages
        )
        assert repeated_content.count(f"checkpoint://{first_id}") == 1
        assert repeated_content.count(f"checkpoint://{second_id}") == 1


def test_relevant_older_checkpoint_can_be_retrieved_by_revision_page(tmp_path):
    with SessionStore(tmp_path / "older-checkpoint.sqlite3") as store:
        session_id, first_id, second_id = _seed_checkpoints(store)
        manager = ContextManager(policy=ContextPolicy(budget_enabled=False))

        recent_page = manager.retrieve_checkpoint_candidates(
            store,
            session_id,
            query="database migration",
            max_candidates=1,
            record_limit=10,
        )
        older_page = manager.retrieve_checkpoint_candidates(
            store,
            session_id,
            query="database migration",
            max_candidates=1,
            record_limit=10,
            before_revision=2,
        )

        assert recent_page
        assert [candidate.item_id for candidate in recent_page] == [
            f"checkpoint:{first_id}"
        ]
        assert [candidate.item_id for candidate in older_page] == [
            f"checkpoint:{first_id}"
        ]
        listed = store.list_compaction_records(session_id)
        assert [row["checkpoint_id"] for row in listed] == [second_id, first_id]


def test_checkpoint_source_rehydration_is_session_scoped_and_bounded(tmp_path):
    with SessionStore(tmp_path / "checkpoint-rehydrate.sqlite3") as store:
        session_id, first_id, _second_id = _seed_checkpoints(store)
        manager = ContextManager(policy=ContextPolicy(budget_enabled=False))

        rehydrated = manager.rehydrate_checkpoint_sources(
            store,
            session_id,
            first_id,
            query="database migration",
            max_candidates=2,
            max_chars=2_000,
        )

        assert len(rehydrated) == 1
        assert rehydrated[0].source == "compaction_source"
        assert "database migration" in str(rehydrated[0].content)
        assert rehydrated[0].reference.startswith(f"checkpoint://{first_id}/source/")
        other_session = store.create_session(
            project="other-context", entry_point="test"
        )
        assert (
            manager.rehydrate_checkpoint_sources(
                store,
                other_session.session_id,
                first_id,
                query="database migration",
            )
            == []
        )


def test_checkpoint_store_failure_leaves_message_context_usable():
    class BrokenStore:
        def list_compaction_records(self, *_args, **_kwargs):
            raise RuntimeError("database unavailable")

        def list_session_items(self, *_args, **_kwargs):
            return []

    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Continue the task."},
    ]
    manager = ContextManager(policy=ContextPolicy(budget_enabled=False))

    active = manager.build_message_context(
        messages,
        session_store=BrokenStore(),
        session_id="session-local",
    )

    assert active.messages == messages
    assert active.decisions == []


def test_checkpoint_data_is_not_promoted_to_system_role(tmp_path):
    with SessionStore(tmp_path / "checkpoint-trust.sqlite3") as store:
        session_id, _first_id, _second_id = _seed_checkpoints(store)
        manager = ContextManager(policy=ContextPolicy(budget_enabled=False))
        active = manager.build_message_context(
            [
                {"role": "system", "content": "Trusted system instruction"},
                {"role": "user", "content": "database migration"},
            ],
            session_store=store,
            session_id=session_id,
        )
        checkpoint_messages = [
            message
            for message in active.messages
            if "Relevant persisted checkpoint context"
            in str(message.get("content") or "")
        ]
        assert checkpoint_messages
        assert all(message["role"] != "system" for message in checkpoint_messages)
        assert "untrusted quoted data" in checkpoint_messages[0]["content"]


def test_checkpoint_evicted_by_message_budget_is_not_reported(tmp_path):
    with SessionStore(tmp_path / "checkpoint-budget.sqlite3") as store:
        session_id, _first_id, _second_id = _seed_checkpoints(store)
        manager = ContextManager(policy=ContextPolicy(budget_enabled=False))
        messages = [
            {"role": "system", "content": "Trusted system instruction"},
            {"role": "user", "content": "database migration"},
        ]
        active = manager.build_message_context(
            messages,
            session_store=store,
            session_id=session_id,
            budget=ContextBudget(total_chars=90),
        )
        assert not any(
            "Relevant persisted checkpoint context" in str(message.get("content") or "")
            for message in active.messages
        )
        assert active.decisions == []
