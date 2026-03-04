from __future__ import annotations

import json
from pathlib import Path

from uagent.tools.libcst_transform_tool import run_tool as libcst_transform


def _load(out: str) -> dict:
    obj = json.loads(out)
    assert isinstance(obj, dict)
    assert obj.get("ok") is True, obj
    return obj


def test_libcst_transform_analyze_and_transform_preview_and_apply(
    repo_tmp_path: Path,
) -> None:
    # Arrange: a tiny python file under workdir (repo_tmp_path is under tests/_tmp)
    p = repo_tmp_path / "sample.py"
    p.write_text(
        """
import os


def old_func(x):
    return x + 1


def main():
    y = old_func(1)
    return y
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )

    # Use a repo-relative path (tool path policy is workdir-relative friendly)
    rel_p = p.resolve().relative_to(Path.cwd().resolve()).as_posix()

    # analyze
    out_analyze = libcst_transform(
        {
            "mode": "analyze",
            "paths": [rel_p],
            "include_glob": "**/*.py",
            "exclude_globs": [],
            "max_files": 100,
            "max_bytes": 2000000,
            "preview": False,
        }
    )
    obj_a = _load(out_analyze)

    analyze = obj_a.get("analyze")
    assert isinstance(analyze, dict)
    assert obj_a.get("files_total") == 1

    files = analyze.get("files")
    assert isinstance(files, dict) and files
    this = next(iter(files.values()))
    assert "old_func" in (this.get("functions") or [])

    # transform preview: rename_symbol and replace_call
    # Note: replace_call only changes call-sites, not the function definition.
    ops = [
        {"op": "rename_symbol", "old": "old_func", "new": "new_func"},
        {"op": "replace_call", "old": "new_func", "new": "newer_func"},
    ]

    out_preview = libcst_transform(
        {
            "mode": "transform",
            "paths": [rel_p],
            "include_glob": "**/*.py",
            "exclude_globs": [],
            "max_files": 100,
            "max_bytes": 2000000,
            "operations": ops,
            "preview": True,
        }
    )
    obj_p = _load(out_preview)

    transform_p = obj_p.get("transform")
    assert isinstance(transform_p, dict)
    assert transform_p.get("preview") is True

    previews = transform_p.get("previews")
    assert isinstance(previews, dict) and previews

    this_preview = next(iter(previews.values()))
    assert isinstance(this_preview, dict)
    assert "diff" in this_preview
    assert "newer_func(1)" in str(this_preview.get("diff") or "")

    # Apply (writes file + creates .org/.orgN backup)
    out_apply = libcst_transform(
        {
            "mode": "transform",
            "paths": [rel_p],
            "include_glob": "**/*.py",
            "exclude_globs": [],
            "max_files": 100,
            "max_bytes": 2000000,
            "operations": ops,
            "preview": False,
        }
    )
    obj_apply = _load(out_apply)

    transform_a = obj_apply.get("transform")
    assert isinstance(transform_a, dict)
    assert transform_a.get("preview") is False

    changed_files = transform_a.get("changed_files")
    assert isinstance(changed_files, list)
    assert any("sample.py" in str(x) for x in changed_files)

    backups = transform_a.get("backups")
    assert isinstance(backups, dict) and backups
    for b in backups.values():
        assert Path(str(b)).exists()

    # File content updated
    txt = p.read_text(encoding="utf-8")
    assert "def new_func" in txt
    assert "newer_func(1)" in txt
