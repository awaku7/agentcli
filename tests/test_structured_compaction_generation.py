from __future__ import annotations

from contextlib import nullcontext
import json
from types import SimpleNamespace

import pytest

from uagent import core
from uagent import llm_message_helpers as lmh
from uagent.core_impl import history
from uagent.runtime.compaction_record import (
    CompactionRecord,
    DecisionRecord,
    GoalDelta,
    SourceRef,
)
from uagent.runtime.session_store import SessionStore
from uagent.runtime.structured_compaction import (
    attempt_structured_compaction,
    project_agent_state,
)


def _seed(store: SessionStore) -> tuple[str, dict[str, object]]:
    session = store.create_session(project="structured", entry_point="test")
    store.append_message(
        session.session_id,
        "user",
        "Ship the durable structured compaction path",
        payload={
            "role": "user",
            "content": "Ship the durable structured compaction path",
        },
    )
    indexed = store.list_indexed_messages(session.session_id)
    source_ref = {
        "kind": "message",
        "ref_id": indexed[0]["ref_id"],
        "scope_id": session.session_id,
        "session_seq": indexed[0]["session_seq"],
    }
    return session.session_id, source_ref


def _response(source_ref: dict[str, object]) -> str:
    return json.dumps(
        {
            "goal_deltas": [
                {
                    "goal_delta_id": "model-generated-id",
                    "association": "new",
                    "title_hint": "Ship durable structured compaction",
                    "progress_events": [
                        {
                            "text": "The user requested the durable structured compaction path.",
                            "source_refs": [source_ref],
                        }
                    ],
                    "source_refs": [source_ref],
                }
            ],
            "shared_constraints": [],
            "shared_facts": [],
            "critical_context": [],
            "narrative_continuation": [
                {
                    "text": "Continue implementing the structured compaction path.",
                    "source_refs": [source_ref],
                }
            ],
        },
        ensure_ascii=False,
    )


def _attempt(
    store,
    session_id,
    generate_text,
    *,
    source_text="Ship the durable structured compaction path",
):
    return attempt_structured_compaction(
        store=store,
        session_id=session_id,
        source_messages=[
            {
                "role": "user",
                "content": source_text,
            }
        ],
        provider="openai",
        model="test-model",
        locale="en",
        generate_text=generate_text,
    )


def test_structured_generation_commits_checkpoint_and_projects_agent_state(
    tmp_path,
):
    with SessionStore(tmp_path / "structured.sqlite3") as store:
        session_id, source_ref = _seed(store)
        calls = []

        def generate(prompt):
            calls.append(prompt)
            return _response(source_ref)

        outcome = _attempt(store, session_id, generate)

        assert outcome.status == "applied"
        assert outcome.reason == "committed"
        assert "Ship durable structured compaction" in outcome.summary
        state = store.get_agent_state(session_id)
        structured = state["structured_compaction"]
        assert len(structured["goals"]) == 1
        assert structured["applied_operations"]
        assert store.get_agent_state_revision(session_id) == 1
        assert store.list_messages(session_id) == [
            {"role": "user", "content": "Ship the durable structured compaction path"}
        ]
        assert store.list_indexed_messages(session_id)[0]["availability"] == "available"
        assert len(calls) == 1

        retry = _attempt(
            store,
            session_id,
            lambda _prompt: (_ for _ in ()).throw(
                AssertionError("must not regenerate")
            ),
        )
        assert retry.status == "applied"
        assert retry.reason == "idempotent_retry"
        assert store.get_agent_state_revision(session_id) == 1


def test_retry_after_store_reopen_does_not_regenerate_or_reapply(tmp_path):
    db_path = tmp_path / "restart.sqlite3"
    with SessionStore(db_path) as store:
        session_id, source_ref = _seed(store)
        initial = _attempt(
            store,
            session_id,
            lambda _prompt: _response(source_ref),
        )
        assert initial.status == "applied"
        committed_state = store.get_agent_state(session_id)
        operation_id = committed_state["structured_compaction"]["applied_operations"][0]

    with SessionStore(db_path) as restarted_store:
        retry = _attempt(
            restarted_store,
            session_id,
            lambda _prompt: (_ for _ in ()).throw(
                AssertionError("committed operation must be loaded, not regenerated")
            ),
        )
        assert retry.status == "applied"
        assert retry.reason == "idempotent_retry"
        assert restarted_store.get_agent_state(session_id) == committed_state
        assert restarted_store.get_agent_state_revision(session_id) == 1
        assert restarted_store.get_compaction_record(operation_id) is not None


