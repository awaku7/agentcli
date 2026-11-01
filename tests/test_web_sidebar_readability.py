"""Regression checks for Web sidebar readability and bundled assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_sidebar_titles_and_metadata_avoid_internal_identifiers() -> None:
    source = _read("frontend/src/lib/components/Sidebar.svelte")
    bundle = _read("src/uagent/static/assets/index.js")

    assert 'session.summary || session.first_message || t("sessionLogs")' in source
    # Vite/Svelte compiler versions rename generated locals and scope CSS
    # classes, so assert the stable fallback fields rather than local names.
    assert 'summary||""' in bundle
    assert 'first_message||""' in bundle
    assert "sessionLogs" in bundle
    assert "title={sessionTitle(session)}" in source
    assert '"title"' in bundle
    assert "プロジェクト未設定" not in source
    assert "要約なし" not in source
    assert "プロジェクト未設定" not in bundle
    assert "要約なし" not in bundle

    # Navigating a bound room stays distinct from loading a local legacy log.
    assert "encodeURIComponent(session.room_id)" in source
    assert 'new CustomEvent("uag-load-session"' in source


def test_sidebar_styles_match_shipped_css() -> None:
    source = _read("frontend/src/lib/components/Sidebar.svelte")
    css = _read("src/uagent/static/assets/index.css")

    assert "-webkit-line-clamp: 2" in source
    assert "-webkit-line-clamp:2" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in source
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert ".footer-action:first-child { grid-column: 1 / -1; }" in source
    assert ":first-child{grid-column:1 / -1}" in css
    assert ".session-item:focus-visible" in source
    assert ".session-item." in css and ":focus-visible" in css
    assert "color: var(--accent); background: var(--accent-subtle)" in source
    assert "color:var(--accent);background:var(--accent-subtle)" in css
