from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from uagent.tools import markitdown_tool as tool
from uagent._pip_auto import _install_allowed


def _rel(path: Path) -> str:
    return path.relative_to(Path.cwd()).as_posix()


def _fake_markitdown(
    monkeypatch, markdown: str = "# Converted\\n\\nText"
) -> list[dict]:
    calls: list[dict] = []

    class FakeMarkItDown:
        def __init__(self, **kwargs):
            calls.append({"init": kwargs})

        def convert_local(self, path: str):
            calls.append({"path": path})
            return types.SimpleNamespace(markdown=markdown)

    monkeypatch.setitem(
        sys.modules,
        "markitdown",
        types.SimpleNamespace(MarkItDown=FakeMarkItDown),
    )
    monkeypatch.setattr(tool, "install_with_status", lambda *a, **k: True)
    return calls


def test_local_conversion_disables_plugins(repo_tmp_path: Path, monkeypatch) -> None:
    assert tool.TOOL_SPEC["tool_level"] == 1
    calls = _fake_markitdown(monkeypatch)
    source = repo_tmp_path / "source.epub"
    source.write_bytes(b"book")

    result = json.loads(tool.run_tool({"input_path": _rel(source)}))

    assert result["ok"] is True
    assert result["markdown"] == "# Converted\\n\\nText"
    assert calls[0]["init"] == {"enable_plugins": False}
    assert calls[1]["path"] == str(source.resolve())


def test_saves_full_markdown_and_backs_up_existing_output(
    repo_tmp_path: Path, monkeypatch
) -> None:
    _fake_markitdown(monkeypatch, "# Full output\\n")
    source = repo_tmp_path / "source.pdf"
    source.write_bytes(b"pdf")
    output = repo_tmp_path / "result.md"
    output.write_text("old", encoding="utf-8")

    result = json.loads(
        tool.run_tool(
            {
                "input_path": _rel(source),
                "output_path": _rel(output),
                "overwrite": True,
            }
        )
    )

    assert result["ok"] is True
    assert output.read_text(encoding="utf-8") == "# Full output\\n"
    assert Path(str(output) + ".org").read_text(encoding="utf-8") == "old"


def test_rejects_oversized_input_before_install(
    repo_tmp_path: Path, monkeypatch
) -> None:
    source = repo_tmp_path / "large.txt"
    source.write_bytes(b"0123456789")
    called = False

    def unexpected_install(*args, **kwargs):
        nonlocal called
        called = True
        return True

    monkeypatch.setattr(tool, "install_with_status", unexpected_install)
    result = json.loads(
        tool.run_tool(
            {
                "input_path": _rel(source),
                "max_input_bytes": 5,
            }
        )
    )

    assert result["ok"] is False
    assert "5" in result["error"]
    assert called is False


def test_rejects_path_outside_workdir(monkeypatch) -> None:
    monkeypatch.setattr(tool, "install_with_status", lambda *a, **k: True)
    result = json.loads(tool.run_tool({"input_path": "../outside.pdf"}))
    assert result["ok"] is False


def test_install_failure_is_reported(repo_tmp_path: Path, monkeypatch) -> None:
    source = repo_tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    seen: list[tuple[tuple, dict]] = []

    def failed_install(*args, **kwargs):
        seen.append((args, kwargs))
        return False

    monkeypatch.setattr(tool, "install_with_status", failed_install)
    result = json.loads(tool.run_tool({"input_path": _rel(source)}))

    assert result["ok"] is False
    assert "MarkItDown" in result["error"]
    assert seen[0][0][:2] == ("markitdown[all]", "markitdown")
    assert seen[0][1]["version_spec"] == ">=0.1.9"


def test_markitdown_extras_are_in_the_auto_install_allowlist() -> None:
    assert _install_allowed("markitdown[all]") is True
