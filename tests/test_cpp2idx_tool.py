from __future__ import annotations

from pathlib import Path

from uagent.tools.cpp2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_cpp2idx_namespace_class_template_free_func(repo_tmp_path: Path) -> None:
    src = """namespace ns {
class Widget {
public:
  Widget();
  ~Widget();
  void draw(int x);
  int value;
};

template<typename T>
T max_of(T a, T b) {
  return a > b ? a : b;
}

enum Color { Red, Green };

using Id = int;
}  // namespace ns

struct Point { int x; int y; };

int free_func(int a) { return a; }
"""
    path = repo_tmp_path / "sample.cpp"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "namespace ns" in out
    assert "type Widget" in out
    assert "draw()" in out
    assert "max_of()" in out or "template max_of" in out
    assert "enum Color" in out
    assert "type Point" in out
    assert "free_func()" in out
    # same-line struct must not swallow following free function as member
    free_lines = [
        line
        for line in out.splitlines()
        if "free_func()" in line and line.lstrip()[:1].isdigit()
    ]
    assert free_lines, out
    for line in free_lines:
        # top-level numbering has two leading spaces, members have more
        assert line.startswith("  ") and not line.startswith("      "), line


def test_cpp2idx_multiline_class_and_section(repo_tmp_path: Path) -> None:
    src = """class Foo
{
public:
  void bar();
};

int baz() {
  return 1;
}
"""
    path = repo_tmp_path / "multi.cpp"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "type Foo" in out
    assert "bar()" in out
    assert "baz()" in out
    baz_lines = [
        line
        for line in out.splitlines()
        if "baz()" in line and line.lstrip()[:1].isdigit()
    ]
    assert baz_lines, out
    for line in baz_lines:
        assert line.startswith("  ") and not line.startswith("      "), line

    # section for free func should be non-empty
    n = int(baz_lines[0].strip().split(".")[0])
    sec_baz = run_tool({"path": str(path), "mode": "section", "section": n})
    assert sec_baz is not None
    assert "baz" in sec_baz


def test_cpp2idx_missing_file(repo_tmp_path: Path) -> None:
    missing = repo_tmp_path / "no_such.cpp"
    out = run_tool({"path": str(missing), "mode": "index"})
    assert (
        "ファイルが見つかりません" in out
        or "not found" in out.lower()
        or "No such" in out
    )
