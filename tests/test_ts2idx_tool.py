from __future__ import annotations

from pathlib import Path

from uagent.tools.ts2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_ts2idx_class_interface_type_enum_top_level(repo_tmp_path: Path) -> None:
    """Brace stack must pop so top-level items are not nested under class/interface."""
    src = """export class App {
  constructor(private name: string) {}
  get title(): string { return this.name; }
  async load(): Promise<void> {}
}

export default function main() {}

interface IFoo { a: number; }

type ID = string | number;

const handler = (x: ID) => x;

enum Color { Red, Green }
"""
    path = repo_tmp_path / "app.ts"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "class App" in out
    assert "constructor()" in out
    assert "title()" in out
    assert "load()" in out
    assert "function main" in out
    assert "interface IFoo" in out
    assert "type ID" in out
    assert "function handler" in out or "handler" in out
    assert "enum Color" in out
    # top-level must NOT be nested under App/IFoo
    for ln in out.splitlines():
        if any(k in ln for k in ("function main", "handler", "type ID", "enum Color")):
            assert not ln.startswith("      "), f"unexpected nesting: {ln!r}"


def test_ts2idx_comment_string_false_positive(repo_tmp_path: Path) -> None:
    src = """// class Fake {}
class Real {
  // nope() {}
  yes() {
    const s = "class NotAType";
  }
}
"""
    path = repo_tmp_path / "c.ts"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "Real" in out
    assert "yes" in out
    assert "Fake" not in out
    assert "NotAType" not in out


def test_ts2idx_section_and_missing(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "s.ts"
    _write(path, "function a() {}\n")
    out = run_tool({"path": str(path), "mode": "section", "section": 1})
    assert "function a" in out or "a()" in out
    bad = run_tool({"path": str(path), "mode": "section", "section": 99})
    assert "99" in bad
    missing = run_tool({"path": str(repo_tmp_path / "no.ts"), "mode": "index"})
    assert "ファイルが見つかりません" in missing or "not found" in missing.lower()
