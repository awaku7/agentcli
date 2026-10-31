"""Keep Web busy indicators visible without distracting blink animations."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_svelte_and_bundled_tool_running_badges_do_not_blink() -> None:
    header = (_REPO_ROOT / "frontend/src/lib/components/Header.svelte").read_text(
        encoding="utf-8"
    )
    bundle = (_REPO_ROOT / "src/uagent/static/assets/index.js").read_text(
        encoding="utf-8"
    )
    source_html = (_REPO_ROOT / "frontend/index.html").read_text(encoding="utf-8")
    built_html = (_REPO_ROOT / "src/uagent/static/index.html").read_text(
        encoding="utf-8"
    )

    assert "t('toolRunning')" in header
    assert "toolRunning" in bundle
    assert "animation:uag-pulse" not in header
    assert "animation:uag-pulse" not in bundle
    assert "@keyframes uag-pulse" not in source_html
    assert "@keyframes uag-pulse" not in built_html


def test_legacy_web_tool_running_badge_does_not_blink() -> None:
    legacy = (_REPO_ROOT / "src/uagent/templates/index.html").read_text(
        encoding="utf-8"
    )

    assert 'id="busy-indicator"' in legacy
    assert 'class="hidden text-[10px] font-mono text-red-500 bg-red-50' in legacy
    assert "animation: blink" not in legacy
