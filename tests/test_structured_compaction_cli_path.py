"""Regression coverage for CLI structured-compaction source projection."""

from __future__ import annotations

import json
from types import SimpleNamespace

from uagent import llm_message_helpers as lmh
from uagent.core_impl import history
from uagent.runtime.session_store import SessionStore
from uagent.runtime.structured_compaction import attempt_structured_compaction


def _delta(ref, *, title="Task A"):
    return json.dumps(
        {
            "goal_deltas": [
                {
                    "goal_delta_id": "new-goal",
                    "association": "new",
                    "title_hint": title,
                    "facts": [
                        {
                            "fact_id": "language",
                            "fact": "Python 3.14",
                            "source_refs": [ref],
                        }
                    ],
                    "source_refs": [ref],
                }
            ],
            "shared_constraints": [],
            "shared_facts": [],
            "critical_context": [],
            "narrative_continuation": [],
        }
    )


def _options(store, session_id, messages, client, *, previous=False):
    return lmh.build_structured_auto_shrink_projection(
        provider="openai",
        client=client,
        depname="gpt-test",
        messages=messages,
        core=SimpleNamespace(
            session_store=store,
            session_id=session_id,
            compress_history_with_llm=history.compress_history_with_llm,
            rewrite_current_log_from_messages=lambda _: (_ for _ in ()).throw(
                AssertionError("must preserve raw log")
            ),
        ),
        cache_mgr=SimpleNamespace(clear_cache=lambda _: None),
        gemini_cache_name=None,
        call_maybe_thread_fn=lambda fn: fn(),
        use_responses_api=False,
        previous_response_id=previous,
    )


def _seed_one_checkpoint(store, session_id):
    first = {"role": "user", "content": "Task A uses Python 3.14"}
    store.append_message(session_id, "user", first["content"], payload=first)
    row = store.list_indexed_messages(session_id)[0]
    ref = {
        "kind": "message",
        "ref_id": row["ref_id"],
        "scope_id": session_id,
        "session_seq": row["session_seq"],
    }
    outcome = attempt_structured_compaction(
        store=store,
        session_id=session_id,
        source_messages=[first],
        provider="openai",
        model="gpt-test",
        locale="en",
        generate_text=lambda _: _delta(ref),
    )
    assert outcome.status == "applied"


def test_initial_cli_projection_commits_checkpoint_without_rewriting_raw(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("UAGENT_STRUCTURED_COMPACTION", "1")
    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "4")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "4")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")
    monkeypatch.setattr(
        "uagent.providers.util_providers.detect_provider", lambda: "openai"
    )
    monkeypatch.setattr(
        history, "_history_summary_chunk_token_budget", lambda *_: 10000
    )
    monkeypatch.setattr(history, "_estimate_history_summary_tokens", lambda *_, **__: 1)

    class Responses:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            request = json.loads(kwargs["messages"][-1]["content"])
            ref = request["sources"][0]["source_ref"]
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=_delta(ref)))]
            )

    with SessionStore(tmp_path / "session.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="cli")
        messages = [{"role": "system", "content": "instructions"}]
        for index in range(7):
            messages.extend(
                [
                    {"role": "user", "content": f"question-{index}"},
                    {"role": "assistant", "content": f"answer-{index}"},
                ]
            )
        messages.append({"role": "user", "content": "latest"})
        for message in messages[1:]:
            store.append_message(
                session.session_id,
                message["role"],
                message["content"],
                payload=message,
            )
        before = store.list_messages(session.session_id)
        responses = Responses()
        client = SimpleNamespace(chat=SimpleNamespace(completions=responses))
        projected = _options(store, session.session_id, messages, client, previous=True)
        assert projected is not None and projected.changed
        assert responses.calls
        assert any(
            "Task A" in str(message["content"])
            for message in projected.messages
            if message["role"] == "system"
        )
        assert store.get_agent_state_revision(session.session_id) == 1
        assert store.list_messages(session.session_id) == before
        assert len(store.list_compaction_records(session.session_id)) == 1


def test_existing_checkpoint_projection_and_hysteresis(tmp_path, monkeypatch):
    monkeypatch.setenv("UAGENT_STRUCTURED_COMPACTION", "1")
    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "4")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "4")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")
    with SessionStore(tmp_path / "session.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="cli")
        _seed_one_checkpoint(store, session.session_id)
        second = {"role": "user", "content": "Task B uses C# 7.3"}
        store.append_message(
            session.session_id, "user", second["content"], payload=second
        )
        messages = [
            {"role": "system", "content": "instructions"},
            {"role": "user", "content": "Task A uses Python 3.14"},
            second,
        ]
        before = store.list_messages(session.session_id)
        invalid_client = SimpleNamespace()
        # Pending Responses continuation already holds the committed summary.
        assert (
            _options(
                store,
                session.session_id,
                messages,
                invalid_client,
                previous=True,
            )
            is None
        )
        # Restoring a session requires projection, but not another checkpoint.
        projected = _options(store, session.session_id, messages, invalid_client)
        assert projected is not None
        texts = [str(item.get("content") or "") for item in projected.messages]
        assert any("Task A" in item for item in texts)
        assert texts[-1] == "Task B uses C# 7.3"
        assert not any(item == "Task A uses Python 3.14" for item in texts)
        assert store.list_messages(session.session_id) == before
        assert len(store.list_compaction_records(session.session_id)) == 1


def test_compaction_does_not_reuse_already_checkpointed_source(tmp_path, monkeypatch):
    monkeypatch.setenv("UAGENT_STRUCTURED_COMPACTION", "1")
    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "4")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "4")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")
    monkeypatch.setattr(
        "uagent.providers.util_providers.detect_provider", lambda: "openai"
    )
    monkeypatch.setattr(
        history, "_history_summary_chunk_token_budget", lambda *_: 10000
    )
    monkeypatch.setattr(history, "_estimate_history_summary_tokens", lambda *_, **__: 1)

    class Responses:
        def create(self, **kwargs):
            request = json.loads(kwargs["messages"][-1]["content"])
            ref = request["sources"][0]["source_ref"]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=_delta(ref, title="Task B"))
                    )
                ]
            )

    with SessionStore(tmp_path / "session.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="cli")
        _seed_one_checkpoint(store, session.session_id)
        messages = [
            {"role": "system", "content": "instructions"},
            {"role": "user", "content": "Task A uses Python 3.14"},
        ]
        for index in range(8):
            messages.extend(
                [
                    {"role": "assistant", "content": f"answer-{index}"},
                    {"role": "user", "content": f"question-{index}"},
                ]
            )
        for message in messages[2:]:
            store.append_message(
                session.session_id,
                message["role"],
                message["content"],
                payload=message,
            )
        before = store.list_messages(session.session_id)
        client = SimpleNamespace(chat=SimpleNamespace(completions=Responses()))
        projected = _options(store, session.session_id, messages, client, previous=True)
        assert projected is not None and projected.changed
        checkpoints = store.list_compaction_records(session.session_id)
        assert len(checkpoints) == 2
        assert checkpoints[0]["source_start_seq"] > checkpoints[1]["source_end_seq"]
        assert store.list_messages(session.session_id) == before
