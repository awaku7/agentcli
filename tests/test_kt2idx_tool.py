from __future__ import annotations

from pathlib import Path

from uagent.tools.kt2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_kt2idx_extension_data_class_companion(repo_tmp_path: Path) -> None:
    src = """package demo

data class User(val id: Int, val name: String) {
    companion object Factory {
        fun create(id: Int) = User(id, "x")
    }
}

fun String.words(): List<String> = this.split(" ")

suspend fun load(): String = "ok"

class Repo {
    fun fetch() {}
}
"""
    path = repo_tmp_path / "Demo.kt"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "data class User" in out or "User" in out
    assert "companion" in out
    assert "words" in out
    assert (
        "String.words" in out or "extension" in out.lower() or "fun String.words" in out
    )
    assert "load" in out
    assert "Repo" in out
    assert "fetch" in out


def test_kt2idx_comment_false_positive(repo_tmp_path: Path) -> None:
    src = """// class Fake
class Real {
    // fun nope()
    fun yes() {}
}
"""
    path = repo_tmp_path / "c.kt"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "Real" in out
    assert "yes" in out
    assert "Fake" not in out
