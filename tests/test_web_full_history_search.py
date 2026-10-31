"""Regression checks for searching the full authorized Web session history."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_search_requests_authorized_server_results() -> None:
    sidebar = (ROOT / "frontend/src/lib/components/Sidebar.svelte").read_text(
        encoding="utf-8"
    )
    client = (ROOT / "frontend/src/lib/stores.svelte.js").read_text(encoding="utf-8")

    assert "fetchLogs(1, 30, query.trim())" in sidebar
    assert "oninput={scheduleSearch}" in sidebar
    assert "searchTimer = setTimeout(loadSessions, 250)" in sidebar
    assert "if (sequence !== requestSequence) return;" in sidebar
    assert "if (sequence === requestSequence) loading = false;" in sidebar
    assert "if (search.trim()) params.set('q', search.trim());" in client


def test_shipped_sidebar_search_matches_source() -> None:
    bundle = (ROOT / "src/uagent/static/assets/index.js").read_text(encoding="utf-8")

    assert 'ho("input",K,scheduleSearch)' in bundle
    assert "xi(1,30,a(s).trim())" in bundle
    assert "searchTimer=setTimeout(l,250)" in bundle
    assert "seq!==requestSequence" in bundle
    assert 'n.set("q",r.trim())' in bundle
