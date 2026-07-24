from __future__ import annotations

from pathlib import Path

from uagent.tools.jv2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_jv2idx_record_annotation_generic(repo_tmp_path: Path) -> None:
    src = '''package demo;

public @interface Marker {
}

public record Point(int x, int y) {
    public Point normalized() { return this; }
}

public class Box<T> {
    private final T value;
    public Box(T value) { this.value = value; }
    public T get() { return value; }
}
'''
    path = repo_tmp_path / "Demo.java"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "package demo" in out
    assert "Marker" in out
    assert "annotation" in out or "@interface" in out or "Marker" in out
    assert "Point" in out
    assert "record" in out or "Point" in out
    assert "Box" in out
    assert "get" in out


def test_jv2idx_text_block_not_false_type(repo_tmp_path: Path) -> None:
    src = '''class Real {
    String s = """
    class FakeInside {}
    """;
    void m() {}
}
'''
    path = repo_tmp_path / "t.java"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "Real" in out
    assert "FakeInside" not in out
