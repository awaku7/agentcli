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


def test_status_defaults_to_all_non_english_locales_without_adding_blocks(
    tmp_path: Path, capsys
) -> None:
    tools_dir = tmp_path / "tools"
    _write_catalog(
        tools_dir / "sample_tool.json",
        {"en": {"tool.description": "Hello"}},
    )

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
    assert f"languages_scanned: {len(batch.SUPPORTED_TARGET_LOCALES)}" in output
    assert "missing_units: 0" in output


def test_status_add_lang_reports_missing_locale_blocks(tmp_path: Path, capsys) -> None:
    tools_dir = tmp_path / "tools"
    _write_catalog(
        tools_dir / "sample_tool.json",
        {"en": {"tool.description": "Hello"}},
    )

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


def test_status_treats_english_fallbacks_as_missing(tmp_path: Path, capsys) -> None:
    tools_dir = tmp_path / "tools"
    catalog: dict[str, object] = {
        "en": {"tool.description": "Hello"},
    }
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
    assert f"missing_units: {len(batch.SUPPORTED_TARGET_LOCALES)}" in output
    assert (
        f"affected_tool_language_pairs: {len(batch.SUPPORTED_TARGET_LOCALES)}" in output
    )
    assert "missing_by_language:" in output
    assert "ja       1" in output


def test_status_explicit_langs_still_limit_scope(tmp_path: Path, capsys) -> None:
    tools_dir = tmp_path / "tools"
    _write_catalog(
        tools_dir / "sample_tool.json",
        {
            "en": {"tool.description": "Hello"},
            "ja": {"tool.description": "Hello"},
        },
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
    assert "missing_units: 1" in output


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
