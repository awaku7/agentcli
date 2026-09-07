"""Provider-neutral Tool Result records and projections.

This module contains the first layer of the context-management design.  It is
intentionally free of provider SDKs and persistence side effects: callers can
use the projections for the LLM, UI/remote clients, and durable history
independently.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .tool_result_persistence import sanitize_binary_payload

ResultClass = Literal["small", "large", "huge"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _derive_summary(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("summary", "message", "status", "next_action"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()[:500]
        keys = ", ".join(str(key) for key in list(value)[:12])
        return f"object keys: {keys}" if keys else "empty object"
    if isinstance(value, list):
        return f"list with {len(value)} items"
    text = str(value or "").strip()
    return text[:500]


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _bounded_preview(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    marker = f"\n[retrieved context truncated: original length={len(text)}]\n"
    if limit <= len(marker):
        return marker[:limit]
    remaining = limit - len(marker)
    head_len = (remaining + 1) // 2
    tail_len = remaining - head_len
    return text[:head_len] + marker + (text[-tail_len:] if tail_len else "")


@dataclass(frozen=True)
class ToolResultRecord:
    """Metadata and bounded projections for one tool result."""

    result_id: str
    tool_name: str
    size_bytes: int
    result_class: ResultClass
    created_at: str
    session_id: str = ""
    task_id: str = ""
    summary: str = ""
    artifact_ref: str = ""
    importance: str = "normal"
    evictable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe metadata representation."""
        return asdict(self)


@dataclass(frozen=True)
class ToolResultProjections:
    """The three independent representations of a tool result."""

    llm_context: str
    ui_remote: Any
    persistent_history: Any


class ContextResultManager:
    """Classify results and produce provider-neutral context projections."""

    def __init__(
        self,
        *,
        inline_limit_chars: int = 12_000,
        large_limit_chars: int = 100_000,
        max_preview_rows: int = 500,
    ) -> None:
        if inline_limit_chars < 0 or large_limit_chars < inline_limit_chars:
            raise ValueError("result limits must be non-negative and ordered")
        if max_preview_rows < 0:
            raise ValueError("max_preview_rows must be non-negative")
        self.inline_limit_chars = inline_limit_chars
        self.large_limit_chars = large_limit_chars
        self.max_preview_rows = max_preview_rows

    def process(
        self,
        value: Any,
        *,
        tool_name: str,
        session_id: str = "",
        task_id: str = "",
        result_id: str | None = None,
        summary: str = "",
        artifact_ref: str = "",
        importance: str = "normal",
        evictable: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[ToolResultRecord, ToolResultProjections]:
        """Return a record and isolated LLM/UI/history projections.

        Artifact registration is deliberately handled by the caller.  Passing
        ``artifact_ref`` lets this manager represent an already persisted
        artifact without coupling classification to storage.
        """
        text = _stringify(value)
        size_bytes = len(text.encode("utf-8", errors="replace"))
        result_class = self._classify(len(text))
        effective_summary = str(summary or "").strip() or _derive_summary(value)
        record = ToolResultRecord(
            result_id=result_id or uuid.uuid4().hex,
            session_id=session_id,
            task_id=task_id,
            tool_name=tool_name,
            size_bytes=size_bytes,
            result_class=result_class,
            created_at=_utc_now(),
            summary=effective_summary,
            artifact_ref=artifact_ref,
            importance=importance,
            evictable=evictable,
            metadata=dict(metadata or {}),
        )
        llm_context = self._llm_projection(text, record, value)
        history_value = sanitize_binary_payload(value)
        projections = ToolResultProjections(
            llm_context=llm_context,
            ui_remote=value,
            persistent_history=history_value,
        )
        return record, projections

    def format_retrieved_context(
        self, records: list[dict[str, Any]], *, max_chars: int = 12_000
    ) -> str:
        """Build a bounded context block from persisted result records."""
        if max_chars <= 0 or not records:
            return ""
        lines = ["[retrieved tool results]"]
        for record in records:
            item = (
                f"result_id={record.get('result_id', '')} "
                f"tool_name={record.get('tool_name', '')} "
                f"class={record.get('result_class', '')}"
            )
            summary = str(record.get("summary") or "").strip()
            artifact_ref = str(record.get("artifact_ref") or "").strip()
            if summary:
                item += f" summary={summary}"
            if artifact_ref:
                item += f" artifact_ref={artifact_ref}"
            preview = str(record.get("artifact_preview") or "").strip()
            lines.append(item)
            if preview:
                lines.append(f"artifact_preview: {preview[:2000]}")
            if sum(len(line) + 1 for line in lines) >= max_chars:
                break
        return _bounded_preview("\n".join(lines), max_chars)

    def _classify(self, length: int) -> ResultClass:
        if length <= self.inline_limit_chars:
            return "small"
        if length <= self.large_limit_chars:
            return "large"
        return "huge"

    def _structured_preview(self, value: Any, text: str) -> str:
        """Preserve the shape of oversized tabular results before char clipping."""
        if self.max_preview_rows == 0 or not isinstance(value, (list, dict)):
            return _bounded_preview(text, self.inline_limit_chars)

        if isinstance(value, list):
            total = len(value)
            if total <= self.max_preview_rows:
                selected = value
            else:
                head = (self.max_preview_rows + 1) // 2
                tail = self.max_preview_rows - head
                selected = value[:head] + [
                    f"... {total - head - tail} rows omitted ..."
                ]
                if tail:
                    selected.extend(value[-tail:])
        else:
            keys = list(value)
            total = len(keys)
            if total <= self.max_preview_rows:
                selected = value
            else:
                head = (self.max_preview_rows + 1) // 2
                tail = self.max_preview_rows - head
                selected = {key: value[key] for key in keys[:head]}
                selected["... omitted keys ..."] = total - head - tail
                selected.update({key: value[key] for key in keys[-tail:]})
        return _bounded_preview(_stringify(selected), self.inline_limit_chars)

    def _llm_projection(self, text: str, record: ToolResultRecord, value: Any) -> str:
        if record.result_class == "small":
            return text
        preview = self._structured_preview(value, text)

        lines = [
            "[tool result projected by ContextResultManager]",
            f"result_id: {record.result_id}",
            f"tool_name: {record.tool_name}",
            f"result_class: {record.result_class}",
            f"original_length: {len(text)}",
        ]
        if record.summary:
            lines.append(f"summary: {record.summary}")
        if record.artifact_ref:
            lines.append(f"artifact_ref: {record.artifact_ref}")
        lines.extend(["preview:", preview])
        return "\n".join(lines)


__all__ = [
    "ContextResultManager",
    "ResultClass",
    "ToolResultProjections",
    "ToolResultRecord",
]
