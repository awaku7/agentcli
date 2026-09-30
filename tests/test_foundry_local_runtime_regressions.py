from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent import tools as tool_registry
from uagent.llm_errors import _is_rate_limit_error
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


def _catalog_followup_messages() -> list[dict]:
    return [
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
    ]


class _Server500(RuntimeError):
    status_code = 500


class _RecordingCompletions:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(dict(kwargs))
        if len(self.calls) <= self.failures:
            raise _Server500("simulated local runtime failure")
        message = SimpleNamespace(content="done", tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_foundry_local_fallback_catalog_rows_do_not_turn_greeting_into_tool_use(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        tool_registry,
        "get_tool_catalog",
        lambda **_kwargs: [
            {"name": "search_web"},
            {"name": "fetch_url"},
        ],
    )
    kwargs = {
        "messages": [{"role": "user", "content": "こんにちわ"}],
        "tools": [_spec("tool_catalog"), _spec("tool_load"), _spec("unload_tool")],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }

    effective = llm_foundry_local.apply_foundry_local_chat_compat(kwargs)

    assert "tools" not in effective
    assert "tool_choice" not in effective
    assert "parallel_tool_calls" not in effective


def test_foundry_local_live_query_keeps_search_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        tool_registry,
        "get_tool_catalog",
        lambda **_kwargs: [
            {"name": "search_web"},
            {"name": "fetch_url"},
        ],
    )
    kwargs = {
        "messages": [{"role": "user", "content": "今日の天気"}],
        "tools": [_spec("tool_catalog"), _spec("tool_load"), _spec("unload_tool")],
        "tool_choice": "auto",
    }

    effective = llm_foundry_local.apply_foundry_local_chat_compat(kwargs)

    assert _forced_name(effective["tool_choice"]) == "tool_catalog"
    assert [spec["function"]["name"] for spec in effective["tools"]] == [
        "tool_catalog"
    ]


def test_foundry_local_tool_followup_500_retries_once_with_required() -> None:
    inner = _RecordingCompletions(failures=1)
    compat = llm_foundry_local._FoundryLocalCompletionsCompat(inner)

    response = compat.create(
        messages=_catalog_followup_messages(),
        tools=[_spec("tool_catalog"), _spec("fetch_url")],
        tool_choice="auto",
    )

    assert response.choices[0].message.content == "done"
    assert len(inner.calls) == 2
    assert _forced_name(inner.calls[0]["tool_choice"]) == "fetch_url"
    assert [spec["function"]["name"] for spec in inner.calls[0]["tools"]] == [
        "fetch_url"
    ]
    assert inner.calls[1]["tool_choice"] == "required"
    assert [spec["function"]["name"] for spec in inner.calls[1]["tools"]] == [
        "fetch_url"
    ]


def test_foundry_local_repeated_followup_500_stops_after_required_fallback() -> None:
    inner = _RecordingCompletions(failures=2)
    compat = llm_foundry_local._FoundryLocalCompletionsCompat(inner)

    with pytest.raises(llm_foundry_local.FoundryLocalServerError) as caught:
        compat.create(
            messages=_catalog_followup_messages(),
            tools=[_spec("tool_catalog"), _spec("fetch_url")],
            tool_choice="auto",
        )

    assert len(inner.calls) == 2
    assert inner.calls[1]["tool_choice"] == "required"
    assert _is_rate_limit_error(caught.value) is False


def test_foundry_local_initial_500_is_not_retried_as_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(
        tool_registry,
        "get_tool_catalog",
        lambda **_kwargs: [{"name": "search_web"}, {"name": "fetch_url"}],
    )
    inner = _RecordingCompletions(failures=1)
    compat = llm_foundry_local._FoundryLocalCompletionsCompat(inner)

    with pytest.raises(llm_foundry_local.FoundryLocalServerError) as caught:
        compat.create(
            messages=[{"role": "user", "content": "今日の天気"}],
            tools=[_spec("tool_catalog"), _spec("tool_load")],
            tool_choice="auto",
        )

    assert len(inner.calls) == 1
    assert _is_rate_limit_error(caught.value) is False
