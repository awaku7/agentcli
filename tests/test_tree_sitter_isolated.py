"""Native crash containment and real UAG repository regression tests."""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

from uagent.tools.code_map_impl import tree_sitter_isolated
from uagent.tools.code_map_impl.symbols import extract_symbols


@pytest.fixture(autouse=True)
def reset_tree_sitter_worker():
    tree_sitter_isolated._stop_worker()
    tree_sitter_isolated._BROKEN = False
    yield
    tree_sitter_isolated._stop_worker()
    tree_sitter_isolated._BROKEN = False


def test_native_process_crash_uses_regex_fallback(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("class Demo:\n    def greet(self):\n        return 1\n")
    monkeypatch.setattr(
        tree_sitter_isolated,
        "_worker_command",
        lambda: [sys.executable, "-c", "import os; os._exit(139)"],
    )

    with pytest.warns(RuntimeWarning, match="Tree-sitter subprocess failed"):
        symbols = extract_symbols(str(source))

    assert {item["name"] for item in symbols} == {"Demo", "greet"}
    assert tree_sitter_isolated._BROKEN is True
    assert tree_sitter_isolated._WORKER is None
    # After a native crash, do not relaunch the failing parser on every file.
    assert extract_symbols(str(source)) == symbols


def test_stalled_worker_uses_regex_fallback(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def greeting():\n    return 42\n")
    monkeypatch.setattr(
        tree_sitter_isolated,
        "_worker_command",
        lambda: [sys.executable, "-c", "import time; time.sleep(60)"],
    )
    monkeypatch.setattr(tree_sitter_isolated, "_WORKER_TIMEOUT_SECONDS", 0.2)

    with pytest.warns(RuntimeWarning, match="Tree-sitter subprocess failed"):
        symbols = extract_symbols(str(source))

    assert [item["name"] for item in symbols] == ["greeting"]
    assert tree_sitter_isolated._BROKEN is True


def _require_language_pack() -> None:
    try:
        version("tree-sitter-language-pack")
    except PackageNotFoundError:
        pytest.skip("Tree-sitter language pack is not installed")


def test_native_worker_reused_across_files(tmp_path: Path) -> None:
    _require_language_pack()
    source = tmp_path / "日本語ファイル.py"
    source.write_text("class Demo:\n    def greet(self):\n        return 1\n")

    symbols = tree_sitter_isolated.extract_tree_sitter_symbols(str(source), "Python")
    assert {item["name"] for item in symbols} == {"Demo", "greet"}
    assert tree_sitter_isolated._WORKER is not None
    pid = tree_sitter_isolated._WORKER.pid

    symbols_again = tree_sitter_isolated.extract_tree_sitter_symbols(
        str(source), "Python"
    )
    assert symbols_again == symbols
    assert tree_sitter_isolated._WORKER is not None
    assert tree_sitter_isolated._WORKER.pid == pid


def test_native_worker_analyzes_agentcli_repository() -> None:
    """Analyze UAG's actual source, not just an artificial parser fixture."""
    _require_language_pack()
    root = Path(__file__).resolve().parents[1]
    source_files = sorted((root / "src" / "uagent").rglob("*.py"))
    assert len(source_files) >= 10

    found = 0
    for path in source_files:
        found += len(extract_symbols(str(path)))
        assert not tree_sitter_isolated._BROKEN, f"Native parser crashed on {path}"

    assert found > 0
