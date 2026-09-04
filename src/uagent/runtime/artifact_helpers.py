from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .artifact_manager import ArtifactManager, ArtifactManagerError
from .session_store import redact_sensitive


def register_artifacts(
    paths: list[str],
    *,
    metadata: dict[str, Any] | None = None,
    workdir: str | None = None,
) -> list[dict[str, Any]]:
    """Register generated files, returning serializable artifact records.

    Files outside workdir are currently skipped because ArtifactManager
    enforces a workdir boundary. Callers should select a workdir-local output
    directory when artifact registration is required.
    """
    from ..tools.context import get_callbacks

    callbacks = get_callbacks()
    root = (
        Path(workdir or os.environ.get("UAGENT_WORKDIR") or os.getcwd())
        .expanduser()
        .resolve()
    )
    session_store = getattr(callbacks, "session_store", None)
    manager = ArtifactManager(root, store=session_store)
    session_id = getattr(callbacks, "session_id", None)
    try:
        result: list[dict[str, Any]] = []
        for path in paths:
            try:
                item = manager.register(
                    path,
                    session_id=session_id,
                    metadata=metadata or {},
                )
            except ArtifactManagerError:
                continue
            result.append(item.as_dict())
        return result
    finally:
        manager.close()


def register_tool_result(
    text: str,
    *,
    tool_name: str,
    workdir: str | None = None,
) -> dict[str, Any] | None:
    """Persist one large textual tool result and return its artifact record."""
    from ..tools.context import get_callbacks

    callbacks = get_callbacks()
    root = (
        Path(workdir or os.environ.get("UAGENT_WORKDIR") or os.getcwd())
        .expanduser()
        .resolve()
    )
    session_store = getattr(callbacks, "session_store", None)
    manager = ArtifactManager(root, store=session_store)
    session_id = getattr(callbacks, "session_id", None)
    try:
        safe_text = redact_sensitive(text if isinstance(text, str) else str(text or ""))
        item = manager.register_text(
            safe_text,
            session_id=session_id,
            name="tool-result.txt",
            metadata={
                "kind": "tool_result",
                "tool_name": str(tool_name),
                "redacted": safe_text != text,
            },
        )
        return item.as_dict()
    except ArtifactManagerError:
        return None
    finally:
        manager.close()


__all__ = ["register_artifacts", "register_tool_result"]
