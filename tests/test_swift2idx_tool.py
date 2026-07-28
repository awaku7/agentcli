from __future__ import annotations

from pathlib import Path

from uagent.tools.swift2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_swift2idx_actor_async_protocol_extension(repo_tmp_path: Path) -> None:
    src = """import Foundation

actor Counter {
    var value = 0
    func inc() { value += 1 }
}

protocol P {
    func work() async
}

extension P {
    func work() async {}
}

struct S {
    subscript(i: Int) -> Int { i }
    deinit {}
}
"""
    # note: deinit on struct is invalid swift but indexer should still see patterns on class-like
    path = repo_tmp_path / "Demo.swift"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "actor Counter" in out or "Counter" in out
    assert "protocol P" in out or "P" in out
    assert "extension P" in out or "extension" in out
    assert "inc" in out
    assert "work" in out
    assert "subscript" in out


def test_swift2idx_async_throws_func(repo_tmp_path: Path) -> None:
    src = """class C {
    func load() async throws -> String { "x" }
}
"""
    path = repo_tmp_path / "a.swift"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "C" in out
    assert "load" in out
