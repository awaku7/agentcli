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
from string import Formatter
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
BRACE_FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FORMATTER = Formatter()
# Key-based gettext entries may obtain their placeholders from the source
# ``default=`` string rather than from the msgid key stored in the PO catalog.
# Keep this explicit so ordinary msgid placeholder mismatches remain strict.
KEYED_DEFAULT_PLACEHOLDER_KEYS = frozenset({"auto.review_judgment_system_prompt"})
ADVISORY_FINDING_KINDS = frozenset({"coverage_missing", "key_extra"})
TOOL_FALLBACK_FINDING_KINDS = frozenset(
    {
        "structure_extra",
        "translation_missing",
        "structure_missing",
        "value_type_mismatch",
        "placeholder_mismatch",
    }
)
# Search terms are locale-specific keyword sets. Their item count does not need
# to match English because runtime English fallback lives in x_search_terms_en.
VARIABLE_LENGTH_ARRAY_KEYS = frozenset({"x_search_terms"})
TOOL_TRANSLATION_LOCALES = tuple(locale for locale in SHIPPED_LOCALES if locale != "en")
TOOL_LOCALE_CANDIDATE_RE = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z]{2})?$")


@dataclass(frozen=True)
class Finding:
    component: str
    kind: str
    path: str
    locale: str | None = None
    key: str | None = None
    detail: dict[str, Any] | None = None


def _placeholders(value: str) -> list[str]:
    names = {match.group("name") for match in PRINTF_PLACEHOLDER_RE.finditer(value)}
    names.update(match.group("name") for match in BRACE_PLACEHOLDER_RE.finditer(value))
    return sorted(names)


def _tool_placeholders(value: str) -> list[str]:
    names = {match.group("name") for match in PRINTF_PLACEHOLDER_RE.finditer(value)}
    try:
        for _literal, field_name, _format_spec, _conversion in FORMATTER.parse(value):
            if field_name is not None and BRACE_FIELD_NAME_RE.fullmatch(field_name):
                names.add(field_name)
    except ValueError:
        names.add("<invalid-brace-format>")
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
            if key in KEYED_DEFAULT_PLACEHOLDER_KEYS:
                continue
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
        key = prefix.rsplit(".", 1)[-1] if prefix else ""
        if key in VARIABLE_LENGTH_ARRAY_KEYS and all(
            isinstance(item, str) for item in value
        ):
            return result
        for index, child in enumerate(value):
            result.update(_walk_structure(child, f"{prefix}[{index}]"))
        return result
    if isinstance(value, str):
        return {prefix: ("string", _tool_placeholders(value))}
    return {prefix: (type(value).__name__, [])}


def _language_blocks(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        key: value
        for key, value in data.items()
        if isinstance(value, dict) and re.fullmatch(r"[a-z]{2,3}(?:_[A-Z]{2})?", key)
    }


def _static_eval(node: ast.AST, constants: dict[str, Any]) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        pass
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_eval(node.left, constants)
        right = _static_eval(node.right, constants)
        try:
            return left + right
        except TypeError:
            return None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                parts.append(part.value)
                continue
            if not isinstance(part, ast.FormattedValue):
                return None
            value = _static_eval(part.value, constants)
            if not isinstance(value, (str, int, float, bool)):
                return None
            format_spec = ""
            if part.format_spec is not None:
                spec = _static_eval(part.format_spec, constants)
                if not isinstance(spec, str):
                    return None
                format_spec = spec
            try:
                parts.append(format(value, format_spec))
            except (TypeError, ValueError):
                return None
        return "".join(parts)
    return None


def _extract_english_source_info(
    py_path: Path,
) -> tuple[dict[str, Any], set[str]]:
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError(f"cannot parse Python source {py_path}: {exc}") from exc

    constants: dict[str, Any] = {}
    for statement in tree.body:
        name: str | None = None
        value_node: ast.AST | None = None
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            name = statement.targets[0].id
            value_node = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            name = statement.target.id
            value_node = statement.value
        if name and value_node is not None:
            value = _static_eval(value_node, constants)
            if value is not None:
                constants[name] = value

    source: dict[str, Any] = {}
    dynamic_keys: set[str] = set()
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    calls.sort(
        key=lambda node: (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))
    )
    for node in calls:
        if not isinstance(node.func, ast.Name) or node.func.id != "_" or not node.args:
            continue
        key_node = node.args[0]
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            continue
        default_node = next(
            (kw.value for kw in node.keywords if kw.arg == "default"),
            None,
        )
        if default_node is None:
            continue
        value = _static_eval(default_node, constants)
        if isinstance(value, (str, list, dict)):
            source.setdefault(key_node.value, value)
        else:
            dynamic_keys.add(key_node.value)
    return source, dynamic_keys


