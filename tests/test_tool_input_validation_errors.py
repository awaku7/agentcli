from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _import_run_tool(tool_module_basename: str):
    """Import a tool module and return its run_tool.

    The repo has both patterns:
      - uagent.tools.<name>_tool
      - uagent.tools.<name>
    Prefer *_tool first.
    """

    candidates = [
        f"uagent.tools.{tool_module_basename}_tool",
        f"uagent.tools.{tool_module_basename}",
    ]
    last_exc: Exception | None = None
    for modname in candidates:
        try:
            mod = importlib.import_module(modname)
            rt = getattr(mod, "run_tool", None)
            if callable(rt):
                return rt
            raise AttributeError(f"{modname} has no callable run_tool")
        except Exception as e:  # noqa: BLE001
            last_exc = e
    raise ImportError(
        f"Could not import run_tool for {tool_module_basename}: {last_exc!r}"
    )


def _loads(s: str) -> dict:
    obj = json.loads(s)
    assert isinstance(obj, dict)
    return obj


def _assert_err_json(out: str) -> dict:
    obj = _loads(out)
    assert obj.get("ok") is False, obj
    assert any(k in obj for k in ("error", "errors", "message")), obj
    return obj


def test_read_file_errors_on_missing_file(repo_tmp_path: Path) -> None:
    read_file = _import_run_tool("read_file")
    missing = repo_tmp_path / "does_not_exist.txt"
    out = read_file({"filename": str(missing), "path": str(missing)})
    _assert_err_json(out)


def test_search_files_errors_on_missing_root(repo_tmp_path: Path) -> None:
    search_files = _import_run_tool("search_files")
    missing_dir = repo_tmp_path / "no_such_dir"
    out = search_files(
        {
            "root_path": str(missing_dir),
            "name_pattern": "*.txt",
            "content_pattern": "x",
            "case_sensitive": False,
            "max_results": 10,
            "exclude_binary": True,
            "binary_sniff_bytes": 8192,
            "fast_read_threshold_bytes": 8000000,
        }
    )
    _assert_err_json(out)


def test_search_files_errors_on_invalid_regex(repo_tmp_path: Path) -> None:
    search_files = _import_run_tool("search_files")
    # Existing directory, but regex compile fails.
    d = repo_tmp_path / "dir"
    d.mkdir(parents=True)
    out = search_files(
        {
            "root_path": str(d),
            "name_pattern": "*.txt",
            "content_pattern": "[",
            "case_sensitive": False,
            "max_results": 10,
            "exclude_binary": True,
            "binary_sniff_bytes": 8192,
            "fast_read_threshold_bytes": 8000000,
        }
    )
    _assert_err_json(out)


def test_replace_in_file_missing_required_keys() -> None:
    replace_in_file = _import_run_tool("replace_in_file")
    out = replace_in_file({"search": "a", "replace": "b"})
    _assert_err_json(out)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"path": "x"},
        {"path": "x", "mode": "literal"},
        {"path": "x", "pattern": "a"},
        {"path": "x", "replacement": "b"},
        {"path": "x", "mode": "literal", "pattern": "a"},
        {"path": "x", "mode": "literal", "replacement": "b"},
    ],
    ids=[
        "empty",
        "only_path",
        "missing_pattern_replacement",
        "missing_mode_replacement",
        "missing_mode_pattern",
        "missing_replacement",
        "missing_pattern",
    ],
)
def test_replace_in_file_rejects_incomplete_inputs(payload: dict) -> None:
    """replace_in_file should reject missing required keys (schema-level or tool-level)."""

    replace_in_file = _import_run_tool("replace_in_file")
    out = replace_in_file(payload)
    _assert_err_json(out)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "path": "x",
            "mode": "literal",
            "pattern": "a",
            "replacement": "b",
            "confirm_if_matches_over": "nope",
        },
        {
            "path": "x",
            "mode": "literal",
            "pattern": "a",
            "replacement": "b",
            "preview": "true",
        },
        {
            "path": "x",
            "mode": "literal",
            "pattern": "a",
            "replacement": "b",
            "expand_newline_tokens": "yes",
        },
    ],
    ids=[
        "confirm_if_matches_over_not_int",
        "preview_not_bool",
        "expand_newline_tokens_not_bool",
    ],
)
def test_replace_in_file_rejects_wrong_types(payload: dict) -> None:
    replace_in_file = _import_run_tool("replace_in_file")
    out = replace_in_file(payload)
    _assert_err_json(out)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "path": "x",
            "mode": "nope",
            "pattern": "a",
            "replacement": "b",
        },
        {
            "path": "x",
            "mode": "literal",
            "pattern": "a",
            "replacement": "b",
            "encoding": "this-encoding-does-not-exist",
        },
    ],
    ids=[
        "invalid_mode",
        "invalid_encoding",
    ],
)
def test_replace_in_file_rejects_invalid_values(payload: dict) -> None:
    replace_in_file = _import_run_tool("replace_in_file")
    out = replace_in_file(payload)
    _assert_err_json(out)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "path": "x",
            "mode": "literal",
            "pattern": "",
            "replacement": "b",
        },
        {
            "path": "x",
            "mode": "literal",
            "pattern": "a",
            "replacement": "b",
            "confirm_if_matches_over": 0,
        },
        {
            "path": "x",
            "mode": "literal",
            "pattern": "a",
            "replacement": "b",
            "confirm_if_matches_over": -1,
        },
    ],
    ids=[
        "empty_pattern",
        "confirm_if_matches_over_zero",
        "confirm_if_matches_over_negative",
    ],
)
def test_replace_in_file_rejects_invalid_constraints(payload: dict) -> None:
    replace_in_file = _import_run_tool("replace_in_file")
    out = replace_in_file(payload)
    _assert_err_json(out)


