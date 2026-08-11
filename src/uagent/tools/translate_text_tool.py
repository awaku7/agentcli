from __future__ import annotations

LAZY_LOAD = True
MAX_TEXT_LENGTH = 10000
BUSY_LABEL = True

import json
import os
import re
import ssl
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir, make_backup_before_overwrite

_ = make_tool_translator(__file__)


def _error_json(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


_LOCALE_TO_GOOGLE: dict[str, str] = {
    "ja": "ja",
    "en": "en",
    "es": "es",
    "fr": "fr",
    "ko": "ko",
    "de": "de",
    "it": "it",
    "ru": "ru",
    "pt_br": "pt",
    "pt": "pt",
    "id": "id",
    "vi": "vi",
    "pl": "pl",
    "hi": "hi",
    "ar": "ar",
    "sv": "sv",
    "sw": "sw",
    "nb": "no",
    "nl": "nl",
    "fi": "fi",
    "cs": "cs",
    "uk": "uk",
    "tr": "tr",
    "th": "th",
    "zh_cn": "zh-CN",
    "zh_tw": "zh-TW",
    "da": "da",
    "bg": "bg",
    "sr": "sr",
    "hr": "hr",
    "ms": "ms",
    "ta": "ta",
    "ur": "ur",
    "ne": "ne",
    "bn": "bn",
    "fa": "fa",
    "mn": "mn",
    "mr": "mr",
    "el": "el",
    "he": "iw",
    "hu": "hu",
    "ro": "ro",
}

# Reverse map: first locale wins for duplicate Google codes (e.g. pt_br/pt -> pt).
_GOOGLE_TO_LOCALE: dict[str, str] = {}
for _loc, _g in _LOCALE_TO_GOOGLE.items():
    _GOOGLE_TO_LOCALE.setdefault(_g, _loc)
# Prefer canonical locale tags for shared Google codes.
_GOOGLE_TO_LOCALE["pt"] = "pt"
_GOOGLE_TO_LOCALE["no"] = "nb"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_LAST_REQUEST_TIME: float = 0
_RATE_LOCK = threading.Lock()
_MYMEMORY_LAST_REQUEST_TIME: float = 0
_MYMEMORY_RATE_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Placeholder protection
# ---------------------------------------------------------------------------

_PH_PREFIX = "__PH_"
_BR_TAG = "⏎"  # newline placeholder inside an element (U+23CE)

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
    ".ts": ".js",
    ".jsx": ".js",
    ".tsx": ".js",
    ".bash": ".sh",
    ".zsh": ".sh",
    ".cpp": ".c",
    ".h": ".c",
    ".hpp": ".c",
    ".cxx": ".c",
    ".hxx": ".c",
    ".pot": ".po",
    ".md": ".md",
    ".txt": ".txt",
    ".json": ".json",
}

_EXT_PATTERNS_CACHE: dict[str, list[tuple[re.Pattern, str]]] = {}

# Encoding detection candidates (no CP932 preference).
_TEXT_ENCODING_CANDIDATES: tuple[str, ...] = (
    "utf-8-sig",
    "utf-8",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "latin-1",
)

_MAX_FILE_BYTES = 5_000_000


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


