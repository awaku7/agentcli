"""Shared session-safe access helpers for Artifact tools."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .context import get_callbacks
from ..runtime.artifact_manager import Artifact, ArtifactManager

_ARTIFACT_ID = re.compile(r"^[0-9a-f]{32}$")
_TEXT_MEDIA_TYPES = {
    "application/graphql",
    "application/javascript",
    "application/json",
    "application/ld+json",
    "application/sql",
    "application/toml",
    "application/xml",
    "application/x-ndjson",
    "application/x-yaml",
    "application/yaml",
}


class ArtifactAccessError(RuntimeError):
    """Raised when an Artifact cannot be accessed by the active session."""


class InvalidArtifactReferenceError(ArtifactAccessError):
    """The supplied Artifact ID or URI is invalid."""


class ArtifactNotActiveError(ArtifactAccessError):
    """The Artifact is not owned by the active session."""


class InvalidOutputPathError(ArtifactAccessError):
    """The requested export path is unsafe or invalid."""


def normalize_artifact_id(value: Any) -> str:
    reference = str(value or "").strip()
    if reference.startswith("artifact://"):
        reference = reference[len("artifact://") :]
    if not _ARTIFACT_ID.fullmatch(reference):
        raise InvalidArtifactReferenceError
    return reference


def get_owned_artifact(reference: Any) -> tuple[ArtifactManager, Artifact, Path, Any]:
    """Open a specified Artifact after validating active-session ownership."""
    callbacks = get_callbacks()
    workdir = (
        Path(os.environ.get("UAGENT_WORKDIR") or os.getcwd()).expanduser().resolve()
    )
    manager = ArtifactManager(
        workdir,
        store=getattr(callbacks, "session_store", None),
    )
    try:
        artifact_id = normalize_artifact_id(reference)
        item = manager.get(artifact_id)
        active_session_id = getattr(callbacks, "session_id", None)
        if item.session_id != active_session_id:
            raise ArtifactNotActiveError
        return manager, item, manager.open(artifact_id), callbacks
    except Exception:
        manager.close()
        raise


def is_textual_artifact(item: Artifact) -> bool:
    media_type = (item.media_type or "").lower().split(";", 1)[0].strip()
    if media_type.startswith("text/") or media_type in _TEXT_MEDIA_TYPES:
        return True
    return item.extension.lower() in {
        ".c",
        ".cc",
        ".cpp",
        ".css",
        ".csv",
        ".go",
        ".h",
        ".hpp",
        ".html",
        ".ini",
        ".java",
        ".js",
        ".jsonl",
        ".kt",
        ".log",
        ".md",
        ".py",
        ".rb",
        ".rs",
        ".sql",
        ".svg",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }


def resolve_workdir_output(workdir: Path, output_path: str) -> Path:
    candidate = Path(str(output_path or "").strip()).expanduser()
    if not str(candidate):
        raise InvalidOutputPathError
    if not candidate.is_absolute():
        candidate = workdir / candidate
    candidate = candidate.absolute()
    try:
        candidate.relative_to(workdir)
        candidate.parent.resolve().relative_to(workdir)
    except ValueError as exc:
        raise InvalidOutputPathError from exc
    if candidate == workdir or candidate.is_symlink():
        raise InvalidOutputPathError
    return candidate


__all__ = [
    "ArtifactAccessError",
    "ArtifactNotActiveError",
    "InvalidArtifactReferenceError",
    "InvalidOutputPathError",
    "get_owned_artifact",
    "is_textual_artifact",
    "normalize_artifact_id",
    "resolve_workdir_output",
]
