from types import SimpleNamespace

from uagent.providers import llm_pfn


def test_pfn_tool_specs_keep_parameters_as_object(monkeypatch):
    monkeypatch.setattr(
        llm_pfn._tools,
        "get_tool_specs",
        lambda: [
            {
                "type": "function",
                "function": {
                    "name": "demo",
                    "description": "demo",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    )
    specs = llm_pfn._pfn_tool_specs()
    assert isinstance(specs[0]["function"]["parameters"], dict)
    assert specs[0]["function"]["parameters"]["type"] == "object"


def test_parse_pfn_response_normalizes_tool_call():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            id="call-1",
                            function=SimpleNamespace(
                                name="demo", arguments={"value": 1}
                            ),
                        )
                    ],
                )
            )
        ]
    )
    text, calls = llm_pfn.parse_pfn_response(response)
    assert text == ""
    assert calls[0]["id"] == "call-1"
    assert calls[0]["function"]["name"] == "demo"
    assert calls[0]["function"]["arguments"] == '{"value": 1}'


def test_parse_pfn_response_recovers_json_content_tool_call():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"name":"tool_catalog","arguments":{"query":"weather"}}',
                    tool_calls=[],
                )
            )
        ]
    )
    text, calls = llm_pfn.parse_pfn_response(response)
    assert text == ""
    assert calls[0]["function"]["name"] == "tool_catalog"


def test_pfn_round_keeps_catalog_available_on_first_round(monkeypatch):
    seen = {}

    class Completions:
        def create(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="ok", tool_calls=[])
                    )
                ]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    ok, _, text, reasoning, calls = llm_pfn.pfn_chat_with_tools(
        client,
        "plamo-3.0-prime",
        [{"role": "user", "content": "hello"}],
        core=SimpleNamespace(),
        make_client_fn=lambda core: (None, client),
        call_maybe_thread_fn=lambda fn: fn(),
        send_tools_this_round=False,
        max_retries_429=0,
        retry_base=0,
        retry_cap=0,
    )
    assert ok is True
    assert text == "ok"
    assert reasoning == ""
    assert calls == []
    assert seen["stream"] is False


def test_pfn_round_disables_streaming_when_tools_are_enabled(monkeypatch, capsys):
    seen = {}

    class Completions:
        def create(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="ok", tool_calls=[])
                    )
                ]
            )

    monkeypatch.setattr(llm_pfn._tools, "get_tool_specs", lambda: [])
    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    ok, _, text, _, calls = llm_pfn.pfn_chat_with_tools(
        client,
        "plamo-3.0-prime",
        [{"role": "user", "content": "hello"}],
        core=SimpleNamespace(),
        make_client_fn=lambda core: (None, client),
        call_maybe_thread_fn=lambda fn: fn(),
        send_tools_this_round=True,
        max_retries_429=0,
        retry_base=0,
        retry_cap=0,
    )
    assert ok is True
    assert text == "ok"
    assert calls == []
    assert seen["stream"] is False
