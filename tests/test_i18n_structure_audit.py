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
    (tools / "example_tool.json").write_text(
        json.dumps(
            {
                "en": {"nested": {"message": "Hello %(name)s"}},
                "ja": {"nested": {"message": "こんにちは %(user)s"}, "extra": "x"},
            }
        ),
        encoding="utf-8",
    )
    findings = audit_module.audit_tool_catalogs(tools)
    kinds = {finding.kind for finding in findings}
    assert "placeholder_mismatch" in kinds
    assert "structure_extra" in kinds


def test_tool_locale_coverage_is_advisory(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "example_tool.json").write_text(
        json.dumps({"en": {"message": "Hello"}, "ja": {"message": "こんにちは"}}),
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
