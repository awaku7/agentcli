"""replace_in_file いじわるテスト: IF（パラメータ定義）だけを参照。

既存テストと重複しないエッジケースをパラメータ定義から抽出し、
実装は見ずにテストする。
"""

from __future__ import annotations

import json
from pathlib import Path


def _run(args: dict) -> dict:
    from uagent.tools.replace_in_file_tool import run_tool

    return json.loads(run_tool(args))


# ===================================================================
# 異常系: パラメータの境界・不正値
# ===================================================================


def test_path_empty(repo_tmp_path: Path) -> None:
    """path が空文字列 -> エラーになるはず."""
    r = _run({"path": "", "replacement": "x", "preview": False})
    assert r["ok"] is False


def test_path_nonexistent(repo_tmp_path: Path) -> None:
    """存在しないファイルへの replace -> エラー."""
    r = _run(
        {"path": str(repo_tmp_path / "nope.txt"), "replacement": "x", "preview": False}
    )
    assert r["ok"] is False


def test_path_is_directory(repo_tmp_path: Path) -> None:
    """path がディレクトリ -> エラー."""
    r = _run({"path": str(repo_tmp_path), "replacement": "x", "preview": False})
    assert r["ok"] is False


def test_negative_occurrence(repo_tmp_path: Path) -> None:
    """occurrence が負の値. 0 (all) として扱われる？エラー？"""
    f = repo_tmp_path / "neg_occ.txt"
    f.write_text("a\na\na\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "pattern": "a",
            "replacement": "b",
            "occurrence": -1,
            "preview": False,
        }
    )
    # クラッシュせず ok/ng が返ればよい
    assert "ok" in r


def test_occurrence_exceeds_matches(repo_tmp_path: Path) -> None:
    """occurrence がマッチ総数より大きい -> 0件マッチ？"""
    f = repo_tmp_path / "occ_exceed.txt"
    f.write_text("a\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "pattern": "a",
            "replacement": "b",
            "occurrence": 999,
            "preview": False,
        }
    )
    assert "ok" in r
    # マッチしないのでファイルは変わらないはず
    assert "match_count" in r


def test_negative_line_no(repo_tmp_path: Path) -> None:
    """insert_at_line で line_no が負の値."""
    f = repo_tmp_path / "neg_line.txt"
    f.write_text("a\nb\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "action": "insert_at_line",
            "line_no": -1,
            "replacement": "x\n",
            "preview": False,
        }
    )
    assert "ok" in r


def test_line_no_exceeds_file(repo_tmp_path: Path) -> None:
    """insert_at_line で line_no がファイル行数より大きい -> 末尾？エラー？"""
    f = repo_tmp_path / "line_exceed.txt"
    f.write_text("a\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "action": "insert_at_line",
            "line_no": 9999,
            "replacement": "x\n",
            "preview": False,
        }
    )
    assert "ok" in r


def test_empty_pattern_literal(repo_tmp_path: Path) -> None:
    """mode=literal で pattern が空文字 -> 何もマッチしない？"""
    f = repo_tmp_path / "empty_pat.txt"
    f.write_text("hello\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "pattern": "",
            "replacement": "x",
            "mode": "literal",
            "preview": False,
        }
    )
    assert "ok" in r


def test_invalid_regex(repo_tmp_path: Path) -> None:
    """mode=regex で不正な正規表現 -> エラー."""
    f = repo_tmp_path / "bad_regex.txt"
    f.write_text("hello\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "pattern": "***",
            "replacement": "x",
            "mode": "regex",
            "preview": False,
        }
    )
    assert r["ok"] is False


def test_unclosed_group_regex(repo_tmp_path: Path) -> None:
    """mode=regex でグループが閉じていない -> エラー."""
    f = repo_tmp_path / "bad_group.txt"
    f.write_text("hello\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "pattern": "(?P<name",
            "replacement": "x",
            "mode": "regex",
            "preview": False,
        }
    )
    assert r["ok"] is False


def test_invalid_encoding(repo_tmp_path: Path) -> None:
    """encoding に存在しない文字コード -> エラー."""
    f = repo_tmp_path / "bad_enc.txt"
    f.write_text("hello\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "replacement": "x",
            "encoding": "nonexistent-encoding",
            "preview": False,
        }
    )
    assert r["ok"] is False


def test_empty_replacement(repo_tmp_path: Path) -> None:
    """replacement が空文字 -> 削除として動作？"""
    f = repo_tmp_path / "empty_repl.txt"
    f.write_text("delete_me\nkeep\n", encoding="utf-8")
    r = _run(
        {"path": str(f), "pattern": "delete_me", "replacement": "", "preview": False}
    )
    assert r["ok"] is True
    content = f.read_text(encoding="utf-8")
    assert "delete_me" not in content
    assert "keep" in content


# ===================================================================
# アクション別エッジケース
# ===================================================================


def test_append_to_nonexistent_file(repo_tmp_path: Path) -> None:
    """存在しないファイルに append -> エラー？新規作成？"""
    f = repo_tmp_path / "new_append.txt"
    r = _run(
        {"path": str(f), "action": "append", "replacement": "new\n", "preview": False}
    )
    # ファイルが存在しないのでエラーになるはず
    assert "ok" in r


