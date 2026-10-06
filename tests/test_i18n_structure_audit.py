from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "i18n_structure_audit", ROOT / "scripts" / "i18n_structure_audit.py"
)
assert SPEC and SPEC.loader
audit_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit_module
SPEC.loader.exec_module(audit_module)


def _write_po(path: Path, entries: dict[str, str]) -> None:
    path.parent.mkdir(parents=True)
    lines = ['msgid ""', 'msgstr ""', '"Language: test\\n"', ""]
    for msgid, msgstr in entries.items():
        lines.extend([f"msgid {json.dumps(msgid)}", f"msgstr {json.dumps(msgstr)}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_tool_source(path: Path, defaults: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"_({key!r}, default={value!r})" for key, value in defaults.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_host_audit_detects_key_and_placeholder_differences(tmp_path: Path) -> None:
    locales = tmp_path / "locales"
    for locale in audit_module.SHIPPED_LOCALES:
        entries = {"Hello %(name)s": "Hello %(name)s"}
        if locale == "ja":
            entries = {"Hello %(name)s": "こんにちは %(user)s"}
        if locale == "de":
            entries = {"Only extra": "Nur zusätzlich"}
        _write_po(locales / locale / "LC_MESSAGES" / "uag.po", entries)

    kinds = {
        (finding.locale, finding.kind)
        for finding in audit_module.audit_host_catalogs(locales)
    }
    assert ("ja", "placeholder_mismatch") in kinds
    assert ("de", "key_missing") in kinds
    assert ("de", "key_extra") in kinds


def test_tool_audit_detects_nested_structure_and_placeholders(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    _write_tool_source(
        tools / "example_tool.py",
        {"nested": {"message": "Hello {name}"}},
    )
    (tools / "example_tool.json").write_text(
        json.dumps({"ja": {"nested": {"message": "こんにちは {user}"}, "extra": "x"}}),
        encoding="utf-8",
    )
    findings = audit_module.audit_tool_catalogs(tools)
    kinds = {finding.kind for finding in findings}
    assert "placeholder_mismatch" in kinds
    assert "structure_extra" in kinds


def test_tool_audit_allows_locale_specific_search_term_counts(
    tmp_path: Path,
) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    _write_tool_source(
        tools / "example_tool.py",
        {
            "x_search_terms": [
                "current location",
                "gps coordinates",
                "geolocation",
            ]
        },
    )
    (tools / "example_tool.json").write_text(
        json.dumps(
            {"ja": {"x_search_terms": ["現在地", "位置情報"]}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    findings = audit_module.audit_tool_catalogs(tools)

    assert not any(
        finding.locale == "ja"
        and finding.kind
        in {"structure_missing", "structure_extra", "value_type_mismatch"}
        for finding in findings
    )


def test_tool_audit_keeps_other_array_lengths_strict(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    _write_tool_source(
        tools / "example_tool.py",
        {"choices": ["one", "two"]},
    )
    (tools / "example_tool.json").write_text(
        json.dumps(
            {"ja": {"choices": ["一"]}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    findings = audit_module.audit_tool_catalogs(tools)

    assert any(
        finding.locale == "ja" and finding.kind == "structure_missing"
        for finding in findings
    )


def test_tool_locale_coverage_is_advisory(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    _write_tool_source(
        tools / "example_tool.py",
        {"message": "Hello"},
    )
    (tools / "example_tool.json").write_text(
        json.dumps({"ja": {"message": "こんにちは"}}),
        encoding="utf-8",
    )
    payload = audit_module.audit(tmp_path / "missing", tools)
    coverage = payload["tool_json"]["findings"]
    assert any(item["kind"] == "coverage_missing" for item in coverage)


def test_strict_mode_fails_but_reporting_mode_is_audit_only(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    assert (
        audit_module.main(
            [
                "--locales-root",
                str(tmp_path / "missing"),
                "--tools-root",
                str(tmp_path / "tools"),
                "--report",
                str(report),
            ]
        )
        == 0
    )
    assert (
        audit_module.main(
            [
                "--locales-root",
                str(tmp_path / "missing"),
                "--tools-root",
                str(tmp_path / "tools"),
                "--strict",
            ]
        )
        == 1
    )
    assert json.loads(report.read_text(encoding="utf-8"))["shipped_locales"] == list(
        audit_module.SHIPPED_LOCALES
    )


def test_tool_audit_rejects_json_english_block(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    _write_tool_source(
        tools / "example_tool.py",
        {"message": "Hello"},
    )
    (tools / "example_tool.json").write_text(
        json.dumps(
            {
                "en": {"message": "Hello"},
                "ja": {"message": "こんにちは"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    findings = audit_module.audit_tool_catalogs(tools)

    assert any(finding.kind == "english_block_present" for finding in findings)


def test_tool_audit_uses_locale_consensus_for_dynamic_default(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    source = tools / "example_tool.py"
    source.write_text(
        '_("message", default=f"Hello {runtime_value}")\n',
        encoding="utf-8",
    )
    (tools / "example_tool.json").write_text(
        json.dumps(
            {
                "ja": {"message": "こんにちは"},
                "de": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    findings = audit_module.audit_tool_catalogs(tools)

    assert any(
        finding.locale == "de" and finding.kind == "translation_missing"
        for finding in findings
    )


def test_dynamic_consensus_ignores_keys_not_referenced_by_python(
    tmp_path: Path,
) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "example_tool.py").write_text(
        '_("message", default=f"Hello {runtime_value}")\n',
        encoding="utf-8",
    )
    (tools / "example_tool.json").write_text(
        json.dumps(
            {
                "ja": {"message": "こんにちは", "orphan": "x"},
                "de": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    findings = audit_module.audit_tool_catalogs(tools)
    de_missing = next(
        finding
        for finding in findings
        if finding.locale == "de" and finding.kind == "translation_missing"
    )

    assert "message" in de_missing.detail["paths"]
    assert "orphan" not in de_missing.detail["paths"]
    assert any(
        finding.locale == "ja" and finding.kind == "structure_extra"
        for finding in findings
    )


def test_tool_structure_extra_is_advisory() -> None:
    assert audit_module._is_advisory_finding(
        audit_module.Finding("tool_json", "structure_extra", "tool.json")
    )


def test_tool_fallback_mismatches_are_advisory_but_host_placeholders_stay_strict() -> (
    None
):
    for kind in (
        "structure_missing",
        "value_type_mismatch",
        "placeholder_mismatch",
    ):
        assert audit_module._is_advisory_finding(
            audit_module.Finding("tool_json", kind, "tool.json")
        )
    assert not audit_module._is_advisory_finding(
        audit_module.Finding(
            "host_gettext",
            "placeholder_mismatch",
            "uag.po",
        )
    )


def test_missing_top_level_translation_uses_python_fallback(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    _write_tool_source(
        tools / "example_tool.py",
        {"message": "Hello", "other": "Other"},
    )
    (tools / "example_tool.json").write_text(
        json.dumps({"ja": {"message": "こんにちは"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    findings = audit_module.audit_tool_catalogs(tools)

    assert any(
        finding.locale == "ja" and finding.kind == "translation_missing"
        for finding in findings
    )
    assert not any(
        finding.locale == "ja" and finding.kind == "structure_missing"
        for finding in findings
    )
    assert audit_module._is_advisory_finding(
        audit_module.Finding(
            "tool_json",
            "translation_missing",
            "tool.json",
        )
    )


def test_audit_follows_delegated_catalog_binding(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "sample_tool.py").write_text(
        "from .sample_impl import runner\n",
        encoding="utf-8",
    )
    impl_dir = tools / "sample_impl"
    impl_dir.mkdir()
    (impl_dir / "runner.py").write_text(
        "from pathlib import Path\n"
        "_ = make_tool_translator(\n"
        '    Path(__file__).resolve().parent.parent / "sample_tool.py"\n'
        ")\n"
        '_("tool.description", default="Hello")\n',
        encoding="utf-8",
    )
    (tools / "sample_tool.json").write_text(
        json.dumps(
            {"ja": {"tool.description": "こんにちは"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    findings = audit_module.audit_tool_catalogs(tools)

    assert not any(
        finding.locale == "ja"
        and finding.kind
        in {"structure_extra", "structure_missing", "translation_missing"}
        for finding in findings
    )
