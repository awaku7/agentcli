from types import SimpleNamespace

from uagent import llm_round_helpers


def test_gemini_model_turn_error_retries_with_full_history(monkeypatch):
    calls = []

    def fake_gemini_chat_with_tools(client, model, messages, **kwargs):
        calls.append(list(messages))
        if len(calls) == 1:
            raise RuntimeError(
                "400 INVALID_ARGUMENT: Requests ending with a model turn are not supported."
            )
        return "continued", [], {}

    monkeypatch.setattr(
        llm_round_helpers, "gemini_chat_with_tools", fake_gemini_chat_with_tools
    )
    core = SimpleNamespace(_gemini_cache_needs_refresh=False)
    history = [
        {"role": "system", "content": "rules"},
        {"role": "assistant", "content": "partial"},
    ]

    ok, _client, text, calls_out, _dump = llm_round_helpers._call_gemini_round(
        client=object(),
        depname="vertex-model",
        call_messages=[{"role": "assistant", "content": "partial"}],
        history_messages=history,
        gemini_cache_name="cached-content",
        core=core,
        make_client_fn=lambda _core: (None, object()),
        call_maybe_thread_fn=lambda fn: fn(),
        max_retries_429=0,
        retry_base=0,
        retry_cap=0,
        stream_responses=False,
        provider="vertexai",
    )

    assert ok is True
    assert text == "continued"
    assert calls_out == []
    assert core._gemini_cache_needs_refresh is True
    assert calls[1][-1] == {"role": "user", "content": "Continue."}