def test_insert_before_empty_anchor(repo_tmp_path: Path) -> None:
    """insert_before で anchor_before が空 -> エラー？"""
    f = repo_tmp_path / "empty_anchor.txt"
    f.write_text("hello\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "action": "insert_before",
            "anchor_before": "",
            "replacement": "x\n",
            "preview": False,
        }
    )
    assert "ok" in r


def test_replace_between_no_anchor_after(repo_tmp_path: Path) -> None:
    """replace_between で anchor_after 未指定."""
    f = repo_tmp_path / "no_after.txt"
    f.write_text("start\nmiddle\nend\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "action": "replace_between",
            "anchor_before": "start",
            "replacement": "replaced\n",
            "preview": False,
        }
    )
    assert "ok" in r


def test_insert_at_line_zero(repo_tmp_path: Path) -> None:
    """insert_at_line で line_no=0 -> 先頭行として扱われる？"""
    f = repo_tmp_path / "line0.txt"
    f.write_text("a\nb\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "action": "insert_at_line",
            "line_no": 0,
            "replacement": "header\n",
            "preview": False,
        }
    )
    assert r["ok"] is True
    content = f.read_text(encoding="utf-8")
    assert content.startswith("header\n")


# ===================================================================
# オプションの組合せ
# ===================================================================


def test_return_hashes(repo_tmp_path: Path) -> None:
    """return_hashes=true で sha256 が返る."""
    f = repo_tmp_path / "hash_test.txt"
    f.write_text("original\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "pattern": "original",
            "replacement": "modified",
            "return_hashes": True,
            "preview": False,
        }
    )
    assert r["ok"] is True
    assert "sha256_before" in r
    assert "sha256_after" in r


def test_preview_not_blocked_by_confirm_over(repo_tmp_path: Path) -> None:
    """preview=true なら confirm_over に関係なくブロックされない."""
    f = repo_tmp_path / "preview_no_block.txt"
    content = "\n".join(f"line{i}" for i in range(100))
    f.write_text(content, encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "pattern": "line",
            "replacement": "ROW",
            "preview": True,
            "confirm_over": 1,
        }
    )
    assert r["ok"] is True
    assert r.get("preview") is not False  # preview mode


def test_expand_newline_tokens_false(repo_tmp_path: Path) -> None:
    """expand_newline_tokens=false で \\n がリテラルマッチ."""
    f = repo_tmp_path / "no_expand.txt"
    f.write_text("hello\\nworld\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "pattern": "\\n",
            "replacement": " ",
            "expand_newline_tokens": False,
            "preview": False,
        }
    )
    assert r["ok"] is True
    content = f.read_text(encoding="utf-8")
    assert "hello world" in content


def test_regex_with_line_anchors(repo_tmp_path: Path) -> None:
    """mode=regex で ^ と $ アンカー."""
    f = repo_tmp_path / "anchors.txt"
    f.write_text("aaa\nbbb\naaa\n", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "pattern": "^aaa$",
            "replacement": "AAA",
            "mode": "regex",
            "occurrence": 0,
            "preview": False,
        }
    )
    assert r["ok"] is True
    lines = f.read_text(encoding="utf-8").splitlines()
    assert lines == ["AAA", "bbb", "AAA"]


def test_glob_replace_all(repo_tmp_path: Path) -> None:
    """replace_all_in_files で複数ファイルを一括置換."""
    (repo_tmp_path / "sub").mkdir()
    f1 = repo_tmp_path / "sub" / "a.txt"
    f2 = repo_tmp_path / "sub" / "b.txt"
    f1.write_text("x\n", encoding="utf-8")
    f2.write_text("x\n", encoding="utf-8")
    r = _run(
        {
            "path": str(repo_tmp_path / "sub"),
            "pattern": "x",
            "replacement": "y",
            "action": "replace_all_in_files",
            "glob": "*.txt",
            "preview": False,
        }
    )
    assert r["ok"] is True
    assert f1.read_text(encoding="utf-8") == "y\n"
    assert f2.read_text(encoding="utf-8") == "y\n"


# ===================================================================
# ファイル内容のエッジケース
# ===================================================================


def test_empty_file_replace(repo_tmp_path: Path) -> None:
    """空ファイルに replace -> マッチ0."""
    f = repo_tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    r = _run({"path": str(f), "pattern": "x", "replacement": "y", "preview": False})
    assert r["ok"] is True
    assert r.get("match_count", 0) == 0


def test_empty_file_insert_at_line(repo_tmp_path: Path) -> None:
    """空ファイルに insert_at_line -> 書き込まれる？"""
    f = repo_tmp_path / "empty_ins.txt"
    f.write_text("", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "action": "insert_at_line",
            "line_no": 1,
            "replacement": "new\n",
            "preview": False,
        }
    )
    assert r["ok"] is True
    assert f.read_text(encoding="utf-8") == "new\n"


def test_empty_file_append(repo_tmp_path: Path) -> None:
    """空ファイルに append -> 追記."""
    f = repo_tmp_path / "empty_app.txt"
    f.write_text("", encoding="utf-8")
    r = _run(
        {
            "path": str(f),
            "action": "append",
            "replacement": "appended\n",
            "preview": False,
        }
    )
    assert r["ok"] is True
    assert f.read_text(encoding="utf-8") == "appended\n"
