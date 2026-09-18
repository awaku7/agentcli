from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.legacy_tool_continuation import execute_legacy_tool_calls


def test_legacy_tool_continuation_executes_collected_calls_once(monkeypatch) -> None:
    tool_call = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "read_file", "arguments": "{}"},
    }
    messages: list[dict[str, object]] = []
    calls = []
    monkeypatch.setattr(
        "uagent.llm_flow_helpers._execute_tool_calls",
        lambda **payload: calls.append(payload) or (True, [tool_call]),
    )
    core = SimpleNamespace(responses_runtime=object())

    result = execute_legacy_tool_calls(
        tool_calls=[tool_call],
        messages=messages,
        core=core,
        cache_mgr="cache",
        responses_api_continuation=True,
    )

    assert result == (True, [tool_call])
    assert len(calls) == 1
    assert calls[0]["tool_calls_list"] == [tool_call]
    assert calls[0]["messages"] is messages
    assert calls[0]["responses_runtime"] is core.responses_runtime


def test_legacy_tool_continuation_is_side_effect_free_in_judgment_mode(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "uagent.llm_flow_helpers._execute_tool_calls",
        lambda **_payload: (_ for _ in ()).throw(AssertionError("must not execute")),
    )

    result = execute_legacy_tool_calls(
        tool_calls=[{"id": "call-1"}],
        messages=[],
        core=SimpleNamespace(),
        judgment_mode=True,
    )

    assert result == (False, [])


__all__ = []
