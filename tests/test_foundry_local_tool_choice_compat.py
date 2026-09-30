from __future__ import annotations

from types import SimpleNamespace

from uagent import tools as tool_registry
from uagent.providers import llm_foundry_local


def _spec(name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": name,
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _forced_name(choice) -> str:
    if not isinstance(choice, dict):
        return ""
    function = choice.get("function") or {}
    return str(function.get("name") or "")


def test_foundry_local_initial_round_forces_catalog_and_narrows_tools(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        tool_registry,
        "get_tool_catalog",
        lambda **_kwargs: [{"name": "fetch_url", "score": 10}],
    )
    kwargs = {
        "model": "phi-4-mini",
        "messages": [{"role": "user", "content": "今日の天気"}],
        "tools": [_spec("tool_catalog"), _spec("tool_load"), _spec("unload_tool")],
        "tool_choice": "auto",
    }

    effective = llm_foundry_local.apply_foundry_local_chat_compat(kwargs)

    assert _forced_name(effective["tool_choice"]) == "tool_catalog"
    assert [spec["function"]["name"] for spec in effective["tools"]] == ["tool_catalog"]


def test_foundry_local_unrelated_prompt_disables_tools(monkeypatch) -> None:
    monkeypatch.setattr(tool_registry, "get_tool_catalog", lambda **_kwargs: [])
    kwargs = {
        "messages": [{"role": "user", "content": "こんにちは"}],
        "tools": [_spec("tool_catalog"), _spec("tool_load"), _spec("unload_tool")],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }

    effective = llm_foundry_local.apply_foundry_local_chat_compat(kwargs)

    assert "tools" not in effective
    assert "tool_choice" not in effective
    assert "parallel_tool_calls" not in effective


def test_foundry_local_initial_round_forces_relevant_loaded_tool(monkeypatch) -> None:
    monkeypatch.setattr(
        tool_registry,
        "get_tool_catalog",
        lambda **_kwargs: [{"name": "fetch_url", "score": 10}],
    )
    kwargs = {
        "messages": [{"role": "user", "content": "今日の天気"}],
        "tools": [
            _spec("tool_catalog"),
            _spec("tool_load"),
            _spec("unload_tool"),
            _spec("fetch_url"),
        ],
        "tool_choice": "auto",
    }

    effective = llm_foundry_local.apply_foundry_local_chat_compat(kwargs)

    assert _forced_name(effective["tool_choice"]) == "fetch_url"
    assert [spec["function"]["name"] for spec in effective["tools"]] == ["fetch_url"]


def test_foundry_local_catalog_lookup_failure_preserves_auto(monkeypatch) -> None:
    def fail_catalog(**_kwargs):
        raise RuntimeError("catalog unavailable")

    monkeypatch.setattr(tool_registry, "get_tool_catalog", fail_catalog)
    kwargs = {
        "messages": [{"role": "user", "content": "今日の天気"}],
        "tools": [_spec("tool_catalog"), _spec("tool_load")],
        "tool_choice": "auto",
    }

    effective = llm_foundry_local.apply_foundry_local_chat_compat(kwargs)

    assert effective["tool_choice"] == "auto"
    assert len(effective["tools"]) == 2


def test_foundry_local_catalog_result_forces_auto_loaded_tool() -> None:
    kwargs = {
        "messages": [
            {"role": "user", "content": "今日の天気"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "catalog-call",
                        "type": "function",
                        "function": {
                            "name": "tool_catalog",
                            "arguments": '{"query":"weather"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "catalog-call",
                "name": "tool_catalog",
                "content": (
                    '{"ok":true,"auto_loaded":"fetch_url",'
                    '"tools":[{"name":"fetch_url","loaded":true}]}'
                ),
            },
        ],
        "tools": [
            _spec("tool_catalog"),
            _spec("tool_load"),
            _spec("unload_tool"),
            _spec("fetch_url"),
        ],
        "tool_choice": "auto",
    }

    effective = llm_foundry_local.apply_foundry_local_chat_compat(kwargs)

    assert _forced_name(effective["tool_choice"]) == "fetch_url"
    assert [spec["function"]["name"] for spec in effective["tools"]] == ["fetch_url"]


def test_foundry_local_catalog_result_uses_top_tool_when_already_loaded() -> None:
    choice = llm_foundry_local.resolve_foundry_local_tool_choice(
        [
            {"role": "user", "content": "今日の天気"},
            {
                "role": "tool",
                "name": "tool_catalog",
                "content": (
                    '{"ok":true,"tools":['
                    '{"name":"get_weather","loaded":true},'
                    '{"name":"fetch_url","loaded":true}]}'
                ),
            },
        ],
        [_spec("tool_catalog"), _spec("get_weather"), _spec("fetch_url")],
    )

    assert _forced_name(choice) == "get_weather"


def test_foundry_local_concrete_tool_result_disables_tools_for_final_answer() -> None:
    kwargs = {
        "messages": [
            {"role": "user", "content": "今日の天気"},
            {
                "role": "tool",
                "tool_call_id": "weather-call",
                "name": "fetch_url",
                "content": '{"ok":true,"text":"sunny"}',
            },
        ],
        "tools": [_spec("tool_catalog"), _spec("fetch_url")],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }

    effective = llm_foundry_local.apply_foundry_local_chat_compat(kwargs)

    assert "tools" not in effective
    assert "tool_choice" not in effective
    assert "parallel_tool_calls" not in effective


def test_foundry_local_explicit_tool_choice_is_preserved() -> None:
    forced = {"type": "function", "function": {"name": "fetch_url"}}
    kwargs = {
        "messages": [{"role": "user", "content": "x"}],
        "tools": [_spec("tool_catalog"), _spec("fetch_url")],
        "tool_choice": forced,
    }

    effective = llm_foundry_local.apply_foundry_local_chat_compat(kwargs)

    assert effective["tool_choice"] == forced
    assert len(effective["tools"]) == 2


def test_foundry_local_client_proxy_rewrites_auto_and_hides_duplicate_marker(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        tool_registry,
        "get_tool_catalog",
        lambda **_kwargs: [{"name": "fetch_url", "score": 10}],
    )
    seen = {}

    class FakeCompletions:
        def create(self, **kwargs):
            seen.update(kwargs)
            message = SimpleNamespace(
                content=(
                    '<|tool_call|>[{"name":"tool_catalog",'
                    '"parameters":{"query":"weather"}}]<|/tool_call|>'
                ),
                tool_calls=[SimpleNamespace(id="x")],
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    llm_foundry_local._install_foundry_local_chat_compat(client)

    response = client.chat.completions.create(
        messages=[{"role": "user", "content": "今日の天気"}],
        tools=[_spec("tool_catalog"), _spec("tool_load")],
        tool_choice="auto",
    )

    assert _forced_name(seen["tool_choice"]) == "tool_catalog"
    assert [spec["function"]["name"] for spec in seen["tools"]] == ["tool_catalog"]
    assert response.choices[0].message.content == ""
