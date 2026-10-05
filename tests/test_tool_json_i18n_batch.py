from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "tool_json_i18n_batch.py"
SPEC = importlib.util.spec_from_file_location("tool_json_i18n_batch", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
batch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = batch
SPEC.loader.exec_module(batch)


def _write_catalog(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_source(path: Path, defaults: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"_({key!r}, default={value!r})"
        for key, value in defaults.items()
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_status_defaults_to_all_non_english_locales_without_adding_blocks(
    tmp_path: Path, capsys
) -> None:
    tools_dir = tmp_path / "tools"
    _write_source(
        tools_dir / "sample_tool.py",
        {"tool.description": "Hello"},
    )
    _write_catalog(tools_dir / "sample_tool.json", {})

    rc = batch.main(
        [
            "status",
            "--tools-dir",
            str(tools_dir),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    output = capsys.readouterr().out
    assert rc == 0
    assert "tools_scanned: 1" in output
    assert len(batch.SUPPORTED_TOOL_LOCALES) == 38
    assert "supported_locales: 38" in output
    assert f"languages_scanned: {len(batch.SUPPORTED_TARGET_LOCALES)}" in output
    assert "missing_units: 0" in output
    assert "same_as_english_candidates: 0" in output
    assert "review_candidates: 0" in output


def test_status_add_lang_reports_missing_locale_blocks(tmp_path: Path, capsys) -> None:
    tools_dir = tmp_path / "tools"
    _write_source(
        tools_dir / "sample_tool.py",
        {"tool.description": "Hello"},
    )
    _write_catalog(tools_dir / "sample_tool.json", {})

    rc = batch.main(
        [
            "status",
            "--add-lang",
            "--tools-dir",
            str(tools_dir),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    output = capsys.readouterr().out
    assert rc == 0
    assert f"missing_units: {len(batch.SUPPORTED_TARGET_LOCALES)}" in output


def test_status_reports_english_matches_as_review_candidates(
    tmp_path: Path, capsys
) -> None:
    tools_dir = tmp_path / "tools"
    _write_source(
        tools_dir / "sample_tool.py",
        {"tool.description": "Hello"},
    )
    catalog: dict[str, object] = {}
    for lang in batch.SUPPORTED_TARGET_LOCALES:
        catalog[lang] = {"tool.description": "Hello"}
    _write_catalog(tools_dir / "sample_tool.json", catalog)

    rc = batch.main(
        [
            "status",
            "--tools-dir",
            str(tools_dir),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    output = capsys.readouterr().out
    assert rc == 0
    assert f"languages_scanned: {len(batch.SUPPORTED_TARGET_LOCALES)}" in output
    assert "missing_units: 0" in output
    assert (
        f"same_as_english_candidates: {len(batch.SUPPORTED_TARGET_LOCALES)}" in output
    )
    assert f"review_candidates: {len(batch.SUPPORTED_TARGET_LOCALES)}" in output
    assert (
        f"affected_tool_language_pairs: {len(batch.SUPPORTED_TARGET_LOCALES)}" in output
    )
    assert "same_as_english_by_language:" in output
    assert "ja       1" in output


def test_status_explicit_langs_still_limit_scope(tmp_path: Path, capsys) -> None:
    tools_dir = tmp_path / "tools"
    _write_source(
        tools_dir / "sample_tool.py",
        {"tool.description": "Hello"},
    )
    _write_catalog(
        tools_dir / "sample_tool.json",
        {"ja": {"tool.description": "Hello"}},
    )

    rc = batch.main(
        [
            "status",
            "--langs",
            "ja",
            "--tools-dir",
            str(tools_dir),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    output = capsys.readouterr().out
    assert rc == 0
    assert "languages_scanned: 1" in output
    assert "missing_units: 0" in output
    assert "same_as_english_candidates: 1" in output
    assert "review_candidates: 1" in output


def test_status_ignores_empty_english_source_values(tmp_path: Path, capsys) -> None:
    tools_dir = tmp_path / "tools"
    _write_source(
        tools_dir / "sample_tool.py",
        {
            "empty": "",
            "nonempty": "Hello",
        },
    )
    catalog: dict[str, object] = {
        "ja": {
            "empty": "",
            "nonempty": "こんにちは",
        },
    }
    _write_catalog(tools_dir / "sample_tool.json", catalog)

    rc = batch.main(
        [
            "status",
            "--langs",
            "ja",
            "--tools-dir",
            str(tools_dir),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    output = capsys.readouterr().out
    assert rc == 0
    assert "missing_units: 0" in output
    assert "same_as_english_candidates: 0" in output
    assert "review_candidates: 0" in output


def test_status_allows_locale_specific_search_term_counts(
    tmp_path: Path, capsys
) -> None:
    tools_dir = tmp_path / "tools"
    _write_source(
        tools_dir / "sample_tool.py",
        {
            "x_search_terms": [
                "current location",
                "gps coordinates",
                "geolocation",
            ]
        },
    )
    _write_catalog(
        tools_dir / "sample_tool.json",
        {"ja": {"x_search_terms": ["現在地", "位置情報"]}},
    )

    rc = batch.main(
        [
            "status",
            "--langs",
            "ja",
            "--tools-dir",
            str(tools_dir),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    output = capsys.readouterr().out
    assert rc == 0
    assert "missing_units: 0" in output
    assert "same_as_english_candidates: 0" in output
    assert "review_candidates: 0" in output


def test_non_search_term_lists_still_require_matching_length() -> None:
    assert batch._is_missing_or_stale(
        ["one", "two"],
        ["一"],
        key="choices",
        force=False,
        skip_same_as_en=False,
    )
    assert not batch._is_missing_or_stale(
        ["current location", "gps coordinates"],
        ["現在地"],
        key="x_search_terms",
        force=False,
        skip_same_as_en=False,
    )


def test_mutating_commands_still_require_langs(tmp_path: Path, capsys) -> None:
    rc = batch.main(
        [
            "extract",
            "--tools-dir",
            str(tmp_path / "tools"),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "error: --langs is required" in captured.err


def test_status_reads_named_python_default(tmp_path: Path, capsys) -> None:
    tools_dir = tmp_path / "tools"
    source = tools_dir / "sample_tool.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        'SEARCH_TERMS = ["current location", "gps coordinates"]\n'
        '_("x_search_terms", default=SEARCH_TERMS)\n',
        encoding="utf-8",
    )
    _write_catalog(
        tools_dir / "sample_tool.json",
        {"ja": {"x_search_terms": ["現在地", "位置情報"]}},
    )

    rc = batch.main(
        [
            "status",
            "--langs",
            "ja",
            "--tools-dir",
            str(tools_dir),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    output = capsys.readouterr().out
    assert rc == 0
    assert "review_candidates: 0" in output