def test_structured_generation_repairs_invalid_json_once(tmp_path):
    with SessionStore(tmp_path / "structured.sqlite3") as store:
        session_id, source_ref = _seed(store)
        invalid_ref = {**source_ref, "session_seq": int(source_ref["session_seq"]) + 1}
        responses = iter([_response(invalid_ref), _response(source_ref)])
        calls = []

        def generate(prompt):
            calls.append(prompt)
            return next(responses)

        outcome = _attempt(store, session_id, generate)

        assert outcome.status == "applied"
        assert len(calls) == 2
        assert "Validation error" in calls[1][1]["content"]
        assert store.get_agent_state_revision(session_id) == 1


def test_failed_generation_and_repair_leave_state_and_raw_sources_untouched(
    tmp_path,
):
    with SessionStore(tmp_path / "structured.sqlite3") as store:
        session_id, _source_ref = _seed(store)
        bad = json.dumps({"unexpected": "field"})
        calls = []

        def generate(prompt):
            calls.append(prompt)
            return bad

        outcome = _attempt(store, session_id, generate)

        assert outcome.status == "fallback"
        assert outcome.reason == "repair_failed"
        assert len(calls) == 2
        assert store.get_agent_state(session_id) is None
        assert store.get_agent_state_revision(session_id) == 0
        assert (
            store._execute("SELECT COUNT(*) AS n FROM checkpoints").fetchone()["n"] == 0
        )
        assert store.list_indexed_messages(session_id)[0]["availability"] == "available"


def test_source_alignment_failure_does_not_call_model(tmp_path):
    with SessionStore(tmp_path / "structured.sqlite3") as store:
        session_id, source_ref = _seed(store)

        outcome = attempt_structured_compaction(
            store=store,
            session_id=session_id,
            source_messages=[{"role": "user", "content": "not in session history"}],
            provider="openai",
            model="test-model",
            locale="en",
            generate_text=lambda _prompt: (_ for _ in ()).throw(
                AssertionError("source mismatch must fallback before generation")
            ),
        )

        assert outcome.status == "fallback"
        assert outcome.reason == "source_alignment_unavailable"
        assert store.get_agent_state(session_id) is None
        assert store.get_agent_state_revision(session_id) == 0
        assert (
            store.list_indexed_messages(session_id)[0]["ref_id"] == source_ref["ref_id"]
        )


def test_revision_conflict_does_not_commit_generated_compaction(tmp_path):
    with SessionStore(tmp_path / "structured.sqlite3") as store:
        session_id, source_ref = _seed(store)

        def concurrent_update(_prompt):
            store.save_agent_state(
                session_id,
                {"goal": "concurrent writer"},
                expected_revision=0,
            )
            return _response(source_ref)

        outcome = _attempt(store, session_id, concurrent_update)

        assert outcome.status == "commit_failed"
        assert outcome.reason == "revision_or_storage_conflict"
        assert store.get_agent_state(session_id) == {"goal": "concurrent writer"}
        assert store.get_agent_state_revision(session_id) == 1
        assert (
            store._execute("SELECT COUNT(*) AS n FROM checkpoints").fetchone()["n"] == 0
        )
        assert store.list_indexed_messages(session_id)[0]["availability"] == "available"


def test_agent_state_projection_is_bounded():
    state = {
        "structured_compaction": {
            "goals": {
                "g": {
                    "title": "Large goal",
                    "progress_events": [
                        {"text": "important " * 500, "source_refs": []}
                    ],
                }
            }
        }
    }

    projected = project_agent_state(state, max_chars=500)

    assert len(projected) <= 500
    assert projected.endswith("[context truncated]")


