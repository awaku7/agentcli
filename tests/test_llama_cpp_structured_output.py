from __future__ import annotations

from uagent.providers.llm_llama_cpp import (
    apply_llama_cpp_extra_body,
    normalize_llama_cpp_messages,
)


def test_llama_cpp_messages_merge_system_context_at_the_front():
    messages = [
        {"role": "user", "content": "first question"},
        {"role": "system", "content": "base prompt"},
        {"role": "assistant", "content": "previous answer"},
        {"role": "system", "content": "late memory context"},
    ]

    normalized = normalize_llama_cpp_messages(messages)

    assert [message["role"] for message in normalized] == [
        "system",
        "user",
        "assistant",
    ]
    assert normalized[0]["content"] == "base prompt\n\nlate memory context"
    assert messages == [
        {"role": "user", "content": "first question"},
        {"role": "system", "content": "base prompt"},
        {"role": "assistant", "content": "previous answer"},
        {"role": "system", "content": "late memory context"},
    ]


def test_llama_cpp_messages_preserve_single_system_message():
    messages = [
        {"role": "user", "content": "question"},
        {"role": "system", "content": "system prompt", "name": "instructions"},
    ]

    normalized = normalize_llama_cpp_messages(messages)

    assert normalized == [
        {"role": "system", "content": "system prompt", "name": "instructions"},
        {"role": "user", "content": "question"},
    ]


def test_llama_cpp_json_format(monkeypatch):
    monkeypatch.setenv("UAGENT_STRUCTURED_OUTPUT", "true")
    monkeypatch.setattr("uagent.llmcapa_util.supports_json_mode", lambda *_: True)
    monkeypatch.setattr("uagent.llmcapa_util.supports_json_schema", lambda *_: False)
    kwargs = {"model": "test-model"}
    messages = [{"role": "system", "content": "response_mode: json"}]

    apply_llama_cpp_extra_body(kwargs, provider="llama_cpp", messages=messages)

    assert kwargs["extra_body"]["response_format"] == {"type": "json_object"}


def test_llama_cpp_json_schema_format(monkeypatch):
    monkeypatch.setenv("UAGENT_STRUCTURED_OUTPUT", "true")
    monkeypatch.setattr("uagent.llmcapa_util.supports_json_mode", lambda *_: True)
    monkeypatch.setattr("uagent.llmcapa_util.supports_json_schema", lambda *_: True)
    kwargs = {"model": "test-model"}
    messages = [
        {
            "role": "system",
            "content": (
                "response_mode: json\n\nresponse_schema:\n"
                + '{"type":"object","properties":{"answer":{"type":"string"}}}'
            ),
        }
    ]

    apply_llama_cpp_extra_body(kwargs, provider="llama_cpp", messages=messages)

    assert kwargs["extra_body"]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "response",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
            },
        },
    }


def test_llama_cpp_grammar(monkeypatch):
    monkeypatch.setenv("UAGENT_LLAMA_CPP_GRAMMAR", 'root ::= "ok"')
    kwargs = {}

    apply_llama_cpp_extra_body(kwargs, provider="llama_cpp")

    assert kwargs["extra_body"]["grammar"] == 'root ::= "ok"'


def test_llama_cpp_explicit_fields_win(monkeypatch):
    monkeypatch.setenv("UAGENT_LLAMA_CPP_FORMAT", "json")
    monkeypatch.setenv("UAGENT_LLAMA_CPP_GRAMMAR", 'root ::= "env"')
    kwargs = {
        "extra_body": {
            "response_format": {"type": "json_schema"},
            "grammar": 'root ::= "explicit"',
        }
    }

    apply_llama_cpp_extra_body(kwargs, provider="llama_cpp")

    assert kwargs["extra_body"]["response_format"] == {"type": "json_schema"}
    assert kwargs["extra_body"]["grammar"] == 'root ::= "explicit"'


def test_llama_cpp_structured_output_is_provider_gated(monkeypatch):
    monkeypatch.setenv("UAGENT_LLAMA_CPP_FORMAT", "json")
    kwargs = {}

    apply_llama_cpp_extra_body(kwargs, provider="ollama")

    assert kwargs == {}
