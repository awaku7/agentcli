from __future__ import annotations

import types

from uagent.providers.llm_grok import parse_xai_stream
from uagent.providers.llm_pfn import parse_pfn_stream
from uagent.runtime.stream_renderer import StreamCallbacks


def test_grok_stream_uses_host_callbacks() -> None:
    deltas: list[str] = []
    reasoning: list[str] = []
    tool_calls: list[dict] = []
    terminals: list[str] = []
    function = types.SimpleNamespace(name="read_file", arguments='{"path":"a"}')
    tool_call = types.SimpleNamespace(id="call_1", function=function)
    chunks = [
        (None, types.SimpleNamespace(reasoning_content="internal")),
        (None, types.SimpleNamespace(content="answer")),
        (None, types.SimpleNamespace(tool_calls=[tool_call])),
    ]

    result = parse_xai_stream(
        chunks,
        callbacks=StreamCallbacks(
            on_delta=deltas.append,
            on_reasoning=reasoning.append,
            on_tool_call=tool_calls.append,
            on_terminal=lambda event_type, _data: terminals.append(event_type),
        ),
    )

    assert result[0] == "answer"
    assert deltas == ["\n", "answer", "\n"]
    assert reasoning == ["internal"]
    assert tool_calls and tool_calls[0]["id"] == "call_1"
    assert terminals == ["ResponseStarted", "ResponseCompleted"]


def test_pfn_stream_uses_host_callbacks() -> None:
    deltas: list[str] = []
    terminals: list[str] = []
    stream = [
        {
            "choices": [
                {"delta": {"content": "answer"}},
            ]
        }
    ]

    result = parse_pfn_stream(
        stream,
        callbacks=StreamCallbacks(
            on_delta=deltas.append,
            on_terminal=lambda event_type, _data: terminals.append(event_type),
        ),
    )

    assert result == "answer"
    assert deltas == ["answer", "\n"]
    assert terminals == ["ResponseStarted", "ResponseCompleted"]
