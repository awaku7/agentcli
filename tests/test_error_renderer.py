from __future__ import annotations

from uagent.runtime.error_renderer import exception_text, provider_error_label


def test_provider_error_label() -> None:
    assert provider_error_label("meta") == "Meta"
    assert provider_error_label("openai") == "Azure/OpenAI"


def test_exception_text_compacts_html_and_limits_length() -> None:
    assert (
        exception_text(RuntimeError("<html><body>bad\nrequest</body></html>"))
        == "bad request"
    )
    assert len(exception_text(RuntimeError("x" * 600))) == 503


__all__ = []