def _extract_x_search_terms_en(py_path: Path) -> list[str] | None:
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None

    constants: dict[str, Any] = {}
    for statement in tree.body:
        name: str | None = None
        value_node: ast.AST | None = None
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            name = statement.targets[0].id
            value_node = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            name = statement.target.id
            value_node = statement.value
        if name and value_node is not None:
            value = _static_eval(value_node, constants)
            if value is not None:
                constants[name] = value

    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key_node, value_node in zip(node.keys, node.values):
            if (
                isinstance(key_node, ast.Constant)
                and key_node.value == "x_search_terms_en"
            ):
                value = _static_eval(value_node, constants)
                if isinstance(value, list) and all(
                    isinstance(item, str) for item in value
                ):
                    return value
    return None


def _english_search_terms(path: Path) -> list[str] | None:
    primary = _extract_x_search_terms_en(path.with_suffix(".py"))
    if primary is not None:
        return primary
    for delegated in _delegated_source_files(path):
        value = _extract_x_search_terms_en(delegated)
        if value is not None:
            return value
    return None


def _delegated_source_files(path: Path) -> list[Path]:
    """Find modules that explicitly bind the default translator to this facade."""
    primary = path.with_suffix(".py")
    target_name = primary.name
    delegated: list[Path] = []
    for candidate in sorted(path.parent.rglob("*.py")):
        if candidate == primary:
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "make_tool_translator" not in text or target_name not in text:
            continue
        try:
            tree = ast.parse(text, filename=str(candidate))
        except SyntaxError:
            continue
        for statement in ast.walk(tree):
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            value = statement.value
            if not isinstance(target, ast.Name) or target.id != "_":
                continue
            if not isinstance(value, ast.Call):
                continue
            if not isinstance(value.func, ast.Name):
                continue
            if value.func.id != "make_tool_translator":
                continue
            explicit_targets = {
                Path(node.value).name
                for node in ast.walk(value)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.endswith(".py")
            }
            if target_name in explicit_targets:
                delegated.append(candidate)
                break
    return delegated


def _english_source_info(path: Path) -> tuple[dict[str, Any], set[str]]:
    py_path = path.with_suffix(".py")
    if not py_path.is_file():
        raise ValueError(f"missing Python source for i18n catalog: {py_path}")

    source, dynamic_keys = _extract_english_source_info(py_path)

    for delegated in _delegated_source_files(path):
        delegated_source, delegated_dynamic = _extract_english_source_info(delegated)
        for key, value in delegated_source.items():
            source.setdefault(key, value)
        dynamic_keys.update(delegated_dynamic)
    return source, dynamic_keys


def _english_source(path: Path) -> dict[str, Any]:
    source, _dynamic_keys = _english_source_info(path)
    return source

def _reference_structure(
    source: dict[str, Any],
    translation_blocks: dict[str, dict[str, Any]],
    dynamic_keys: set[str],
) -> dict[str, tuple[str, list[str]]]:
    """Build structure from Python defaults plus locale consensus for dynamic defaults."""
    reference = _walk_structure(source)
    for key in sorted(dynamic_keys - set(source)):
        candidates: dict[
            tuple[tuple[str, str, tuple[str, ...]], ...],
            tuple[int, dict[str, tuple[str, list[str]]]],
        ] = {}
        for block in translation_blocks.values():
            if key not in block:
                continue
            structure = _walk_structure({key: block[key]})
            signature = tuple(
                sorted(
                    (path, kind, tuple(placeholders))
                    for path, (kind, placeholders) in structure.items()
                )
            )
            count, _existing = candidates.get(signature, (0, structure))
            candidates[signature] = (count + 1, structure)
        if not candidates:
            continue
        _signature, (_count, chosen) = max(
            candidates.items(),
            key=lambda item: (item[1][0], item[0]),
        )
        for path, shape in chosen.items():
            reference.setdefault(path, shape)
    return reference


