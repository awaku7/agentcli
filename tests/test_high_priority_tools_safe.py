from __future__ import annotations

import json
from pathlib import Path


def _loads(s: str) -> dict:
    obj = json.loads(s)
    assert isinstance(obj, dict)
    return obj


def test_binary_edit_dry_run_write_keeps_file(repo_tmp_path: Path) -> None:
    from uagent.tools.binary_edit_tool import run_tool

    p = repo_tmp_path / "bin.dat"
    p.write_bytes(bytes.fromhex("00112233"))

    out = run_tool(
        {
            "path": str(p),
            "mode": "write",
            "dry_run": True,
            "offset": 1,
            "data_hex": "AA",
            "max_bytes": 200000000,
        }
    )
    obj = _loads(out)
    assert obj["ok"] is True
    assert obj["dry_run"] is True
    assert obj["would_write"] is True
    assert p.read_bytes() == bytes.fromhex("00112233")


def test_binary_edit_replace_rejects_size_change(repo_tmp_path: Path) -> None:
    from uagent.tools.binary_edit_tool import run_tool

    p = repo_tmp_path / "bin.dat"
    p.write_bytes(bytes.fromhex("AABBCCDD"))

    try:
        run_tool(
            {
                "path": str(p),
                "mode": "replace",
                "dry_run": True,
                "search_hex": "AA",
                "replace_hex": "AABB",
                "occurrence": 1,
                "max_bytes": 200000000,
            }
        )
    except SystemExit as e:
        assert "same length" in str(e)
        return

    raise AssertionError("expected SystemExit for size-changing replace")


def test_binary_edit_non_dry_run_with_monkeypatched_confirm(
    monkeypatch, repo_tmp_path: Path
) -> None:
    from uagent.tools.binary_edit_tool import run_tool

    p = repo_tmp_path / "bin.dat"
    p.write_bytes(bytes.fromhex("0011"))

    monkeypatch.setattr(
        "uagent.tools.binary_edit_tool._confirm_or_cancel", lambda _m: None
    )

    out = run_tool(
        {
            "path": str(p),
            "mode": "write",
            "dry_run": False,
            "offset": 0,
            "data_hex": "FF",
            "max_bytes": 200000000,
        }
    )
    obj = _loads(out)
    assert obj["ok"] is True
    assert obj["changed"] is True
    assert p.read_bytes() == bytes.fromhex("FF11")


def test_cmd_exec_blocks_destructive_command() -> None:
    from uagent.tools.cmd_exec_tool import run_tool

    out = run_tool({"command": "shutdown /s /t 0"})
    assert "[cmd_exec blocked]" in out


def test_cmd_exec_blocks_when_confirmation_fails(monkeypatch) -> None:
    from uagent.tools.cmd_exec_tool import run_tool
    from uagent.tools.safe_exec_ops import ExecDecision

    monkeypatch.setattr(
        "uagent.tools.cmd_exec_tool.decide_cmd_exec",
        lambda _c, require_confirm_for_shell_metachar=False: ExecDecision(
            allowed=True,
            reason="need confirm",
            require_confirm=True,
            confirm_message="confirm",
        ),
    )
    monkeypatch.setattr(
        "uagent.tools.cmd_exec_tool.confirm_if_needed",
        lambda _d: "user cancelled",
    )

    out = run_tool({"command": "echo hi"})
    assert "[cmd_exec blocked]" in out
    assert "cancelled" in out


def test_cmd_exec_json_blocks_destructive_command() -> None:
    from uagent.tools.cmd_exec_json_tool import run_tool

    out = run_tool({"command": "shutdown /s /t 0", "cwd": None})
    obj = _loads(out)
    assert obj["ok"] is False
    assert "error" in obj


def test_cmd_exec_json_rejects_invalid_cwd_type() -> None:
    from uagent.tools.cmd_exec_json_tool import run_tool

    try:
        run_tool({"command": "echo hi", "cwd": 123})
    except ValueError as e:
        assert "cwd must be a string or null" in str(e)
        return

    raise AssertionError("expected ValueError for non-string cwd")


def test_delete_file_glob_execute_confirmed(monkeypatch, repo_tmp_path: Path) -> None:
    from uagent.tools.delete_file_tool import run_tool

    f1 = repo_tmp_path / "a.tmp"
    f2 = repo_tmp_path / "b.tmp"
    f1.write_text("x", encoding="utf-8")
    f2.write_text("y", encoding="utf-8")

    monkeypatch.setattr("uagent.tools.delete_file_tool._human_confirm", lambda _m: True)

    out = run_tool(
        {
            "filename": str(repo_tmp_path / "*.tmp"),
            "missing_ok": False,
            "dry_run": False,
            "allow_dir": True,
        }
    )
    obj = _loads(out)
    assert obj["ok"] is True
    assert obj["deleted"] is True
    assert obj["count"] == 2
    assert not f1.exists()
    assert not f2.exists()


def test_delete_file_glob_cancelled_without_confirm(
    monkeypatch, repo_tmp_path: Path
) -> None:
    from uagent.tools.delete_file_tool import run_tool

    f1 = repo_tmp_path / "a.tmp"
    f1.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        "uagent.tools.delete_file_tool._human_confirm", lambda _m: False
    )

    out = run_tool(
        {
            "filename": str(repo_tmp_path / "*.tmp"),
            "missing_ok": False,
            "dry_run": False,
            "allow_dir": True,
        }
    )
    obj = _loads(out)
    assert obj["ok"] is False
    assert obj["cancelled"] is True
    assert f1.exists()


def test_git_ops_rejects_force_push_without_allow_danger() -> None:
    from uagent.tools.git_ops_tool import run_tool

    out = run_tool({"command": "push", "args": ["--force"], "allow_danger": False})
    obj = _loads(out)
    assert obj["ok"] is False
    assert "allow_danger" in obj["stderr"]


def test_git_ops_rejects_shell_metachar_in_args() -> None:
    from uagent.tools.git_ops_tool import run_tool

    out = run_tool(
        {"command": "status", "args": ["--short&&whoami"], "allow_danger": False}
    )
    obj = _loads(out)
    assert obj["ok"] is False
    assert (
        "metacharacter" in obj["stderr"].lower() or "dangerous" in obj["stderr"].lower()
    )


def test_rename_path_wraps_errors_from_safe_layer(monkeypatch) -> None:
    from uagent.tools.rename_path_tool import run_tool

    def _boom(*, src: str, dst: str, overwrite: bool, mkdirs: bool) -> None:
        raise FileExistsError("already exists")

    monkeypatch.setattr("uagent.tools.rename_path_tool.safe_rename_path", _boom)

    out = run_tool(
        {"src": "a.txt", "dst": "b.txt", "overwrite": False, "mkdirs": False}
    )
    assert out.startswith("[rename_path error]")
    assert "already exists" in out
