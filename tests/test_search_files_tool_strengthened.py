from __future__ import annotations

import json
from pathlib import Path

import pytest

import uagent.tools.search_files_tool as sft


def _no_i18n(*args, **kwargs) -> str:
    default = kwargs.get("default")
    if isinstance(default, str):
        return default
    if args:
        return str(args[0])
    return ""


def _err_obj(out: str) -> dict:
    obj = json.loads(out)
    assert isinstance(obj, dict)
    assert obj.get("ok") is False
    return obj


def test_search_files_name_pattern_and_relative_glob(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    (repo_tmp_path / "sub").mkdir()
    (repo_tmp_path / "sub" / "x.txt").write_text("hello", encoding="utf-8")
    (repo_tmp_path / "sub" / "x.py").write_text("print('x')", encoding="utf-8")

    out = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "sub/*.txt",
            "content_pattern": "",
            "case_sensitive": False,
            "max_results": 50,
            "exclude_binary": True,
            "binary_sniff_bytes": 8192,
            "fast_read_threshold_bytes": 8000000,
        }
    )

    assert "File: sub" in out and "x.txt" in out
    assert "x.py" not in out


def test_search_files_content_case_sensitive_toggle(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    (repo_tmp_path / "a.txt").write_text("Hello", encoding="utf-8")

    out_insensitive = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*.txt",
            "content_pattern": "hello",
            "case_sensitive": False,
            "max_results": 50,
            "exclude_binary": True,
            "binary_sniff_bytes": 8192,
            "fast_read_threshold_bytes": 8000000,
        }
    )
    assert "a.txt" in out_insensitive

    out_sensitive = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*.txt",
            "content_pattern": "hello",
            "case_sensitive": True,
            "max_results": 50,
            "exclude_binary": True,
            "binary_sniff_bytes": 8192,
            "fast_read_threshold_bytes": 8000000,
        }
    )
    assert "No files matched" in out_sensitive


def test_search_files_truncates_by_max_results(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    for i in range(5):
        (repo_tmp_path / f"f{i}.txt").write_text("x", encoding="utf-8")

    out = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*.txt",
            "content_pattern": "",
            "case_sensitive": False,
            "max_results": 2,
            "exclude_binary": True,
            "binary_sniff_bytes": 8192,
            "fast_read_threshold_bytes": 8000000,
        }
    )

    assert "truncated to 2" in out
    assert out.count("File:") == 2


def test_search_files_invalid_regex_returns_error_json(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    out = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*.txt",
            "content_pattern": "[",
            "case_sensitive": False,
            "max_results": 10,
            "exclude_binary": True,
            "binary_sniff_bytes": 8192,
            "fast_read_threshold_bytes": 8000000,
        }
    )
    obj = _err_obj(out)
    assert "Failed to compile regex" in str(obj.get("error", ""))


def test_search_files_missing_root_returns_error_json(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    missing = repo_tmp_path / "no_such"
    out = sft.run_tool(
        {
            "root_path": str(missing),
            "name_pattern": "*.txt",
            "content_pattern": "x",
            "case_sensitive": False,
            "max_results": 10,
            "exclude_binary": True,
            "binary_sniff_bytes": 8192,
            "fast_read_threshold_bytes": 8000000,
        }
    )
    obj = _err_obj(out)
    assert str(missing) in str(obj.get("error", ""))


def test_search_files_exclude_binary_toggle(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    p = repo_tmp_path / "bin.txt"
    p.write_bytes(b"\x00hello\n")

    out_excluded = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*.txt",
            "content_pattern": "hello",
            "case_sensitive": False,
            "max_results": 10,
            "exclude_binary": True,
            "binary_sniff_bytes": 8192,
            "fast_read_threshold_bytes": 8000000,
        }
    )
    assert "No files matched" in out_excluded

    out_included = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*.txt",
            "content_pattern": "hello",
            "case_sensitive": False,
            "max_results": 10,
            "exclude_binary": False,
            "binary_sniff_bytes": 8192,
            "fast_read_threshold_bytes": 8000000,
        }
    )
    assert "bin.txt" in out_included


def test_search_files_uses_streaming_for_large_files(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    p = repo_tmp_path / "big.txt"
    p.write_text("hello\n", encoding="utf-8")

    calls: dict[str, int] = {"full": 0, "stream": 0}

    def fake_full(*_args, **_kwargs):
        calls["full"] += 1
        return []

    def fake_stream(*_args, **_kwargs):
        calls["stream"] += 1
        return ["L1: hello"]

    monkeypatch.setattr(sft, "_grep_text_full_read", fake_full)
    monkeypatch.setattr(sft, "_grep_text_streaming", fake_stream)

    out = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*.txt",
            "content_pattern": "hello",
            "case_sensitive": False,
            "max_results": 10,
            "exclude_binary": True,
            "binary_sniff_bytes": 8192,
            "fast_read_threshold_bytes": 1,
        }
    )

    assert "big.txt" in out
    assert calls["stream"] >= 1
    assert calls["full"] == 0