def audit_tool_catalogs(tools_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(tools_root.glob("*.json")):
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
            continue
        locale_candidates = {
            key
            for key, value in data.items()
            if isinstance(value, dict) and TOOL_LOCALE_CANDIDATE_RE.fullmatch(key)
        }
        for locale in sorted(locale_candidates - set(SHIPPED_LOCALES)):
            findings.append(
                Finding("tool_json", "unexpected_tool_locale", str(path), locale)
            )
        blocks = _language_blocks(data)
        if "en" in blocks:
            findings.append(Finding("tool_json", "english_block_present", str(path)))
        translation_blocks = {
            locale: block
            for locale, block in blocks.items()
            if locale in TOOL_TRANSLATION_LOCALES
        }
        if not translation_blocks:
            continue
        try:
            source, dynamic_keys = _english_source_info(path)
            reference = _reference_structure(source, translation_blocks, dynamic_keys)
            source_search_terms = source.get("x_search_terms")
            english_search_terms = _english_search_terms(path)
            if (
                isinstance(source_search_terms, list)
                and english_search_terms is not None
                and source_search_terms != english_search_terms
            ):
                findings.append(
                    Finding(
                        "tool_json",
                        "english_search_terms_mismatch",
                        str(path),
                        detail={
                            "default": source_search_terms,
                            "x_search_terms_en": english_search_terms,
                        },
                    )
                )
        except ValueError as exc:
            findings.append(
                Finding(
                    "tool_json",
                    "python_source_error",
                    str(path),
                    detail={"error": str(exc)},
                )
            )
            continue
        missing_coverage = sorted(set(TOOL_TRANSLATION_LOCALES) - set(translation_blocks))
        if missing_coverage:
            findings.append(
                Finding(
                    "tool_json",
                    "coverage_missing",
                    str(path),
                    detail={"locales": missing_coverage},
                )
            )
        for locale, block in sorted(translation_blocks.items()):
            current = _walk_structure(block)
            missing = sorted(set(reference) - set(current))
            extra = sorted(set(current) - set(reference))
            translation_missing = [
                item
                for item in missing
                if item
                and item.split(".", 1)[0].split("[", 1)[0] not in block
            ]
            structure_missing = [
                item for item in missing if item not in translation_missing
            ]
            if translation_missing:
                findings.append(
                    Finding(
                        "tool_json",
                        "translation_missing",
                        str(path),
                        locale,
                        detail={"paths": translation_missing},
                    )
                )
            if structure_missing:
                findings.append(
                    Finding(
                        "tool_json",
                        "structure_missing",
                        str(path),
                        locale,
                        detail={"paths": structure_missing},
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


def _is_advisory_finding(item: Finding) -> bool:
    if item.kind in ADVISORY_FINDING_KINDS:
        return True
    return (
        item.component == "tool_json"
        and item.kind in TOOL_FALLBACK_FINDING_KINDS
    )


def audit(locales_root: Path, tools_root: Path) -> dict[str, Any]:
    host_findings = audit_host_catalogs(locales_root)
    tool_findings = audit_tool_catalogs(tools_root)
    findings = host_findings + tool_findings
    coverage_findings = [item for item in findings if item.kind == "coverage_missing"]
    structural_findings = [
        item for item in findings if not _is_advisory_finding(item)
    ]
    strict_findings_by_kind: dict[str, int] = {}
    for item in structural_findings:
        strict_findings_by_kind[item.kind] = (
            strict_findings_by_kind.get(item.kind, 0) + 1
        )
    return {
        "shipped_locales": list(SHIPPED_LOCALES),
        "host_gettext": {"findings": [asdict(item) for item in host_findings]},
        "tool_json": {"findings": [asdict(item) for item in tool_findings]},
        "summary": {
            "host_gettext_findings": len(host_findings),
            "tool_json_findings": len(tool_findings),
            "coverage_findings": len(coverage_findings),
            "structural_findings": len(structural_findings),
            "strict_findings_by_kind": dict(sorted(strict_findings_by_kind.items())),
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
        help="Exit non-zero for non-advisory key, placeholder, or JSON structure findings; coverage, missing translation keys, and extra keys are advisory.",
    )
    args = parser.parse_args(argv)
    payload = audit(args.locales_root, args.tools_root)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    if args.strict and payload["summary"]["structural_findings"]:
        for section in ("host_gettext", "tool_json"):
            for item in payload[section]["findings"]:
                finding = Finding(**item)
                if not _is_advisory_finding(finding):
                    sys.stdout.write(
                        json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
                    )
    sys.stdout.write(
        json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True) + "\n"
    )
    return 1 if args.strict and payload["summary"]["structural_findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