def _detect_extension(text: str, path_hint: str | None = None) -> str:
    if path_hint:
        ext = os.path.splitext(path_hint)[1].lower()
        if ext:
            if ext in _EXT_PATTERNS or ext in _EXT_ALIASES:
                return _EXT_ALIASES.get(ext, ext)
            if ext == ".po":
                return ".po"
    lines = text.split("\n")
    if any(re.search(r"\bdef \w+\s*\(", ln) for ln in lines[:30]):
        return ".py"
    if any(re.search(r"\bimport \w+", ln) for ln in lines[:10]):
        return ".py"
    if any(re.search(r"\bclass \w+\s*[:\(]", ln) for ln in lines[:20]):
        return ".py"
    if any(re.search(r"^\s*#!.*(?:bash|sh|zsh)", ln) for ln in lines[:5]):
        return ".sh"
    if any(
        re.search(r"^\s*(?:if|then|else|fi|case|esac|while|do|done)\s", ln)
        for ln in lines[:30]
    ):
        return ".sh"
    if any(re.search(r"<\?php", ln) for ln in lines[:5]):
        return ".php"
    if any(re.search(r'#include\s*[<"]', ln) for ln in lines[:20]):
        return ".c"
    if any(re.search(r"\bpackage\s+[\w.]+;", ln) for ln in lines[:10]):
        return ".java"
    if any(re.search(r"\bpublic\s+(static\s+)?void\s+main\b", ln) for ln in lines[:30]):
        return ".java"
    if any(re.search(r"\bpackage\s+\w+\b", ln) for ln in lines[:5]):
        return ".go"
    if any(re.search(r"\bfn\s+\w+\s*\(", ln) for ln in lines[:20]):
        return ".rs"
    if any(re.search(r"\bdef\s+\w+\s*", ln) for ln in lines[:20]):
        return ".rb"
    if any(re.search(r"\bfun\s+\w+\s*\(", ln) for ln in lines[:20]):
        return ".kt"
    if any(re.search(r"\bfunction\s+\w*\s*\(", ln) for ln in lines[:20]):
        return ".js"
    if any(re.search(r"\b(?:const|let|var)\s+\w+\s*=", ln) for ln in lines[:10]):
        return ".js"
    if any(re.search(r"\bfunc\s+\w+\s*\(", ln) for ln in lines[:20]):
        return ".swift"
    if any(re.search(r'^msgid\s+"', ln) for ln in lines[:30]):
        return ".po"
    if any(re.search(r'^msgstr\s+"', ln) for ln in lines[:30]):
        return ".po"
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


def protect_placeholders(
    text: str, path_hint: str | None = None
) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}
    seen: dict[str, str] = {}
    idx = 0
    detected = _detect_extension(text, path_hint=path_hint)
    if detected == ".po":
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
        if not patterns:
            patterns = _po_placeholder_patterns(text)
    else:
        # Plain text fallback: protect common placeholders even without code detection.
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
        # _get_patterns returns (Pattern, desc); _po_placeholder_patterns returns Pattern.
        regex = pat[0] if isinstance(pat, tuple) else pat
        text = regex.sub(_replacer, text)
    return text, mapping


def restore_placeholders(text: str, mapping: dict[str, str]) -> str:
    # Longer tokens first to avoid prefix collisions (__PH_1 vs __PH_10).
    for token, original in sorted(
        mapping.items(), key=lambda kv: len(kv[0]), reverse=True
    ):
        text = text.replace(token, original)
    return text


# ---------------------------------------------------------------------------
# Proper-noun / fixed-term protection
# ---------------------------------------------------------------------------

# Lightweight defaults: brands, products, and tokens that machine translation
# often mangles. Voice/model ids are NOT all included; pass them via
# extra_protect_terms when needed (e.g. alloy, eve).
_DEFAULT_PROTECT_TERMS: tuple[str, ...] = (
    # products / companies
    "OpenAI",
    "Azure",
    "Google Translate",
    "Google",
    "ChatGPT",
    "Claude",
    "Anthropic",
    "Grok",
    "xAI",
    "n8n",
    "uagent",
    "uag",
    "GitHub",
    "Docker",
    "Kubernetes",
    "Playwright",
    "Nominatim",
    # model / API family tokens
    "GPT-5.4",
    "GPT-5",
    "GPT-4o",
    "GPT-4",
    "GPT",
    # tech tokens / codecs / protocols
    "BCP-47",
    "LLM",
    "TTS",
    "STT",
    "API",
    "HTTP",
    "HTTPS",
    "JSON",
    "UTF-8",
    "UTF-16",
    "SSO",
    "SAML",
    "LDAP",
    "RBAC",
    "MCP",
    "A2A",
    "mp3",
    "wav",
    "pcm",
    "opus",
    "aac",
    "flac",
    "mulaw",
    "alaw",
    # common tool/param identifiers (keep machine-readable names stable)
    "protect_terms",
    "protect_placeholders",
    "extra_protect_terms",
    "target_lang",
    "source_lang",
    "output_path",
    "response_format",
    "x_search_terms",
    "translate_text",
    "audio_speech",
    "audio_transcribe",
)


def _iter_extra_terms(raw: Any) -> list[str]:
    """Normalize extra_protect_terms from list/tuple/str/JSON-ish input."""
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        # allow comma-separated or JSON array string
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                pass
        return [p.strip() for p in re.split(r"[,;\n]", s) if p.strip()]
    if isinstance(raw, (list, tuple, set)):
        out: list[str] = []
        for x in raw:
            t = str(x).strip()
            if t:
                out.append(t)
        return out
    t = str(raw).strip()
    return [t] if t else []


