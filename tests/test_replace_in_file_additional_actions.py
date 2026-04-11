from __future__ import annotations

import json
from pathlib import Path

import pytest

from uagent.tools.replace_in_file_tool import run_tool as replace_in_file


def _load(out: str) -> dict:
    obj = json.loads(out)
    assert isinstance(obj, dict)
    assert obj.get("ok") is True, obj
    return obj


@pytest.mark.parametrize("action", ["append", "insert_at_end"], ids=["append", "insert_at_end"])
def test_replace_in_file_append_aliases(action: str, repo_tmp_path: Path) -> None:
    p = repo_tmp_path / f"{action}.txt"
    p.write_text("base\n", encoding="utf-8", newline="\n")

    out = replace_in_file(
        {
            "path": str(p),
            "action": action,
            "replacement": "tail\n",
            "preview": False,
            "confirm_over": 999,
        }
    )
    obj = _load(out)
    assert obj["action"] == "insert_at_end"
    assert obj["changed"] is True
    assert p.read_text(encoding="utf-8") == "base\ntail\n"


@pytest.mark.parametrize("action,expected", [("insert_before", "one\nX\ntwo\n"), ("insert_after", "one\ntwo\nX\n")], ids=["before", "after"])
def test_replace_in_file_insert_before_after(action: str, expected: str, repo_tmp_path: Path) -> None:
    p = repo_tmp_path / f"{action}.txt"
    p.write_text("one\ntwo\n", encoding="utf-8", newline="\n")

    out = replace_in_file(
        {
            "path": str(p),
            "action": action,
            "mode": "literal",
            "pattern": "two",
            "replacement": "X\n",
            "preview": False,
            "confirm_over": 999,
        }
    )
    obj = _load(out)
    assert obj["action"] == action
    assert obj["match_count"] == 1
    assert obj["replaced_count"] == 1
    assert p.read_text(encoding="utf-8") == expected


def test_replace_in_file_insert_at_line(repo_tmp_path: Path) -> None:
    p = repo_tmp_path / "insert_at_line.txt"
    p.write_text("a\nb\nc\n", encoding="utf-8", newline="\n")

    out = replace_in_file(
        {
            "path": str(p),
            "action": "insert_at_line",
            "line_no": 2,
            "replacement": "X\n",
            "preview": False,
            "confirm_over": 999,
        }
    )
    obj = _load(out)
    assert obj["action"] == "insert_at_line"
    assert obj["line_no"] == 2
    assert obj["changed"] is True
    assert p.read_text(encoding="utf-8") == "a\nX\nb\nc\n"


def test_replace_in_file_replace_all_in_files(repo_tmp_path: Path) -> None:
    root = repo_tmp_path / "bulk"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("cat\n", encoding="utf-8", newline="\n")
    (root / "sub" / "b.txt").write_text("cat\n", encoding="utf-8", newline="\n")
    (root / "skip.bin").write_bytes(b"cat\x00dog")

    out = replace_in_file(
        {
            "path": str(root),
            "action": "replace_all_in_files",
            "name_pattern": "*.txt",
            "recursive": True,
            "mode": "literal",
            "pattern": "cat",
            "replacement": "dog",
            "preview": False,
            "confirm_over": 999,
        }
    )
    obj = _load(out)
    assert obj["action"] == "replace_all_in_files"
    assert obj["scanned_files"] == 2
    assert obj["changed_files"] == 2
    assert obj["written_files"] == 2
    assert obj["match_count"] == 2
    assert obj["replaced_count"] == 2
    assert (root / "a.txt").read_text(encoding="utf-8") == "dog\n"
    assert (root / "sub" / "b.txt").read_text(encoding="utf-8") == "dog\n"
    assert (root / "skip.bin").read_bytes() == b"cat\x00dog"
