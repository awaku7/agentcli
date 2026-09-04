"""Export a session-owned Artifact to a workdir-local file without base64."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .artifact_access import (
    ArtifactAccessError,
    ArtifactNotActiveError,
    InvalidArtifactReferenceError,
    InvalidOutputPathError,
    get_owned_artifact,
    resolve_workdir_output,
)
from .i18n_helper import make_tool_translator
from ..runtime.artifact_manager import ArtifactManagerError

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:artifact_export"


def _json_result(**data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _error(message: str, **extra: Any) -> str:
    return _json_result(ok=False, error=message, **extra)


TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "artifact_export",
        "description": _(
            "tool.description",
            default="Export a previously stored session-owned artifact to a workdir-local file without returning base64 data.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "artifact_export",
                "export artifact",
                "save artifact",
                "copy binary artifact",
            ],
        ),
        "x_search_terms_en": [
            "artifact_export",
            "export artifact",
            "save artifact",
            "copy binary artifact",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "string",
                    "description": _(
                        "param.artifact_id.description",
                        default="Artifact ID or artifact:// reference from an earlier tool result.",
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": _(
                        "param.output_path.description",
                        default="Destination path relative to the current workdir. Absolute paths must still be inside the workdir.",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.overwrite.description",
                        default="Overwrite the destination if it already exists (default: false).",
                    ),
                },
            },
            "required": ["artifact_id", "output_path"],
            "additionalProperties": False,
        },
    },
}


def _copy_atomically(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".part", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as target:
            with source.open("rb") as origin:
                shutil.copyfileobj(origin, target, length=1024 * 1024)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_tool(args: dict[str, Any]) -> str:
    manager = None
    try:
        manager, item, source, _callbacks = get_owned_artifact(args.get("artifact_id"))
        workdir = (
            Path(os.environ.get("UAGENT_WORKDIR") or os.getcwd()).expanduser().resolve()
        )
        destination = resolve_workdir_output(workdir, args.get("output_path", ""))
        overwrite = args.get("overwrite", False)
        if not isinstance(overwrite, bool):
            return _error(
                _(
                    "error.invalid_overwrite",
                    default="overwrite must be a boolean",
                )
            )
        if destination.exists() and not overwrite:
            return _error(
                _(
                    "error.destination_exists",
                    default="destination already exists; set overwrite to true to replace it",
                )
            )
        if destination.exists() and destination.is_dir():
            return _error(
                _(
                    "error.destination_directory",
                    default="output_path must name a file, not a directory",
                )
            )
        _copy_atomically(source, destination)
        return _json_result(
            ok=True,
            artifact_id=item.artifact_id,
            output_path=str(destination.relative_to(workdir).as_posix()),
            media_type=item.media_type,
            size=destination.stat().st_size,
            sha256=_sha256(destination),
            saved_files=[str(destination)],
            attachments=[
                {
                    "type": "file",
                    "mime": item.media_type,
                    "name": item.name,
                    "path": str(destination),
                }
            ],
        )
    except ArtifactNotActiveError:
        return _error(
            _(
                "error.not_active_session",
                default="artifact does not belong to the active session",
            )
        )
    except InvalidArtifactReferenceError:
        return _error(
            _(
                "error.invalid_artifact_id",
                default="artifact_id must be a valid artifact ID or artifact:// reference",
            )
        )
    except InvalidOutputPathError:
        return _error(
            _(
                "error.invalid_output_path",
                default="output_path must be inside the workdir",
            )
        )
    except ArtifactAccessError as exc:
        return _error(str(exc))
    except (ArtifactManagerError, OSError) as exc:
        return _error(str(exc))
    finally:
        if manager is not None:
            manager.close()


__all__ = ["TOOL_SPEC", "run_tool"]