def _merge_protect_terms(
    *,
    protect_terms_enabled: bool,
    extra_terms: list[str] | None = None,
) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    def _add(term: str) -> None:
        t = term.strip()
        if not t:
            return
        # Avoid protecting our own placeholder tokens.
        if t.startswith(_PH_PREFIX):
            return
        key = t.casefold()
        if key in seen:
            return
        seen.add(key)
        terms.append(t)

    if protect_terms_enabled:
        for t in _DEFAULT_PROTECT_TERMS:
            _add(t)
    for t in extra_terms or []:
        _add(t)

    # Longer first so "Google Translate" wins over "Google".
    terms.sort(key=lambda s: (-len(s), s))
    return terms


def _term_pattern(term: str) -> re.Pattern[str]:
    """Build a conservative search pattern for a fixed term.

    - Escape regex metacharacters.
    - Use ASCII word boundaries when the term starts/ends with word chars.
    - Keep matching case-sensitive (brand capitalization matters).
    """
    esc = re.escape(term)
    # Word-ish edges: letter/digit/underscore
    left = r"(?<![A-Za-z0-9_])" if re.match(r"^[A-Za-z0-9_]", term) else ""
    right = r"(?![A-Za-z0-9_])" if re.search(r"[A-Za-z0-9_]$", term) else ""
    return re.compile(left + esc + right)


def protect_fixed_terms(
    text: str,
    terms: list[str],
    *,
    start_idx: int = 0,
    existing_mapping: dict[str, str] | None = None,
) -> tuple[str, dict[str, str], int]:
    """Replace fixed terms with __PH_N tokens.

    Returns (text, mapping, next_idx). mapping maps token -> original term.
    """
    mapping: dict[str, str] = dict(existing_mapping or {})
    # reverse lookup original -> token for reuse
    seen: dict[str, str] = {v: k for k, v in mapping.items()}
    idx = int(start_idx)

    if not terms or not text:
        return text, mapping, idx

    for term in terms:
        if not term:
            continue
        # Fast path: only run regex when the exact substring exists.
        if term not in text:
            continue
        pat = _term_pattern(term)

        def _replacer(m: re.Match[str], _term: str = term) -> str:
            nonlocal idx
            orig = m.group(0)
            if orig in seen:
                return seen[orig]
            token = f"{_PH_PREFIX}{idx}"
            idx += 1
            mapping[token] = orig
            seen[orig] = token
            return token

        text = pat.sub(_replacer, text)

    return text, mapping, idx


def protect_for_translation(
    text: str,
    *,
    path_hint: str | None = None,
    protect_placeholders_enabled: bool = True,
    protect_terms_list: list[str] | None = None,
) -> tuple[str, dict[str, str]]:
    """Apply placeholder protection then fixed-term protection."""
    mapping: dict[str, str] = {}
    idx = 0
    if protect_placeholders_enabled:
        text, mapping = protect_placeholders(text, path_hint=path_hint)
        # continue index after existing tokens
        if mapping:
            nums = []
            for tok in mapping:
                m = re.match(rf"{re.escape(_PH_PREFIX)}(\d+)$", tok)
                if m:
                    nums.append(int(m.group(1)))
            idx = (max(nums) + 1) if nums else 0
    if protect_terms_list:
        text, mapping, idx = protect_fixed_terms(
            text,
            protect_terms_list,
            start_idx=idx,
            existing_mapping=mapping,
        )
    return text, mapping


# ---------------------------------------------------------------------------
# Encoding / newline helpers
# ---------------------------------------------------------------------------


def _detect_newline_from_text(text: str) -> str:
    """Return 'crlf', 'cr', or 'lf' based on decoded text (pre-normalization)."""
    if "\r\n" in text:
        return "crlf"
    if "\r" in text:
        return "cr"
    return "lf"


def _detect_newline(raw: bytes) -> str:
    """Return 'crlf', 'cr', or 'lf' based on raw file bytes (8-bit encodings)."""
    if b"\r\n" in raw:
        return "crlf"
    if b"\r" in raw:
        return "cr"
    return "lf"


