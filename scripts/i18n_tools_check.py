#!/usr/bin/env python
"""i18n_tools_check.py

Validate tool-side i18n JSON files under src/uagent/tools.

Checks:
- All language sections have the same key set (base language defaults to 'en' if present).
- Placeholders like {name} match the base language for each key.
- (Optional warning) Mentions of Skill_dir / SkillDir (commonly a typo of skills_dir).

Exit code:
- 0: OK (no issues)
- 1: Issues found (or warnings when --strict)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


LANG_KEY_RE = re.compile(r"^[a-z]{2}(_[A-Z]{2})?$")
PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def _reconfigure_stdout() -> None:
    # Avoid Windows cp932 UnicodeEncodeError when printing CJK.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass


@dataclass
class Finding:
    severity: str  # "error" | "warning"
    file: str
    kind: str
    lang: Optional[str] = None
    key: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None


def iter_tool_json_files(root: str, recursive: bool) -> List[str]:
    root = os.path.normpath(root)
    pattern = os.path.join(root, "**", "*.json") if recursive else os.path.join(root, "*.json")
    files = glob.glob(pattern, recursive=recursive)
    files = [f for f in files if os.path.isfile(f)]
    files.sort()
    return files


def load_json(path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None, "root_is_not_object"
        return data, None
    except Exception as e:
        return None, f"json_parse_error: {e}"


def extract_lang_sections(data: Dict[str, Any]) -> List[str]:
    langs: List[str] = []
    for k, v in data.items():
        if LANG_KEY_RE.match(k) and isinstance(v, dict):
            langs.append(k)
    langs.sort()
    return langs


def placeholders_in(value: Any) -> Set[str]:
    if not isinstance(value, str):
        return set()
    return set(PLACEHOLDER_RE.findall(value))


def scan_skill_dir_mentions(data: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    # Returns (lang, key, text)
    mentions: List[Tuple[str, str, str]] = []
    needles = ("Skill_dir", "SkillDir")
    for lang, block in data.items():
        if not isinstance(block, dict):
            continue
        if not LANG_KEY_RE.match(lang):
            continue
        for k, t in block.items():
            if isinstance(t, str) and any(n in t for n in needles):
                mentions.append((lang, str(k), t))
    return mentions


def check_file(path: str, *, base_lang: str, warn_skill_dir: bool) -> List[Finding]:
    findings: List[Finding] = []

    data, err = load_json(path)
    if err:
        findings.append(Finding(severity="error", file=path, kind="json_parse", detail={"error": err}))
        return findings
    assert data is not None

    langs = extract_lang_sections(data)
    if len(langs) < 2:
        # Not an i18n bundle (or only one lang); skip.
        return findings

    base = base_lang if base_lang in langs else langs[0]

    base_block = data.get(base)
    if not isinstance(base_block, dict):
        findings.append(Finding(severity="error", file=path, kind="base_lang_missing_or_invalid", lang=base))
        return findings

    base_keys = set(base_block.keys())

    # Key set mismatches
    for lg in langs:
        block = data.get(lg)
        if not isinstance(block, dict):
            findings.append(Finding(severity="error", file=path, kind="lang_block_invalid", lang=lg))
            continue
        keys = set(block.keys())
        if keys != base_keys:
            findings.append(
                Finding(
                    severity="error",
                    file=path,
                    kind="key_mismatch",
                    lang=lg,
                    detail={
                        "base": base,
                        "missing": sorted(base_keys - keys),
                        "extra": sorted(keys - base_keys),
                    },
                )
            )

    # Placeholder mismatches (only for keys that exist in both)
    base_ph = {k: placeholders_in(v) for k, v in base_block.items()}
    for lg in langs:
        if lg == base:
            continue
        block = data.get(lg)
        if not isinstance(block, dict):
            continue
        for k in sorted(base_keys & set(block.keys())):
            cur_ph = placeholders_in(block.get(k))
            if cur_ph != base_ph.get(k, set()):
                findings.append(
                    Finding(
                        severity="error",
                        file=path,
                        kind="placeholder_mismatch",
                        lang=lg,
                        key=k,
                        detail={
                            "base": base,
                            "base_placeholders": sorted(base_ph.get(k, set())),
                            "cur_placeholders": sorted(cur_ph),
                            "text": block.get(k),
                        },
                    )
                )

    if warn_skill_dir:
        for lg, k, t in scan_skill_dir_mentions(data):
            findings.append(
                Finding(
                    severity="warning",
                    file=path,
                    kind="suspicious_skill_dir_mention",
                    lang=lg,
                    key=k,
                    detail={"text": t},
                )
            )

    return findings


def format_text(findings: List[Finding]) -> str:
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]

    lines: List[str] = []
    lines.append(f"errors: {len(errors)}")
    lines.append(f"warnings: {len(warnings)}")

    for f in findings:
        loc = f"{f.file}"
        if f.lang is not None:
            loc += f" [{f.lang}]"
        if f.key is not None:
            loc += f" {f.key}"
        lines.append(f"- {f.severity}: {f.kind}: {loc}")
        if f.detail:
            # Keep stable, ASCII-safe output for Windows consoles.
            lines.append("  " + json.dumps(f.detail, ensure_ascii=True, sort_keys=True))

    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    _reconfigure_stdout()

    ap = argparse.ArgumentParser(description="Check i18n JSON bundles under src/uagent/tools")
    ap.add_argument("--root", default="./src/uagent/tools", help="Root directory to scan (default: ./src/uagent/tools)")
    ap.add_argument("--recursive", action="store_true", help="Scan recursively")
    ap.add_argument("--base-lang", default="en", help="Base language key (default: en; falls back to first lang if missing)")
    ap.add_argument("--json", dest="json_out", action="store_true", help="Output findings as JSON")
    ap.add_argument("--warn-skill-dir", action="store_true", help="Warn on Skill_dir / SkillDir mentions")
    ap.add_argument("--strict", action="store_true", help="Treat warnings as failures")

    args = ap.parse_args(argv)

    files = iter_tool_json_files(args.root, args.recursive)

    all_findings: List[Finding] = []
    for p in files:
        all_findings.extend(check_file(p, base_lang=args.base_lang, warn_skill_dir=args.warn_skill_dir))

    errors = [f for f in all_findings if f.severity == "error"]
    warnings = [f for f in all_findings if f.severity == "warning"]

    if args.json_out:
        payload = {
            "root": os.path.normpath(args.root),
            "file_count": len(files),
            "errors": [f.__dict__ for f in errors],
            "warnings": [f.__dict__ for f in warnings],
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
    else:
        sys.stdout.write(format_text(all_findings))

    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
