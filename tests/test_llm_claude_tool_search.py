from __future__ import annotations

from types import SimpleNamespace


def _spec(name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Description for {name}",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        },
    }


class _Block:
    def __init__(self, block_type: str, **values) -> None:
        self.type = block_type
        for key, value in values.items():
            setattr(self, key, value)


class _Response:
    def __init__(self, content) -> None:
        self.content = content
        self.usage = None
        self.id = "msg_test"


class _Messages:
    def __init__(self, responses) -> None:
        self.responses = iter(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.responses)


class _Client:
    def __init__(self, responses) -> None:
        self.messages = _Messages(responses)


def test_anthropic_tool_search_uses_llmcapa_messages_metadata(monkeypatch) -> None:
    from uagent import llmcapa_util
    from uagent.runtime.tool_discovery import anthropic_messages_tool_search_variant

    capability = SimpleNamespace(
        tool_search=SimpleNamespace(
            execution=("server", "client"),
            api_surfaces=("messages",),
            variants=("regex", "bm25"),
        )
    )
    monkeypatch.setattr(llmcapa_util, "supports_feature", lambda *_a, **_k: True)
    monkeypatch.setattr(llmcapa_util, "get_capability", lambda *_a, **_k: capability)

    assert anthropic_messages_tool_search_variant("claude", "custom-model") == "bm25"
    assert (
        anthropic_messages_tool_search_variant(
            "claude", "custom-model", configured_mode="regex"
        )
        == "regex"
    )
    assert (
        anthropic_messages_tool_search_variant(
            "claude", "custom-model", configured_mode="off"
        )
        is None
    )
    assert anthropic_messages_tool_search_variant("openai", "custom-model") is None

    monkeypatch.setattr(llmcapa_util, "supports_feature", lambda *_a, **_k: None)
    assert anthropic_messages_tool_search_variant("claude", "unknown-model") is None


def test_anthropic_tool_search_defers_full_catalog_and_replays_native_blocks(
    monkeypatch,
) -> None:
    from uagent import tools
    from uagent.providers import llm_claude
    from uagent.runtime import execution_broker, provider_context, tool_discovery

    all_specs = [
        _spec(name)
        for name in (
            "human_ask",
            "calculator",
            "fetch_url",
            "search_web",
            "python_exec",
            "tool_catalog",
            "tool_load",
            "unload_tool",
            "local_tool_a",
            "local_tool_b",
        )
    ]
    monkeypatch.setattr(tools, "get_tool_specs", lambda: all_specs)
    monkeypatch.setattr(
        tool_discovery,
        "anthropic_messages_tool_search_variant",
        lambda *_a, **_k: "bm25",
    )
    monkeypatch.setattr(execution_broker, "computer_use_allowed", lambda: False)
    monkeypatch.setattr(
        execution_broker, "is_computer_use_tool_spec", lambda _spec: False
    )

    server_use = _Block(
        "server_tool_use",
        id="srvtoolu_search",
        name="tool_search_tool_bm25",
        input={"query": "find the local tool that does the requested operation"},
    )
    search_result = _Block(
        "tool_search_tool_result",
        tool_use_id="srvtoolu_search",
        content={
            "type": "tool_search_tool_search_result",
            "tool_references": [
                {"type": "tool_reference", "tool_name": "local_tool_a"}
            ],
        },
    )
    local_use = _Block(
        "tool_use", id="toolu_local", name="local_tool_a", input={"value": "x"}
    )
    raw_content = [
        _Block("text", text="I found a tool."),
        server_use,
        search_result,
        local_use,
    ]
    client = _Client(
        [
            _Response(raw_content),
            _Response([_Block("text", text="Finished.")]),
        ]
    )
    core = SimpleNamespace(context_tool_specs=[_spec("context_limited_tool")])

    assistant_text, calls = llm_claude.claude_chat_with_tools(
        client, "claude-opus-4-6", [{"role": "user", "content": "do it"}], core=core
    )
    request_tools = client.messages.calls[0]["tools"]

    assert assistant_text == "I found a tool."
    assert [call["function"]["name"] for call in calls] == ["local_tool_a"]
    assert request_tools[0] == {
        "type": "tool_search_tool_bm25_20251119",
        "name": "tool_search_tool_bm25",
    }
    function_tools = {item["name"]: item for item in request_tools[1:]}
    excluded_management_tools = {"tool_catalog", "tool_load", "unload_tool"}
    assert set(function_tools) == {
        spec["function"]["name"]
        for spec in all_specs
        if spec["function"]["name"] not in excluded_management_tools
    }
    assert not (set(function_tools) & excluded_management_tools)
    assert not any(
        function_tools[name].get("defer_loading")
        for name in (
            "human_ask",
            "calculator",
            "fetch_url",
            "search_web",
            "python_exec",
        )
    )
    assert function_tools["local_tool_a"]["defer_loading"] is True
    assert function_tools["local_tool_b"]["defer_loading"] is True
    assert "input_schema" in function_tools["local_tool_a"]

    raw_content_blocks = core._last_claude_content_blocks
    assert [block["type"] for block in raw_content_blocks] == [
        "text",
        "server_tool_use",
        "tool_search_tool_result",
        "tool_use",
    ]
    assistant_message = {
        "role": "assistant",
        "content": assistant_text,
        "tool_calls": calls,
        "_anthropic_content_blocks": raw_content_blocks,
    }
    projected = provider_context.project_messages_for_provider(
        [assistant_message], provider="claude", model="claude-opus-4-6"
    )
    assert projected[0]["_anthropic_content_blocks"] == core._last_claude_content_blocks
    assert (
        "_anthropic_content_blocks"
        not in provider_context.project_messages_for_provider(
            [assistant_message], provider="openai"
        )[0]
    )

    continuation = [
        {"role": "user", "content": "do it"},
        projected[0],
        {"role": "tool", "tool_call_id": "toolu_local", "content": "tool result"},
    ]
    llm_claude.claude_chat_with_tools(
        client, "claude-opus-4-6", continuation, core=core
    )
    replayed = client.messages.calls[1]["messages"]
    assert replayed[1]["role"] == "assistant"
    assert replayed[1]["content"] == raw_content_blocks
    assert replayed[2]["role"] == "user"
    assert replayed[2]["content"][0]["type"] == "tool_result"
    assert replayed[2]["content"][0]["tool_use_id"] == "toolu_local"
    assert not any(
        block.get("type") == "tool_result"
        and block.get("tool_use_id") == "srvtoolu_search"
        for message in replayed
        for block in message.get("content", [])
        if isinstance(block, dict)
    )


