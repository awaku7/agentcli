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
            "fast_read_threshold_bytes": 8000000,
        }
    )
    obj = _err_obj(out)
    assert str(missing) in str(obj.get("error", ""))



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
            "fast_read_threshold_bytes": 1,
        }
    )

    assert "big.txt" in out
    assert calls["stream"] >= 1
    assert calls["full"] == 0


def test_search_files_threshold_equal_size_uses_streaming(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    p = repo_tmp_path / "eq.txt"
    p.write_text("hello\n", encoding="utf-8")
    size = p.stat().st_size

    calls: dict[str, int] = {"full": 0, "stream": 0}

    def fake_full(*_args, **_kwargs):
        calls["full"] += 1
        return ["L1: hello"]

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
            "fast_read_threshold_bytes": size,
        }
    )

    assert "eq.txt" in out
    assert calls["stream"] >= 1
    assert calls["full"] == 0


def test_search_files_ignores_default_dirs_and_exts(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    (repo_tmp_path / ".git").mkdir()
    (repo_tmp_path / ".git" / "secret.txt").write_text("hello", encoding="utf-8")
    (repo_tmp_path / "ok.txt").write_text("hello", encoding="utf-8")
    (repo_tmp_path / "image.png").write_text("hello", encoding="utf-8")

    out = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*",
            "content_pattern": "",
            "case_sensitive": False,
            "max_results": 50,
            "fast_read_threshold_bytes": 8000000,
        }
    )

    assert "ok.txt" in out
    assert "secret.txt" not in out
    assert "image.png" not in out


def test_search_files_limits_matches_per_file(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    lines = "".join([f"hello {i}\n" for i in range(10)])
    (repo_tmp_path / "many.txt").write_text(lines, encoding="utf-8")

    out = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*.txt",
            "content_pattern": "hello",
            "case_sensitive": False,
            "max_results": 10,
            "fast_read_threshold_bytes": 8000000,
        }
    )

    assert "many.txt" in out
    assert "... (more matches in file)" in out


def test_search_files_cross_line_match_shows_excerpt(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    (repo_tmp_path / "multi.txt").write_text("foo\nbar\n", encoding="utf-8")

    out = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*.txt",
            "content_pattern": "foo\\nbar",
            "case_sensitive": False,
            "max_results": 10,
            "fast_read_threshold_bytes": 8000000,
        }
    )

    assert "multi.txt" in out
    assert "MATCH:" in out


def test_search_files_newline_token_normalization_literal_backslash_n(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    (repo_tmp_path / "nl.txt").write_text("foo\nbar\n", encoding="utf-8")

    out = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "*.txt",
            "content_pattern": r"foo\\nbar",
            "case_sensitive": False,
            "max_results": 10,
            "fast_read_threshold_bytes": 8000000,
        }
    )

    assert "nl.txt" in out


def test_search_files_globstar_relative_path(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sft, "_", _no_i18n)

    (repo_tmp_path / "a" / "b").mkdir(parents=True)
    (repo_tmp_path / "a" / "b" / "deep.txt").write_text("x", encoding="utf-8")

    out = sft.run_tool(
        {
            "root_path": str(repo_tmp_path),
            "name_pattern": "**/*.txt",
            "content_pattern": "",
            "case_sensitive": False,
            "max_results": 10,
            "fast_read_threshold_bytes": 8000000,
        }
    )

    assert "deep.txt" in out
