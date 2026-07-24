from __future__ import annotations

from pathlib import Path

from uagent.tools.dart2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_dart2idx_class_extension_mixin_factory_getset(repo_tmp_path: Path) -> None:
    src = """library demo;

import 'dart:core';

class Box {
  final int value;
  Box(this.value);
  factory Box.empty() => Box(0);
  int get data => value;
  set data(int v) {}
  Future<void> load() async {}
}

extension StringX on String {
  List<String> words() => split(' ');
}

mixin M {
  void m() {}
}

enum Color { red, green }

typedef IntList = List<int>;

void topLevel() {}
"""
    path = repo_tmp_path / "demo.dart"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "lib demo" in out or "demo" in out
    assert "Box" in out
    assert "Box()" in out or "constructor" in out.lower()
    assert "factory Box.empty" in out or "empty" in out
    assert "get data" in out
    assert "set data" in out
    assert "load()" in out
    assert "extension StringX on String" in out or "StringX" in out
    assert "words()" in out
    assert "M" in out
    assert "Color" in out
    assert "IntList" in out
    assert "topLevel()" in out


def test_dart2idx_comment_string_false_positive(repo_tmp_path: Path) -> None:
    src = """// class Fake {}
class Real {
  // void nope() {}
  void yes() {
    var s = "class NotAType";
  }
}
"""
    path = repo_tmp_path / "c.dart"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "Real" in out
    assert "yes" in out
    assert "Fake" not in out
    assert "NotAType" not in out


def test_dart2idx_section_and_missing(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "s.dart"
    _write(path, "void a() {}\n")
    out = run_tool({"path": str(path), "mode": "section", "section": 1})
    assert "a()" in out or "void a" in out
    bad = run_tool({"path": str(path), "mode": "section", "section": 99})
    assert "99" in bad
    missing = run_tool({"path": str(repo_tmp_path / "no.dart"), "mode": "index"})
    assert "ファイルが見つかりません" in missing or "not found" in missing.lower()
