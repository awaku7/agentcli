"""Secret masking helpers for logs and tool traces.

Keep this module free of higher-layer imports (tools/LLM) so both
``uagent.core`` and ``uagent.tools`` can reuse it safely.
"""

from __future__ import annotations

import json
import re
from typing import Any

SECRET_MASK = "********"

# Key names that look like secrets.
# Prefer compound forms (password/token/secret/...) over bare substrings
# so keys like session_action / session_id are not over-masked.
_SECRET_KEY_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in (
        r"pass(word|wd|code)?$",
        r"(^|[_-])pass(word|wd|code)?([_-]|$)",
        r"(^|[_-])pwd([_-]|$)",
        r"(^|[_-])token([_-]|$)",
        r"(^|[_-])secret([_-]|$)",
        r"api[_-]?key",
        r"access[_-]?key",
        r"private[_-]?key",
        r"(^|[_-])bearer([_-]|$)",
        r"(^|[_-])authorization([_-]|$)",
        r"auth[_-]?token",
        r"credential",
        r"(^|[_-])cookie([_-]|$)",
        r"session[_-]?(key|token|secret|cookie)",
        r"(^|[_-])sas([_-]|$)",
        r"(^|[_-])signature([_-]|$)",
        r"user[_-]?reply",  # raw answer for human_ask
    )
]

# Boolean / flag keys that contain "password" but are not secret values.
_SECRET_KEY_ALLOWLIST = frozenset(
    {
        "is_password",
        "use_password",
        "enable_password",
        "mask",
        "session_id",
        "session_action",
    }
)

# Selector / field identifiers that indicate a password-like input.
_PASSWORD_FIELD_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in (
        r"password",
        r"passwd",
        r"passcode",
        r"pwd",
        r"secret",
        r"credential",
        r"loginpassword",
        r"current[_-]?password",
        r"new[_-]?password",
        r"confirm[_-]?password",
        r"type\s*=\s*['\"]?password['\"]?",
        r"input\[type\s*=\s*['\"]?password['\"]?\]",
    )
]

# Browser action types whose "value" may hold typed secrets.
_BROWSER_SECRET_ACTION_TYPES = frozenset(
    {
        "fill",
        "keyboard_type",
        "type",
        "press_sequentially",
    }
)


def looks_like_secret_key(key: str) -> bool:
    """Return True if *key* looks like a secret-bearing field name."""
    if not key:
        return False
    # Normalize camelCase / PascalCase to snake_case for matching.
    ks = (
        re.sub(
            r"([a-z0-9])([A-Z])",
            lambda m: m.group(1) + "_" + m.group(2),
            str(key),
        )
        .replace("-", "_")
        .lower()
    )
    if ks in _SECRET_KEY_ALLOWLIST:
        return False
    return any(p.search(ks) for p in _SECRET_KEY_PATTERNS)


def looks_like_password_field(text: str | None) -> bool:
    """Return True if a selector / label / name looks password-related."""
    if not text:
        return False
    s = str(text)
    return any(p.search(s) for p in _PASSWORD_FIELD_PATTERNS)


def mask_value(v: Any) -> Any:
    """Replace a secret value with a fixed mask token."""
    if v is None:
        return None
    return SECRET_MASK


_INLINE_SECRET_RE = re.compile(
    r"(?i)(\b(?:password|passwd|passcode|pwd|token|secret|api[_-]?key|"
    r"access[_-]?key|private[_-]?key|authorization|bearer|credential|"
    r"cookie|signature|nsec)\b[\"']?\s*[:=]\s*)([\"']?)([^\"'&\s,};]+)",
)
_BEARER_RE = re.compile(
    r"(?i)(\bbearer\s+)([A-Za-z0-9._~+/-]+=*)",
)
_URL_PASSWORD_RE = re.compile(
    r"(://[^/@\s:]+:)([^/@\s]+)(@)",
)


def _mask_inline_secrets(text: str) -> str:
    """Mask secret-looking values embedded in otherwise generic strings."""
    text = _INLINE_SECRET_RE.sub(r"\1\2" + SECRET_MASK, text)
    text = _BEARER_RE.sub(r"\1" + SECRET_MASK, text)
    text = _URL_PASSWORD_RE.sub(r"\1" + SECRET_MASK + r"\3", text)
    return text


