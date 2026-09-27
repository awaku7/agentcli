from __future__ import annotations

from types import SimpleNamespace

from uagent import core
from uagent.runtime.legacy_round_support import (
    append_legacy_reasoning_assistant,
    consume_legacy_interrupt,
    translate_and_append_legacy_assistant,
)


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


def test_translate_and_append_legacy_assistant_captures_web_append(monkeypatch) -> None:
    messages: list[dict[str, object]] = []
    captured: list[dict[str, object]] = []
    core_obj = SimpleNamespace(_is_web=True)
    monkeypatch.setattr(
        "uagent.runtime.observability.content_runtime.capture_logged_message",
        lambda message: captured.append(message) or True,
    )

    def append_assistant_message(**payload) -> None:
        payload["messages"].append(
            {"role": "assistant", "content": payload["assistant_text"]}
        )

    translated = translate_and_append_legacy_assistant(
        assistant_text="raw",
        tr_cfg="cfg",
        use_responses_api=False,
        stream_responses=False,
        translate_assistant_fn=lambda **payload: payload["assistant_text"] + "!",
        should_keep_assistant_message_fn=lambda *_args: True,
        append_assistant_message_fn=append_assistant_message,
        append_kwargs={
            "messages": messages,
            "core": core_obj,
            "tool_calls_list": [],
        },
    )

    assert translated == "raw!"
    assert captured == [messages[-1]]


def test_append_legacy_reasoning_assistant_captures_web_when_logging_skipped(
    monkeypatch,
) -> None:
    messages: list[dict[str, object]] = []
    captured: list[dict[str, object]] = []
    logged: list[dict[str, object]] = []
    core_obj = SimpleNamespace(_is_web=True, log_message=logged.append)
    monkeypatch.setattr(
        "uagent.runtime.observability.content_runtime.capture_logged_message",
        lambda message: captured.append(message) or True,
    )

    message = append_legacy_reasoning_assistant(
        messages=messages,
        core=core_obj,
        assistant_text="answer",
        tool_calls_list=[],
        reasoning_content="thought",
        build_assistant_message_fn=lambda **payload: {
            "role": "assistant",
            "content": payload["assistant_text"],
            "reasoning_content": payload["reasoning_content"],
        },
        streaming_enabled=True,
        judgment_mode=False,
        log_message=False,
    )

    assert captured == [message]
    assert logged == []
