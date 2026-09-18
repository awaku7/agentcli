from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.responses_common import (
    parse_responses_response,
    parse_responses_stream,
)
from uagent.runtime.stream_renderer import StreamCallbacks


def test_parse_responses_response_emits_compaction_notice() -> None:
    notices: list[str] = []
    core = SimpleNamespace(print_stream_delta=notices.append)
    response = SimpleNamespace(
        id="resp_compact_1",
        output=[SimpleNamespace(type="compaction", id="cmp_1")],
        usage=None,
    )

    text, reasoning, tools, response_id, items = parse_responses_response(
        response, core=core
    )

    assert (text, reasoning, tools, response_id) == ("", "", [], "resp_compact_1")
    assert items and items[0]["type"] == "compaction"
    assert len(notices) == 1
    assert "compressed" in notices[0] or "圧縮" in notices[0]


def test_parse_responses_stream_emits_compaction_done_notice() -> None:
    notices: list[str] = []
    core = SimpleNamespace(_is_web=False, print_stream_delta=notices.append)
    stream = [
        SimpleNamespace(
            type="response.compaction.done",
            response=SimpleNamespace(id="resp_compact_2"),
        )
    ]

    text, reasoning, tools, response_id, items = parse_responses_stream(
        stream, print_delta_fn=lambda _text: None, core=core
    )

    assert (text, reasoning, tools, response_id, items) == ("", "", [], None, [])
    assert len(notices) == 1
    assert "compressed" in notices[0] or "圧縮" in notices[0]


def test_parse_responses_stream_emits_compaction_output_item_notice() -> None:
    notices: list[str] = []
    core = SimpleNamespace(_is_web=False, print_stream_delta=notices.append)
    stream = [
        SimpleNamespace(
            type="response.output_item.done",
            item=SimpleNamespace(type="compaction", id="cmp_2"),
        )
    ]

    parse_responses_stream(stream, print_delta_fn=lambda _text: None, core=core)

    assert len(notices) == 1
    assert "compressed" in notices[0] or "圧縮" in notices[0]


def test_parse_responses_stream_uses_stream_callbacks() -> None:
    deltas: list[str] = []
    reasoning: list[str] = []
    tool_calls: list[dict] = []
    terminals: list[str] = []
    stream = [
        SimpleNamespace(type="response.output_text.delta", delta="hello"),
        SimpleNamespace(type="response.reasoning_summary_text.delta", delta="internal"),
        SimpleNamespace(
            type="response.output_item.done",
            item=SimpleNamespace(
                type="function_call",
                call_id="call_1",
                id="item_1",
                name="read_file",
                arguments='{"path":"a"}',
            ),
        ),
    ]

    result = parse_responses_stream(
        stream,
        print_delta_fn=lambda text: (_ for _ in ()).throw(
            AssertionError(f"legacy callback used: {text}")
        ),
        callbacks=StreamCallbacks(
            on_delta=deltas.append,
            on_reasoning=reasoning.append,
            on_tool_call=tool_calls.append,
            on_terminal=lambda event_type, _data: terminals.append(event_type),
        ),
    )

    assert result[0] == "hello"
    assert deltas == ["hello"]
    assert reasoning == ["internal"]
    assert tool_calls and tool_calls[0]["id"] == "call_1"
    assert terminals == ["ResponseStarted", "ResponseCompleted"]


__all__ = []