def _normalize_newline_name(value: str | None) -> str | None:
    if value is None:
        return None
    v = str(value).strip().lower().replace("-", "").replace("_", "")
    if v in ("", "auto"):
        return "auto"
    if v in ("lf", "\n", "unix", "posix"):
        return "lf"
    if v in ("crlf", "\r\n", "windows", "dos", "win"):
        return "crlf"
    if v in ("cr", "\r", "mac"):
        return "cr"
    return None


def _apply_newline(text: str, newline: str) -> str:
    # text is expected to use LF internally
    if newline == "crlf":
        return text.replace("\n", "\r\n")
    if newline == "cr":
        return text.replace("\n", "\r")
    return text


def _ordered_encodings(preferred: str | None = None) -> list[str]:
    order: list[str] = []
    if preferred:
        order.append(preferred)
    for enc in _TEXT_ENCODING_CANDIDATES:
        if enc not in order:
            order.append(enc)
    return order


def _detect_text_encoding(head: bytes) -> str:
    if not head:
        return "utf-8"
    if head.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if head.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if head.startswith(b"\xfe\xff"):
        return "utf-16-be"
    # Prefer plain utf-8 over utf-8-sig when no BOM is present.
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            head.decode(enc, errors="strict")
        except UnicodeDecodeError:
            continue
        return enc
    return "utf-8"


def _decode_file_bytes(
    data: bytes, encoding: str | None = None
) -> tuple[str, str, str]:
    """Decode bytes -> (text_lf, encoding_used, newline_style)."""
    if encoding:
        candidates = _ordered_encodings(encoding)
    else:
        preferred = _detect_text_encoding(data[:8192])
        # Avoid reporting utf-8-sig for non-BOM utf-8 content.
        if preferred == "utf-8":
            candidates = ["utf-8", "latin-1"]
        else:
            candidates = _ordered_encodings(preferred)
    last_err: Exception | None = None
    for enc in candidates:
        try:
            text = data.decode(enc, errors="strict")
            # Strip UTF-16 BOM if present as character.
            if text.startswith("\ufeff"):
                text = text[1:]
            newline = _detect_newline_from_text(text)
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            return text, enc, newline
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise ValueError(
        _(
            "err.decode_failed",
            default="Failed to decode file with encoding candidates (last error: {error})",
        ).format(error=last_err)
    )


def _read_input_file(
    path: str, encoding: str | None = None
) -> tuple[str, str, str, str]:
    """Return (text_lf, abs_path, encoding_used, newline_style)."""
    safe_path = ensure_within_workdir(path)
    if not os.path.isfile(safe_path):
        raise FileNotFoundError(
            _("err.file_not_found", default="File not found: {path}").format(
                path=safe_path
            )
        )
    size = os.path.getsize(safe_path)
    if size > _MAX_FILE_BYTES:
        raise ValueError(
            _(
                "err.file_too_large",
                default="File too large: {size} bytes (max {max_bytes})",
            ).format(size=size, max_bytes=_MAX_FILE_BYTES)
        )
    with open(safe_path, "rb") as f:
        data = f.read()
    text, enc_used, newline = _decode_file_bytes(data, encoding=encoding)
    return text, safe_path, enc_used, newline