@pytest.mark.parametrize("status", ["applied", "fallback"])
def test_structured_auto_shrink_keeps_persistent_raw_history(monkeypatch, status):
    monkeypatch.setenv("UAGENT_STRUCTURED_COMPACTION", "1")
    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "4")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "4")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")

    class FakeStore:
        def __init__(self):
            self.saved_summary = ""
            self.replace_count = 0

        def save_session_summary(self, session_id, summary):
            self.saved_summary = summary

        def replace_messages(self, session_id, messages):
            self.replace_count += 1

    store = FakeStore()
    received = {}

    def compress(**kwargs):
        received.update(kwargs)
        return SimpleNamespace(
            messages=[
                {"role": "system", "content": "SYSTEM_PROMPT"},
                {
                    "role": "system",
                    "content": "Summary of the conversation so far:\ncompacted",
                },
                {"role": "user", "content": "latest"},
            ],
            preserve_raw_history=True,
            structured_status=status,
        )

    messages = [{"role": "system", "content": "SYSTEM_PROMPT"}]
    for index in range(5):
        messages.append({"role": "user", "content": f"user-{index}"})
        messages.append({"role": "assistant", "content": f"assistant-{index}"})

    core = SimpleNamespace(
        compress_history_with_llm=compress,
        session_store=store,
        session_id="session-id",
        rewrite_current_log_from_messages=lambda _messages: pytest.fail(
            "structured mode must not rewrite the raw session log"
        ),
    )
    lmh._maybe_auto_shrink_messages(
        provider="openai",
        client=object(),
        depname="gpt-test",
        messages=messages,
        core=core,
        cache_mgr=SimpleNamespace(clear_cache=lambda _client: None),
        gemini_cache_name=None,
        call_maybe_thread_fn=lambda fn: fn(),
        use_responses_api=False,
    )

    assert received["structured_compaction"] is True
    assert received["return_outcome"] is True
    assert store.replace_count == 0
    assert store.saved_summary == "compacted"
    assert messages[1]["content"].endswith("compacted")


def test_legacy_fallback_in_structured_mode_does_not_rewrite_raw_messages(
    monkeypatch, tmp_path
):
    class FakeCompletions:
        def __init__(self):
            self.responses = iter(["not-json", "still-not-json", "LEGACY_SUMMARY"])

        def create(self, **_kwargs):
            message = SimpleNamespace(content=next(self.responses))
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    messages = [{"role": "system", "content": "SYSTEM_PROMPT"}]
    messages.extend(
        [
            (
                {"role": "user", "content": f"user-{index}"}
                if index % 2 == 0
                else {"role": "assistant", "content": f"assistant-{index}"}
            )
            for index in range(12)
        ]
    )

    with SessionStore(tmp_path / "structured-fallback.sqlite3") as store:
        session = store.create_session(project="structured", entry_point="test")
        for message in messages[1:]:
            store.append_message(
                session.session_id,
                message["role"],
                message["content"],
                payload=message,
            )
        monkeypatch.setattr(core, "session_store", store, raising=False)
        monkeypatch.setattr(
            core, "_session_store_active_id", session.session_id, raising=False
        )
        monkeypatch.setattr(core, "session_id", session.session_id, raising=False)

        outcome = history.compress_history_with_llm(
            client=client,
            depname="gpt-test",
            messages=messages,
            keep_last=4,
            emit_log=False,
            structured_compaction=True,
            return_outcome=True,
        )

        assert outcome.preserve_raw_history is True
        assert outcome.structured_status == "fallback"
        assert any(
            "LEGACY_SUMMARY" in item.get("content", "") for item in outcome.messages
        )
        assert store.list_messages(session.session_id) == messages[1:]
        assert all(
            item["availability"] == "available"
            for item in store.list_indexed_messages(session.session_id)
        )
        assert store.get_agent_state(session.session_id) is None


def test_opt_in_auto_shrink_commits_record_and_keeps_raw_history(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_STRUCTURED_COMPACTION", "1")
    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "4")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "4")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")
    monkeypatch.setattr(
        "uagent.providers.util_providers.detect_provider", lambda: "openai"
    )
    monkeypatch.setattr(
        history, "_history_summary_chunk_token_budget", lambda *_args: 10_000
    )
    monkeypatch.setattr(
        history, "_estimate_history_summary_tokens", lambda *_args, **_kwargs: 1
    )

    messages = [{"role": "system", "content": "SYSTEM_PROMPT"}]
    for index in range(6):
        messages.extend(
            [
                {"role": "user", "content": f"user-{index}"},
                {"role": "assistant", "content": f"assistant-{index}"},
            ]
        )

    class FakeCompletions:
        def __init__(self, response):
            self.response = response
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content=self.response))
                ]
            )

    with SessionStore(tmp_path / "auto-shrink.sqlite3") as store:
        session = store.create_session(project="structured", entry_point="test")
        for message in messages[1:]:
            store.append_message(
                session.session_id,
                message["role"],
                message["content"],
                payload=message,
            )
        first_source = store.list_indexed_messages(session.session_id)[0]
        source_ref = {
            "kind": "message",
            "ref_id": first_source["ref_id"],
            "scope_id": session.session_id,
            "session_seq": first_source["session_seq"],
        }
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=FakeCompletions(_response(source_ref)))
        )
        core_obj = SimpleNamespace(
            compress_history_with_llm=history.compress_history_with_llm,
            session_store=store,
            session_id=session.session_id,
            rewrite_current_log_from_messages=lambda _messages: pytest.fail(
                "structured auto-shrink must preserve the raw JSONL log"
            ),
        )

        lmh._maybe_auto_shrink_messages(
            provider="openai",
            client=client,
            depname="gpt-test",
            messages=messages,
            core=core_obj,
            cache_mgr=SimpleNamespace(clear_cache=lambda _client: None),
            gemini_cache_name=None,
            call_maybe_thread_fn=lambda fn: fn(),
            use_responses_api=False,
        )

        assert client.chat.completions.calls
        assert any(
            "Ship durable structured compaction" in item["content"]
            for item in messages
            if item["role"] == "system"
        )
        assert store.get_agent_state_revision(session.session_id) == 1
        assert len(store.list_messages(session.session_id)) == 12
        assert all(
            item["availability"] == "available"
            for item in store.list_indexed_messages(session.session_id)
        )
        assert store.get_session_summary(session.session_id)


