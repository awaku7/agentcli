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
            "fast_read_threshold_bytes": 8000000,
        }
    )
    _assert_err_json(out)


def test_search_files_errors_on_invalid_regex(repo_tmp_path: Path) -> None:
    search_files = _import_run_tool("search_files")
    d = repo_tmp_path / "dir"
    d.mkdir(parents=True)
    out = search_files(
        {
            "root_path": str(d),
            "name_pattern": "*.txt",
            "content_pattern": "[",
            "case_sensitive": False,
            "max_results": 10,
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
            "confirm_over": "nope",
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
        {
            "path": "x",
            "mode": "literal",
            "pattern": "a",
            "replacement": "b",
            "occurrence": "2",
        },
    ],
    ids=[
        "confirm_over_not_int",
        "preview_not_bool",
        "expand_newline_tokens_not_bool",
        "occurrence_not_int",
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
            "confirm_over": 0,
        },
        {
            "path": "x",
            "mode": "literal",
            "pattern": "a",
            "replacement": "b",
            "confirm_over": -1,
        },
        {
            "path": "x",
            "mode": "literal",
            "pattern": "a",
            "replacement": "b",
            "occurrence": -1,
        },
    ],
    ids=[
        "empty_pattern",
        "confirm_over_zero",
        "confirm_over_negative",
        "occurrence_negative",
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
    out = file_hash({})
    _assert_err_json(out)
