from __future__ import annotations

import types

import pytest

from uagent.runtime.stream_renderer import StreamCallbacks


@pytest.mark.parametrize(
    ("parser_name", "provider"),
    [
        ("_parse_vercel_stream", "Vercel"),
        ("_parse_together_stream", "Together"),
        ("_parse_novita_stream", "Novita"),
    ],
)
def test_chat_reasoning_stream_parsers_use_host_callbacks(
    parser_name, provider
) -> None:
    if provider == "Vercel":
        from uagent.providers.llm_vercel import _parse_vercel_stream as parser
    elif provider == "Together":
        from uagent.providers.llm_together import _parse_together_stream as parser
    else:
        from uagent.providers.llm_novita import _parse_novita_stream as parser

    deltas: list[str] = []
    reasoning: list[str] = []
    tool_calls: list[dict] = []
    terminals: list[str] = []
    function = types.SimpleNamespace(name="read_file", arguments='{"path":"a"}')
    tool_call = types.SimpleNamespace(id="call_1", index=0, function=function)

    def chunk(*, content=None, reasoning_content=None, tool_calls=None):
        delta = types.SimpleNamespace(
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=tool_calls or [],
        )
        return types.SimpleNamespace(choices=[types.SimpleNamespace(delta=delta)])

    result = parser(
        [
            chunk(reasoning_content="internal"),
            chunk(content="answer"),
            chunk(tool_calls=[tool_call]),
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
