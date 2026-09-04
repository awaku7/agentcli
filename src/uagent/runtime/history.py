"""Pure history/output helpers extracted from core."""

from __future__ import annotations


import json
import os
from typing import Any, Callable

from ..env_utils import env_get

_DEFAULT_HISTORY_TOOL_RESULT_MAX_CHARS = 12_000


def _truncate_text_to_limit(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    marker = f"\n[tool output truncated: original length={len(value)}]\n"
    if limit <= len(marker):
        return marker[:limit]
    remaining = limit - len(marker)
    head_len = (remaining + 1) // 2
    tail_len = remaining - head_len
    return value[:head_len] + marker + (value[-tail_len:] if tail_len else "")


def truncate_history_tool_result(text: Any) -> str:
    """Limit a tool result before it is retained in an LLM conversation.

    ``UAGENT_TOOL_RESULT_MAX_CHARS=0`` disables this limit. The legacy
    ``UAGENT_HISTORY_TOOL_RESULT_MAX_CHARS`` name is accepted as a fallback.
    Invalid or negative values use the safe default. Both the beginning and
    end are kept
    because command output often contains a summary at the end.
    """
    value = "" if text is None else str(text)
    raw_limit = env_get("UAGENT_TOOL_RESULT_MAX_CHARS")
    if raw_limit is None or str(raw_limit).strip() == "":
        raw_limit = env_get("UAGENT_HISTORY_TOOL_RESULT_MAX_CHARS")
    if raw_limit is None or str(raw_limit).strip() == "":
        limit = _DEFAULT_HISTORY_TOOL_RESULT_MAX_CHARS
    else:
        try:
            limit = int(str(raw_limit).strip())
        except (TypeError, ValueError):
            limit = _DEFAULT_HISTORY_TOOL_RESULT_MAX_CHARS
    if limit == 0:
        return value
    if limit < 0:
        limit = _DEFAULT_HISTORY_TOOL_RESULT_MAX_CHARS
    return _truncate_text_to_limit(value, limit)


_DEFAULT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS = 100_000


def tool_result_artifact_threshold() -> int:
    """Return the size at which a textual result is promoted to an artifact."""
    raw = env_get("UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS")
    if raw is None or str(raw).strip() == "":
        return _DEFAULT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return _DEFAULT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS
    return value if value >= 0 else _DEFAULT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS


def materialize_large_tool_result(text: Any, *, tool_name: str) -> str:
    """Keep a safe context entry while preserving a large result as an artifact.

    This is deliberately deterministic and does not call an LLM. If artifact
    registration is unavailable, the normal bounded-result policy remains the
    fallback so a storage failure cannot reintroduce an oversized request.
    """
    value = "" if text is None else str(text)
    threshold = tool_result_artifact_threshold()
    if threshold == 0 or len(value) <= threshold:
        return truncate_history_tool_result(value)
    try:
        from .artifact_helpers import register_tool_result

        artifact = register_tool_result(value, tool_name=tool_name)
    except Exception:
        artifact = None
    if not artifact:
        return truncate_history_tool_result(value)
    artifact_id = str(artifact.get("artifact_id") or "")
    stored_path = str(artifact.get("stored_path") or "")
    # Artifact references must remain bounded even when the normal history
    # limit is disabled or set above the artifact threshold.
    preview = _truncate_text_to_limit(value, _DEFAULT_HISTORY_TOOL_RESULT_MAX_CHARS)
    return (
        "[tool result stored as artifact]\n"
        f"tool_name: {tool_name}\n"
        f"original_length: {len(value)}\n"
        f"artifact_ref: artifact://{artifact_id}\n"
        f"artifact_path: {stored_path}\n"
        "preview:\n"
        f"{preview}"
    )


def rewrite_jsonl_log(
    log_path: str,
    messages: list[dict[str, Any]],
    response_records: list[dict[str, Any]],
    mask_fn: Callable[[dict[str, Any]], dict[str, Any]],
    tool_context_records: list[dict[str, Any]] | None = None,
) -> str:
    """Rewrite a masked conversation log with preserved metadata."""
    log_dir = os.path.dirname(log_path) or "."
    backup_dir = os.path.join(log_dir, ".backup")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, os.path.basename(log_path) + ".org")
    try:
        if os.path.exists(log_path):
            with open(log_path, "rb") as source, open(backup_path, "wb") as target:
                target.write(source.read())
    except Exception:
        pass
    tmp_path = log_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as stream:
        for item in messages:
            try:
                stream.write(json.dumps(mask_fn(item), ensure_ascii=False) + "\n")
            except Exception:
                continue
        for record in tool_context_records or []:
            try:
                stream.write(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
            except Exception:
                continue
        for record in response_records:
            try:
                stream.write(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
            except Exception:
                continue
    os.replace(tmp_path, log_path)
    return log_path


def truncate_output(label: str, text: str, limit: int = 400_000) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return text[:limit] + f"\n[{label} truncated: {omitted} chars omitted]"