def _write_output_file(
    path: str,
    text_lf: str,
    *,
    encoding: str,
    newline: str,
    overwrite: bool,
) -> tuple[str, str | None]:
    """Write translated text. Returns (abs_path, backup_path|None)."""
    safe_path = ensure_within_workdir(path)
    existed = os.path.exists(safe_path)
    if existed and not overwrite:
        raise FileExistsError(
            _(
                "err.file_exists",
                default="File already exists: {path}",
            ).format(path=safe_path)
        )
    backup_path: str | None = None
    if existed and overwrite:
        backup_path = make_backup_before_overwrite(safe_path)

    parent = os.path.dirname(safe_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    payload = _apply_newline(text_lf, newline)
    # newline="" keeps exact line endings we already applied.
    with open(safe_path, "w", encoding=encoding, newline="") as f:
        f.write(payload)
    return safe_path, backup_path


# ---------------------------------------------------------------------------
# Translation core
# ---------------------------------------------------------------------------


def _translate(
    text: str, target_lang: str, source_lang: str | None = None
) -> tuple[str, str | None]:
    # Google Translate exposes Norwegian Bokmal (`no`/`nb`) but not
    # Norwegian Nynorsk (`nn`). Route Nynorsk through MyMemory, which has
    # exact `nn-NO` translation-memory entries and a free public endpoint.
    if target_lang.lower().replace("-", "_") in {"nn", "nn_no"}:
        return _translate_mymemory(text, source_lang)

    global _LAST_REQUEST_TIME
    with _RATE_LOCK:
        now = time.time()
        since_last = now - _LAST_REQUEST_TIME
        if since_last < 0.5:
            time.sleep(0.5 - since_last)
        # Reserve the slot before releasing the lock so concurrent callers wait.
        _LAST_REQUEST_TIME = time.time()
    params = {
        "client": "gtx",
        "sl": source_lang if source_lang else "auto",
        "tl": target_lang,
        "dt": "t",
        "q": text,
    }
    url = (
        "https://translate.googleapis.com/translate_a/single?"
        + urllib.parse.urlencode(params)
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            parts: list[str] = []
            for segment in data[0]:
                if segment[0]:
                    parts.append(segment[0])
            translated = "".join(parts)
            detected_raw = (
                data[2] if len(data) > 2 and isinstance(data[2], str) else None
            )
            detected = (
                _GOOGLE_TO_LOCALE.get(detected_raw, detected_raw)
                if detected_raw
                else None
            )
            return translated, detected
    except Exception as e:
        raise RuntimeError(f"Translation request failed: {e}")


def _translate_mymemory(
    text: str, source_lang: str | None = None
) -> tuple[str, str | None]:
    """Translate Nynorsk through MyMemory's public endpoint.

    MyMemory may return a Bokmal match even for an ``nn-NO`` request when no
    exact Nynorsk memory entry exists. Prefer an exact ``nn-NO`` match when
    available; otherwise use the service's best result as a fallback.
    """
    global _MYMEMORY_LAST_REQUEST_TIME
    with _MYMEMORY_RATE_LOCK:
        now = time.time()
        since_last = now - _MYMEMORY_LAST_REQUEST_TIME
        if since_last < 1.0:
            time.sleep(1.0 - since_last)
        _MYMEMORY_LAST_REQUEST_TIME = time.time()

    source = (source_lang or "en").strip().lower().replace("_", "-")
    if source in {"", "auto"}:
        source = "en"
    params = {"q": text, "langpair": f"{source}|nn-NO"}
    url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "uagentcli/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, dict) or data.get("responseStatus") not in (None, 200):
            detail = data.get("responseDetails") if isinstance(data, dict) else data
            raise RuntimeError(f"MyMemory response error: {detail}")

        translated: str | None = None
        matches = data.get("matches")
        if isinstance(matches, list):
            for match in matches:
                if not isinstance(match, dict):
                    continue
                target = str(match.get("target") or "").lower().replace("_", "-")
                candidate = match.get("translation")
                if target == "nn-no" and isinstance(candidate, str) and candidate:
                    translated = candidate
                    break
        if translated is None:
            response_data = data.get("responseData")
            if isinstance(response_data, dict):
                candidate = response_data.get("translatedText")
                if isinstance(candidate, str):
                    translated = candidate
        if not translated:
            raise RuntimeError("MyMemory returned no translation")
        return translated, "nn"
    except Exception as e:
        raise RuntimeError(f"MyMemory translation request failed: {e}")


def _adjust_split_away_from_placeholder(text: str, split_at: int) -> int:
    """Move split_at left if it would cut inside a __PH_N token."""
    if split_at <= 0 or split_at >= len(text):
        return split_at
    left = text[:split_at]
    idx = left.rfind(_PH_PREFIX)
    if idx < 0:
        return split_at
    m = re.match(r"__PH_\d+", text[idx:])
    if not m:
        # Incomplete prefix like "__PH_" or "__PH".
        return idx
    token_end = idx + len(m.group(0))
    if split_at < token_end:
        return idx
    return split_at


def _chunk_text(text: str, max_len: int = MAX_TEXT_LENGTH) -> list[str]:
    """Split long text without breaking mid-line/placeholder when possible."""
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break
        window = remaining[:max_len]
        split_at = window.rfind("\n")
        if split_at < max_len // 2:
            split_at = window.rfind(" ")
        if split_at < max_len // 2:
            split_at = max_len
        else:
            split_at += 1  # keep delimiter with left chunk
        split_at = _adjust_split_away_from_placeholder(remaining, split_at)
        if split_at <= 0:
            hard = _adjust_split_away_from_placeholder(remaining, max_len)
            if hard <= 0:
                m = re.match(r"__PH_\d+", remaining)
                hard = len(m.group(0)) if m else max_len
            split_at = hard
        if split_at <= 0:
            split_at = max_len
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
    return chunks


def _is_mymemory_target(target_lang: str) -> bool:
    return target_lang.lower().replace("-", "_") in {"nn", "nn_no"}


def _translate_long(
    text: str, target_lang: str, source_lang: str | None = None
) -> tuple[str, str | None]:
    # MyMemory's public endpoint accepts at most 500 query characters.
    max_len = 450 if _is_mymemory_target(target_lang) else MAX_TEXT_LENGTH
    chunks = _chunk_text(text, max_len)
    if len(chunks) == 1:
        return _translate(chunks[0], target_lang, source_lang)
    out_parts: list[str] = []
    detected: str | None = None
    for chunk in chunks:
        if not chunk:
            out_parts.append("")
            continue
        translated, det = _translate(chunk, target_lang, source_lang)
        if detected is None and det:
            detected = det
        out_parts.append(translated)
    return "".join(out_parts), detected


def _resolve_google_lang(lang: str | None) -> str | None:
    if not lang:
        return None
    norm = lang.lower().replace("-", "_")
    mapped = _LOCALE_TO_GOOGLE.get(norm)
    return mapped if mapped is not None else lang


TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "tool_genre": "devel",
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "translate_text",
        "description": _(
            "tool.description",
            default=(
                "Translate one or more texts using Google Translate. Supports 30+ languages. "
                "Multiple texts are joined and translated as a single block to preserve context. "
                "Max 10000 characters per element for texts[]; longer file content is auto-chunked. "
                "Do NOT truncate text before sending. When protect_placeholders is enabled (default), "
                "placeholders (%(name)s, {name}, ${name}, etc.) are protected. Brand/product terms can be protected via protect_terms/extra_protect_terms. "
                "Optional path/output_path enable file-to-file translation with encoding/newline preservation."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "translate",
                "translation",
                "google translate",
                "language",
                "file translate",
            ],
        ),
        "x_search_terms_en": [
            "translate",
            "translation",
            "google translate",
            "language",
            "i18n",
            "localization",
            "file translate",
            "translate file",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "texts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.texts.description",
                        default=(
                            "Array of text strings to translate (max 10000 characters each). "
                            "Send full text without truncation. Texts are joined and translated "
                            "as a single block (context preserved). Optional when path is set."
                        ),
                    ),
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default=(
                            "Input file path to translate. When set, file content is used "
                            "instead of texts. Relative paths are resolved from workdir."
                        ),
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": _(
                        "param.output_path.description",
                        default=(
                            "Output file path for translated content. If omitted in file mode, "
                            "translated text is returned in JSON only (no write)."
                        ),
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
                        default=(
                            "If true, protect placeholders (auto-detected from content/path) "
                            "from being translated. Default: true."
                        ),
                    ),
                },
                "encoding": {
                    "type": "string",
                    "description": _(
                        "param.encoding.description",
                        default=(
                            "File encoding for read/write. If omitted, encoding is auto-detected "
                            "(BOM/utf-8/utf-16/latin-1). Output uses the same encoding as input "
                            "unless explicitly set."
                        ),
                    ),
                },
                "newline": {
                    "type": "string",
                    "description": _(
                        "param.newline.description",
                        default=(
                            "Output newline style: auto (default, preserve input), lf, crlf, or cr."
                        ),
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": _(
                        "param.overwrite.description",
                        default=(
                            "Overwrite output_path if it already exists (creates .org backup). "
                            "Default: false."
                        ),
                    ),
                },
                "protect_terms": {
                    "type": "boolean",
                    "description": _(
                        "param.protect_terms.description",
                        default=(
                            "If true, protect built-in brand/product/tech terms (OpenAI, Grok, "
                            "mp3, API, ...) from being translated. Default: true."
                        ),
                    ),
                },
                "extra_protect_terms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.extra_protect_terms.description",
                        default=(
                            "Additional fixed terms to keep unchanged (e.g. voice ids alloy/eve, "
                            "model names). Applied in addition to built-in terms when "
                            "protect_terms is true; still applied when protect_terms is false."
                        ),
                    ),
                },
            },
            "required": ["target_lang"],
        },
    },
}


