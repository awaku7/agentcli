from __future__ import annotations

from pathlib import Path

from uagent.tools.go2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_go2idx_struct_interface_receiver_generic(repo_tmp_path: Path) -> None:
    src = '''package demo

type ID = string

type Box[T any] struct {
        Value T
}

type Reader interface {
        Read([]byte) (int, error)
}

func NewBox[T any](v T) *Box[T] {
        return &Box[T]{Value: v}
}

func (b *Box[T]) Get() T {
        return b.Value
}

func (r Reader) unused() {}
'''
    path = repo_tmp_path / "demo.go"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "package demo" in out
    assert "type Box struct" in out or "type Box" in out
    assert "type Reader interface" in out or "Reader" in out
    assert "type ID" in out
    assert "func NewBox" in out
    assert "Get()" in out
    assert "*Box" in out or "Box" in out


def test_go2idx_ignores_comment_and_string_false_positives(repo_tmp_path: Path) -> None:
    src = '''package p

// func Fake() {}
func Real() {
        s := "func NotReal()"
        _ = s
}
'''
    path = repo_tmp_path / "c.go"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "Real" in out
    assert "Fake" not in out
    assert "NotReal" not in out


def test_go2idx_section_range(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "s.go"
    _write(path, "package p\n\nfunc A() {}\n")
    out = run_tool({"path": str(path), "mode": "section", "section": 99})
    assert "99" in out
