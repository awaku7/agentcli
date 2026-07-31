from __future__ import annotations

from types import SimpleNamespace

from uagent import core as core_mod
from uagent.providers.responses_common import parse_responses_stream
from uagent.uagent_llm import _inject_stop_prompt


def test_clear_responses_continuation_drops_rid_and_stale_flag(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        core_mod,
        "responses_state",
        {
            "previous_response_id": "resp_test_123",
            "provider": "openai",
            "model": "gpt-5.4-nano",
            "_stale_rid_occurred": True,
        },
    )
    monkeypatch.setenv("UAGENT_RESPONSES_STATE_DIR", str(tmp_path))

    core_mod.clear_responses_continuation()

    assert "previous_response_id" not in core_mod.responses_state
    assert "_stale_rid_occurred" not in core_mod.responses_state


def test_inject_stop_prompt_clears_responses_continuation(monkeypatch) -> None:
    state = {
        "previous_response_id": "resp_test_456",
        "provider": "openai",
        "model": "gpt-5.4-nano",
        "_stale_rid_occurred": True,
    }
    monkeypatch.setattr(core_mod, "responses_state", state)
    monkeypatch.setattr(core_mod, "_save_responses_state", lambda: None)

    messages: list[dict] = []
    dummy_core = SimpleNamespace(
        responses_state=state,
        log_message=lambda msg: None,
    )

    _inject_stop_prompt(messages, dummy_core)

    assert "previous_response_id" not in state
    assert "_stale_rid_occurred" not in state
    assert messages and messages[-1]["role"] == "user"


class _InterruptStream:
    def __init__(self) -> None:
        self._events = [
            SimpleNamespace(
                type="response.created",
                response=SimpleNamespace(id="resp_stream_1"),
            ),
            SimpleNamespace(type="response.output_text.delta", delta="hi"),
            SimpleNamespace(
                type="response.output_item.done",
                item=SimpleNamespace(
                    type="function_call",
                    call_id="call_1",
                    id="fc_1",
                    name="get_geoip",
                    arguments="{}",
                ),
            ),
        ]

    def __iter__(self):
        return iter(self._events)


def test_parse_responses_stream_interrupt_drops_rid_and_tools(monkeypatch) -> None:
    monkeypatch.setattr(core_mod, "interrupt_requested", True)
    monkeypatch.setattr(
        core_mod,
        "responses_state",
        {
            "previous_response_id": "resp_old",
            "provider": "openai",
            "model": "gpt-5.4-nano",
        },
    )
    monkeypatch.setattr(core_mod, "_save_responses_state", lambda: None)

    text, reasoning, tools, rid, items = parse_responses_stream(
        _InterruptStream(),
        print_delta_fn=lambda _s: None,
        core=SimpleNamespace(_is_web=False),
        provider="OpenAI",
    )

    assert rid is None
    assert tools == []
    assert items == []
    assert "previous_response_id" not in core_mod.responses_state
    # Outer round still needs to observe the interrupt flag.
    assert core_mod.interrupt_requested is True