def _translate_texts_batch(
    raw_texts: list[Any],
    *,
    google_target: str,
    google_source: str | None,
    protect: bool,
    path_hint: str | None = None,
    protect_terms_list: list[str] | None = None,
) -> tuple[list[str], str | None, int]:
    protected_parts: list[str] = []
    mappings: list[dict[str, str]] = []
    placeholders_count = 0

    for i, text in enumerate(raw_texts):
        text = str(text)
        if text == "":
            protected_parts.append("")
            mappings.append({})
            continue
        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError(
                f"Element {i} too long: {len(text)} characters (max {MAX_TEXT_LENGTH})"
            )

        if protect or protect_terms_list:
            protected_text, ph_mapping = protect_for_translation(
                text,
                path_hint=path_hint,
                protect_placeholders_enabled=protect,
                protect_terms_list=protect_terms_list,
            )
        else:
            protected_text, ph_mapping = text, {}
        placeholders_count += len(ph_mapping)
        protected_text = protected_text.replace("\n", _BR_TAG)
        protected_parts.append(protected_text)
        mappings.append(ph_mapping)

    if _is_mymemory_target(google_target):
        # MyMemory has a 500-character query limit and does not preserve
        # newline-separated multi-item batches reliably. Translate each item
        # independently while retaining the existing placeholder mapping.
        results: list[str] = []
        for protected_text, ph_mapping in zip(protected_parts, mappings):
            if protected_text == "":
                results.append("")
                continue
            translated, _detected = _translate_long(
                protected_text, google_target, google_source
            )
            line = translated.replace(_BR_TAG, "\n")
            if ph_mapping:
                line = restore_placeholders(line, ph_mapping)
            results.append(line)
        return results, "nn", placeholders_count

    joined = "\n".join(protected_parts)
    translated, detected = _translate_long(joined, google_target, google_source)
    translated_lines = translated.split("\n")
    if len(translated_lines) != len(raw_texts):
        raise RuntimeError(
            f"Line count mismatch after translation: got {len(translated_lines)}, expected {len(raw_texts)}"
        )

    results: list[str] = []
    for translated_line, ph_mapping in zip(translated_lines, mappings):
        line = translated_line.replace(_BR_TAG, "\n")
        if ph_mapping:
            line = restore_placeholders(line, ph_mapping)
        results.append(line)
    return results, detected, placeholders_count


