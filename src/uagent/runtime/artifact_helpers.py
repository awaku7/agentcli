from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .artifact_manager import ArtifactManager, ArtifactManagerError


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
    root = Path(workdir or os.environ.get("UAGENT_WORKDIR") or os.getcwd()).expanduser().resolve()
    manager = ArtifactManager(root)
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


__all__ = ["register_artifacts"]
