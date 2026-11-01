"""Regression checks for searching the full authorized Web session history."""

import re
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

    assert re.search(r'\("input",[\w$]+,[\w$]+\)', bundle)
    assert 'set("q",' in bundle
    assert "/api/logs?" in bundle
    assert re.search(r"setTimeout\([\w$]+,250\)", bundle)
