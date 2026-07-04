from __future__ import annotations

LAZY_LOAD = True
MAX_TEXT_LENGTH = 10000
BUSY_LABEL = True

import json
import ssl
import time
import urllib.request
import urllib.parse
from typing import Any
import re

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_LOCALE_TO_GOOGLE: dict[str, str] = {
    "ja": "ja", "en": "en", "es": "es", "fr": "fr", "ko": "ko",
    "de": "de", "it": "it", "ru": "ru", "pt_br": "pt", "pt": "pt",
    "id": "id", "vi": "vi", "pl": "pl", "hi": "hi", "ar": "ar",
    "sv": "sv", "sw": "sw", "nb": "no", "nl": "nl", "fi": "fi",
    "cs": "cs", "uk": "uk", "tr": "tr", "th": "th",
    "zh_cn": "zh-CN", "zh_tw": "zh-TW",
    "bn": "bn", "fa": "fa", "mn": "mn", "mr": "mr",
    "el": "el", "he": "iw", "hu": "hu", "ro": "ro",
}

_GOOGLE_TO_LOCALE: dict[str, str] = {v: k for k, v in _LOCALE_TO_GOOGLE.items()}

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_LAST_REQUEST_TIME: float = 0

# ---------------------------------------------------------------------------
# Placeholder protection
# ---------------------------------------------------------------------------

_PH_PREFIX = "__PH_"
_BR_TAG = "[=BR=]"  # newline placeholder inside an element

_EXT_PATTERNS: dict[str, list[tuple[str, str]]] = {
    ".py": [
        (r"%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[hlL]?[dsfr]", "printf_named"),
        (r"\{([A-Za-z_][A-Za-z0-9_]*)\}", "format_named"),
    ],
    ".js": [(r"\$\{([^}]+)\}", "template_literal")],
    ".sh": [
        (r"\$\{([^}]+)\}", "shell_var_brace"),
        (r"(?<!\w)\$([A-Za-z_][A-Za-z0-9_]+)", "shell_var"),
    ],
    ".c": [(r"%[+#0\- ]*\d*(?:\.\d+)?[hlLzjt]?[diuoxXfFeEgGaAcspn]", "printf_full")],
    ".java": [
        (r"%[+#0\- ]*\d*(?:\.\d+)?[hlLzjt]?[diuoxXfFeEgGaAcspn]", "printf_full"),
        (r"\{(\d+)\}", "message_format_pos"),
    ],
    ".go": [(r"%[+#0\- ]*[vT%%tbcdoOqxXUbeEfFgGspw]", "go_printf")],
    ".rs": [(r"\{([^}]*)\}", "rust_format")],
    ".rb": [(r"%\{([^}]+)\}", "ruby_format")],
    ".php": [(r"\$([A-Za-z_][A-Za-z0-9_]*)", "php_var")],
    ".swift": [(r"\\(([^)]+)\)", "swift_interpolation")],
    ".kt": [(r"\$\{([^}]+)\}", "template_brace")],
}

_EXT_ALIASES: dict[str, str] = {
    ".ts": ".js", ".jsx": ".js", ".tsx": ".js",
    ".bash": ".sh", ".zsh": ".sh",
    ".cpp": ".c", ".h": ".c", ".hpp": ".c", ".cxx": ".c", ".hxx": ".c",
    ".pot": ".po",
}

_EXT_PATTERNS_CACHE: dict[str, list[tuple[re.Pattern, str]]] = {}

def _get_patterns(ext: str) -> list[tuple[re.Pattern, str]]:
    if ext in _EXT_PATTERNS_CACHE:
        return _EXT_PATTERNS_CACHE[ext]
    resolved = _EXT_ALIASES.get(ext, ext)
    raw = _EXT_PATTERNS.get(resolved)
    if raw is None:
        return []
    compiled = [(re.compile(p), desc) for p, desc in raw]
    _EXT_PATTERNS_CACHE[ext] = compiled
    return compiled

