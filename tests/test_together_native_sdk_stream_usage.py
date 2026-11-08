"""Exercise Together's native SDK transport for measured streamed usage."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from uagent.providers.llm_together import together_chat_with_tools
from uagent.runtime.stream_renderer import StreamCallbacks


def test_together_stream_usage_passes_through_real_sdk_http_body(monkeypatch) -> None:
    httpx = pytest.importorskip("httpx")
    together = pytest.importorskip("together")
    requests: list[dict] = []

    def handle(request):
        requests.append(json.loads(request.content))
        text_chunk = {
            "id": "together-test",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": "answer"},
                    "finish_reason": None,
                }
            ],
        }
        usage_chunk = {
            "id": "together-test",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "test-model",
            "choices": [],
            "usage": {
                "prompt_tokens": 90,
                "completion_tokens": 25,
                "total_tokens": 115,
            },
        }
        events = (
            f"data: {json.dumps(text_chunk)}\n\n"
            f"data: {json.dumps(usage_chunk)}\n\n"
            "data: [DONE]\n\n"
        )
        return httpx.Response(
            200,
            text=events,
            headers={"content-type": "text/event-stream"},
        )

    monkeypatch.setattr(
        "uagent.providers.llm_together.build_together_chat_kwargs",
        lambda **_kwargs: ({"model": "test-model", "messages": []}, None),
    )
    core = SimpleNamespace(_last_responses_usage={})
    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        sdk = together.Together(
            api_key="test-only",
            base_url="https://together-sdk.example",
            http_client=transport,
        )
        result = together_chat_with_tools(
            client=sdk,
            depname="test-model",
            call_messages=[],
            core=core,
            make_client_fn=lambda _core: (None, sdk),
            call_maybe_thread_fn=lambda fn: fn(),
            send_tools_this_round=False,
            max_retries_429=0,
            retry_base=0.0,
            retry_cap=0.0,
            stream=True,
            callbacks=StreamCallbacks(on_delta=lambda _s: None),
        )

    assert result[0] is True
    assert result[2] == "answer"
    assert len(requests) == 1
    assert requests[0]["stream"] is True
    assert requests[0]["stream_options"] == {"include_usage": True}
    assert core._last_responses_usage == {
        "input_tokens": 90,
        "output_tokens": 25,
        "total_tokens": 115,
    }
