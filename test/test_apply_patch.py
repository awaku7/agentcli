"""test_apply_patch.py — Comprehensive edge-case tests for apply_patch_tool + diff_files_tool

Usage:
    python test/test_apply_patch.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

_script_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(_script_dir, "..", "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from uagent.tools.apply_patch_tool import run_tool as apply_patch
from uagent.tools.diff_files_tool import run_tool as diff_files

PASS = 0
FAIL = 0


def test(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f"  -- {detail}" if detail else ""))


def ensure_workdir():
    os.chdir(tempfile.gettempdir())


# ========================================================================
def test_apply_patch_basic():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hello\nworld\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1,2 +1,2 @@\n hello\n-world\n+earth\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    test("Simple replacement", r["ok"])
    with open(p) as f: test("  content correct", "earth" in f.read())
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("keep\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-keep\n+changed\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": True}))
    with open(p) as f: test("Dry run leaves file intact", r["dry_run"] and "keep" in f.read())
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("same\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-same\n+same\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    with open(p) as f: test("Identical patch (no-op)", r["ok"] and "same" in f.read())
    os.unlink(p)


# ========================================================================
def test_apply_patch_tricky():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("alpha\nbeta\n"); p1 = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("gamma\ndelta\n"); p2 = f.name
    patch = (f"--- a/{p1}\n+++ b/{p1}\n@@ -1,2 +1,2 @@\n alpha\n-beta\n+XXX\n"
             f"--- a/{p2}\n+++ b/{p2}\n@@ -1,2 +1,2 @@\n gamma\n-delta\n+YYY\n")
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    ok = r["ok"] and r["total_applied"] == 2
    with open(p1) as f: ok = ok and "XXX" in f.read()
    with open(p2) as f: ok = ok and "YYY" in f.read()
    test("Multiple files", ok); os.unlink(p1); os.unlink(p2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1,3 +1,3 @@\n a\n-b\n+Z\n c\n"
    with open(p, "w") as f: f.write("a\nDIFFERENT\nc\n")
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    test("Context mismatch fails", not r["ok"] and r["files"][0]["hunks_failed"] == 1)
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        pass; p = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("first line\n"); p2 = f.name
    rd = json.loads(diff_files({"path1": p, "path2": p2, "path1_label": f"a/{p}", "path2_label": f"b/{p}"}))
    r = json.loads(apply_patch({"patch_text": rd["diff"], "dry_run": False}))
    with open(p) as f: test("Empty -> content", r["ok"] and "first line" in f.read())
    os.unlink(p); os.unlink(p2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\nd\ne\nf\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1,2 +1,2 @@\n a\n-b\n+X\n@@ -5,2 +5,2 @@\n e\n-f\n+Y\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    ok = r["ok"] and r["total_applied"] == 2
    with open(p) as f: c = f.read(); ok = ok and "X" in c and "Y" in c
    test("Interleaved hunks", ok); os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1,1 +1,1 @@\n-a\n+A\n@@ -2,1 +2,1 @@\n-b\n+B\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    with open(p) as f: test("Adjacent hunks", r["ok"] and f.read() == "A\nB\nc\n")
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1,3 +1,1 @@\n a\n-b\n-c\n+ONELINE\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    with open(p) as f: test("Unbalanced 3->1", r["ok"] and f.read().strip() == "a\nONELINE")
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("start\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -0,0 +1 @@\n+inserted\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    with open(p) as f: test("Insert before (old_start=0)", r["ok"] and "inserted" in f.read())
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("first\nsecond\nthird\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -3,1 +3,1 @@\n-third\n+LAST\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    with open(p) as f: test("Last line change", r["ok"] and f.read().strip().endswith("LAST"))
    os.unlink(p)


# ========================================================================
def test_apply_patch_crlf():
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write(b"a\r\nb\r\nc\r\n"); p = f.name
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write(b"a\r\nMOD\r\nc\r\n"); p2 = f.name
    rd = json.loads(diff_files({"path1": p, "path2": p2, "path1_label": f"a/{p}", "path2_label": f"b/{p}", "preserve_line_endings": True}))
    r = json.loads(apply_patch({"patch_text": rd["diff"], "dry_run": False, "preserve_line_endings": True}))
    with open(p, "rb") as f: test("CRLF roundtrip", r["ok"] and b"MOD\r\n" in f.read())
    os.unlink(p); os.unlink(p2)

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write(b"1\r\n2\r\n3\r\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1,3 +1,3 @@\n 1\n-2\n+chg\n 3\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    with open(p, "rb") as f: test("CRLF file + LF patch", r["ok"] and b"chg" in f.read())
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write(b"a\r\nb\nc\r\n"); p = f.name
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write(b"a\r\nMOD\nc\r\n"); p2 = f.name
    rd = json.loads(diff_files({"path1": p, "path2": p2, "path1_label": f"a/{p}", "path2_label": f"b/{p}", "preserve_line_endings": True}))
    r = json.loads(apply_patch({"patch_text": rd["diff"], "dry_run": False, "preserve_line_endings": True}))
    test("Mixed line endings (no crash)", r["ok"])
    os.unlink(p); os.unlink(p2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1,3 +1,3 @@\n a\r\n-b\r\n+MOD\r\n c\r\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    test("LF file + CRLF patch", r["ok"]); os.unlink(p)


# ========================================================================
def test_apply_patch_fuzzy():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("x  \n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-x\n+y\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False, "ignore_whitespace": True}))
    with open(p) as f: test("Trailing whitespace tolerant", r["ok"] and "y" in f.read())
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("def foo():\n  return 1\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1,2 +1,2 @@\n def foo():\n-    return 1\n+    return 42\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False, "ignore_whitespace": True}))
    with open(p) as f: test("Fuzzy indent match", r["ok"] and "return 42" in f.read())
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\n"); p = f.name
    with open(p, "w") as f: f.write("a\nCOMPLETELY_DIFFERENT\nc\n")
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1,3 +1,3 @@\n a\n-b\n+Z\n c\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    test("Too different still fails", not r["ok"]); os.unlink(p)


# ========================================================================
def test_apply_patch_edge():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for i in range(50): f.write(f"line{i}\n"); p = f.name
    parts = [f"--- a/{p}\n+++ b/{p}\n"]
    for i in range(0, 50, 5):
        parts.append(f"@@ -{i+1},1 +{i+1},1 @@\n-line{i}\n+MOD{i}\n")
    r = json.loads(apply_patch({"patch_text": "".join(parts), "dry_run": False}))
    ok = r["ok"] and r["total_applied"] == 10
    with open(p) as f: c = f.read(); ok = ok and "MOD0" in c and "MOD5" in c
    test("10 hunks / 50 lines", ok); os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("original\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-original\n+MODIFIED\n"
    r1 = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    r2 = json.loads(apply_patch({"patch_text": patch, "dry_run": False, "revert": True}))
    with open(p) as f: test("Revert to original", r2["ok"] and "original" in f.read())
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("target\n"); p = f.name
    bn = os.path.basename(p)
    patch = f"--- a/dir/sub/{bn}\n+++ b/dir/sub/{bn}\n@@ -1 +1 @@\n-target\n+PATCHED\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False, "strip": 2}))
    with open(p) as f: test("Strip path dir/sub/file (strip=2)", r["ok"] and "PATCHED" in f.read())
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hello\n"); p = f.name
    bn = os.path.basename(p)
    patch = f"--- a/dir/{bn}\n+++ b/dir/{bn}\n@@ -1 +1 @@\n-hello\n+WORLD\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False, "strip": 1}))
    with open(p) as f: test("Strip path dir/file (strip=1)", r["ok"] and "WORLD" in f.read())
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("backup me\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-backup me\n+done\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    bp = r["files"][0].get("backup", "")
    test("Backup created", bool(bp) and os.path.exists(bp))
    if bp and os.path.exists(bp): os.unlink(bp)
    os.unlink(p)

    r = json.loads(apply_patch({"patch_text": "--- a/nope.txt\n+++ b/nope.txt\n@@ -1 +1 @@\n-old\n+new\n"}))
    test("Nonexistent file error", not r["ok"])
    r = json.loads(apply_patch({"patch_text": ""}))
    test("Empty patch error", not r["ok"])
    r = json.loads(apply_patch({"patch_text": "--- a/f\n+++ b/f\n"}))
    test("Headers only (no hunks)", not r["ok"])

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1,3 +1,3 @@\n a\n-b\n+MOD\n c\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    with open(p) as f: test("Explicit hunk counts", r["ok"] and "MOD" in f.read())
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("keep\n"); p = f.name
    patch = f"--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-keep\n+keep\n"
    r = json.loads(apply_patch({"patch_text": patch, "dry_run": False}))
    with open(p) as f: test("No-op (before==after)", r["ok"] and "keep" in f.read())
    os.unlink(p)


# ========================================================================
def test_roundtrip():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def hello():\n    return 1\n"); p = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def hello(name):\n    return f'hi {name}'\n"); p2 = f.name
    rd = json.loads(diff_files({"path1": p, "path2": p2, "path1_label": f"a/{p}", "path2_label": f"b/{p}"}))
    r = json.loads(apply_patch({"patch_text": rd["diff"], "dry_run": False}))
    with open(p) as f: test("Python file roundtrip", r["ok"] and "name" in f.read())
    os.unlink(p); os.unlink(p2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\n"); p = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\n  b\nc\n"); p2 = f.name
    rd = json.loads(diff_files({"path1": p, "path2": p2, "path1_label": f"a/{p}", "path2_label": f"b/{p}", "ignore_whitespace": True}))
    r = json.loads(apply_patch({"patch_text": rd["diff"], "dry_run": False, "ignore_whitespace": True}))
    with open(p) as f: test("Ignore whitespace roundtrip", r["ok"] and "  b" in f.read())
    os.unlink(p); os.unlink(p2)

    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False) as f:
        f.write("\u3053\u3093\u306b\u3061\u306f\n\U0001f600\n"); p = f.name
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False) as f:
        f.write("\u3053\u3093\u306b\u3061\u306f\n\U0001f601\n"); p2 = f.name
    rd = json.loads(diff_files({"path1": p, "path2": p2, "path1_label": f"a/{p}", "path2_label": f"b/{p}"}))
    r = json.loads(apply_patch({"patch_text": rd["diff"], "dry_run": False}))
    with open(p, encoding="utf-8") as f: test("Unicode/emoji roundtrip", r["ok"] and "\U0001f601" in f.read())
    os.unlink(p); os.unlink(p2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("ctx1\nctx2\nctx3\nchange\nctx5\nctx6\nctx7\n"); p = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("ctx1\nctx2\nctx3\nMODIFIED\nctx5\nctx6\nctx7\n"); p2 = f.name
    rd = json.loads(diff_files({"path1": p, "path2": p2, "context_lines": 0, "path1_label": f"a/{p}", "path2_label": f"b/{p}"}))
    r = json.loads(apply_patch({"patch_text": rd["diff"], "dry_run": False}))
    with open(p) as f: test("Zero context lines", r["ok"] and "MODIFIED" in f.read())
    os.unlink(p); os.unlink(p2)


# ========================================================================
def test_diff_files_features():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\n"); p = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nx\nc\n"); p2 = f.name
    r = json.loads(diff_files({"path1": p, "path2": p2, "mode": "summary"}))
    test("summary mode", r["changed"] and r["added_lines"] == 1)
    os.unlink(p); os.unlink(p2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\n"); p = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nx\nc\n"); p2 = f.name
    r = json.loads(diff_files({"path1": p, "path2": p2, "mode": "json_diff"}))
    test("json_diff mode", r["changed"] and len(r.get("hunks", [])) == 1)
    os.unlink(p); os.unlink(p2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("same\ncontent\n"); p = f.name
    r = json.loads(diff_files({"path1": p, "path2": p, "mode": "summary"}))
    test("identical detection", r["identical"] and r["similarity_ratio"] == 1.0)
    os.unlink(p)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("old\n"); p = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("new\n"); p2 = f.name
    r = json.loads(diff_files({"path1": p, "path2": p2, "path1_label": "a/original.py", "path2_label": "b/modified.py"}))
    test("custom labels", "original.py" in r.get("diff", ""))
    os.unlink(p); os.unlink(p2)

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write(b"a\r\nb\r\nc\r\n"); p = f.name
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write(b"a\r\nx\r\nc\r\n"); p2 = f.name
    r = json.loads(diff_files({"path1": p, "path2": p2, "preserve_line_endings": True}))
    diff_text = r.get("diff", "")
    has_crlf = "\r\n" in diff_text and "\n" in diff_text
    test("diff_files CRLF preserve", r["ok"] and has_crlf)
    os.unlink(p); os.unlink(p2)


# ========================================================================
def main() -> int:
    global PASS, FAIL
    ensure_workdir()
    print("=" * 60)
    print("apply_patch + diff_files — Edge case tests")
    print("=" * 60)

    print("\n--- basic ---"); test_apply_patch_basic()
    print("\n--- tricky ---"); test_apply_patch_tricky()
    print("\n--- CRLF ---"); test_apply_patch_crlf()
    print("\n--- fuzzy ---"); test_apply_patch_fuzzy()
    print("\n--- edge ---"); test_apply_patch_edge()
    print("\n--- roundtrip ---"); test_roundtrip()
    print("\n--- diff_files features ---"); test_diff_files_features()

    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS}/{total} passed, {FAIL}/{total} failed")
    print(f"{'=' * 60}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
