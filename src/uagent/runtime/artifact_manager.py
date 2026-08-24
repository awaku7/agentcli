"""Durable, session-addressable artifact management."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .session_store import SessionStore, SessionStoreError


class ArtifactManagerError(RuntimeError):
    """Raised when an artifact cannot be safely registered or retrieved."""


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    session_id: str | None
    name: str
    relative_path: str
    stored_path: str
    media_type: str
    extension: str
    size: int
    sha256: str
    created_at: str
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArtifactManager:
    """Copy files into a workdir-local artifact store and persist metadata.

    If a :class:`SessionStore` is supplied, its SQLite connection is reused;
    otherwise a small private SQLite database is created below ``artifact_root``.
    """

    def __init__(
        self,
        workdir: str | Path,
        *,
        store: SessionStore | None = None,
        artifact_root: str | Path | None = None,
    ) -> None:
        self.workdir = Path(workdir).expanduser().absolute()
        if not self.workdir.is_dir():
            raise ArtifactManagerError(f"workdir is not a directory: {workdir}")
        self.workdir = self.workdir.resolve()
        root = (
            Path(artifact_root)
            if artifact_root is not None
            else self.workdir / ".uag" / "artifacts"
        )
        self.artifact_root = root.expanduser().absolute().resolve()
        if not self._under(self.artifact_root, self.workdir):
            raise ArtifactManagerError("artifact_root must be inside workdir")
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self._store = store
        self._owns_connection = store is None
        self._connection = (
            store._connection
            if store is not None
            else sqlite3.connect(
                self.artifact_root / "artifacts.sqlite3", isolation_level=None
            )
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("""CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                session_id TEXT,
                name TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                media_type TEXT NOT NULL,
                extension TEXT NOT NULL,
                size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT NOT NULL
            )""")

    @staticmethod
    def _under(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def close(self) -> None:
        if self._owns_connection:
            self._connection.close()

    def __enter__(self) -> "ArtifactManager":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _input_file(self, path: str | Path) -> Path:
        if not str(path).strip():
            raise ArtifactManagerError("path is empty")
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.workdir / candidate
        try:
            relative = candidate.relative_to(self.workdir)
        except ValueError as exc:
            raise ArtifactManagerError("artifact path must be inside workdir") from exc
        current = self.workdir
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ArtifactManagerError("symlink artifacts are not allowed")
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ArtifactManagerError(f"artifact does not exist: {path}") from exc
        if not self._under(resolved, self.workdir) or resolved.is_symlink():
            raise ArtifactManagerError(
                "artifact path must be a regular file inside workdir"
            )
        if not resolved.is_file():
            raise ArtifactManagerError("artifact path is not a file")
        return resolved

    def register(
        self,
        path: str | Path,
        *,
        session_id: str | None = None,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        source = self._input_file(path)
        if session_id is not None and self._store is not None:
            try:
                self._store._require_session(session_id)
            except SessionStoreError as exc:
                raise ArtifactManagerError(str(exc)) from exc
        if metadata is not None:
            try:
                metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
            except (TypeError, ValueError) as exc:
                raise ArtifactManagerError(
                    "metadata must be JSON serializable"
                ) from exc
        else:
            metadata = {}
            metadata_json = "{}"
        artifact_id = uuid.uuid4().hex
        filename = (
            name.strip() if isinstance(name, str) and name.strip() else source.name
        )
        safe_name = Path(filename).name
        if not safe_name or safe_name in {".", ".."}:
            raise ArtifactManagerError("invalid artifact name")
        target_dir = self.artifact_root / artifact_id
        target_dir.mkdir()
        target = target_dir / safe_name
        digest = hashlib.sha256()
        size = 0
        try:
            with source.open("rb") as src, target.open("wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    size += len(chunk)
                    dst.write(chunk)
                dst.flush()
                os.fsync(dst.fileno())
            rel = source.relative_to(self.workdir).as_posix()
            stored_rel = target.relative_to(self.workdir).as_posix()
            media_type = (
                mimetypes.guess_type(source.name)[0] or "application/octet-stream"
            )
            extension = source.suffix.lower()
            created_at = self._connection.execute(
                "SELECT CURRENT_TIMESTAMP"
            ).fetchone()[0]
            self._connection.execute(
                "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    artifact_id,
                    session_id,
                    safe_name,
                    rel,
                    stored_rel,
                    media_type,
                    extension,
                    size,
                    digest.hexdigest(),
                    str(created_at),
                    metadata_json,
                ),
            )
        except (OSError, sqlite3.Error) as exc:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise ArtifactManagerError(f"could not register artifact: {exc}") from exc
        return self.get(artifact_id)

    def get(self, artifact_id: str) -> Artifact:
        row = self._connection.execute(
            "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
        ).fetchone()
        if row is None:
            raise ArtifactManagerError(f"unknown artifact: {artifact_id}")
        return self._row(row)

    def open(self, artifact_id: str) -> Path:
        item = self.get(artifact_id)
        path = (self.workdir / item.stored_path).resolve()
        if not self._under(path, self.artifact_root) or not path.is_file():
            raise ArtifactManagerError("stored artifact is unavailable")
        return path

    def list(
        self,
        *,
        session_id: str | None = None,
        media_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Artifact]:
        if not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ArtifactManagerError("limit must be between 1 and 1000")
        if not isinstance(offset, int) or offset < 0:
            raise ArtifactManagerError("offset must be non-negative")
        clauses: list[str] = []
        params: list[Any] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if media_type is not None:
            clauses.append("media_type = ?")
            params.append(media_type)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self._connection.execute(
            f"SELECT * FROM artifacts{where} ORDER BY created_at, artifact_id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [self._row(row) for row in rows]

    def attach(self, artifact_id: str, session_id: str) -> Artifact:
        if self._store is not None:
            try:
                self._store._require_session(session_id)
            except SessionStoreError as exc:
                raise ArtifactManagerError(str(exc)) from exc
        self.get(artifact_id)
        self._connection.execute(
            "UPDATE artifacts SET session_id = ? WHERE artifact_id = ?",
            (session_id, artifact_id),
        )
        return self.get(artifact_id)

    @staticmethod
    def _row(row: sqlite3.Row) -> Artifact:
        return Artifact(
            artifact_id=str(row["artifact_id"]),
            session_id=row["session_id"],
            name=str(row["name"]),
            relative_path=str(row["relative_path"]),
            stored_path=str(row["stored_path"]),
            media_type=str(row["media_type"]),
            extension=str(row["extension"]),
            size=int(row["size"]),
            sha256=str(row["sha256"]),
            created_at=str(row["created_at"]),
            metadata=json.loads(row["metadata_json"]),
        )


__all__ = ["Artifact", "ArtifactManager", "ArtifactManagerError"]
