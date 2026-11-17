"""Tests for the bitchat DM display preview.

DM bodies are shown as a bounded one-line preview, mirroring the
Nostr remote (NIP-17) incoming-DM display rule: control characters
become spaces, whitespace collapses to a single line, and the result
is truncated at 2,000 characters. The preview is display-only; the
LLM injection path keeps the full original text.
"""

from __future__ import annotations

from uagent.tools.pybitchat_shared import _dm_preview_text


def test_short_text_unchanged() -> None:
    assert _dm_preview_text("hello there") == "hello there"


def test_empty_text() -> None:
    assert _dm_preview_text("") == ""


def test_newlines_and_tabs_collapse_to_one_line() -> None:
    assert _dm_preview_text("line one\nline two\t end") == "line one line two end"


def test_control_characters_become_spaces() -> None:
    # ANSI escape sequence and a bell must not reach the terminal raw.
    assert _dm_preview_text("\x1b[31mred\x07") == "[31mred"


def test_truncates_at_2000_with_ellipsis() -> None:
    out = _dm_preview_text("a" * 2500)
    assert len(out) == 2001
    assert out.endswith("…")


def test_exactly_2000_not_truncated() -> None:
    text = "a" * 2000
    assert _dm_preview_text(text) == text
