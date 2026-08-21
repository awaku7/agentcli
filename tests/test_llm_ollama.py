from __future__ import annotations

from uagent.providers.llm_ollama import (
    _ollama_extra_params,
    apply_ollama_extra_body,
)
from uagent.providers.llm_ollama_responses import apply_ollama_responses_compat


def test_ollama_extra_params_defaults(monkeypatch):
    for key in (
        "UAGENT_OLLAMA_KEEP_ALIVE",
        "UAGENT_OLLAMA_NUM_CTX",
        "UAGENT_OLLAMA_NUM_KEEP",
        "UAGENT_OLLAMA_TEMPERATURE",
        "UAGENT_OLLAMA_TOP_P",
        "UAGENT_OLLAMA_TOP_K",
        "UAGENT_OLLAMA_REPEAT_PENALTY",
        "UAGENT_REASONING",
    ):
        monkeypatch.delenv(key, raising=False)

    params = _ollama_extra_params()

    assert params["keep_alive"] == "5m"
    assert params["options"] == {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "num_ctx": 8192,
        "num_keep": 256,
    }


def test_ollama_extra_params_reasoning(monkeypatch):
    monkeypatch.setenv("UAGENT_REASONING", "high")

    params = _ollama_extra_params()

    assert params["options"]["think"] is True


def test_ollama_extra_body_is_provider_gated(monkeypatch):
    monkeypatch.setenv("UAGENT_OLLAMA_TOP_K", "17")
    kwargs = {"model": "test-model"}

    apply_ollama_extra_body(kwargs, provider="llama_cpp")

    assert "extra_body" not in kwargs


def test_ollama_extra_body_preserves_existing_fields(monkeypatch):
    monkeypatch.setenv("UAGENT_OLLAMA_TOP_K", "17")
    kwargs = {"model": "test-model", "extra_body": {"format": "json"}}

    apply_ollama_extra_body(kwargs, provider="ollama")

    assert kwargs["extra_body"]["format"] == "json"
    assert kwargs["extra_body"]["options"]["top_k"] == 17


def test_ollama_responses_compat_uses_responses_token_field(monkeypatch):
    monkeypatch.setenv("UAGENT_OLLAMA_NUM_CTX", "4096")
    kwargs = {}

    apply_ollama_responses_compat(
        kwargs,
        provider="ollama",
        depname="test-model",
    )

    assert kwargs["extra_body"]["options"]["num_ctx"] == 4096
    assert "max_output_tokens" not in kwargs


def test_ollama_output_format_json(monkeypatch):
    monkeypatch.setenv("UAGENT_STRUCTURED_OUTPUT", "true")
    monkeypatch.setattr("uagent.llmcapa_util.supports_json_mode", lambda *_: True)
    monkeypatch.setattr("uagent.llmcapa_util.supports_json_schema", lambda *_: False)
    kwargs = {"model": "test-model"}
    messages = [{"role": "system", "content": "response_mode: json"}]

    apply_ollama_extra_body(kwargs, provider="ollama", messages=messages)

    assert kwargs["extra_body"]["format"] == "json"


def test_ollama_output_format_json_schema(monkeypatch):
    monkeypatch.setenv("UAGENT_STRUCTURED_OUTPUT", "true")
    monkeypatch.setattr("uagent.llmcapa_util.supports_json_mode", lambda *_: True)
    monkeypatch.setattr("uagent.llmcapa_util.supports_json_schema", lambda *_: True)
    kwargs = {"model": "test-model"}
    messages = [
        {
            "role": "system",
            "content": ("""response_mode: json

response_schema:
""" '{"type":"object","properties":{"answer":{"type":"string"}}}'),
        }
    ]

    apply_ollama_extra_body(kwargs, provider="ollama", messages=messages)

    assert kwargs["extra_body"]["format"] == {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
    }


def test_ollama_output_format_disabled_is_ignored(monkeypatch):
    monkeypatch.setenv("UAGENT_STRUCTURED_OUTPUT", "false")
    kwargs = {}
    messages = [{"role": "system", "content": "response_mode: json"}]

    apply_ollama_extra_body(kwargs, provider="ollama", messages=messages)

    assert "format" not in kwargs["extra_body"]


def test_ollama_responses_compat_is_provider_gated():
    kwargs = {}

    apply_ollama_responses_compat(
        kwargs,
        provider="llama_cpp",
        depname="test-model",
    )

    assert kwargs == {}
