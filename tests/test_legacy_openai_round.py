from __future__ import annotations

from uagent.runtime import legacy_openai_round


def _kwargs() -> dict[str, object]:
    return {
        "provider": "openai",
        "client": object(),
        "depname": "model",
        "call_messages": [],
        "core": object(),
        "make_client_fn": object(),
        "call_maybe_thread_fn": object(),
        "use_responses_api": False,
        "stream_responses": False,
        "send_tools_this_round": True,
        "max_retries_429": 2,
        "retry_base": 1.0,
        "retry_cap": 4.0,
        "messages": [],
        "responses_state": {},
        "round_count": 1,
    }


def test_openai_compatible_dispatch_normalizes_result(monkeypatch) -> None:
    monkeypatch.setattr(
        legacy_openai_round,
        "call_legacy_openai_azure_round",
        lambda **_kwargs: (True, "new-client", "answer", "reasoning", []),
    )

    result = legacy_openai_round.call_legacy_openai_compatible_round(**_kwargs())

    assert result == (True, "new-client", "answer", "reasoning", [], False)


def test_openai_compatible_outcome_preserves_raw_tuple_and_metadata(monkeypatch) -> None:
    raw_result = (True, "new-client", "answer", "reasoning", [], True)
    monkeypatch.setattr(
        legacy_openai_round,
        "call_legacy_openai_compatible_round",
        lambda **_kwargs: raw_result,
    )

    outcome = legacy_openai_round.call_legacy_openai_compatible_outcome(
        **_kwargs()
    )

    assert outcome.provider == "openai"
    assert outcome.status == "ok"
    assert outcome.client == "new-client"
    assert outcome.assistant_text == "answer"
    assert outcome.reasoning_text == "reasoning"
    assert outcome.is_xai_grpc is True
    assert outcome.capabilities.host_rendered is False
    assert outcome.capabilities.supports_tool_continuation is False
    assert outcome.raw_result == raw_result

    streamed_kwargs = _kwargs()
    streamed_kwargs["stream_responses"] = True
    streamed = legacy_openai_round.call_legacy_openai_compatible_outcome(
        **streamed_kwargs
    )
    assert streamed.capabilities.host_rendered is True


__all__ = []
