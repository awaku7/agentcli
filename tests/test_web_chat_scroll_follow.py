"""Regression checks for Web chat scroll-follow behavior."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_chat_scroll_follows_only_when_near_bottom() -> None:
    source = (ROOT / "frontend/src/lib/components/Chat.svelte").read_text(
        encoding="utf-8"
    )

    assert "onscroll={handleChatScroll}" in source
    assert "const bottomThreshold = 80;" in source
    assert "followLatest = distance <= bottomThreshold;" in source
    assert "if (!followLatest || !chatBox || scrollScheduled) return;" in source
    assert (
        "if (followLatest && chatBox) chatBox.scrollTop = chatBox.scrollHeight;"
        in source
    )


def test_shipped_chat_bundle_preserves_scroll_follow_gate() -> None:
    bundle = (ROOT / "src/uagent/static/assets/index.js").read_text(encoding="utf-8")

    assert re.search(r'\("scroll",[\w$]+,[\w$]+\)', bundle)
    assert "scrollHeight" in bundle
    assert "scrollTop" in bundle
    assert "clientHeight" in bundle
    assert "requestAnimationFrame" in bundle


def test_shipped_chat_bundle_receives_scroll_events() -> None:
    """Confirm the built asset retains scroll events and frame scheduling."""
    bundle = (ROOT / "src/uagent/static/assets/index.js").read_text(encoding="utf-8")

    assert re.search(r'\("scroll",[\w$]+,[\w$]+\)', bundle)
    assert "requestAnimationFrame" in bundle
