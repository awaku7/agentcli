"""Test: diff_files + apply_patch workflow as used by LLM agents.

Covers the end-to-end flow where an LLM would:
  1. Read a file, propose changes
  2. Generate a unified diff (simulated here via diff_files tool)
  3. Apply the patch via apply_patch tool

All tests use repo_tmp_path fixture (under tests/_tmp/) and call
run_tool() directly with dict arguments, matching the tool-calling
convention the LLM uses.
"""

from __future__ import annotations

import json
from pathlib import Path


def _run_diff(args: dict) -> dict:
    from uagent.tools.diff_files_tool import run_tool

    return json.loads(run_tool(args))


def _run_patch(args: dict) -> dict:
    from uagent.tools.apply_patch_tool import run_tool

    return json.loads(run_tool(args))


def _normalize_patch_target(patch_text: str, target: str) -> str:
    lines = patch_text.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        if line.startswith("+++ "):
            out.append(f"+++ b/{target}\n")
        elif line.startswith("--- "):
            out.append(f"--- a/{target}\n")
        else:
            out.append(line)
    return "".join(out)


# ---------------------------------------------------------------------------
# 1. Basic flow: diff -> patch round-trip
# ---------------------------------------------------------------------------
def test_diff_then_patch_roundtrip(repo_tmp_path: Path) -> None:
    original = repo_tmp_path / "hello.txt"
    modified = repo_tmp_path / "hello_modified.txt"
    original.write_text("hello\nworld\n", encoding="utf-8")
    modified.write_text("hello\nearth\n", encoding="utf-8")

    diff_result = _run_diff(
        {
            "path1": str(original),
            "path2": str(modified),
            "mode": "unified",
        }
    )
    assert diff_result["ok"] is True
    patch_text: str = diff_result["diff"]
    assert "+earth" in patch_text
    assert "-world" in patch_text

    fixed_patch = _normalize_patch_target(patch_text, str(original))
    patch_result = _run_patch({"patch_text": fixed_patch, "dry_run": False})
    assert patch_result["ok"] is True, patch_result.get("summary", "")
    assert patch_result["total_applied"] == 1
    assert original.read_text(encoding="utf-8") == "hello\nearth\n"


