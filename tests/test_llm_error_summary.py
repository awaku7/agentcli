from __future__ import annotations

from uagent.llm_round_helpers import _exception_text, _is_zscaler_responses_block


class _Response:
    text = "<!DOCTYPE html><html>Zscaler Website blocked https://api.openai.com/v1/responses</html>"


class _Error(Exception):
    response = _Response()


def test_zscaler_error_is_compact_and_detected() -> None:
    error = _Error(_Response.text)

    assert _is_zscaler_responses_block(error)
    summary = _exception_text(error)
    assert summary.startswith("Zscaler blocked access to")
    assert "<!DOCTYPE" not in summary
    assert "\n" not in summary
