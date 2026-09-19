from __future__ import annotations

from types import SimpleNamespace

from uagent import core
from uagent.runtime.legacy_round_support import consume_legacy_interrupt
from uagent.runtime.legacy_round_support import translate_and_append_legacy_assistant


def test_consume_legacy_interrupt_injects_once(monkeypatch) -> None:
    monkeypatch.setattr(core, "interrupt_requested", True)
    messages: list[dict[str, object]] = []
    injected: list[tuple[object, object]] = []
    core_obj = SimpleNamespace(name="core")

    assert (
        consume_legacy_interrupt(
            messages=messages,
            core=core_obj,
            inject_stop_prompt_fn=lambda current, current_core: injected.append(
                (current, current_core)
            ),
        )
        is True
    )
    assert core.interrupt_requested is False
    assert injected == [(messages, core_obj)]

    assert (
        consume_legacy_interrupt(
            messages=messages,
            core=SimpleNamespace(name="core"),
            inject_stop_prompt_fn=lambda *_args: injected.append((None, None)),
        )
        is False
    )
    assert len(injected) == 1


def test_consume_legacy_interrupt_does_not_inject_when_clear(monkeypatch) -> None:
    monkeypatch.setattr(core, "interrupt_requested", False)
    injected: list[bool] = []

    assert (
        consume_legacy_interrupt(
            messages=[],
            core=SimpleNamespace(),
            inject_stop_prompt_fn=lambda *_args: injected.append(True),
        )
        is False
    )
    assert injected == []


def test_translate_and_append_legacy_assistant_shares_policy() -> None:
    appended: list[dict[str, object]] = []
    translated = translate_and_append_legacy_assistant(
        assistant_text="raw",
        tr_cfg="cfg",
        use_responses_api=True,
        stream_responses=False,
        translate_assistant_fn=lambda **payload: payload["assistant_text"] + "!",
        should_keep_assistant_message_fn=lambda text, calls: bool(text and calls),
        append_assistant_message_fn=lambda **payload: appended.append(payload),
        append_kwargs={"messages": [], "tool_calls_list": [{"id": "call-1"}]},
    )

    assert translated == "raw!"
    assert appended == [
        {
            "messages": [],
            "tool_calls_list": [{"id": "call-1"}],
            "assistant_text": "raw!",
        }
    ]
