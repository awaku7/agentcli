from __future__ import annotations

from pathlib import Path

from uagent.tools.md2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_md2idx_atx_setext_fence_preamble(repo_tmp_path: Path) -> None:
    src = (
        "Intro before any heading.\n"
        "\n"
        "# Title\n"
        "body of title\n"
        "\n"
        "## Section A\n"
        "alpha\n"
        "\n"
        "Not a heading\n"
        "=============\n"
        "\n"
        "### Nested\n"
        "nested body\n"
        "\n"
        "```python\n"
        "# not a heading\n"
        "def fake():\n"
        "    pass\n"
        "```\n"
        "\n"
        "## Section B\n"
        "beta\n"
    )
    path = repo_tmp_path / "doc.md"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "Title" in out
    assert "Section A" in out
    assert "Nested" in out
    assert "Section B" in out
    assert "Not a heading" in out
    # fenced code heading must not appear as index entry
    assert "fake" not in out.lower()

    pre = run_tool({"path": str(path), "mode": "section", "section": 0})
    assert "Intro before any heading" in pre

    s1 = run_tool({"path": str(path), "mode": "section", "section": 1})
    assert "Title" in s1
    assert "body of title" in s1


def test_md2idx_bom_crlf_and_oor(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "bom.md"
    text = "\ufeff# Hello\r\n\r\nworld\r\n"
    path.write_bytes(text.encode("utf-8"))
    out = run_tool({"path": str(path), "mode": "index"})
    assert "Hello" in out

    bad = run_tool({"path": str(path), "mode": "section", "section": 99})
    assert "99" in bad


def test_md2idx_missing_file(repo_tmp_path: Path) -> None:
    missing = repo_tmp_path / "no_such.md"
    out = run_tool({"path": str(missing), "mode": "index"})
    assert (
        "ファイルが見つかりません" in out
        or "not found" in out.lower()
        or "No such" in out
    )
