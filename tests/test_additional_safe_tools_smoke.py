from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def test_calculator_smoke() -> None:
    from uagent.tools.calculator_tool import run_tool

    out = run_tool({"expression": "sqrt(144) + 1"})
    assert isinstance(out, str)
    assert out.startswith("[calculator]\n")
    assert "Result:" in out
    assert "13.0" in out


def test_db_query_select_and_pragma(repo_tmp_path: Path) -> None:
    from uagent.tools.db_query_tool import run_tool

    db = repo_tmp_path / "sample.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('alice')")
        conn.commit()
    finally:
        conn.close()

    out_select = run_tool({"db_path": str(db), "sql": "SELECT id, name FROM t"})
    rows = json.loads(out_select)
    assert isinstance(rows, list)
    assert rows[0]["name"] == "alice"

    out_pragma = run_tool({"db_path": str(db), "sql": "PRAGMA table_info(t)"})
    cols = json.loads(out_pragma)
    assert isinstance(cols, list)
    assert any(c.get("name") == "name" for c in cols)


def test_file_exists_metadata_smoke(repo_tmp_path: Path) -> None:
    from uagent.tools.file_exists_tool import run_tool

    p = repo_tmp_path / "meta.txt"
    p.write_text("x", encoding="utf-8")

    out = run_tool({"path": str(p)})
    assert isinstance(out, str)
    assert out.startswith("[file_exists]\n")
    assert "exists=True" in out
    assert "is_dir=False" in out
    assert "created_time=" in out
    assert "mtime=" in out
    assert "atime=" in out
    assert "ctime=" in out
    assert "owner=" in out
    assert "group=" in out


def test_get_env_mask_and_unmask(monkeypatch) -> None:
    from uagent.tools.get_env_tool import run_tool

    monkeypatch.setenv("UAGENT_TEST_ENV", "ABCDEFGH")

    out_masked = run_tool(
        {
            "name": "UAGENT_TEST_ENV",
            "missing_ok": False,
            "mask": True,
            "unmasked_chars": 2,
        }
    )
    assert out_masked == "UAGENT_TEST_ENV=AB***GH"

    out_plain = run_tool(
        {
            "name": "UAGENT_TEST_ENV",
            "missing_ok": False,
            "mask": False,
            "unmasked_chars": 2,
        }
    )
    assert out_plain == "UAGENT_TEST_ENV=ABCDEFGH"


def test_get_system_specs_smoke() -> None:
    from uagent.tools.system_specs_tools import run_tool

    out = run_tool({})
    obj = json.loads(out)
    assert isinstance(obj, dict)
    assert isinstance(obj.get("os"), dict)
    assert isinstance(obj["os"].get("sys_platform"), str)
    assert obj["os"]["sys_platform"]


def test_python_exec_smoke() -> None:
    from uagent.tools.python_exec_tool import run_tool

    out = run_tool({"code": "print(1 + 2)"})
    assert isinstance(out, str)
    assert "3" in out


def test_recalc_excel_dry_run_defaults(repo_tmp_path: Path) -> None:
    from uagent.tools.recalc_excel_tool import run_tool

    xlsx = repo_tmp_path / "book.xlsx"
    xlsx.write_bytes(b"dummy")

    out = run_tool(
        {
            "path": str(repo_tmp_path),
            "include_glob": "*.xlsx",
            "recursive": False,
            "dry_run": True,
            "visible": False,
            "max_files": 200,
        }
    )
    obj = json.loads(out)
    assert obj["count"] == 1
    assert obj["dry_run"] is True
    assert obj["backup"] is False
    assert len(obj["targets"]) == 1
