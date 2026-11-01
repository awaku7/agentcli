"""Prevent duplicate Web status indicators below the chat."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_web_status_is_only_rendered_in_header() -> None:
    app = (ROOT / "frontend/src/App.svelte").read_text(encoding="utf-8")
    header = (ROOT / "frontend/src/lib/components/Header.svelte").read_text(
        encoding="utf-8"
    )
    assert "<StatusBar />" not in app
    assert "import StatusBar" not in app
    assert "<Header " in app
    assert ": status.label}" in header
    assert "{t('toolRunning')}" in header


def test_distributed_web_has_no_duplicate_status_instance() -> None:
    bundle = (ROOT / "src/uagent/static/assets/index.js").read_text(encoding="utf-8")
    assert bundle.count('"status-idle"') == 1
    assert bundle.count('"status-busy"') == 1