def test_anthropic_tool_search_fails_closed_and_respects_toolless_rounds(
    monkeypatch,
) -> None:
    from uagent import tools
    from uagent.providers import llm_claude
    from uagent.runtime import tool_discovery

    selected_specs = [_spec("selected_tool")]
    monkeypatch.setattr(tools, "get_tool_specs", lambda: [_spec("full_catalog_tool")])
    monkeypatch.setattr(
        tool_discovery, "anthropic_messages_tool_search_variant", lambda *_a, **_k: None
    )
    client = _Client([_Response([_Block("text", text="ok")])])
    core = SimpleNamespace(context_tool_specs=selected_specs)

    llm_claude.claude_chat_with_tools(
        client,
        "unknown-claude-model",
        [{"role": "user", "content": "hello"}],
        core=core,
    )
    assert [tool["name"] for tool in client.messages.calls[0]["tools"]] == [
        "selected_tool"
    ]
    assert all(
        "defer_loading" not in tool for tool in client.messages.calls[0]["tools"]
    )

    no_tools_client = _Client([_Response([_Block("text", text="ok")])])
    llm_claude.claude_chat_with_tools(
        no_tools_client,
        "claude-opus-4-6",
        [{"role": "user", "content": "hello"}],
        send_tools=False,
        core=core,
    )
    assert "tools" not in no_tools_client.messages.calls[0]


def test_openrouter_messages_search_is_regex_only_and_metadata_gated(
    monkeypatch,
) -> None:
    from uagent import llmcapa_util
    from uagent.runtime.tool_discovery import anthropic_messages_tool_search_variant

    capability = SimpleNamespace(
        tool_search={
            "execution": ["server"],
            "api_surfaces": ["responses", "messages"],
            "variants": ["regex", "bm25"],
        }
    )
    monkeypatch.setattr(llmcapa_util, "supports_feature", lambda *_a, **_k: True)
    monkeypatch.setattr(llmcapa_util, "get_capability", lambda *_a, **_k: capability)

    assert anthropic_messages_tool_search_variant("openrouter", "model-x") == "regex"
    monkeypatch.setenv("UAGENT_OPENROUTER_TOOL_SEARCH", "off")
    assert anthropic_messages_tool_search_variant("openrouter", "model-x") is None


