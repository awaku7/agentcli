#!/usr/bin/env python3
"""Build a safe I18N migration catalog with placeholder/code protection.

This tool extracts Japanese literals, masks placeholders and code-like spans,
and emits a reviewable 38-locale catalog. It never rewrites Python source or
claims that a protected code fragment has been translated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

LOCALES = (
    "en", "ar", "bn", "cs", "da", "de", "el", "es", "fa", "fi", "fil",
    "fr", "he", "hi", "hu", "id", "it", "ja", "ko", "mn", "mr", "ms",
    "nb", "nl", "nn", "pl", "pt", "pt_BR", "ro", "ru", "sv", "sw", "th",
    "tr", "uk", "vi", "zh_CN", "zh_TW",
)

# Keep placeholders, format strings, URLs, environment variables, and code
# fragments byte-for-byte identical during translation.
PROTECTED_RE = re.compile(
    r"(?:"
    r"\{\{.*?\}\}|\{[A-Za-z_][A-Za-z0-9_.-]*(?:![rsa])?(?::[^{}]*)?\}"
    r"|%\([A-Za-z_][A-Za-z0-9_]*\)[#0 +\-]?[0-9]*(?:\.[0-9]+)?[a-zA-Z]"
    r"|%[#0 +\-]?[0-9]*(?:\.[0-9]+)?[a-zA-Z]"
    r"|\$\{[^{}]+\}"
    r"|https?://[^\s)]+"
    r"|\b(?:UAGENT|AWS|Azure|GCP|API|JSON|HTTP|HTTPS|URL|UUID|UUIDs)\b"
    r")"
)
CODE_MARKERS = (
    "\nimport ", "\nfrom ", "def ", "class ", "async def ", "{\n", "\\nimport ",
    '"type":', "#!/", "__main__", "regex", "re.compile",
)


def key_for(text: str) -> str:
    return "auto." + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def protect(text: str) -> tuple[str, list[dict[str, str]], str]:
    tokens: list[dict[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        index = len(tokens)
        token = f"__UAG_PROTECTED_{index}__"
        tokens.append({"token": token, "value": match.group(0)})
        return token

    masked = PROTECTED_RE.sub(replace, text)
    risk = "code_or_template" if any(marker in text for marker in CODE_MARKERS) else "plain_text"
    return masked, tokens, risk


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a protected I18N migration catalog.")
    parser.add_argument("--report", type=Path, default=Path("outputs/i18n_audit.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/i18n_migration_catalog.json"))
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    entries: dict[str, dict[str, object]] = {}
    for item in report.get("python_japanese_literals", []):
        text = item.get("text")
        if not isinstance(text, str) or text.startswith("<parse error"):
            continue
        key = key_for(text)
        masked, protected, risk = protect(text)
        entry = entries.setdefault(
            key,
            {
                "source_ja": text,
                "source_masked": masked,
                "english": "",
                "translations": {locale: "" for locale in LOCALES if locale != "ja"},
                "protected_tokens": protected,
                "risk": risk,
                "locations": [],
            },
        )
        entry["locations"].append(
            {"file": item.get("file"), "line": item.get("line"), "context": item.get("context")}
        )

    catalog = {
        "schema": 2,
        "status": "translation_required",
        "placeholder_protection": {
            "enabled": True,
            "token_pattern": "__UAG_PROTECTED_N__",
            "restore_after_translation": True,
        },
        "locales": list(LOCALES),
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} protected literals to {args.output}")
    print(f"code/template entries: {sum(v['risk'] == 'code_or_template' for v in entries.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
