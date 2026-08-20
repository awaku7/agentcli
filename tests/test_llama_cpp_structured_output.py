from __future__ import annotations

from uagent.providers.llm_llama_cpp import apply_llama_cpp_extra_body


def test_llama_cpp_json_format(monkeypatch):
    monkeypatch.setenv("UAGENT_LLAMA_CPP_FORMAT", "json")
    kwargs = {}

    apply_llama_cpp_extra_body(kwargs, provider="llama_cpp")

    assert kwargs["extra_body"]["response_format"] == {"type": "json_object"}


def test_llama_cpp_json_schema_format(monkeypatch):
    monkeypatch.setenv(
        "UAGENT_LLAMA_CPP_FORMAT",
        '{"type":"object","properties":{"answer":{"type":"string"}}}',
    )
    kwargs = {}

    apply_llama_cpp_extra_body(kwargs, provider="llama_cpp")

    assert kwargs["extra_body"]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "response",
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