def test_messages_api_provider_client_uses_documented_base_urls(monkeypatch) -> None:
    from uagent.providers import util_providers

    monkeypatch.setattr(util_providers, "detect_provider", lambda: "openrouter")
    monkeypatch.setattr(util_providers, "get_model_name", lambda: "openai/gpt-5.4")
    monkeypatch.setattr(util_providers, "_ensure_provider_dependency", lambda _p: None)
    monkeypatch.setattr(
        util_providers,
        "_provider_api_key",
        lambda _core, _provider: "test-key",
    )
    constructed = []
    monkeypatch.setattr(
        util_providers,
        "_make_anthropic_messages_client",
        lambda **kwargs: constructed.append(kwargs) or "messages-client",
    )
    monkeypatch.setenv("UAGENT_OPENROUTER_API", "messages")
    core = SimpleNamespace(get_env_url=lambda _name, default=None: default)

    provider, client, model = util_providers.make_client(core)

    assert (provider, client, model) == (
        "openrouter",
        "messages-client",
        "openai/gpt-5.4",
    )
    assert constructed[0]["base_url"] == "https://openrouter.ai/api"
    assert constructed[0]["api_key"] == "test-key"

    monkeypatch.setattr(util_providers, "detect_provider", lambda: "deepseek")
    monkeypatch.setattr(util_providers, "get_model_name", lambda: "deepseek-flash")
    monkeypatch.setenv("UAGENT_DEEPSEEK_API", "messages")
    provider, client, model = util_providers.make_client(core)
    assert (provider, client, model) == (
        "deepseek",
        "messages-client",
        "deepseek-flash",
    )
    assert constructed[1]["base_url"] == "https://api.deepseek.com/anthropic"


def test_deepseek_messages_client_search_defers_and_replays_tool_references(
    monkeypatch,
) -> None:
    import json

    from uagent import tools
    from uagent.providers import llm_claude
    from uagent.runtime import execution_broker, tool_discovery

    all_specs = [
        _spec(name)
        for name in (
            "tool_catalog",
            "tool_load",
            "unload_tool",
            "human_ask",
            "calculator",
            "local_tool_a",
        )
    ]
    monkeypatch.setattr(tools, "get_tool_specs", lambda: all_specs)
    monkeypatch.setattr(
        tool_discovery,
        "anthropic_messages_tool_search_variant",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        tool_discovery,
        "deepseek_messages_tool_search_enabled",
        lambda provider, _model: provider == "deepseek",
    )
    monkeypatch.setattr(execution_broker, "computer_use_allowed", lambda: False)
    monkeypatch.setattr(
        execution_broker, "is_computer_use_tool_spec", lambda _spec: False
    )

    catalog_call = _Block(
        "tool_use",
        id="toolu_catalog",
        name="tool_catalog",
        input={"query": "find local tool"},
    )
    client = _Client(
        [
            _Response([catalog_call]),
            _Response([_Block("text", text="Done.")]),
        ]
    )
    core = SimpleNamespace(context_tool_specs=[_spec("selected_only")])

    assistant_text, calls = llm_claude.claude_chat_with_tools(
        client,
        "deepseek-flash",
        [{"role": "user", "content": "use a local tool"}],
        provider="deepseek",
        core=core,
    )
    assert assistant_text == ""
    assert calls[0]["function"]["name"] == "tool_catalog"
    first_tools = {tool["name"]: tool for tool in client.messages.calls[0]["tools"]}
    assert "defer_loading" not in first_tools["tool_catalog"]
    assert first_tools["local_tool_a"]["defer_loading"] is True

    assistant_message = {
        "role": "assistant",
        "content": assistant_text,
        "tool_calls": calls,
        "_anthropic_content_blocks": core._last_claude_content_blocks,
    }
    catalog_result = json.dumps({"ok": True, "tools": [{"name": "local_tool_a"}]})
    llm_claude.claude_chat_with_tools(
        client,
        "deepseek-flash",
        [
            {"role": "user", "content": "use a local tool"},
            assistant_message,
            {
                "role": "tool",
                "tool_call_id": "toolu_catalog",
                "content": catalog_result,
            },
        ],
        provider="deepseek",
        core=core,
    )
    replayed = client.messages.calls[1]["messages"]
    reference_result = replayed[2]["content"][0]
    assert reference_result["type"] == "tool_result"
    assert reference_result["content"] == [
        {"type": "tool_reference", "tool_name": "local_tool_a"},
        {"type": "text", "text": "Continue."},
    ]


def test_deepseek_messages_search_requires_api_mode_and_messages_metadata(
    monkeypatch,
) -> None:
    from uagent import llmcapa_util
    from uagent.runtime.tool_discovery import deepseek_messages_tool_search_enabled

    capability = SimpleNamespace(
        tool_search={
            "execution": ["client"],
            "api_surfaces": ["responses", "messages"],
        }
    )
    monkeypatch.setattr(llmcapa_util, "supports_feature", lambda *_a, **_k: True)
    monkeypatch.setattr(llmcapa_util, "get_capability", lambda *_a, **_k: capability)
    assert not deepseek_messages_tool_search_enabled("deepseek", "deepseek-flash")

    monkeypatch.setenv("UAGENT_DEEPSEEK_API", "messages")
    assert deepseek_messages_tool_search_enabled("deepseek", "deepseek-flash")
    monkeypatch.setenv("UAGENT_DEEPSEEK_TOOL_SEARCH", "off")
    assert not deepseek_messages_tool_search_enabled("deepseek", "deepseek-flash")
