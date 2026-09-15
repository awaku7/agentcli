#!/usr/bin/env python3
"""Audit structural consistency of UAG host and tool i18n catalogs.

This script deliberately does not assess translation quality.  It keeps the two
catalog mechanisms separate: gettext PO catalogs for the host, and per-tool JSON
catalogs for tool plug-ins.  Findings are reported without modifying catalogs.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

# This is a release contract, rather than a directory listing, so a removed or
# accidentally added locale is visible to CI and to the audit report.
SHIPPED_LOCALES = (
    "ar",
    "bn",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "es",
    "fa",
    "fi",
    "fil",
    "fr",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "mn",
    "mr",
    "ms",
    "nb",
    "nl",
    "nn",
    "pl",
    "pt",
    "pt_BR",
    "ro",
    "ru",
    "sv",
    "sw",
    "th",
    "tr",
    "uk",
    "vi",
    "zh_CN",
    "zh_TW",
)
PRINTF_PLACEHOLDER_RE = re.compile(
    r"%\((?P<name>[A-Za-z0-9_]+)\)[#0 +\-]?[0-9]*(?:\.[0-9]+)?[diouxXeEfFgGcrs]"
)
BRACE_PLACEHOLDER_RE = re.compile(r"\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True)
class Finding:
    component: str
    kind: str
    path: str
    locale: str | None = None
    key: str | None = None
    detail: dict[str, Any] | None = None


def _placeholders(value: str) -> list[str]:
    names = {
        match.group("name") for match in PRINTF_PLACEHOLDER_RE.finditer(value)
    }
    names.update(match.group("name") for match in BRACE_PLACEHOLDER_RE.finditer(value))
    return sorted(names)


def _po_unquote(value: str) -> str:
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"invalid PO string: {value!r}") from exc
    if not isinstance(parsed, str):
        raise ValueError(f"PO value is not a string: {value!r}")
    return parsed


def parse_po(path: Path) -> dict[str, list[str]]:
    """Parse msgid/msgstr entries needed for structural validation.

    A small parser is intentional here: the audit must run in CI without an
    optional PO parsing dependency.  It supports multiline strings and plural
    translations, which are the parts relevant to keys and placeholders.
    """

    entries: dict[str, list[str]] = {}
    msgid: str | None = None
    msgstrs: dict[int, str] = {}
    active: tuple[str, int] | None = None

    def flush() -> None:
        nonlocal msgid, msgstrs, active
        if msgid:
            entries[msgid] = [msgstrs[index] for index in sorted(msgstrs)]
        msgid = None
        msgstrs = {}
        active = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            if not line:
                flush()
            continue
        if line.startswith("msgid "):
            flush()
            msgid = _po_unquote(line[6:])
            active = ("msgid", 0)
        elif line.startswith("msgid_plural "):
            active = ("plural", 0)
        elif line.startswith("msgstr["):
            index_end = line.index("]")
            index = int(line[7:index_end])
            msgstrs[index] = _po_unquote(line[index_end + 1 :].strip())
            active = ("msgstr", index)
        elif line.startswith("msgstr "):
            msgstrs[0] = _po_unquote(line[7:])
            active = ("msgstr", 0)
        elif line.startswith('"') and active:
            fragment = _po_unquote(line)
            if active[0] == "msgid":
                msgid = (msgid or "") + fragment
            elif active[0] == "msgstr":
                msgstrs[active[1]] = msgstrs.get(active[1], "") + fragment
    flush()
    return entries


def audit_host_catalogs(locales_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not locales_root.is_dir():
        return [Finding("host_gettext", "locales_root_missing", str(locales_root))]
    expected_locales = set(SHIPPED_LOCALES)
    actual_locales = {path.name for path in locales_root.iterdir() if path.is_dir()}
    for locale in sorted(expected_locales - actual_locales):
        findings.append(
            Finding("host_gettext", "locale_missing", str(locales_root), locale)
        )
    for locale in sorted(actual_locales - expected_locales):
        findings.append(
            Finding("host_gettext", "unexpected_locale", str(locales_root), locale)
        )

    parsed: dict[str, dict[str, list[str]]] = {}
    for locale in SHIPPED_LOCALES:
        po_path = locales_root / locale / "LC_MESSAGES" / "uag.po"
        if not po_path.exists():
            findings.append(
                Finding("host_gettext", "catalog_missing", str(po_path), locale)
            )
            continue
        try:
            parsed[locale] = parse_po(po_path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            findings.append(
                Finding(
                    "host_gettext",
                    "catalog_parse_error",
                    str(po_path),
                    locale,
                    detail={"error": str(exc)},
                )
            )

    reference = parsed.get("en")
    if reference is None:
        return findings + [
            Finding(
                "host_gettext", "reference_catalog_missing", str(locales_root), "en"
            )
        ]
    reference_keys = set(reference)
    for locale, catalog in parsed.items():
        if locale == "en":
            continue
        missing = sorted(reference_keys - set(catalog))
        extra = sorted(set(catalog) - reference_keys)
        if missing:
            findings.append(
                Finding(
                    "host_gettext",
                    "key_missing",
                    str(locales_root / locale / "LC_MESSAGES" / "uag.po"),
                    locale,
                    detail={"keys": missing},
                )
            )
        if extra:
            findings.append(
                Finding(
                    "host_gettext",
                    "key_extra",
                    str(locales_root / locale / "LC_MESSAGES" / "uag.po"),
                    locale,
                    detail={"keys": extra},
                )
            )
        for key in sorted(reference_keys & set(catalog)):
            expected = _placeholders(key)
            for index, translation in enumerate(catalog[key]):
                # Empty msgstr intentionally falls back to English and is not a
                # translation-quality finding.
                if translation and _placeholders(translation) != expected:
                    findings.append(
                        Finding(
                            "host_gettext",
                            "placeholder_mismatch",
                            str(locales_root / locale / "LC_MESSAGES" / "uag.po"),
                            locale,
                            key,
                            {
                                "form": index,
                                "expected": expected,
                                "actual": _placeholders(translation),
                            },
                        )
                    )
    return findings


def _walk_structure(value: Any, prefix: str = "") -> dict[str, tuple[str, list[str]]]:
    if isinstance(value, dict):
        result = {prefix: ("object", [])}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            result.update(_walk_structure(child, child_prefix))
        return result
    if isinstance(value, list):
        result = {prefix: ("array", [])}
        for index, child in enumerate(value):
            result.update(_walk_structure(child, f"{prefix}[{index}]"))
        return result
    if isinstance(value, str):
        return {prefix: ("string", _placeholders(value))}
    return {prefix: (type(value).__name__, [])}


def _language_blocks(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        key: value
        for key, value in data.items()
        if isinstance(value, dict) and re.fullmatch(r"[a-z]{2,3}(?:_[A-Z]{2})?", key)
    }


def audit_tool_catalogs(tools_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(tools_root.glob("*_tool.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            findings.append(
                Finding(
                    "tool_json",
                    "catalog_parse_error",
                    str(path),
                    detail={"error": str(exc)},
                )
            )
            continue
        if not isinstance(data, dict):
            findings.append(Finding("tool_json", "catalog_not_object", str(path)))
            continue
        blocks = _language_blocks(data)
        if not blocks:
            continue
        if "en" not in blocks:
            findings.append(
                Finding("tool_json", "reference_language_missing", str(path))
            )
            continue
        missing_coverage = sorted(set(SHIPPED_LOCALES) - set(blocks))
        if missing_coverage:
            # Tool catalogs intentionally ship independently.  This is coverage
            # information for the 38-locale objective, never a parity failure.
            findings.append(
                Finding(
                    "tool_json",
                    "coverage_missing",
                    str(path),
                    detail={"locales": missing_coverage},
                )
            )
        reference = _walk_structure(blocks["en"])
        for locale, block in sorted(blocks.items()):
            if locale == "en":
                continue
            current = _walk_structure(block)
            missing = sorted(set(reference) - set(current))
            extra = sorted(set(current) - set(reference))
            if missing:
                findings.append(
                    Finding(
                        "tool_json",
                        "structure_missing",
                        str(path),
                        locale,
                        detail={"paths": missing},
                    )
                )
            if extra:
                findings.append(
                    Finding(
                        "tool_json",
                        "structure_extra",
                        str(path),
                        locale,
                        detail={"paths": extra},
                    )
                )
            for key in sorted(set(reference) & set(current)):
                expected_type, expected_placeholders = reference[key]
                actual_type, actual_placeholders = current[key]
                if actual_type != expected_type:
                    findings.append(
                        Finding(
                            "tool_json",
                            "value_type_mismatch",
                            str(path),
                            locale,
                            key,
                            {"expected": expected_type, "actual": actual_type},
                        )
                    )
                elif (
                    expected_type == "string"
                    and actual_placeholders != expected_placeholders
                ):
                    findings.append(
                        Finding(
                            "tool_json",
                            "placeholder_mismatch",
                            str(path),
                            locale,
                            key,
                            {
                                "expected": expected_placeholders,
                                "actual": actual_placeholders,
                            },
                        )
                    )
    return findings


def audit(locales_root: Path, tools_root: Path) -> dict[str, Any]:
    host_findings = audit_host_catalogs(locales_root)
    tool_findings = audit_tool_catalogs(tools_root)
    findings = host_findings + tool_findings
    coverage_findings = [item for item in findings if item.kind == "coverage_missing"]
    structural_findings = [item for item in findings if item.kind != "coverage_missing"]
    return {
        "shipped_locales": list(SHIPPED_LOCALES),
        "host_gettext": {"findings": [asdict(item) for item in host_findings]},
        "tool_json": {"findings": [asdict(item) for item in tool_findings]},
        "summary": {
            "host_gettext_findings": len(host_findings),
            "tool_json_findings": len(tool_findings),
            "coverage_findings": len(coverage_findings),
            "structural_findings": len(structural_findings),
            "total_findings": len(findings),
        },
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit UAG i18n catalog structure without changing translations."
    )
    parser.add_argument("--locales-root", type=Path, default=Path("src/uagent/locales"))
    parser.add_argument("--tools-root", type=Path, default=Path("src/uagent/tools"))
    parser.add_argument(
        "--report", type=Path, help="Write a JSON audit report to this path."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero for key, placeholder, or JSON structure findings; coverage is advisory.",
    )
    args = parser.parse_args(argv)
    payload = audit(args.locales_root, args.tools_root)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    sys.stdout.write(
        json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True) + "\n"
    )
    return 1 if args.strict and payload["summary"]["structural_findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
