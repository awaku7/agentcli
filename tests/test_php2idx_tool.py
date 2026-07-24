from __future__ import annotations

from pathlib import Path

from uagent.tools.php2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_php2idx_namespace_class_trait_enum_attr(repo_tmp_path: Path) -> None:
    src = r"""<?php
namespace App\Demo;

#[Attribute]
class User {
    public const ROLE = 'admin';
    public string $name;
    public function __construct(string $name) {
        $this->name = $name;
    }
    public function greet(): string {
        return "hi";
    }
}

interface I { public function x(): void; }
trait T {
    public function t(): void {}
}
enum Status: string { case Ok = 'ok'; }

function helper(): void {}
"""
    path = repo_tmp_path / "User.php"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert r"namespace App\Demo" in out or r"App\Demo" in out
    assert "class User" in out
    assert "ROLE" in out
    assert "$name" in out
    assert "__construct()" in out
    assert "greet()" in out
    assert "interface I" in out
    assert "trait T" in out
    assert "enum Status" in out
    assert "helper()" in out


def test_php2idx_comment_string_false_positive(repo_tmp_path: Path) -> None:
    src = """<?php
// class Fake {}
class Real {
    // function nope() {}
    public function yes() {
        $s = "function NotReal()";
    }
}
"""
    path = repo_tmp_path / "c.php"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "Real" in out
    assert "yes" in out
    assert "Fake" not in out
    assert "NotReal" not in out


def test_php2idx_section_and_missing(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "s.php"
    _write(path, "<?php\nfunction a() {}\n")
    out = run_tool({"path": str(path), "mode": "section", "section": 1})
    assert "function a" in out or "a()" in out
    bad = run_tool({"path": str(path), "mode": "section", "section": 99})
    assert "99" in bad
    missing = run_tool({"path": str(repo_tmp_path / "no.php"), "mode": "index"})
    assert "ファイルが見つかりません" in missing or "not found" in missing.lower()
