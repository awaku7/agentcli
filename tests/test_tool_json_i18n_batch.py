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
    lines = [f"_({key!r}, default={value!r})" for key, value in defaults.items()]
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


def test_english_cannot_be_used_as_json_target(tmp_path: Path, capsys) -> None:
    rc = batch.main(
        [
            "status",
            "--langs",
            "en",
            "--tools-dir",
            str(tmp_path / "tools"),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "cannot be a JSON target locale" in captured.err


def test_english_source_follows_delegated_catalog_binding(tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "sample_tool.py").write_text(
        "from .sample_impl import runner\n"
        '_("facade.description", default="Facade")\n',
        encoding="utf-8",
    )
    impl_dir = tools_dir / "sample_impl"
    impl_dir.mkdir()
    (impl_dir / "runner.py").write_text(
        "from pathlib import Path\n"
        "_ = make_tool_translator(\n"
        '    Path(__file__).resolve().parent.parent / "sample_tool.py"\n'
        ")\n"
        '_("tool.description", default="Hello")\n',
        encoding="utf-8",
    )

    source = batch._english_source(tools_dir / "sample_tool.json")

    assert source == {
        "facade.description": "Facade",
        "tool.description": "Hello",
    }


def test_non_english_source_language_is_rejected(tmp_path: Path, capsys) -> None:
    rc = batch.main(
        [
            "status",
            "--source-lang",
            "ja",
            "--tools-dir",
            str(tmp_path / "tools"),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "--source-lang must be en" in captured.err


def test_placeholder_qc_supports_brace_conversion_and_format_spec() -> None:
    assert batch._placeholders(
        "Value={name!r} amount={amount:.2f} count=%(count)03d"
    ) == {"name", "amount", "count"}


def test_placeholder_qc_ignores_numeric_braces_used_as_literal_aliases() -> None:
    assert batch._placeholders("Aliases @A{0} through @A{9}") == set()


def test_tool_label_supports_arbitrary_catalog_names() -> None:
    assert batch._tool_label(Path("safe_exec_ops.json")) == "safe_exec_ops"
    assert batch._tool_label(Path("vision_openai.json")) == "vision_openai"
    assert batch._tool_label(Path("sample_tool.json")) == "sample"


def test_status_require_complete_counts_absent_locale_blocks(
    tmp_path: Path, capsys
) -> None:
    tools_dir = tmp_path / "tools"
    _write_source(
        tools_dir / "sample_tool.py",
        {"tool.description": "Hello"},
    )
    _write_catalog(
        tools_dir / "sample_tool.json",
        {"ja": {"tool.description": "こんにちは"}},
    )

    rc = batch.main(
        [
            "status",
            "--require-complete",
            "--tools-dir",
            str(tools_dir),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert f"missing_units: {len(batch.SUPPORTED_TARGET_LOCALES) - 1}" in captured.out
    assert "missing_by_tool:" in captured.out
    assert f"sample{(40 - len('sample')) * ' '}" in captured.out
    assert "tool i18n catalogs are incomplete" in captured.err


def test_status_require_complete_succeeds_for_complete_catalog(
    tmp_path: Path, capsys
) -> None:
    tools_dir = tmp_path / "tools"
    _write_source(
        tools_dir / "sample_tool.py",
        {"tool.description": "Hello"},
    )
    catalog = {
        lang: {"tool.description": f"{lang} translation"}
        for lang in batch.SUPPORTED_TARGET_LOCALES
    }
    _write_catalog(tools_dir / "sample_tool.json", catalog)

    rc = batch.main(
        [
            "status",
            "--require-complete",
            "--tools-dir",
            str(tools_dir),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert "missing_units: 0" in captured.out
    assert captured.err == ""


def test_intentional_english_debug_value_is_not_stale() -> None:
    value = "[bitchat] [debug] HS skip rs=%(rs)s attempts=%(a)d"

    assert not batch._is_missing_or_stale(
        value,
        value,
        key="bitchat.debug_hs_skip",
        force=False,
        skip_same_as_en=True,
    )
    assert batch._is_missing_or_stale(
        value,
        value,
        key="ordinary.message",
        force=False,
        skip_same_as_en=True,
    )


def test_status_can_report_same_as_english_keys(tmp_path: Path, capsys) -> None:
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
            "--show-same-as-english-keys",
            "--tools-dir",
            str(tools_dir),
            "--tmp-dir",
            str(tmp_path / "tmp"),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert "same_as_english_by_tool_key:" in captured.out
    assert "tool.description" in captured.out
