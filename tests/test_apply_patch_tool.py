"""Execution tests for apply_patch file deletion (--- a/f, +++ /dev/null)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DELETE_PATCH = "\n".join(
    [
        "--- a/old_config.yaml",
        "+++ /dev/null",
        "@@ -1,2 +0,0 @@",
        "-key: value",
        "-foo: bar",
        "",
    ]
)


@pytest.fixture()
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_apply_patch_deletes_file(workdir: Path) -> None:
    from uagent.tools import apply_patch_tool

    target = workdir / "old_config.yaml"
    target.write_text("key: value\nfoo: bar\n", encoding="utf-8")

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": DELETE_PATCH, "dry_run": False})
    )

    assert result["ok"] is True
    assert not target.exists()
    assert result["files"][0]["target"] == "old_config.yaml"
    assert result["files"][0]["deleted"] is True


def test_apply_patch_delete_dry_run_keeps_file(workdir: Path) -> None:
    from uagent.tools import apply_patch_tool

    target = workdir / "old_config.yaml"
    target.write_text("key: value\nfoo: bar\n", encoding="utf-8")

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": DELETE_PATCH, "dry_run": True})
    )

    assert result["ok"] is True
    assert target.exists()
    assert result["files"][0]["deleted"] is True


def test_apply_patch_delete_partial_content_fails(workdir: Path) -> None:
    from uagent.tools import apply_patch_tool

    target = workdir / "old_config.yaml"
    target.write_text("key: value\nfoo: bar\nextra: stays\n", encoding="utf-8")

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": DELETE_PATCH, "dry_run": False})
    )

    assert result["ok"] is False
    assert target.exists()
    assert "extra: stays" in target.read_text(encoding="utf-8")


def test_apply_patch_delete_mismatched_context_fails(workdir: Path) -> None:
    from uagent.tools import apply_patch_tool

    target = workdir / "old_config.yaml"
    target.write_text("different: content\n", encoding="utf-8")

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": DELETE_PATCH, "dry_run": False})
    )

    assert result["ok"] is False
    assert target.exists()


def test_apply_patch_delete_changed_content_fails(workdir: Path) -> None:
    from uagent.tools import apply_patch_tool

    # The file changed after the patch was generated (bar -> NEW). A fuzzy
    # hunk match must not be enough to delete it.
    target = workdir / "old_config.yaml"
    target.write_text("key: value\nfoo: NEW\n", encoding="utf-8")

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": DELETE_PATCH, "dry_run": False})
    )

    assert result["ok"] is False
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "key: value\nfoo: NEW\n"


def test_apply_patch_delete_symlink_removes_link_not_referent(
    workdir: Path,
) -> None:
    from uagent.tools import apply_patch_tool

    real = workdir / "real.txt"
    real.write_text("key: value\nfoo: bar\n", encoding="utf-8")
    link = workdir / "link.txt"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available on this platform")
    patch_text = "\n".join(
        [
            "--- a/link.txt",
            "+++ /dev/null",
            "@@ -1,2 +0,0 @@",
            "-key: value",
            "-foo: bar",
            "",
        ]
    )

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": patch_text, "dry_run": False})
    )

    assert result["ok"] is True
    assert not link.exists() and not link.is_symlink()
    assert real.exists()
    assert real.read_text(encoding="utf-8") == "key: value\nfoo: bar\n"


def test_apply_patch_mixed_modify_and_delete(workdir: Path) -> None:
    from uagent.tools import apply_patch_tool

    doomed = workdir / "old_config.yaml"
    doomed.write_text("key: value\nfoo: bar\n", encoding="utf-8")
    app = workdir / "app.py"
    app.write_text("x = 1\n", encoding="utf-8")
    patch_text = DELETE_PATCH + "\n".join(
        [
            "--- a/app.py",
            "+++ b/app.py",
            "@@ -1 +1 @@",
            "-x = 1",
            "+x = 2",
            "",
        ]
    )

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": patch_text, "dry_run": False})
    )

    assert result["ok"] is True
    assert not doomed.exists()
    assert app.read_text(encoding="utf-8") == "x = 2\n"


CREATE_PATCH = "\n".join(
    [
        "--- /dev/null",
        "+++ b/new_file.txt",
        "@@ -0,0 +1,2 @@",
        "+alpha",
        "+beta",
        "",
    ]
)


def test_apply_patch_creates_new_file_and_dry_run_is_read_only(workdir: Path) -> None:
    from uagent.tools import apply_patch_tool

    target = workdir / "new_file.txt"
    preview = json.loads(
        apply_patch_tool.run_tool({"patch_text": CREATE_PATCH, "dry_run": True})
    )
    assert preview["ok"] is True
    assert preview["files"][0]["created"] is True
    assert not target.exists()

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": CREATE_PATCH, "dry_run": False})
    )
    assert result["ok"] is True
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert result["files"][0]["created"] is True
    assert "backup" not in result["files"][0]


def test_apply_patch_reverse_delete_restores_file_and_counts_additions(
    workdir: Path,
) -> None:
    from uagent.tools import apply_patch_tool

    target = workdir / "old_config.yaml"
    preview = json.loads(
        apply_patch_tool.run_tool(
            {"patch_text": DELETE_PATCH, "dry_run": True, "revert": True}
        )
    )
    assert preview["ok"] is True
    assert preview["files"][0]["created"] is True
    assert not target.exists()

    result = json.loads(
        apply_patch_tool.run_tool(
            {"patch_text": DELETE_PATCH, "dry_run": False, "revert": True}
        )
    )
    assert result["ok"] is True
    assert target.read_text(encoding="utf-8") == "key: value\nfoo: bar\n"
    assert result["total_added"] == 2
    assert result["total_removed"] == 0


def test_apply_patch_reverse_creation_deletes_file_and_counts_removals(
    workdir: Path,
) -> None:
    from uagent.tools import apply_patch_tool

    target = workdir / "new_file.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    result = json.loads(
        apply_patch_tool.run_tool(
            {"patch_text": CREATE_PATCH, "dry_run": False, "revert": True}
        )
    )
    assert result["ok"] is True
    assert not target.exists()
    assert result["files"][0]["deleted"] is True
    assert result["total_added"] == 0
    assert result["total_removed"] == 2


UPDATE_FILE_PATCH = """*** Begin Patch
*** Update File: note.txt
@@
 head