def _translate_single_document(
    text: str,
    *,
    google_target: str,
    google_source: str | None,
    protect: bool,
    path_hint: str | None = None,
    protect_terms_list: list[str] | None = None,
) -> tuple[str, str | None, int]:
    """Translate a whole document with placeholder/term protection (may exceed MAX_TEXT_LENGTH)."""
    if protect or protect_terms_list:
        protected_text, ph_mapping = protect_for_translation(
            text,
            path_hint=path_hint,
            protect_placeholders_enabled=protect,
            protect_terms_list=protect_terms_list,
        )
    else:
        protected_text, ph_mapping = text, {}

    # Protect internal newlines for each chunk independently after chunking,
    # so chunk boundaries stay on real newlines.
    chunks = _chunk_text(protected_text, MAX_TEXT_LENGTH)
    out_parts: list[str] = []
    detected: str | None = None
    for chunk in chunks:
        if chunk == "":
            out_parts.append("")
            continue
        # Convert newlines inside chunk to BR tag so API doesn't alter structure badly.
        # For multi-chunk docs we translate chunk-by-chunk (not joined), so BR is optional
        # but still helps preserve blank lines.
        payload = chunk.replace("\n", _BR_TAG)
        translated, det = _translate(payload, google_target, google_source)
        if detected is None and det:
            detected = det
        restored = translated.replace(_BR_TAG, "\n")
        out_parts.append(restored)

    result = "".join(out_parts)
    if ph_mapping:
        result = restore_placeholders(result, ph_mapping)
    return result, detected, len(ph_mapping)


