"""Deterministic query construction for memory retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

CONTINUATION_TERMS_BY_LOCALE = {
    "ar": "تابع",
    "bn": "চালিয়ে যান",
    "cs": "pokračujte",
    "da": "fortsæt",
    "de": "weiter",
    "el": "συνεχίστε",
    "en": "continue",
    "es": "continúa",
    "fa": "ادامه دهید",
    "fi": "jatka",
    "fil": "magpatuloy",
    "fr": "continuez",
    "he": "המשך",
    "hi": "जारी रखें",
    "hu": "folytasd",
    "id": "lanjutkan",
    "it": "continua",
    "ja": "続けて",
    "ko": "계속해 주세요",
    "mn": "үргэлжлүүл",
    "mr": "सुरू ठेवा",
    "ms": "teruskan",
    "nb": "fortsett",
    "nl": "doorgaan",
    "nn": "hald fram",
    "pl": "kontynuuj",
    "pt": "continue",
    "pt_BR": "continue",
    "ro": "continuă",
    "ru": "продолжай",
    "sv": "fortsätt",
    "sw": "endelea",
    "th": "ดำเนินการต่อ",
    "tr": "devam et",
    "uk": "продовжуй",
    "vi": "tiếp tục",
    "zh_CN": "继续",
    "zh_TW": "繼續",
}
_CONTINUATION_TERMS = set(CONTINUATION_TERMS_BY_LOCALE.values()) | {
    "again",
    "go ahead",
    "next",
    "ok",
    "okay",
    "proceed",
    "same",
    "yes",
    "うん",
    "おなじ",
    "これ",
    "それ",
    "つづき",
    "はい",
    "もういちど",
    "お願いします",
    "同じ",
    "次",
    "続き",
    "進めて",
}
_PUNCTUATION_RE = re.compile(r"[^\w\u3040-\u30ff\u3400-\u9fff]+", re.UNICODE)
_SHORT_CONTINUATION_MARKERS = (
    "again",
    "continue",
    "next",
    "proceed",
    "same",
    "これ",
    "その件",
    "それ",
    "はい",
    "お願い",
    "前の",
    "続き",
    "続け",
    "進め",
    "adelante",
    "continu",
    "doorgaan",
    "fortfahr",
    "kontynu",
    "weiter",
    "дальше",
    "продолж",
    "تابع",
    "استمر",
    "जारी",
    "계속",
    "다음",
    "继续",
    "下一步",
)


def _compact(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalized_request(value: str) -> str:
    return _PUNCTUATION_RE.sub("", value.casefold())


def _is_context_poor(value: str) -> bool:
    normalized = _normalized_request(value)
    if not normalized:
        return True
    normalized_terms = {_normalized_request(term) for term in _CONTINUATION_TERMS}
    if normalized in normalized_terms:
        return True
    return len(normalized) <= 24 and any(
        _normalized_request(marker) in normalized
        for marker in _SHORT_CONTINUATION_MARKERS
    )


def _user_messages(messages: Sequence[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            text = _compact(content)
            if text:
                values.append(text)
    return values


def _agent_state(core: Any) -> dict[str, Any]:
    getter = getattr(core, "get_agent_state", None)
    if callable(getter):
        try:
            state = getter()
            if isinstance(state, dict):
                return state
        except Exception:
            pass
    state = getattr(getattr(core, "agent_state_manager", None), "state", None)
    to_dict = getattr(state, "to_dict", None)
    if callable(to_dict):
        try:
            value = to_dict()
            if isinstance(value, dict):
                return value
        except Exception:
            pass
    return {}


@dataclass(frozen=True)
class MemoryRetrievalQuery:
    """Query text plus metadata safe for diagnostics."""

    text: str
    sources: tuple[str, ...]
    context_enriched: bool

    @property
    def chars(self) -> int:
        return len(self.text)


def build_memory_retrieval_query(
    messages: Sequence[dict[str, Any]],
    core: Any,
    *,
    project: str = "",
    max_chars: int = 4_000,
) -> MemoryRetrievalQuery:
    """Build a bounded query without changing provider input.

    A concrete current request remains the sole query. A generic continuation
    request is enriched with the preceding user request and the existing task
    state so phrases such as ``continue`` or ``続き`` do not erase the retrieval
    subject. Each component stays on its own line for independent scoring.
    """
    max_chars = max(1, int(max_chars))
    user_messages = _user_messages(messages)
    latest = user_messages[-1] if user_messages else ""
    parts: list[tuple[str, str]] = [("latest_user", latest)] if latest else []
    enriched = _is_context_poor(latest)

    if enriched:
        if len(user_messages) > 1:
            parts.append(("previous_user", user_messages[-2]))
        state = _agent_state(core)
        for source, field in (
            ("agent_goal", "goal"),
            ("agent_current_step", "current_step"),
            ("agent_next_action", "next_action"),
        ):
            value = _compact(state.get(field))
            if value:
                parts.append((source, value))
        project_text = _compact(project)
        if project_text:
            parts.append(("project", project_text))

    selected: list[str] = []
    sources: list[str] = []
    seen: set[str] = set()
    for source, value in parts:
        value = _compact(value)
        key = value.casefold()
        if not value or key in seen:
            continue
        candidate = "\n".join([*selected, value])
        if len(candidate) > max_chars:
            remaining = max_chars - len("\n".join(selected)) - (1 if selected else 0)
            if source == "latest_user" and remaining > 0:
                selected.append(value[-remaining:])
                sources.append(source)
            continue
        selected.append(value)
        sources.append(source)
        seen.add(key)

    return MemoryRetrievalQuery(
        text="\n".join(selected),
        sources=tuple(sources),
        context_enriched=enriched and len(sources) > 1,
    )


__all__ = [
    "CONTINUATION_TERMS_BY_LOCALE",
    "MemoryRetrievalQuery",
    "build_memory_retrieval_query",
]
