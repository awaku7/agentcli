import re
import threading
from typing import Any, Dict, List

from .env_utils import env_get

try:
    import certifi
except Exception:
    certifi = None


_AUTO_EFFORT_LADDER = ("minimal", "low", "medium", "high", "xhigh")


def _maybe_print_certifi_where(exc: Exception) -> None:
    if certifi is None:
        print("[SSL Info] certifi is not available")
        return

    try:
        s = f"{type(exc).__name__}: {exc}".lower()
    except Exception:
        s = ""

    if not any(k in s for k in ("ssl", "tls", "cert", "certificate")):
        return

    try:
        print(f"[SSL Info] certifi.where() = {certifi.where()}")
    except Exception:
        pass


def _extract_latest_user_text(call_messages: List[Dict[str, Any]]) -> str:
    for m in reversed(call_messages or []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts: List[str] = []
            for item in c:
                if isinstance(item, dict):
                    t = item.get("type")
                    if t in ("text", "input_text", "output_text"):
                        txt = item.get("text")
                        if isinstance(txt, str) and txt.strip():
                            parts.append(txt)
            if parts:
                return "\n".join(parts)
    return ""


def _is_thinking_task(user_text: str) -> bool:
    t = (user_text or "").strip().lower()
    if not t:
        return False

    keywords = (
        "why",
        "explain",
        "analyze",
        "analysis",
        "compare",
        "design",
        "plan",
        "strategy",
        "debug",
        "refactor",
        "optimize",
        "architecture",
        "tradeoff",
        "pros",
        "cons",
        "root cause",
        "root cause",
        "investigation",
        "analysis",
        "design",
        "comparison",
        "policy",
        "strategy",
        "optimization",
        "debugging",
        "implementation",
        "fix",
        "improvement",
    )
    if any(k in t for k in keywords):
        return True

    return len(t) >= 200


def _choose_auto_effort(user_text: str) -> str:
    n = len((user_text or "").strip())
    if n >= 900:
        return "high"
    if n >= 450:
        return "medium"
    if n >= 120:
        return "low"
    return "minimal"


def _bump_effort(effort: str | None) -> str | None:
    if effort not in _AUTO_EFFORT_LADDER:
        return "minimal"
    idx = _AUTO_EFFORT_LADDER.index(effort)
    if idx >= len(_AUTO_EFFORT_LADDER) - 1:
        return None
    return _AUTO_EFFORT_LADDER[idx + 1]


def _auto_low_quality(user_text: str, assistant_text: str) -> bool:
    """Heuristic detector for unusable assistant outputs (for auto-retry).

    Goals:
    - Be as language-agnostic as possible.
    - Prefer structural checks (empty/too short/format mismatch) over phrase lists.
    - Keep a small set of broad refusal/unknown patterns as a backstop.

    This is intentionally conservative: it is used only to decide a single retry.
    """

    a = (assistant_text or "").strip()
    if not a:
        return True

    if len(a) < 8:
        return True

    al = a.lower()

    ut = (user_text or "").lower()
    if "json" in ut:
        s = a.lstrip()
        if not (s.startswith("{") or s.startswith("[") or "```json" in s.lower()):
            return True

    refusal_patterns = (
        r"\b(i\s*(can't|cannot)|unable\s+to|won't)\b",
        r"\b(i\s+do\s+not\s+know|i\s+don't\s+know|dont\s+know|not\s+sure)\b",
        r"\b(as\s+an\s+ai|i\s+cannot\s+access|i\s+can't\s+access|no\s+access)\b",
        r"\b(i\s+can't\s+help\s+with|i\s+cannot\s+help\s+with|i\s+can't\s+assist|i\s+cannot\s+assist)\b",
        r"\b(i\s+can't\s+comply|i\s+cannot\s+comply|not\s+able\s+to\s+comply)\b",
        r"\b(sorry,?\s+i\s+(can't|cannot))\b",
        r"(i\s*(?:can't|cannot)|unable\s+to|won't|i\s+don't\s+know|not\s+sure|unknown|no\s+idea)",
    )

    for pat in refusal_patterns:
        try:
            if re.search(pat, al, flags=re.IGNORECASE):
                return True
        except Exception:
            continue

    return False


def _effectively_empty_text(s: Any) -> bool:
    if s is None:
        return True
    if not isinstance(s, str):
        try:
            s = str(s)
        except Exception:
            return True
    t = s.strip()
    for cp in (
        0x200B,
        0x200C,
        0x200D,
        0xFEFF,
        0x00A0,
        0x2060,
        0x2063,
        0x00AD,
    ):
        t = t.replace(chr(cp), "")
    try:
        import unicodedata

        t = "".join(
            ch
            for ch in t
            if unicodedata.category(ch) not in ("Cf", "Zs", "Zl", "Zp", "Cc")
        )
    except Exception:
        pass
    return t == ""


def _env_default_on(name: str) -> bool:
    v = (env_get(name, "") or "").strip().lower()
    return v not in ("0", "false", "no", "off")


def _env_default_true(name: str, default: bool = True) -> bool:
    v = (env_get(name, "") or "").strip().lower()
    if v == "":
        return bool(default)
    return v in ("1", "true", "yes", "on")


def _call_maybe_thread(fn: Any, *, use_llm_thread: bool) -> Any:
    """Run a potentially-blocking LLM call.

    When UAGENT_LLM_IN_THREAD is enabled (default), run the call in a daemon
    thread so the main thread can respond to Ctrl-C more promptly.

    Note: This does not guarantee immediate network cancel; timeouts are the
    primary safety net.
    """

    if not use_llm_thread:
        return fn()

    box: Dict[str, Any] = {"res": None, "exc": None}

    def _runner() -> None:
        try:
            box["res"] = fn()
        except BaseException as e:
            box["exc"] = e

    th = threading.Thread(target=_runner, daemon=True, name="uagent-llm-call")
    th.start()

    while th.is_alive():
        th.join(0.05)

    if box.get("exc") is not None:
        raise box["exc"]

    return box.get("res")
