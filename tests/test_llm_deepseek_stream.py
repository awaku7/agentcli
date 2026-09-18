from __future__ import annotations

import types

from uagent.providers.llm_deepseek import parse_deepseek_stream
from uagent.runtime.stream_renderer import StreamCallbacks


def _chunk(*, content=None, reasoning=None, tool_calls=None):
    delta = types.SimpleNamespace(
        content=content,
        reasoning_content=reasoning,
        tool_calls=tool_calls or [],
    )
    return types.SimpleNamespace(choices=[types.SimpleNamespace(delta=delta)])


def test_deepseek_stream_uses_host_callbacks() -> None:
    deltas: list[str] = []
    reasoning: list[str] = []
    tool_calls: list[dict] = []
    terminals: list[str] = []
    function = types.SimpleNamespace(name="read_file", arguments='{"path":"a"}')
    tool_call = types.SimpleNamespace(id="call_1", index=0, function=function)

    result = parse_deepseek_stream(
        [
            _chunk(reasoning="internal"),
            _chunk(content="answer"),
            _chunk(tool_calls=[tool_call]),
        ],
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

    assert result[0] == "answer"
    assert result[1] == "internal"
    assert deltas == ["\nanswer", "\n"]
    assert reasoning == ["internal"]
    assert tool_calls and tool_calls[0]["id"] == "call_1"
    assert terminals == ["ResponseStarted", "ResponseCompleted"]