def test_zip_ops_rejects_zip_slip_on_extract(repo_tmp_path: Path) -> None:
    zip_ops = _import_run_tool("zip_ops")

    zip_path = repo_tmp_path / "bad.zip"
    import zipfile

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.txt", "nope")

    rel_zip = zip_path.resolve().relative_to(Path.cwd().resolve()).as_posix()

    out = zip_ops(
        {
            "action": "extract",
            "zip_path": rel_zip,
            "sources": [],
            "dest_dir": "tests/_tmp",
            "exclude_globs": [],
            "overwrite": False,
            "max_files": 5000,
            "max_total_uncompressed_bytes": 500000000,
            "dry_run": False,
        }
    )
    _assert_err_json(out)


def test_file_hash_rejects_missing_paths_key() -> None:
    file_hash = _import_run_tool("file_hash")
    out = file_hash({"algo": "sha256", "chunk_size": 1048576, "return": "json"})
    _assert_err_json(out)


def test_find_large_files_rejects_nonint_min_bytes() -> None:
    find_large_files = _import_run_tool("find_large_files")
    out = find_large_files(
        {
            "root": ".",
            "top_n": 10,
            "min_bytes": "not-an-int",
            "group_by_ext": True,
            "exclude_dirs": [".git"],
            "max_files": 1000,
        }
    )
    _assert_err_json(out)


def test_date_calc_rejects_invalid_date() -> None:
    date_calc = _import_run_tool("date_calc")
    out = date_calc(
        {
            "base_date": "2025-99-99",
            "years": 0,
            "months": 0,
            "weeks": 0,
            "days": 1,
            "country": "JP",
            "check_holiday": True,
        }
    )
    _assert_err_json(out)


def test_create_file_rejects_nonbool_overwrite(repo_tmp_path: Path) -> None:
    create_file = _import_run_tool("create_file")
    with pytest.raises(ValueError, match="overwrite must be a boolean"):
        create_file(
            {
                "filename": str(repo_tmp_path / "x.txt"),
                "content": "abc",
                "overwrite": "false",
            }
        )


def test_delete_file_rejects_nonbool_flags(repo_tmp_path: Path) -> None:
    delete_file = _import_run_tool("delete_file")
    with pytest.raises(ValueError, match="missing_ok must be a boolean"):
        delete_file(
            {
                "filename": str(repo_tmp_path / "*.txt"),
                "missing_ok": "false",
                "dry_run": True,
                "allow_dir": True,
            }
        )

    with pytest.raises(ValueError, match="dry_run must be a boolean"):
        delete_file(
            {
                "filename": str(repo_tmp_path / "*.txt"),
                "missing_ok": False,
                "dry_run": "false",
                "allow_dir": True,
            }
        )

    with pytest.raises(ValueError, match="allow_dir must be a boolean"):
        delete_file(
            {
                "filename": str(repo_tmp_path / "*.txt"),
                "missing_ok": False,
                "dry_run": True,
                "allow_dir": "false",
            }
        )


def test_rename_path_rejects_nonbool_flags(repo_tmp_path: Path) -> None:
    rename_path = _import_run_tool("rename_path")
    src = repo_tmp_path / "src.txt"
    src.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="overwrite must be a boolean"):
        rename_path(
            {
                "src": str(src),
                "dst": str(repo_tmp_path / "dst.txt"),
                "overwrite": "false",
                "mkdirs": False,
            }
        )

    with pytest.raises(ValueError, match="mkdirs must be a boolean"):
        rename_path(
            {
                "src": str(src),
                "dst": str(repo_tmp_path / "dst2.txt"),
                "overwrite": False,
                "mkdirs": "false",
            }
        )


@pytest.mark.skip(reason="Dangerous tool; kept non-executed by policy")
def test_binary_edit_missing_required_args() -> None:
    binary_edit = _import_run_tool("binary_edit")

    out = binary_edit(
        {
            "path": "x",
            "mode": "write",
            "dry_run": True,
            "max_bytes": 10,
            "offset": 0,
            "data_hex": "",
            "search_hex": "",
            "replace_hex": "",
            "occurrence": 1,
            "splice_op": "insert",
            "delete_len": 0,
            "patch_json": "{}",
        }
    )
    _assert_err_json(out)
