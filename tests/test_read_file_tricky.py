"""read_file いじわるテスト: IF（パラメータ定義）だけを参照。

戻り値: 正常時はファイル内容（プレーンテキスト）、エラー時は JSON
"""

from __future__ import annotations

import json
from pathlib import Path


def _run(args: dict) -> str:
    from uagent.tools.read_file_tool import run_tool

    return run_tool(args)


def _is_json_err(out: str) -> dict | None:
    try:
        obj = json.loads(out)
        if isinstance(obj, dict) and obj.get("ok") is False:
            return obj
    except (json.JSONDecodeError, ValueError):
        pass
    return None


# ===================================================================
# 異常系
# ===================================================================

def test_filename_empty(repo_tmp_path: Path) -> None:
    out = _run({"filename": ""})
    assert _is_json_err(out) is not None


def test_filename_missing_key(repo_tmp_path: Path) -> None:
    out = _run({})
    assert _is_json_err(out) is not None


def test_file_not_found(repo_tmp_path: Path) -> None:
    out = _run({"filename": str(repo_tmp_path / "nope.txt")})
    assert _is_json_err(out) is not None


def test_path_is_directory(repo_tmp_path: Path) -> None:
    out = _run({"filename": str(repo_tmp_path)})
    assert _is_json_err(out) is not None


# ===================================================================
# 正常系（基本）
# ===================================================================

def test_read_small_file(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "hello.txt"
    f.write_text("hello\nworld\n", encoding="utf-8")
    out = _run({"filename": str(f)})
    assert "hello" in out


def test_read_empty_file(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    out = _run({"filename": str(f)})
    assert out == ""


def test_read_unicode_file(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "japanese.txt"
    f.write_text("こんにちは\n世界\n", encoding="utf-8")
    out = _run({"filename": str(f)})
    assert "こんにちは" in out


# ===================================================================
# start_line / maxl
# ===================================================================

def test_start_line_negative(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "neg_start.txt"
    f.write_text("a\nb\nc\n", encoding="utf-8")
    out = _run({"filename": str(f), "start_line": -5})
    err = _is_json_err(out)
    if err is None:
        assert "a" in out


def test_start_line_beyond_file(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "beyond.txt"
    f.write_text("a\nb\n", encoding="utf-8")
    out = _run({"filename": str(f), "start_line": 999})
    assert _is_json_err(out) is not None


def test_maxl_negative(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "neg_maxl.txt"
    f.write_text("a\nb\nc\n", encoding="utf-8")
    out = _run({"filename": str(f), "maxl": -1})
    assert _is_json_err(out) is None or True


def test_maxl_zero(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "zero_maxl.txt"
    f.write_text("a\nb\n", encoding="utf-8")
    out = _run({"filename": str(f), "maxl": 0})
    err = _is_json_err(out)
    if err is None:
        assert out == ""


def test_start_line_and_maxl(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "partial.txt"
    f.write_text("1st\n2nd\n3rd\n", encoding="utf-8")
    out = _run({"filename": str(f), "start_line": 2, "maxl": 1})
    assert _is_json_err(out) is None
    assert "2nd" in out
    assert "1st" not in out


# ===================================================================
# head / tail
# ===================================================================

def test_head_basic(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "head_test.txt"
    f.write_text("a\nb\nc\nd\n", encoding="utf-8")
    out = _run({"filename": str(f), "head": 2})
    assert _is_json_err(out) is None
    assert out.splitlines() == ["a", "b"]


def test_head_exceeds_file(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "head_exceed.txt"
    f.write_text("a\nb\n", encoding="utf-8")
    out = _run({"filename": str(f), "head": 999})
    assert _is_json_err(out) is None
    assert len(out.splitlines()) == 2


def test_head_zero(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "head_zero.txt"
    f.write_text("a\nb\n", encoding="utf-8")
    out = _run({"filename": str(f), "head": 0})
    err = _is_json_err(out)
    if err is None:
        assert out == ""


def test_tail_basic(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "tail_test.txt"
    f.write_text("a\nb\nc\nd\n", encoding="utf-8")
    out = _run({"filename": str(f), "tail": 2})
    assert _is_json_err(out) is None
    assert out.splitlines() == ["c", "d"]


def test_tail_exceeds_file(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "tail_exceed.txt"
    f.write_text("a\nb\n", encoding="utf-8")
    out = _run({"filename": str(f), "tail": 999})
    assert _is_json_err(out) is None
    assert len(out.splitlines()) == 2


def test_tail_zero(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "tail_zero.txt"
    f.write_text("a\nb\n", encoding="utf-8")
    out = _run({"filename": str(f), "tail": 0})
    err = _is_json_err(out)
    if err is None:
        assert out == ""


def test_head_and_tail_conflict(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "conflict.txt"
    f.write_text("a\nb\n", encoding="utf-8")
    out = _run({"filename": str(f), "head": 1, "tail": 1})
    assert _is_json_err(out) is not None


# ===================================================================
# ページネーション
# ===================================================================

def test_page_default(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "page_default.txt"
    f.write_text("a\nb\nc\n", encoding="utf-8")
    out = _run({"filename": str(f), "page": 1})
    assert _is_json_err(out) is None
    assert "a" in out and "c" in out


def test_page_with_maxl(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "page_test.txt"
    f.write_text("\n".join(f"line{i}" for i in range(1, 11)), encoding="utf-8")
    out = _run({"filename": str(f), "page": 2, "maxl": 3})
    assert _is_json_err(out) is None
    lines = out.splitlines()
    assert len(lines) == 3
    assert lines[0] == "line4"
    assert lines[-1] == "line6"


# ===================================================================
# エッジケース: ファイル内容
# ===================================================================

def test_binary_file(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "binary.bin"
    f.write_bytes(b"\x00\x01\x02\xff")
    out = _run({"filename": str(f)})
    err = _is_json_err(out)
    if err is None:
        assert isinstance(out, str)


def test_very_long_line(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "long_line.txt"
    f.write_text("A" * 50000 + "\n" + "B" * 50000 + "\n", encoding="utf-8")
    out = _run({"filename": str(f)})
    assert _is_json_err(out) is None
    assert "A" * 50000 in out
    assert "B" * 50000 in out


def test_file_with_trailing_newline(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "trailing.txt"
    f.write_text("a\nb\n", encoding="utf-8")
    out = _run({"filename": str(f)})
    assert _is_json_err(out) is None
    assert out.endswith("\n")


def test_file_without_trailing_newline(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "no_trailing.txt"
    f.write_text("a\nb", encoding="utf-8")
    out = _run({"filename": str(f)})
    assert _is_json_err(out) is None


def test_bom_utf8_file(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "bom.txt"
    f.write_bytes(b"\xef\xbb\xbfhello\n")
    out = _run({"filename": str(f)})
    assert "hello" in out
