from __future__ import annotations

from pathlib import Path

from uagent.tools.cs2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_cs2idx_file_scoped_namespace_record_operator(repo_tmp_path: Path) -> None:
    src = """namespace Demo.App;

[AttributeUsage(AttributeTargets.Class)]
public partial record Person(string Name)
{
    public static Person operator +(Person a, Person b) => a;
    public async Task RunAsync() { await Task.CompletedTask; }
}

public class Calc
{
    public int this[int i] => i;
}
"""
    path = repo_tmp_path / "Demo.cs"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "namespace Demo.App" in out
    assert "file-scoped" in out
    assert "Person" in out
    assert "operator" in out
    assert "RunAsync" in out
    assert "Calc" in out


def test_cs2idx_comment_string_false_positive(repo_tmp_path: Path) -> None:
    src = """namespace N {
// class Fake {}
class Real {
    void M() {
        var s = "class NotAType";
    }
}
}
"""
    path = repo_tmp_path / "c.cs"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "Real" in out
    assert "Fake" not in out
    assert "NotAType" not in out