def run_tool(args: dict[str, Any]) -> str:
    raw_texts = args.get("texts")
    path = str(args.get("path") or "").strip() or None
    output_path = str(args.get("output_path") or "").strip() or None
    target_lang = str(args.get("target_lang") or "").strip()
    source_lang = str(args.get("source_lang") or "").strip() or None
    protect = args.get("protect_placeholders")
    protect_terms_arg = args.get("protect_terms")
    extra_terms = _iter_extra_terms(args.get("extra_protect_terms"))
    encoding_arg = str(args.get("encoding") or "").strip() or None
    newline_arg = _normalize_newline_name(args.get("newline"))
    overwrite_raw = args.get("overwrite", False)

    if not target_lang:
        return _error_json(
            _("err.target_lang_required", default="target_lang is required")
        )

    if newline_arg is None and args.get("newline") not in (None, ""):
        return _error_json(
            _(
                "err.invalid_newline",
                default="newline must be one of: auto, lf, crlf, cr",
            )
        )

    if not isinstance(overwrite_raw, bool):
        return _error_json(
            _("err.overwrite_bool", default="overwrite must be a boolean")
        )
    overwrite = bool(overwrite_raw)

    if path is None and (
        raw_texts is None or not isinstance(raw_texts, list) or len(raw_texts) == 0
    ):
        return _error_json(
            _(
                "err.texts_or_path_required",
                default="texts (non-empty array) or path is required",
            )
        )

    if path is not None and raw_texts is not None:
        return _error_json(
            _(
                "err.texts_and_path_mutex",
                default="Specify either texts or path, not both",
            )
        )

    google_target = _resolve_google_lang(target_lang) or target_lang
    google_source = _resolve_google_lang(source_lang)
    do_protect = True if protect is None else bool(protect)
    do_protect_terms = True if protect_terms_arg is None else bool(protect_terms_arg)
    terms_list = _merge_protect_terms(
        protect_terms_enabled=do_protect_terms,
        extra_terms=extra_terms,
    )

    try:
        if path is not None:
            text, source_abs, enc_used, newline_in = _read_input_file(
                path, encoding=encoding_arg
            )
            translated, detected, ph_count = _translate_single_document(
                text,
                google_target=google_target,
                google_source=google_source,
                protect=do_protect,
                path_hint=source_abs,
                protect_terms_list=terms_list or None,
            )
            out_newline = newline_in if (newline_arg in (None, "auto")) else newline_arg
            # encoding: explicit arg wins for output; else keep detected/input encoding
            out_encoding = encoding_arg or enc_used

            result: dict[str, Any] = {
                "ok": True,
                "translated": [translated],
                "source_path": source_abs,
                "chars_in": len(text),
                "chars_out": len(translated),
                "encoding": out_encoding,
                "newline": out_newline,
                "placeholders_protected": ph_count,
                "terms_protected": len(terms_list),
            }
            if detected:
                result["detected_source_lang"] = detected

            if output_path:
                out_abs, backup_path = _write_output_file(
                    output_path,
                    translated,
                    encoding=out_encoding,
                    newline=out_newline or "lf",
                    overwrite=overwrite,
                )
                result["output_path"] = out_abs
                result["backup_path"] = backup_path
            return json.dumps(result, ensure_ascii=False)

        # texts[] mode (existing behavior, with optional output_path for joined result)
        assert isinstance(raw_texts, list)
        results, detected, ph_count = _translate_texts_batch(
            raw_texts,
            google_target=google_target,
            google_source=google_source,
            protect=do_protect,
            path_hint=None,
            protect_terms_list=terms_list or None,
        )
        result = {
            "ok": True,
            "translated": results,
            "placeholders_protected": ph_count,
            "terms_protected": len(terms_list),
        }
        if detected:
            result["detected_source_lang"] = detected

        if output_path:
            # Join translated elements with LF; newline/encoding apply to file write.
            joined = "\n".join(results)
            out_encoding = encoding_arg or "utf-8"
            out_newline = "lf" if newline_arg in (None, "auto") else newline_arg
            out_abs, backup_path = _write_output_file(
                output_path,
                joined,
                encoding=out_encoding,
                newline=out_newline or "lf",
                overwrite=overwrite,
            )
            result["output_path"] = out_abs
            result["backup_path"] = backup_path
            result["encoding"] = out_encoding
            result["newline"] = out_newline
            result["chars_out"] = len(joined)
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return _error_json(str(e))
