from __future__ import annotations

from pathlib import Path

from uagent.tools.rs2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_rs2idx_mod_struct_trait_impl_async_macro(repo_tmp_path: Path) -> None:
    src = """mod inner {
    pub fn nested() {}
}

pub struct Point {
    pub x: i32,
}

pub trait Drawable {
    fn draw(&self);
}

impl Drawable for Point {
    fn draw(&self) {}
}

pub async fn run() {}

macro_rules! say {
    () => {};
}

const MAX: i32 = 10;
"""
    path = repo_tmp_path / "lib.rs"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "mod inner" in out or "inner" in out
    assert "Point" in out
    assert "Drawable" in out
    assert "impl" in out.lower()
    assert "draw()" in out
    assert "run()" in out
    assert "say" in out or "macro" in out.lower()
    assert "MAX" in out


def test_rs2idx_comment_string_false_positive(repo_tmp_path: Path) -> None:
    src = """// fn fake() {}
fn real() {
    let s = "fn not_real()";
    let _ = s;
}
"""
    path = repo_tmp_path / "c.rs"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "real()" in out
    assert "fake" not in out
    assert "not_real" not in out


def test_rs2idx_section_and_missing(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "s.rs"
    _write(path, "fn a() {}\n")
    out = run_tool({"path": str(path), "mode": "section", "section": 1})
    assert "fn a" in out or "a()" in out
    bad = run_tool({"path": str(path), "mode": "section", "section": 99})
    assert "99" in bad
    missing = run_tool({"path": str(repo_tmp_path / "no.rs"), "mode": "index"})
    assert "ファイルが見つかりません" in missing or "not found" in missing.lower()
