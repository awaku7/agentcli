"""Tests for Claude thinking parameter handling in llm_claude.py.

Covers:
- adaptive thinking model detection (Fable 5+ / Claude 5+)
- first-request adaptive thinking (no 400 round-trip)
- legacy enabled+budget_tokens path for older models
- runtime fallback (enabled rejected -> adaptive) and memoization
- empty thinking block does not print a bare [Claude Thinking] header
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from uagent.providers.llm_claude import (  # noqa: E402
    _ADAPTIVE_THINKING_MODELS,
    _claude_requires_adaptive_thinking,
    build_claude_output_config_for_effort,
    claude_chat_with_tools,
)

ENABLED_REJECT_ERR = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': '\"thinking.type.enabled\" is not supported for this model. "
    'Use "thinking.type.adaptive" and "output_config.effort" to control '
    "thinking behavior.'}}"
)


class Block:
    def __init__(self, type: str, **kw):
        self.type = type
        for k, v in kw.items():
            setattr(self, k, v)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Block(type={self.type!r})"


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeMessages:
    """Fake Anthropic messages endpoint.

    reject_enabled=True simulates newer models that 400 on thinking.type=enabled.
    """

    def __init__(self, content, reject_enabled=False):
        self._content = content
        self._reject_enabled = reject_enabled
        self.calls: list[dict] = []

    def create(self, **kw):
        self.calls.append(dict(kw))
        th = kw.get("thinking")
        if self._reject_enabled and th and th.get("type") == "enabled":
            raise Exception(ENABLED_REJECT_ERR)
        return FakeResponse(self._content)


class FakeClient:
    def __init__(self, content, reject_enabled=False):
        self.messages = FakeMessages(content, reject_enabled=reject_enabled)


MSGS = [{"role": "user", "content": "test"}]


@pytest.fixture(autouse=True)
def _clear_memo():
    _ADAPTIVE_THINKING_MODELS.clear()
    yield
    _ADAPTIVE_THINKING_MODELS.clear()


# ---------------------------------------------------------------------------
# Model detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model,expected",
    [
        ("claude-fable-5", True),
        ("claude-fable-5-1", True),
        ("claude-sonnet-5", True),
        ("claude-sonnet-4-5", False),
        ("claude-3-7-sonnet", False),
        ("claude-opus-4-6", False),
    ],
)
def test_requires_adaptive_thinking(model, expected):
    assert _claude_requires_adaptive_thinking(model) is expected


def test_memoized_model_requires_adaptive():
    assert _claude_requires_adaptive_thinking("claude-opus-4-6") is False
    _ADAPTIVE_THINKING_MODELS.add("claude-opus-4-6")
    assert _claude_requires_adaptive_thinking("claude-opus-4-6") is True


# ---------------------------------------------------------------------------
# Request building
# ---------------------------------------------------------------------------


def test_fable5_sends_adaptive_first_request(capsys):
    client = FakeClient([Block("text", text="ok")], reject_enabled=True)
    out_cfg = build_claude_output_config_for_effort("claude-fable-5", "high")
    assert out_cfg == {"effort": "high"}

    text, calls = claude_chat_with_tools(
        client, "claude-fable-5", MSGS, output_config=out_cfg
    )
    assert text == "ok"
    assert calls == []
    # Exactly one API call: no 400 round-trip.
    assert len(client.messages.calls) == 1
    req = client.messages.calls[0]
    assert req["thinking"] == {"type": "adaptive"}
    assert req["output_config"] == {"effort": "high"}
    assert "temperature" not in req


def test_legacy_modern_model_sends_enabled_budget():
    # "claude-4-opus" matches the is_modern_claude regex (claude-[4-9])
    # and is not detected as adaptive -> legacy enabled+budget path.
    client = FakeClient([Block("text", text="ok")])
    out_cfg = build_claude_output_config_for_effort("claude-4-opus", "high")
    assert out_cfg == {"effort": "high"}

    text, _ = claude_chat_with_tools(
        client, "claude-4-opus", MSGS, output_config=out_cfg
    )
    assert text == "ok"
    assert len(client.messages.calls) == 1
    req = client.messages.calls[0]
    assert req["thinking"]["type"] == "enabled"
    assert req["thinking"]["budget_tokens"] >= 1024
    assert "output_config" not in req


def test_non_modern_model_sends_output_config_only():
    # "claude-sonnet-4-5" does not match the is_modern_claude regex,
    # so no thinking param is sent; output_config is passed through.
    client = FakeClient([Block("text", text="ok")])
    out_cfg = build_claude_output_config_for_effort("claude-sonnet-4-5", "high")
    assert out_cfg == {"effort": "high"}

    text, _ = claude_chat_with_tools(
        client, "claude-sonnet-4-5", MSGS, output_config=out_cfg
    )
    assert text == "ok"
    assert len(client.messages.calls) == 1
    req = client.messages.calls[0]
    assert "thinking" not in req
    assert req["output_config"] == {"effort": "high"}


# ---------------------------------------------------------------------------
# Runtime fallback + memoization
# ---------------------------------------------------------------------------


def test_enabled_rejected_falls_back_to_adaptive_and_memoizes():
    # Use a model that is modern (sends thinking.type=enabled first) but is
    # NOT detected as adaptive, so the runtime fallback path is exercised.
    model = "claude-4-opus"
    content = [
        Block("thinking", thinking="思考過程"),
        Block("text", text="answer"),
    ]
    client = FakeClient(content, reject_enabled=True)
    out_cfg = build_claude_output_config_for_effort(model, "high")

    text, _ = claude_chat_with_tools(client, model, MSGS, output_config=out_cfg)
    assert "answer" in text
    assert "<thinking>" in text
    # Two calls: enabled (400) then adaptive (success).
    assert len(client.messages.calls) == 2
    assert client.messages.calls[0]["thinking"]["type"] == "enabled"
    assert client.messages.calls[1]["thinking"] == {"type": "adaptive"}
    assert client.messages.calls[1]["output_config"] == {"effort": "high"}
    # Model is memoized for the rest of the session.
    assert model in _ADAPTIVE_THINKING_MODELS

    # Second request in the same session goes adaptive directly (one call).
    client2 = FakeClient(content, reject_enabled=True)
    claude_chat_with_tools(client2, model, MSGS, output_config=out_cfg)
    assert len(client2.messages.calls) == 1
    assert client2.messages.calls[0]["thinking"] == {"type": "adaptive"}


# ---------------------------------------------------------------------------
# Thinking block display
# ---------------------------------------------------------------------------


def test_nonempty_thinking_is_printed_and_embedded(capsys):
    content = [
        Block("thinking", thinking="ここが思考です"),
        Block("text", text="final"),
    ]
    client = FakeClient(content)
    text, _ = claude_chat_with_tools(client, "claude-fable-5", MSGS)
    out = capsys.readouterr().out
    assert "[Claude Thinking]" in out
    assert "ここが思考です" in out
    assert text.startswith("<thinking>")
    assert "final" in text


def test_empty_thinking_block_prints_no_header(capsys, monkeypatch):
    monkeypatch.delenv("UAGENT_DEBUG", raising=False)
    content = [
        Block("thinking", thinking="", signature="xxx"),
        Block("text", text="final"),
    ]
    client = FakeClient(content)
    text, _ = claude_chat_with_tools(client, "claude-fable-5", MSGS)
    out = capsys.readouterr().out
    assert "[Claude Thinking]" not in out
    assert text == "final"


def test_redacted_thinking_block_is_ignored(capsys, monkeypatch):
    monkeypatch.delenv("UAGENT_DEBUG", raising=False)
    content = [
        Block("redacted_thinking", data="opaque"),
        Block("text", text="final"),
    ]
    client = FakeClient(content)
    text, _ = claude_chat_with_tools(client, "claude-fable-5", MSGS)
    out = capsys.readouterr().out
    assert "[Claude Thinking]" not in out
    assert text == "final"