def _detect_extension(text: str) -> str:
    lines = text.split("\n")
    if any(re.search(r'\bdef \w+\s*\(', ln) for ln in lines[:30]): return ".py"
    if any(re.search(r'\bimport \w+', ln) for ln in lines[:10]): return ".py"
    if any(re.search(r'\bclass \w+\s*[:\(]', ln) for ln in lines[:20]): return ".py"
    if any(re.search(r'^\s*#!.*(?:bash|sh|zsh)', ln) for ln in lines[:5]): return ".sh"
    if any(re.search(r'^\s*(?:if|then|else|fi|case|esac|while|do|done)\s', ln) for ln in lines[:30]): return ".sh"
    if any(re.search(r'<\?php', ln) for ln in lines[:5]): return ".php"
    if any(re.search(r'#include\s*[<"]', ln) for ln in lines[:20]): return ".c"
    if any(re.search(r'\bpackage\s+[\w.]+;', ln) for ln in lines[:10]): return ".java"
    if any(re.search(r'\bpublic\s+(static\s+)?void\s+main\b', ln) for ln in lines[:30]): return ".java"
    if any(re.search(r'\bpackage\s+\w+\b', ln) for ln in lines[:5]): return ".go"
    if any(re.search(r'\bfn\s+\w+\s*\(', ln) for ln in lines[:20]): return ".rs"
    if any(re.search(r'\bdef\s+\w+\s*', ln) for ln in lines[:20]): return ".rb"
    if any(re.search(r'\bfun\s+\w+\s*\(', ln) for ln in lines[:20]): return ".kt"
    if any(re.search(r'\bfunction\s+\w*\s*\(', ln) for ln in lines[:20]): return ".js"
    if any(re.search(r'\b(?:const|let|var)\s+\w+\s*=', ln) for ln in lines[:10]): return ".js"
    if any(re.search(r'\bfunc\s+\w+\s*\(', ln) for ln in lines[:20]): return ".swift"
    if any(re.search(r'^msgid\s+"', ln) for ln in lines[:30]): return ".po"
    if any(re.search(r'^msgstr\s+"', ln) for ln in lines[:30]): return ".po"
    return ""

def _po_placeholder_patterns(text: str) -> list[re.Pattern]:
    """Dynamically detect placeholder patterns from msgid lines in .po text."""
    patterns: list[re.Pattern] = []
    candidates = [
        (r"%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[hlL]?[dsfr]", "printf_named"),
        (r"%[#0\- +]*\d*(?:\.\d+)?[hlLzjt]?[diuoxXfFeEgGaAcspn]", "printf_full"),
        (r"\{([A-Za-z_][A-Za-z0-9_]*)\}", "format_named"),
        (r"\{(\d+)\}", "format_pos"),
        (r"\$\{([^}]+)\}", "template_brace"),
    ]
    for pat_str, _desc in candidates:
        pat = re.compile(pat_str)
        if pat.search(text):
            patterns.append(pat)
    return patterns


def protect_placeholders(text: str) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}
    seen: dict[str, str] = {}
    idx = 0
    detected = _detect_extension(text)
    if detected == ".po":
        # .po: dynamically detect placeholders from msgid lines
        msgid_lines = []
        for ln in text.split("\n"):
            if ln.startswith("msgid "):
                m = re.search(r'^msgid\s+"(.*)"', ln)
                if m:
                    msgid_lines.append(m.group(1))
        combined = "\n".join(msgid_lines)
        patterns = _po_placeholder_patterns(combined)
    elif detected:
        patterns = _get_patterns(detected)
    else:
        # Plain text fallback: protect common placeholders even without code detection.
        # Google Translate tends to translate {xxx} placeholder names (e.g. {path} -> {パス})
        # so we must protect them proactively.
        patterns = _po_placeholder_patterns(text)
    
    def _replacer(m: re.Match) -> str:
        nonlocal idx
        orig = m.group(0)
        if orig in seen:
            return seen[orig]
        token = f"{_PH_PREFIX}{idx}"
        idx += 1
        mapping[token] = orig
        seen[orig] = token
        return token
    
    for pat in patterns:
        text = pat.sub(_replacer, text)
    return text, mapping

def restore_placeholders(text: str, mapping: dict[str, str]) -> str:
    for token, original in mapping.items():
        text = text.replace(token, original)
    return text

def _translate(text: str, target_lang: str, source_lang: str | None = None) -> tuple[str, str | None]:
    global _LAST_REQUEST_TIME
    now = time.time()
    since_last = now - _LAST_REQUEST_TIME
    if since_last < 0.5:
        time.sleep(0.5 - since_last)
    params = {
        "client": "gtx",
        "sl": source_lang if source_lang else "auto",
        "tl": target_lang,
        "dt": "t",
        "q": text,
    }
    url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            parts: list[str] = []
            for segment in data[0]:
                if segment[0]:
                    parts.append(segment[0])
            translated = "".join(parts)
            detected_raw = data[2] if len(data) > 2 and isinstance(data[2], str) else None
            detected = _GOOGLE_TO_LOCALE.get(detected_raw, detected_raw) if detected_raw else None
            _LAST_REQUEST_TIME = time.time()
            return translated, detected
    except Exception as e:
        raise RuntimeError(f"Translation request failed: {e}")


TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "tool_genre": "devel",
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "translate_text",
        "description": _(
            "tool.description",
            default="Translate one or more texts using Google Translate. Supports 30+ languages. Multiple texts are joined and translated as a single block to preserve context. Max 10000 characters per element. Do NOT truncate text before sending; the API handles long text natively. When protect_placeholders is enabled (default), various placeholder types (%(name)s, {name}, ${name}, etc.) are protected from translation if the file type is auto-detected from content.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["translate", "translation", "google translate", "language"],
        ),
        "x_search_terms_en": [
        "translate",
        "translation",
        "google translate",
        "language",
        "i18n",
        "localization",
    ],
        "parameters": {
            "type": "object",
            "properties": {
                "texts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.texts.description",
                        default="Array of text strings to translate (max 10000 characters each). Send full text without truncation; the API handles length natively. Texts are joined and translated as a single block (context preserved).",
                    ),
                },
                "target_lang": {
                    "type": "string",
                    "description": _(
                        "param.target_lang.description",
                        default="Target language code (e.g. ja, en, zh_CN, pt_BR, fr, de, es, ko).",
                    ),
                },
                "source_lang": {
                    "type": "string",
                    "description": _(
                        "param.source_lang.description",
                        default="Source language code. Auto-detected if omitted.",
                    ),
                },
                "protect_placeholders": {
                    "type": "boolean",
                    "description": _(
                        "param.protect_placeholders.description",
                        default="If true, protect placeholders (auto-detected from content) from being translated. Default: true.",
                    ),
                },
            },
            "required": ["texts", "target_lang"],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    raw_texts = args.get("texts")
    if raw_texts is None or not isinstance(raw_texts, list) or len(raw_texts) == 0:
        return json.dumps({"error": "texts is required (non-empty array)"}, ensure_ascii=False)

    target_lang = str(args.get("target_lang") or "").strip()
    source_lang = str(args.get("source_lang") or "").strip() or None
    protect = args.get("protect_placeholders")

    if not target_lang:
        return json.dumps({"error": "target_lang is required"}, ensure_ascii=False)

    target_norm = target_lang.lower().replace("-", "_")
    google_target = _LOCALE_TO_GOOGLE.get(target_norm)
    if google_target is None:
        return json.dumps({"error": f"Unsupported target language: {target_lang}"}, ensure_ascii=False)

    google_source: str | None = None
    if source_lang:
        source_norm = source_lang.lower().replace("-", "_")
        google_source = _LOCALE_TO_GOOGLE.get(source_norm)
        if google_source is None:
            return json.dumps({"error": f"Unsupported source language: {source_lang}"}, ensure_ascii=False)

    # ---------------------------------------------------------------
    # Batch: protect each element, join with \n, single API call
    # ---------------------------------------------------------------
    protected_parts: list[str] = []
    mappings: list[dict[str, str]] = []

    for i, text in enumerate(raw_texts):
        text = str(text).strip()
        if not text:
            protected_parts.append("")
            mappings.append({})
            continue
        if len(text) > MAX_TEXT_LENGTH:
            return json.dumps({"error": f"Element {i} too long: {len(text)} characters (max {MAX_TEXT_LENGTH})"}, ensure_ascii=False)

        # Protect placeholders per element
        if protect is None or protect is True:
            protected_text, ph_mapping = protect_placeholders(text)
        else:
            protected_text, ph_mapping = text, {}

        # Escape newlines inside element so they don't become element separators
        protected_text = protected_text.replace("\n", _BR_TAG)
        protected_parts.append(protected_text)
        mappings.append(ph_mapping)

    # Join with newline (element separator)
    joined = "\n".join(protected_parts)

    try:
        translated, detected = _translate(joined, google_target, google_source)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    # Split back
    translated_lines = translated.split("\n")
    if len(translated_lines) != len(raw_texts):
        return json.dumps({
            "error": f"Line count mismatch after translation: got {len(translated_lines)}, expected {len(raw_texts)}"
        }, ensure_ascii=False)

    # Restore placeholders & internal newlines
    results: list[str] = []
    detected_lang: str | None = detected if detected else None
    for translated_line, ph_mapping in zip(translated_lines, mappings):
        line = translated_line.strip()
        line = line.replace(_BR_TAG, "\n")
        if ph_mapping:
            line = restore_placeholders(line, ph_mapping)
        results.append(line)

    result: dict[str, Any] = {"translated": results}
    if detected_lang:
        result["detected_source_lang"] = detected_lang
    return json.dumps(result, ensure_ascii=False)
