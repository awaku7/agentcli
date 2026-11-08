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


def test_vercel_stream_reports_measured_usage_from_final_chunk() -> None:
    from uagent.providers.llm_vercel import _parse_vercel_stream

    terminals: list[tuple[str, dict]] = []
    data_chunk = types.SimpleNamespace(
        choices=[
            types.SimpleNamespace(
                delta=types.SimpleNamespace(
                    content="answer", reasoning_content=None, tool_calls=[]
                )
            )
        ],
        usage=None,
    )
    final = types.SimpleNamespace(
        choices=[],
        usage=types.SimpleNamespace(
            prompt_tokens=80, completion_tokens=20, total_tokens=100
        ),
    )
    output = _parse_vercel_stream(
        [data_chunk, final],
        callbacks=StreamCallbacks(
            on_delta=lambda _: None,
            on_terminal=lambda event, data: terminals.append((event, dict(data))),
        ),
    )

    assert output[0] == "answer"
    assert terminals[-1] == (
        "ResponseCompleted",
        {"usage": {"input_tokens": 80, "output_tokens": 20, "total_tokens": 100}},
    )


def test_vercel_stream_does_not_report_usage_after_interruption() -> None:
    from uagent.providers.llm_vercel import _parse_vercel_stream

    def broken_stream():
        yield types.SimpleNamespace(
            choices=[],
            usage={"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
        )
        raise OSError("connection interrupted")

    terminals: list[tuple[str, dict]] = []
    _parse_vercel_stream(
        broken_stream(),
        callbacks=StreamCallbacks(
            on_terminal=lambda event, data: terminals.append((event, dict(data))),
        ),
    )

    assert terminals[-1] == ("ResponseCompleted", {})


def test_vercel_stream_requests_usage_only_when_streaming() -> None:
    from uagent.providers.llm_vercel import vercel_chat_with_tools

    class _Completions:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if kwargs.get("stream"):
                return iter([types.SimpleNamespace(choices=[], usage=None)])
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(
                            content="ok", reasoning_content=None, tool_calls=[]
                        )
                    )
                ]
            )

    completions = _Completions()
    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=completions)
    )
    core = types.SimpleNamespace(_is_web=True)
    for stream in (True, False):
        success, *_ = vercel_chat_with_tools(
            client=client,
            depname="test-model",
            call_messages=[{"role": "user", "content": "hello"}],
            core=core,
            make_client_fn=lambda _: ("vercel", client),
            call_maybe_thread_fn=lambda callback: callback(),
            send_tools_this_round=False,
            max_retries_429=0,
            retry_base=0.1,
            retry_cap=1.0,
            stream=stream,
            callbacks=StreamCallbacks(on_terminal=lambda *_: None),
        )
        assert success is True
    assert completions.calls[0]["stream_options"]["include_usage"] is True
    assert "stream_options" not in completions.calls[1]
