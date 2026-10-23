from __future__ import annotations

from uagent.runtime.error_renderer import exception_text, provider_error_label


def test_provider_error_label() -> None:
    assert provider_error_label("meta") == "Meta"
    assert provider_error_label("openai") == "OpenAI"
    assert provider_error_label("azure") == "Azure"
    assert provider_error_label("ollama") == "Ollama"
    assert provider_error_label("llama_cpp") == "llama.cpp"
    assert provider_error_label("vllm") == "vLLM"
    assert provider_error_label("custom-provider") == "custom-provider"


def test_exception_text_compacts_html_and_limits_length() -> None:
    assert (
        exception_text(RuntimeError("<html><body>bad\nrequest</body></html>"))
        == "bad request"
    )
    assert len(exception_text(RuntimeError("x" * 600))) == 503


__all__ = []