-old1
+new1
@@
 middle
-old2
+new2
 tail
*** End Patch
"""


def test_apply_patch_update_file_format(workdir: Path) -> None:
    from uagent.tools import apply_patch_tool

    target = workdir / "note.txt"
    target.write_text("head\nold1\nmiddle\nold2\ntail\n", encoding="utf-8")

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": UPDATE_FILE_PATCH, "dry_run": False})
    )

    assert result["ok"] is True
    assert target.read_text(encoding="utf-8") == "head\nnew1\nmiddle\nnew2\ntail\n"


@pytest.mark.parametrize("marker", ["*** End Patch", "*** End of File"])
def test_update_file_marker_text_is_preserved_as_context(
    workdir: Path, marker: str
) -> None:
    from uagent.tools import apply_patch_tool

    target = workdir / "marker.txt"
    target.write_text(f"head\n{marker}\nold\n", encoding="utf-8")
    patch = f"""*** Begin Patch
*** Update File: marker.txt
@@
 head
 {marker}
-old
+new
*** End Patch
"""

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": patch, "dry_run": False})
    )

    assert result["ok"] is True
    assert target.read_text(encoding="utf-8") == f"head\n{marker}\nnew\n"


def test_update_file_addition_without_context_inserts_at_start(workdir: Path) -> None:
    from uagent.tools import apply_patch_tool

    target = workdir / "insert.txt"
    target.write_text("one\ntwo\n", encoding="utf-8")
    patch = """*** Begin Patch
*** Update File: insert.txt
@@
+top
*** End Patch
"""

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": patch, "dry_run": False})
    )

    assert result["ok"] is True
    assert target.read_text(encoding="utf-8") == "top\none\ntwo\n"


def test_update_file_addition_uses_section_context(workdir: Path) -> None:
    from uagent.tools import apply_patch_tool

    target = workdir / "section.py"
    target.write_text(
        "header\n\ndef helper():\n    pass\n\ndef target():\n    pass\n",
        encoding="utf-8",
    )
    patch = """*** Begin Patch
*** Update File: section.py
@@ def target():
+    inserted = True
*** End Patch
"""

    result = json.loads(
        apply_patch_tool.run_tool({"patch_text": patch, "dry_run": False})
    )

    assert result["ok"] is True
    assert target.read_text(encoding="utf-8") == (
        "header\n\ndef helper():\n    pass\n\ndef target():\n"
        "    inserted = True\n    pass\n"
    )