def test_structured_auto_shrink_flag_off_keeps_legacy_path(monkeypatch):
    monkeypatch.setenv("UAGENT_STRUCTURED_COMPACTION", "0")
    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "4")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "4")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")

    class FakeStore:
        def __init__(self):
            self.replace_count = 0

        def replace_messages(self, _session_id, _messages):
            self.replace_count += 1

        def save_session_summary(self, _session_id, _summary):
            pass

    store = FakeStore()
    calls = []

    def compress(**kwargs):
        calls.append(kwargs)
        return [
            {"role": "system", "content": "SYSTEM_PROMPT"},
            {"role": "system", "content": "Summary of the conversation so far: legacy"},
            {"role": "user", "content": "latest"},
        ]

    messages = [{"role": "system", "content": "SYSTEM_PROMPT"}]
    for index in range(5):
        messages.extend(
            [
                {"role": "user", "content": f"user-{index}"},
                {"role": "assistant", "content": f"assistant-{index}"},
            ]
        )
    core_obj = SimpleNamespace(
        compress_history_with_llm=compress,
        session_store=store,
        session_id="session-id",
        rewrite_current_log_from_messages=lambda _messages: None,
    )

    lmh._maybe_auto_shrink_messages(
        provider="openai",
        client=object(),
        depname="gpt-test",
        messages=messages,
        core=core_obj,
        cache_mgr=SimpleNamespace(clear_cache=lambda _client: None),
        gemini_cache_name=None,
        call_maybe_thread_fn=lambda fn: fn(),
        use_responses_api=False,
    )

    assert len(calls) == 1
    assert "structured_compaction" not in calls[0]
    assert store.replace_count == 1


def test_existing_goal_decision_supersession_uses_only_known_ids(tmp_path):
    first_text = "Track a durable workstream"
    next_text = "Revise the prior implementation decision"
    with SessionStore(tmp_path / "lifecycle.sqlite3") as store:
        session = store.create_session(project="structured", entry_point="test")
        store.append_message(
            session.session_id,
            "user",
            first_text,
            payload={"role": "user", "content": first_text},
        )
        first_item = store.list_indexed_messages(session.session_id)[0]
        first_ref = SourceRef(
            kind="message",
            ref_id=first_item["ref_id"],
            scope_id=session.session_id,
            session_seq=first_item["session_seq"],
        )
        first_delta = GoalDelta(
            goal_delta_id="first-delta",
            association="new",
            title_hint="Existing workstream",
            decisions=(
                DecisionRecord(
                    decision_id="decision-old",
                    decision="Use the first implementation",
                    source_refs=(first_ref,),
                ),
            ),
            source_refs=(first_ref,),
        )
        store.commit_compaction_record(
            CompactionRecord(
                record_id="seed-checkpoint",
                operation_id="seed-operation",
                application_status="applied",
                session_id=session.session_id,
                actor_kind="runtime",
                actor_id="test",
                source_start_id=first_ref.ref_id,
                source_end_id=first_ref.ref_id,
                source_start_seq=first_ref.session_seq,
                source_end_seq=first_ref.session_seq,
                source_message_count=1,
                source_chars=len(first_text),
                base_revision=0,
                goal_deltas=(first_delta,),
            )
        )
        goal_id = next(
            iter(
                store.get_agent_state(session.session_id)["structured_compaction"][
                    "goals"
                ]
            )
        )
        store.append_message(
            session.session_id,
            "user",
            next_text,
            payload={"role": "user", "content": next_text},
        )
        current_item = store.list_indexed_messages(session.session_id)[-1]
        current_ref = {
            "kind": "message",
            "ref_id": current_item["ref_id"],
            "scope_id": session.session_id,
            "session_seq": current_item["session_seq"],
        }

        response = json.dumps(
            {
                "goal_deltas": [
                    {
                        "goal_delta_id": "new-delta",
                        "association": "existing",
                        "goal_id": goal_id,
                        "decisions": [
                            {
                                "decision_id": "replacement-decision",
                                "decision": "Use the revised implementation",
                                "supersedes": ["decision-old"],
                                "source_refs": [current_ref],
                            }
                        ],
                        "source_refs": [current_ref],
                    }
                ],
                "shared_constraints": [],
                "shared_facts": [],
                "critical_context": [],
                "narrative_continuation": [],
            }
        )
        prompts = []

        outcome = _attempt(
            store,
            session.session_id,
            lambda prompt: (prompts.append(prompt), response)[1],
            source_text=next_text,
        )

        assert outcome.status == "applied"
        known = json.loads(prompts[0][1]["content"])["known_goals"][0]
        assert "decision-old" in known["active_decision_ids"]
        goals = store.get_agent_state(session.session_id)["structured_compaction"][
            "goals"
        ]
        decisions = next(iter(goals.values()))["decisions"]
        assert decisions["decision-old"]["status"] == "superseded"
        assert any(
            item["decision"] == "Use the revised implementation"
            for key, item in decisions.items()
            if key != "decision-old"
        )


