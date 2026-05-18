from __future__ import annotations

import os
from pathlib import Path


def test_date_calc_basic_text_output() -> None:
    from uagent.tools.date_calc_tool import run_tool

    out = run_tool(
        {
            "base_date": "2024-01-31",
            "years": 0,
            "months": 1,
            "weeks": 0,
            "days": 0,
            "country": "JP",
            "check_holiday": True,
        }
    )
    assert isinstance(out, str)
    assert out.startswith("[date_calc]\n")
    assert "Result Date:" in out
    assert "2024-02-29" in out


def test_file_hash_sha256(repo_tmp_path: Path) -> None:
    from uagent.tools.file_hash_tool import run_tool

    p = repo_tmp_path / "x.txt"
    p.write_text("abc", encoding="utf-8")

    out = run_tool(
        {
            "paths": [str(p)],
            "algo": "sha256",
            "chunk_size": 1024,
            "return": "json",
        }
    )
    assert isinstance(out, str)
    assert "sha256" in out.lower()


def test_get_workdir() -> None:
    from uagent.tools.get_workdir_tool import run_tool

    out = run_tool({})
    assert isinstance(out, str)
    assert os.getcwd().replace("\\", "/") in out.replace("\\", "/")


def test_get_current_time_text_output() -> None:
    from uagent.tools.get_current_time_tool import run_tool

    out = run_tool({})
    assert isinstance(out, str)
    assert out.startswith("[get_current_time]\n")
    assert "ISO8601" in out
    assert "Weekday" in out


def test_search_files_name_only(repo_tmp_path: Path) -> None:
    from uagent.tools.search_files_tool import run_tool

    (repo_tmp_path / "a.py").write_text("print('x')", encoding="utf-8")
    (repo_tmp_path / "b.txt").write_text("hello", encoding="utf-8")

    out = run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*.txt",
            "content_pattern": "",
            "case_sensitive": False,
            "max_results": 50,
            "fast_read_threshold_bytes": 8000000,
        }
    )
    assert isinstance(out, str)
    assert '"ok": false' not in out
    assert "b.txt" in out
