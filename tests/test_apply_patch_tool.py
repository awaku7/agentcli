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