def _mask_browser_action(action: dict[str, Any]) -> dict[str, Any]:
    """Mask secret-bearing fields inside a single browser action dict."""
    out = dict(action)
    a_type = str(out.get("type") or "").lower()

    # fill / keyboard_type: mask value when selector or name looks password-like
    if a_type in _BROWSER_SECRET_ACTION_TYPES:
        selector = out.get("selector")
        name = out.get("name")
        label = out.get("label")
        if (
            looks_like_password_field(selector)
            or looks_like_password_field(name)
            or looks_like_password_field(label)
            or looks_like_secret_key(str(selector or ""))
        ):
            if "value" in out:
                out["value"] = mask_value(out.get("value"))

    # http auth style fields if present on any action
    for k in list(out.keys()):
        if looks_like_secret_key(str(k)):
            out[k] = mask_value(out[k])
    return out


def mask_args(args: Any) -> Any:
    """Recursively walk arguments and mask secret values.

    Also understands browser_playwright-style ``actions`` lists:
    if an action is ``fill``/``keyboard_type`` and its selector looks
    password-related, the ``value`` is masked even though the key is
    just ``value``.
    """
    if isinstance(args, dict):
        out: dict[str, Any] = {}
        for k, v in args.items():
            ks = str(k)
            if looks_like_secret_key(ks):
                out[k] = mask_value(v)
            elif ks == "actions" and isinstance(v, list):
                masked_actions: list[Any] = []
                for item in v:
                    if isinstance(item, dict):
                        masked_actions.append(_mask_browser_action(item))
                    else:
                        masked_actions.append(mask_args(item))
                out[k] = masked_actions
            else:
                out[k] = mask_args(v)
        return out
    if isinstance(args, list):
        return [mask_args(item) for item in args]
    if isinstance(args, str):
        args = _mask_inline_secrets(args)
        if len(args) > 300:
            return args[:20] + "...(truncated)..." + args[-20:]
    return args


def mask_tool_call_arguments_json(arguments: str | None) -> str:
    """Mask secrets inside a tool-call ``arguments`` JSON string.

    Returns the original string if it is not valid JSON.
    """
    if not arguments or not isinstance(arguments, str):
        return arguments or ""
    try:
        parsed = json.loads(arguments)
    except Exception:
        # Best-effort fallback for non-JSON / partial payloads:
        # mask fill value when selector looks password-like.
        return _mask_password_fill_in_text(arguments)
    if not isinstance(parsed, (dict, list)):
        return arguments
    masked = mask_args(parsed)
    try:
        return json.dumps(masked, ensure_ascii=False)
    except Exception:
        return arguments


_FILL_PASSWORD_VALUE_RE = re.compile(
    r'("type"\s*:\s*"(?:fill|keyboard_type|type)"\s*,(?:(?!"type"\s*:).)*?'
    r'"(?:selector|name|label)"\s*:\s*"[^"]*(?:password|passwd|pwd|secret|credential)[^"]*"'
    r'(?:(?!"type"\s*:).)*?"value"\s*:\s*")([^"]*)(")',
    re.IGNORECASE | re.DOTALL,
)


def _mask_password_fill_in_text(text: str) -> str:
    """Best-effort regex mask for password fill values in raw text/JSON."""
    if not text:
        return text
    return _FILL_PASSWORD_VALUE_RE.sub(r"\1" + SECRET_MASK + r"\3", text)


def mask_message(obj: Any) -> Any:
    """Recursively mask sensitive information for logging.

    Handles:
    - human_ask password replies (``display_reply == [SECRET]``)
    - secret-looking keys (password/token/...)
    - browser_playwright fill values for password-like selectors
    - tool_calls[].function.arguments JSON strings
    """
    if isinstance(obj, dict):
        new_dict: dict[str, Any] = {}
        for k, v in obj.items():
            ks = str(k)

            # Fast human_ask detection: sub-string check before costly json.loads
            if (
                ks == "content"
                and isinstance(v, str)
                and v[:1] == "{"
                and v[-1:] == "}"
                and "human_ask" in v
            ):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, dict) and parsed.get("tool") == "human_ask":
                        if parsed.get("display_reply") == "[SECRET]":
                            parsed["user_reply"] = SECRET_MASK
                        v = json.dumps(parsed, ensure_ascii=False)
                except Exception:
                    pass
                new_dict[k] = mask_message(v)
                continue

            # tool call arguments are often a JSON string
            if ks == "arguments" and isinstance(v, str):
                new_dict[k] = mask_tool_call_arguments_json(v)
                continue

            if looks_like_secret_key(ks):
                new_dict[k] = mask_value(v)
                continue

            if ks == "actions" and isinstance(v, list):
                new_dict[k] = mask_args({ks: v})[ks]
                continue

            new_dict[k] = mask_message(v)
        return new_dict
    if isinstance(obj, list):
        return [mask_message(x) for x in obj]
    return obj
