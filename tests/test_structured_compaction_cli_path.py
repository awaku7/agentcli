"""Regression coverage for CLI structured-compaction source projection."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

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


def _options(
    store,
    session_id,
    messages,
    client,
    *,
    previous=False,
    provider="openai",
    cache_name=None,
    allow_checkpoint_creation=True,
):
    return lmh.build_structured_auto_shrink_projection(
        provider=provider,
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
        gemini_cache_name=cache_name,
        call_maybe_thread_fn=lambda fn: fn(),
        use_responses_api=False,
        previous_response_id=previous,
        allow_checkpoint_creation=allow_checkpoint_creation,
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


@pytest.mark.parametrize("keep_last", [0, 4])
def test_initial_cli_projection_commits_checkpoint_without_rewriting_raw(
    tmp_path, monkeypatch, keep_last
):
    monkeypatch.setenv("UAGENT_STRUCTURED_COMPACTION", "1")
    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", str(keep_last))
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
        assert projected.messages[-1]["role"] == "user"
        assert projected.messages[-1]["content"] == "latest"
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


def test_restored_gemini_checkpoint_keeps_agent_state_system_summary(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("UAGENT_STRUCTURED_COMPACTION", "1")
    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "4")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "4")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")
    with SessionStore(tmp_path / "session.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="cli")
        _seed_one_checkpoint(store, session.session_id)
        newer = {"role": "user", "content": "Task B uses C# 7.3"}
        store.append_message(
            session.session_id, "user", newer["content"], payload=newer
        )
        messages = [
            {"role": "system", "content": "startup instructions"},
            {"role": "user", "content": "Task A uses Python 3.14"},
            newer,
        ]
        projection = _options(
            store,
            session.session_id,
            messages,
            SimpleNamespace(),
            provider="gemini",
            cache_name="cached-startup-instructions",
        )
        assert projection is not None
        assert projection.cache_name is None
        provider_messages = lmh._build_call_messages(
            provider="gemini",
            messages=list(projection.messages),
            core=SimpleNamespace(),
            depname="gemini-test",
            gemini_cache_name=projection.cache_name,
        )
        assert any(
            item.get("role") == "system" and "Task A" in str(item.get("content"))
            for item in provider_messages
        )


def test_stateless_tool_round_uses_checkpoint_without_recompressing(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("UAGENT_STRUCTURED_COMPACTION", "1")
    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "4")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "4")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")
    with SessionStore(tmp_path / "session.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="cli")
        _seed_one_checkpoint(store, session.session_id)
        user = {"role": "user", "content": "run the tool"}
        assistant = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "sample_tool", "arguments": "{}"},
                }
            ],
        }
        tool = {
            "role": "tool",
            "name": "sample_tool",
            "tool_call_id": "call-1",
            "content": "result: 42",
        }
        for item in (user, assistant, tool):
            store.append_message(
                session.session_id,
                item["role"],
                item["content"],
                payload=item,
            )
        messages = [
            {"role": "system", "content": "instructions"},
            {"role": "user", "content": "Task A uses Python 3.14"},
            {**user, "content": "turn-only context\\n" + user["content"]},
            assistant,
            tool,
        ]
        before = store.list_messages(session.session_id)
        projected = _options(
            store,
            session.session_id,
            messages,
            SimpleNamespace(),
            allow_checkpoint_creation=False,
        )
        assert projected is not None and projected.changed
        assert projected.messages[-1] == tool
        assert projected.messages[-2] == assistant
        assert projected.messages[-3] == messages[-3]
        assert any(
            item.get("role") == "system" and "Task A" in str(item.get("content"))
            for item in projected.messages
        )
        assert len(store.list_compaction_records(session.session_id)) == 1
        assert store.list_messages(session.session_id) == before
        assert (
            _options(
                store,
                session.session_id,
                messages,
                SimpleNamespace(),
                previous=True,
                allow_checkpoint_creation=False,
            )
            is None
        )

def test_long_cli_history_commits_bounded_incremental_windows(tmp_path, monkeypatch):
    """More than 80 eligible sources must progress instead of retrying fallback."""
    monkeypatch.setenv("UAGENT_STRUCTURED_COMPACTION", "1")
    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "4")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "10")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")
    monkeypatch.setattr(
        "uagent.providers.util_providers.detect_provider", lambda: "openai"
    )
    monkeypatch.setattr(
        history, "_history_summary_chunk_token_budget", lambda *_: 10000
    )
    monkeypatch.setattr(history, "_estimate_history_summary_tokens", lambda *_, **__: 1)

    class FakeCompletions:
        def __init__(self):
            self.source_lengths = []

        def create(self, **kwargs):
            payload = json.loads(kwargs["messages"][-1]["content"])
            sources = payload["sources"]
            self.source_lengths.append(len(sources))
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=_delta(
                                sources[0]["source_ref"],
                                title=f"Batch {len(self.source_lengths)}",
                            )
                        )
                    )
                ]
            )

    with SessionStore(tmp_path / "many-messages.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="cli")
        history_messages = [{"role": "system", "content": "instructions"}]
        for index in range(60):
            history_messages.extend(
                [
                    {"role": "user", "content": f"question-{index}"},
                    {"role": "assistant", "content": f"answer-{index}"},
                ]
            )
        history_messages.append({"role": "user", "content": "latest"})
        for item in history_messages[1:]:
            store.append_message(
                session.session_id,
                item["role"],
                item["content"],
                payload=item,
            )

        initial_raw = store.list_messages(session.session_id)
        client_calls = FakeCompletions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=client_calls))
        first = _options(
            store, session.session_id, history_messages, client, previous=True
        )
        assert first is not None and first.changed
        first_checkpoint = store.list_compaction_records(session.session_id)[0]
        assert first_checkpoint["source_end_seq"] <= 80
        assert first.messages[-1]["content"] == "latest"
        assert store.list_messages(session.session_id) == initial_raw

        # The next user turn continues from the first exact source window.
        next_assistant = {"role": "assistant", "content": "acknowledged"}
        next_user = {"role": "user", "content": "now review Task B"}
        for item in (next_assistant, next_user):
            history_messages.append(item)
            store.append_message(
                session.session_id,
                item["role"],
                item["content"],
                payload=item,
            )

        second_raw = store.list_messages(session.session_id)
        second = _options(
            store, session.session_id, history_messages, client, previous=True
        )
        assert second is not None and second.changed
        checkpoints = store.list_compaction_records(session.session_id)
        assert len(checkpoints) == 2
        assert checkpoints[0]["source_start_seq"] > checkpoints[1]["source_end_seq"]
        assert checkpoints[0]["source_end_seq"] <= checkpoints[0]["source_start_seq"] + 79
        assert client_calls.source_lengths == [80, checkpoints[0]["record"]["source_message_count"]]
        assert second.messages[-1]["content"] == "now review Task B"
        assert store.list_messages(session.session_id) == second_raw