def test_compaction_telemetry_records_outcome_without_source_content(
    monkeypatch, tmp_path
):
    class FakeSpan:
        def __init__(self):
            self.attributes = {}
            self.events = []
            self.status = None

        def set_attribute(self, key, value):
            self.attributes[key] = value

        def add_event(self, name, attributes=None):
            self.events.append((name, attributes or {}))

        def set_status(self, status, description=None):
            self.status = status

    span = FakeSpan()
    telemetry = {"events": [], "counters": [], "histograms": []}
    backend = SimpleNamespace(
        start_span=lambda *_args, **_kwargs: nullcontext(span),
        record_event=lambda name, attrs=None: telemetry["events"].append(
            (name, attrs or {})
        ),
        record_counter=lambda *args: telemetry["counters"].append(args),
        record_histogram=lambda *args: telemetry["histograms"].append(args),
    )
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )

    with SessionStore(tmp_path / "telemetry.sqlite3") as store:
        session_id, _source_ref = _seed(store)
        outcome = attempt_structured_compaction(
            store=store,
            session_id=session_id,
            source_messages=[{"role": "user", "content": "private source text"}],
            provider="openai",
            model="test-model",
            locale="en",
            generate_text=lambda _prompt: pytest.fail("alignment should fail first"),
        )

    assert outcome.status == "fallback"
    assert span.attributes["uag.compaction.outcome"] == "fallback"
    serialized = repr((span.attributes, span.events, telemetry))
    assert "private source text" not in serialized
    assert "source_content" not in serialized


def test_deterministic_fallback_is_used_when_both_llm_paths_fail(monkeypatch, tmp_path):
    class FailingCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **_kwargs):
            self.calls += 1
            if self.calls <= 2:
                content = "not-json"
            else:
                raise RuntimeError("legacy summary provider unavailable")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=FailingCompletions()))
    messages = [{"role": "system", "content": "SYSTEM_PROMPT"}]
    messages.extend(
        [
            (
                {"role": "user", "content": f"user-{index}"}
                if index % 2 == 0
                else {"role": "assistant", "content": f"assistant-{index}"}
            )
            for index in range(12)
        ]
    )
    with SessionStore(tmp_path / "deterministic-fallback.sqlite3") as store:
        session = store.create_session(project="structured", entry_point="test")
        for message in messages[1:]:
            store.append_message(
                session.session_id,
                message["role"],
                message["content"],
                payload=message,
            )
        monkeypatch.setattr(core, "session_store", store, raising=False)
        monkeypatch.setattr(
            core, "_session_store_active_id", session.session_id, raising=False
        )
        monkeypatch.setattr(core, "session_id", session.session_id, raising=False)

        outcome = history.compress_history_with_llm(
            client=client,
            depname="gpt-test",
            messages=messages,
            keep_last=4,
            emit_log=False,
            structured_compaction=True,
            return_outcome=True,
        )

        assert outcome.preserve_raw_history is True
        assert any(
            "Deterministic excerpts" in item.get("content", "")
            for item in outcome.messages
        )
        assert store.list_messages(session.session_id) == messages[1:]
        assert store.get_agent_state(session.session_id) is None
