"""Gemini/Vertex per-response usage collection without live provider calls."""

from __future__ import annotations

import sys
from threading import Lock
from types import ModuleType, SimpleNamespace

from uagent.providers.llm_gemini import gemini_chat_with_tools


class _FakeType:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeModels:
    def __init__(self) -> None:
        self.response = None
        self.chunks = []

    def generate_content(self, **_kwargs):
        return self.response

    def generate_content_stream(self, **_kwargs):
        return iter(self.chunks)


def _fake_google_sdk(monkeypatch) -> None:
    google = ModuleType("google")
    google.__path__ = []
    genai = ModuleType("google.genai")
    types = SimpleNamespace(
        Part=_FakeType,
        Content=_FakeType,
        Tool=_FakeType,
        GoogleSearch=_FakeType,
        GenerateContentConfig=_FakeType,
        ThinkingConfig=_FakeType,
        FunctionCallingConfig=_FakeType,
        ToolConfig=_FakeType,
        SafetySetting=_FakeType,
        HarmBlockThreshold=SimpleNamespace(BLOCK_NONE="none"),
        HarmCategory=SimpleNamespace(
            HARM_CATEGORY_HARASSMENT="harassment",
            HARM_CATEGORY_HATE_SPEECH="hate",
            HARM_CATEGORY_SEXUALLY_EXPLICIT="sexual",
            HARM_CATEGORY_DANGEROUS_CONTENT="dangerous",
            HARM_CATEGORY_CIVIC_INTEGRITY="civic",
        ),
    )
    genai.types = types
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)


def _response(**usage):
    return SimpleNamespace(
        candidates=[],
        usage_metadata=SimpleNamespace(**usage) if usage else None,
    )


def test_gemini_nonstream_usage_records_provider_snapshot(monkeypatch) -> None:
    _fake_google_sdk(monkeypatch)
    models = _FakeModels()
    models.response = _response(
        prompt_token_count=110,
        cached_content_token_count=45,
        candidates_token_count=20,
        thoughts_token_count=7,
    )
    core = SimpleNamespace(_last_responses_usage={"input_tokens": 9999})
    text, calls, _ = gemini_chat_with_tools(
        SimpleNamespace(models=models),
        "gemini-test",
        [{"role": "user", "content": "PRIVATE"}],
        core=core,
        send_tools=False,
        provider="gemini",
    )
    assert (text, calls) == ("", [])
    assert core._last_responses_usage == {
        "input_tokens": 110,
        "output_tokens": 27,
        "total_tokens": 137,
        "cache_read_input_tokens": 45,
        "reasoning_output_tokens": 7,
    }
    assert "PRIVATE" not in str(core._last_responses_usage)


def test_vertex_stream_usage_uses_last_cumulative_chunk_only(monkeypatch) -> None:
    _fake_google_sdk(monkeypatch)
    models = _FakeModels()
    models.chunks = [
        _response(prompt_token_count=10, candidates_token_count=3),
        _response(
            prompt_token_count=110,
            cached_content_token_count=70,
            tool_use_prompt_token_count=5,
            candidates_token_count=20,
            thoughts_token_count=11,
        ),
    ]
    core = SimpleNamespace(
        interrupt_lock=Lock(), interrupt_requested=False, _last_responses_usage={}
    )
    text, calls, _ = gemini_chat_with_tools(
        SimpleNamespace(models=models),
        "vertex-test",
        [{"role": "user", "content": "PRIVATE"}],
        core=core,
        send_tools=False,
        stream=True,
        provider="vertexai",
    )
    assert (text, calls) == ("", [])
    assert core._last_responses_usage == {
        "input_tokens": 115,
        "output_tokens": 31,
        "total_tokens": 146,
        "cache_read_input_tokens": 70,
        "reasoning_output_tokens": 11,
    }


def test_gemini_does_not_reuse_stale_usage_on_missing_response(monkeypatch) -> None:
    _fake_google_sdk(monkeypatch)
    models = _FakeModels()
    models.response = _response()
    previous = {"input_tokens": 9999}
    core = SimpleNamespace(_last_responses_usage=previous)
    gemini_chat_with_tools(
        SimpleNamespace(models=models),
        "gemini-test",
        [{"role": "user", "content": "PRIVATE"}],
        core=core,
        send_tools=False,
    )
    assert core._last_responses_usage is previous


def test_gemini_interrupted_stream_does_not_report_partial_usage(
    monkeypatch,
) -> None:
    _fake_google_sdk(monkeypatch)
    models = _FakeModels()
    core = SimpleNamespace(
        interrupt_lock=Lock(),
        interrupt_requested=False,
        _last_responses_usage={"input_tokens": 9999},
    )

    def interrupted():
        yield _response(prompt_token_count=10, candidates_token_count=5)
        core.interrupt_requested = True
        yield _response(prompt_token_count=100, candidates_token_count=50)

    models.chunks = interrupted()
    gemini_chat_with_tools(
        SimpleNamespace(models=models),
        "gemini-test",
        [{"role": "user", "content": "PRIVATE"}],
        core=core,
        send_tools=False,
        stream=True,
    )
    assert core._last_responses_usage == {"input_tokens": 9999}
