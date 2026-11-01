from __future__ import annotations

import threading
from types import SimpleNamespace

from uagent.web_impl import agent_worker
from uagent.web_impl.rooms import WebRoom


def test_assistant_reasoning_and_tool_messages_keep_history_order(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UAGENT_PROVIDER", "offline-test")
    monkeypatch.setattr(agent_worker, "resolve_identity_mode", lambda: "local")
    monkeypatch.setattr(
        agent_worker.web_manager, "execution_profile", "local_trusted", raising=False
    )
    monkeypatch.setattr(
        agent_worker.web_manager, "sandbox_enabled", False, raising=False
    )

    logged = []
    core = SimpleNamespace(
        log_message=lambda message: logged.append(dict(message)),
        auto_pilot_active=False,
        interrupt_lock=threading.Lock(),
        interrupt_requested=False,
        status_busy=False,
        status_label="IDLE",
        _last_round_outcome={},
    )
    monkeypatch.setattr(agent_worker, "core", core)
    monkeypatch.setattr(
        agent_worker.providers,
        "make_client",
        lambda _core: ("offline-test", object(), "test-model"),
    )

    def fake_run_llm_rounds(_provider, _client, _model, history, *, core, **_kwargs):
        assistant_before_tool = {
            "role": "assistant",
            "content": "Checking the result.",
            "reasoning_content": "I should inspect the data first.",
            "tool_calls": [{"id": "call-1"}],
        }
        history.append(assistant_before_tool)
        core.log_message(assistant_before_tool)

        tool_result = {"role": "tool", "name": "lookup", "content": "Found it."}
        history.append(tool_result)
        core.log_message(tool_result)

        final_answer = {"role": "assistant", "content": "Here is the answer."}
        history.append(final_answer)
        core.log_message(final_answer)

    monkeypatch.setattr(agent_worker.llm_util, "run_llm_rounds", fake_run_llm_rounds)

    room = WebRoom("reasoning-order")
    room.base_dir = str(tmp_path)
    room.history_initialized = True

    agent_worker.run_agent_worker(room, "Please look this up")

    visible = [(message["role"], message["content"]) for message in room.messages]
    assert [role for role, _ in visible] == ["user", "assistant", "tool", "assistant"]
    assert [content for _, content in visible[1:]] == [
        "Checking the result.",
        "Found it.",
        "Here is the answer.",
    ]
    assert visible[1][0] == "assistant"
    assert room.messages[1]["reasoning_content"] == "I should inspect the data first."
    assert (
        len([message for message in room.messages if message["role"] == "assistant"])
        == 2
    )
