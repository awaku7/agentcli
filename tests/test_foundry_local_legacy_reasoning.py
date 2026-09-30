from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime import legacy_openai_round


def test_foundry_legacy_normalizes_inline_think_block() -> None:
    visible, reasoning = legacy_openai_round._normalize_foundry_local_reasoning(
        "foundry_local",
        "<think>private chain</think>visible answer",
        "",
    )

    assert visible == "visible answer"
    assert reasoning == "private chain"


def test_foundry_legacy_keeps_explicit_reasoning_without_duplication() -> None:
    visible, reasoning = legacy_openai_round._normalize_foundry_local_reasoning(
        "foundry_local",
        "<think>duplicate inline</think>visible answer",
        "explicit reasoning",
    )

    assert visible == "visible answer"
    assert reasoning == "explicit reasoning"


def test_foundry_legacy_does_not_change_other_providers() -> None:
    text = "<think>provider-owned text</think>visible answer"

    visible, reasoning = legacy_openai_round._normalize_foundry_local_reasoning(
        "openai",
        text,
        "",
    )

    assert visible == text
    assert reasoning == ""


def test_foundry_legacy_round_applies_normalization(monkeypatch) -> None:
    client = object()

    def fake_call(**_kwargs):
        return (
            True,
            client,
            "<think>reasoning</think>こんにちは。",
            "",
            [],
        )

    monkeypatch.setattr(
        legacy_openai_round,
        "call_legacy_openai_azure_round",
        fake_call,
    )

    result = legacy_openai_round.call_legacy_openai_compatible_round(
        provider="foundry_local",
        client=client,
        depname="Phi-4-mini-reasoning-openvino-gpu",
        call_messages=[{"role": "user", "content": "こんにちわ"}],
        core=SimpleNamespace(),
        make_client_fn=lambda _core: (None, client),
        call_maybe_thread_fn=lambda fn: fn(),
        use_responses_api=False,
        stream_responses=False,
        send_tools_this_round=True,
        max_retries_429=20,
        retry_base=2.0,
        retry_cap=300.0,
        messages=[],
        responses_state={},
        round_count=1,
    )

    ok, returned_client, assistant_text, reasoning_content, tool_calls, is_grpc = result
    assert ok is True
    assert returned_client is client
    assert assistant_text == "こんにちは。"
    assert reasoning_content == "reasoning"
    assert tool_calls == []
    assert is_grpc is False