# ---------------------------------------------------------------------------
# 2. Patch with multiple hunks
# ---------------------------------------------------------------------------
def test_patch_multi_hunk(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "multi.txt"
    f.write_text("line1\nline2\nline3\nline4\nline5\n", encoding="utf-8")
    patch = (
        f"--- a/{f}\n+++ b/{f}\n"
        "@@ -1,3 +1,3 @@\n"
        " line1\n-line2\n+line2_modified\n line3\n"
        "@@ -4,3 +4,3 @@\n"
        " line4\n-line5\n+line5_modified\n"
    )
    result = _run_patch({"patch_text": patch, "dry_run": False})
    assert result["ok"] is True
    assert result["total_applied"] == 2
    content = f.read_text(encoding="utf-8")
    assert "line2_modified" in content
    assert "line5_modified" in content


# ---------------------------------------------------------------------------
# 3. Dry-run does not modify file
# ---------------------------------------------------------------------------
def test_patch_dry_run_preserves_file(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "dry.txt"
    f.write_text("before\n", encoding="utf-8")
    patch = "--- a/{f}\n+++ b/{f}\n@@ -1 +1 @@\n-before\n+after\n".format(f=f)
    result = _run_patch({"patch_text": patch, "dry_run": True})
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert f.read_text(encoding="utf-8") == "before\n"


# ---------------------------------------------------------------------------
# 4. LLM-simulated patch: add lines and remove lines
# ---------------------------------------------------------------------------
def test_llm_style_patch_add_remove(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "notes.txt"
    f.write_text("apple\nbanana\ncherry\n", encoding="utf-8")
    patch = (
        "--- a/{f}\n+++ b/{f}\n"
        "@@ -1,3 +1,4 @@\n apple\n-banana\n cherry\n+date\n+elderberry\n"
    ).format(f=f)
    result = _run_patch({"patch_text": patch, "dry_run": False})
    assert result["ok"] is True
    assert result["total_added"] == 2
    assert result["total_removed"] == 1
    content = f.read_text(encoding="utf-8")
    assert "date" in content and "banana" not in content


# ---------------------------------------------------------------------------
# 5. Multi-file patch
# ---------------------------------------------------------------------------
def test_patch_multiple_files(repo_tmp_path: Path) -> None:
    f1 = repo_tmp_path / "a.txt"
    f2 = repo_tmp_path / "b.txt"
    f1.write_text("aaa\n", encoding="utf-8")
    f2.write_text("bbb\n", encoding="utf-8")
    patch = (
        "--- a/{f1}\n+++ b/{f1}\n@@ -1 +1 @@\n-aaa\n+aaa_modified\n"
        "--- a/{f2}\n+++ b/{f2}\n@@ -1 +1 @@\n-bbb\n+bbb_modified\n"
    ).format(f1=f1, f2=f2)
    result = _run_patch({"patch_text": patch, "dry_run": False})
    assert result["ok"] is True
    assert len(result["files"]) == 2
    assert f1.read_text(encoding="utf-8") == "aaa_modified\n"
    assert f2.read_text(encoding="utf-8") == "bbb_modified\n"


# ---------------------------------------------------------------------------
# 6. Append new line at end of file
# ---------------------------------------------------------------------------
def test_patch_append_to_end(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "append.txt"
    f.write_text("existing\n", encoding="utf-8")
    patch = ("--- a/{f}\n+++ b/{f}\n@@ -1 +1,2 @@\n existing\n+new_line\n").format(f=f)
    result = _run_patch({"patch_text": patch, "dry_run": False})
    assert result["ok"] is True
    assert f.read_text(encoding="utf-8") == "existing\nnew_line\n"


# ---------------------------------------------------------------------------
# 7. Revert mode
# ---------------------------------------------------------------------------
def test_patch_revert(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "revert.txt"
    f.write_text("original\n", encoding="utf-8")
    patch = "--- a/{f}\n+++ b/{f}\n@@ -1 +1 @@\n-original\n+modified\n".format(f=f)
    _run_patch({"patch_text": patch, "dry_run": False})
    assert f.read_text(encoding="utf-8") == "modified\n"
    result = _run_patch({"patch_text": patch, "dry_run": False, "revert": True})
    assert result["ok"] is True
    assert f.read_text(encoding="utf-8") == "original\n"


# ---------------------------------------------------------------------------
# 8. diff_files json_diff mode -> apply_patch
# ---------------------------------------------------------------------------
def test_diff_json_mode_then_patch(repo_tmp_path: Path) -> None:
    original = repo_tmp_path / "data.json"
    modified = repo_tmp_path / "data_modified.json"
    original.write_text('{"a": 1, "b": 2}\n', encoding="utf-8")
    modified.write_text('{"a": 1, "b": 3}\n', encoding="utf-8")

    diff_result = _run_diff(
        {
            "path1": str(original),
            "path2": str(modified),
            "mode": "json_diff",
        }
    )
    assert diff_result["ok"] is True
    assert len(diff_result["hunks"]) >= 1

    diff_result2 = _run_diff(
        {
            "path1": str(original),
            "path2": str(modified),
            "mode": "unified",
        }
    )
    fixed_patch = _normalize_patch_target(diff_result2["diff"], str(original))
    patch_result = _run_patch({"patch_text": fixed_patch, "dry_run": False})
    assert patch_result["ok"] is True
    assert original.read_text(encoding="utf-8") == '{"a": 1, "b": 3}\n'


# ---------------------------------------------------------------------------
# 9. Identical files
# ---------------------------------------------------------------------------
def test_diff_identical_files_empty_patch(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "same.txt"
    f2 = repo_tmp_path / "same_copy.txt"
    f.write_text("content\n", encoding="utf-8")
    f2.write_text("content\n", encoding="utf-8")
    diff_result = _run_diff({"path1": str(f), "path2": str(f2)})
    assert diff_result["ok"] is True
    assert diff_result["diff"] == ""
    assert diff_result["identical"] is True
    patch_result = _run_patch({"patch_text": "", "dry_run": False})
    assert patch_result["ok"] is False


# ---------------------------------------------------------------------------
# 10. Create new file
# ---------------------------------------------------------------------------
def test_patch_create_new_file(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "new_file.txt"
    f.write_text("", encoding="utf-8")
    patch = ("--- a/{f}\n+++ b/{f}\n@@ -0,0 +1,3 @@\n+line1\n+line2\n+line3\n").format(
        f=f
    )
    result = _run_patch({"patch_text": patch, "dry_run": False})
    assert result["ok"] is True
    assert f.read_text(encoding="utf-8") == "line1\nline2\nline3\n"


# ---------------------------------------------------------------------------
# 11. Delete all content
# ---------------------------------------------------------------------------
def test_patch_clear_file(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "clear_me.txt"
    f.write_text("delete\nthis\ncontent\n", encoding="utf-8")
    patch = (
        "--- a/{f}\n+++ b/{f}\n@@ -1,3 +0,0 @@\n-delete\n-this\n-content\n"
    ).format(f=f)
    result = _run_patch({"patch_text": patch, "dry_run": False})
    assert result["ok"] is True
    assert result["total_removed"] == 3
    assert f.read_text(encoding="utf-8") == ""


# ---------------------------------------------------------------------------
# 12. Whitespace tolerance
# ---------------------------------------------------------------------------
def test_patch_ignore_whitespace(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "space.txt"
    f.write_text("  indented\nnormal\n", encoding="utf-8")
    patch = (
        "--- a/{f}\n+++ b/{f}\n@@ -1,2 +1,2 @@\n  indented\n+modified\n normal\n"
    ).format(f=f)
    result = _run_patch(
        {"patch_text": patch, "dry_run": False, "ignore_whitespace": True}
    )
    assert result["ok"] is True
    assert "modified" in f.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 13. diff_files summary stats
# ---------------------------------------------------------------------------
def test_diff_summary_stats(repo_tmp_path: Path) -> None:
    original = repo_tmp_path / "stats.txt"
    modified = repo_tmp_path / "stats_modified.txt"
    original.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
    modified.write_text("a\nx\nc\nd\nf\n", encoding="utf-8")
    diff_result = _run_diff(
        {
            "path1": str(original),
            "path2": str(modified),
            "mode": "summary",
        }
    )
    assert diff_result["ok"] is True
    assert diff_result["added_lines"] == 2
    assert diff_result["removed_lines"] == 2
    assert diff_result["hunks"] == 2


# ---------------------------------------------------------------------------
# 14. Non-existent target file
# ---------------------------------------------------------------------------
def test_patch_nonexistent_file(repo_tmp_path: Path) -> None:
    patch = ("--- a/{f}\n+++ b/{f}\n@@ -1 +1 @@\n-old\n+new\n").format(
        f=repo_tmp_path / "nope.txt"
    )
    result = _run_patch({"patch_text": patch, "dry_run": False})
    assert result["ok"] is False
    files = result.get("files", [])
    assert any(f.get("error") for f in files)


# ---------------------------------------------------------------------------
# 15. diff_files text comparison mode
# ---------------------------------------------------------------------------
def test_diff_text_mode_then_patch(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "greeting.txt"
    f.write_text("hello\n", encoding="utf-8")
    diff_result = _run_diff(
        {
            "path1": str(f),
            "text": "hello\nworld\n",
            "mode": "unified",
        }
    )
    assert diff_result["ok"] is True
    fixed_patch = _normalize_patch_target(diff_result["diff"], str(f))
    patch_result = _run_patch({"patch_text": fixed_patch, "dry_run": False})
    assert patch_result["ok"] is True
    assert f.read_text(encoding="utf-8") == "hello\nworld\n"


# ---------------------------------------------------------------------------
# 16. CRLF roundtrip
# ---------------------------------------------------------------------------
def test_diff_patch_crlf_roundtrip(repo_tmp_path: Path) -> None:
    original = repo_tmp_path / "crlf_original.txt"
    modified = repo_tmp_path / "crlf_modified.txt"
    original.write_bytes(b"line1\r\nline2\r\n")
    modified.write_bytes(b"line1\r\nline2_modified\r\n")
    diff_result = _run_diff(
        {
            "path1": str(original),
            "path2": str(modified),
            "mode": "unified",
            "preserve_line_endings": True,
        }
    )
    assert diff_result["ok"] is True
    fixed_patch = _normalize_patch_target(diff_result["diff"], str(original))
    patch_result = _run_patch(
        {
            "patch_text": fixed_patch,
            "dry_run": False,
            "preserve_line_endings": True,
        }
    )
    assert patch_result["ok"] is True
    assert original.read_bytes() == b"line1\r\nline2_modified\r\n"


# ===================================================================
# いじわるテスト: IFだけを見て追加 (実装未参照)
# ===================================================================


# ---------------------------------------------------------------------------
# 17. diff_files: path2 と text の同時指定 -> エラー
# ---------------------------------------------------------------------------
def test_diff_path2_and_text_conflict(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "conflict.txt"
    f.write_text("dummy\n", encoding="utf-8")
    result = _run_diff({"path1": str(f), "path2": str(f), "text": "dummy\n"})
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# 18. diff_files: context_lines = 0 -> コンテキスト行なし
# ---------------------------------------------------------------------------
def test_diff_zero_context_lines(repo_tmp_path: Path) -> None:
    f1 = repo_tmp_path / "ctx_a.txt"
    f2 = repo_tmp_path / "ctx_b.txt"
    f1.write_text("keep\nremove\nkeep\n", encoding="utf-8")
    f2.write_text("keep\nadded\nkeep\n", encoding="utf-8")
    result = _run_diff(
        {
            "path1": str(f1),
            "path2": str(f2),
            "context_lines": 0,
        }
    )
    assert result["ok"] is True
    assert "-remove" in result["diff"]
    assert "+added" in result["diff"]


# ---------------------------------------------------------------------------
# 19. diff_files: max_diff_lines = 1 -> 極端に短いdiff
# ---------------------------------------------------------------------------
def test_diff_max_lines_one(repo_tmp_path: Path) -> None:
    f1 = repo_tmp_path / "big_a.txt"
    f2 = repo_tmp_path / "big_b.txt"
    f1.write_text("\n".join(f"line{i}" for i in range(100)), encoding="utf-8")
    f2.write_text("\n".join(f"line{i}_mod" for i in range(100)), encoding="utf-8")
    result = _run_diff(
        {
            "path1": str(f1),
            "path2": str(f2),
            "max_diff_lines": 1,
        }
    )
    assert result["ok"] is True
    # truncated marker が含まれていることを確認
    assert "[diff" in result["diff"].lower() or "truncat" in result["diff"].lower()


# ---------------------------------------------------------------------------
# 20. diff_files: 片方のファイルが空
# ---------------------------------------------------------------------------
def test_diff_one_empty_file(repo_tmp_path: Path) -> None:
    f1 = repo_tmp_path / "empty_a.txt"
    f2 = repo_tmp_path / "nonempty_b.txt"
    f1.write_text("", encoding="utf-8")
    f2.write_text("content\n", encoding="utf-8")
    result = _run_diff({"path1": str(f1), "path2": str(f2)})
    assert result["ok"] is True
    assert result["added_lines"] == 1
    assert result["removed_lines"] == 0
    result2 = _run_diff({"path1": str(f2), "path2": str(f1)})
    assert result2["added_lines"] == 0
    assert result2["removed_lines"] == 1


# ---------------------------------------------------------------------------
# 21. diff_files: 両方空ファイル -> identical
# ---------------------------------------------------------------------------
def test_diff_both_empty(repo_tmp_path: Path) -> None:
    f1 = repo_tmp_path / "empty1.txt"
    f2 = repo_tmp_path / "empty2.txt"
    f1.write_text("", encoding="utf-8")
    f2.write_text("", encoding="utf-8")
    result = _run_diff({"path1": str(f1), "path2": str(f2)})
    assert result["ok"] is True
    assert result["identical"] is True
    assert result["diff"] == ""


# ---------------------------------------------------------------------------
# 22. apply_patch: ハンクヘッダの行数カウントが実際と合わない
# ---------------------------------------------------------------------------
def test_patch_wrong_hunk_line_count(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "wrong_count.txt"
    f.write_text("a\nb\n", encoding="utf-8")
    patch = ("--- a/{f}\n+++ b/{f}\n@@ -1,2 +1,1 @@\n-a\n-b\n+x\n+y\n").format(f=f)
    result = _run_patch({"patch_text": patch, "dry_run": False})
    assert "ok" in result


# ---------------------------------------------------------------------------
# 23. apply_patch: パッチ内のパスに余計なディレクトリプレフィックス
# ---------------------------------------------------------------------------
def test_patch_wrong_path_prefix(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "target.txt"
    f.write_text("old\n", encoding="utf-8")
    patch = (
        "--- a/extra_dir/{name}\n+++ b/extra_dir/{name}\n@@ -1 +1 @@\n-old\n+new\n"
    ).format(name=f.name)
    result = _run_patch({"patch_text": patch, "dry_run": False})
    assert result["ok"] is False
    assert f.read_text(encoding="utf-8") == "old\n"


# ---------------------------------------------------------------------------
# 24. apply_patch: パッチ内に変更行がない（全行コンテキスト行のみ）
# ---------------------------------------------------------------------------
def test_patch_no_changes(repo_tmp_path: Path) -> None:
    f = repo_tmp_path / "nochange.txt"
    f.write_text("same\n", encoding="utf-8")
    patch = "--- a/{f}\n+++ b/{f}\n@@ -1 +1 @@\n same\n".format(f=f)
    result = _run_patch({"patch_text": patch, "dry_run": False})
    assert result["ok"] is True
    assert f.read_text(encoding="utf-8") == "same\n"


# ---------------------------------------------------------------------------
# 25. apply_patch: 存在しないファイルに dry_run -> エラー
# ---------------------------------------------------------------------------
def test_patch_nonexistent_dry_run(repo_tmp_path: Path) -> None:
    patch = ("--- a/{f}\n+++ b/{f}\n@@ -1 +1 @@\n-old\n+new\n").format(
        f=repo_tmp_path / "ghost.txt"
    )
    result = _run_patch({"patch_text": patch, "dry_run": True})
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# 26. diff_files: ignore_whitespace で空白のみ異なる
# ---------------------------------------------------------------------------
def test_diff_ignore_whitespace_only(repo_tmp_path: Path) -> None:
    f1 = repo_tmp_path / "spaces_a.txt"
    f2 = repo_tmp_path / "spaces_b.txt"
    f1.write_text("a\nb\n", encoding="utf-8")
    f2.write_text("a  \nb\n", encoding="utf-8")
    result = _run_diff(
        {
            "path1": str(f1),
            "path2": str(f2),
            "ignore_whitespace": True,
        }
    )
    assert result["ok"] is True
    assert result["identical"] is True
    assert result["diff"] == ""
