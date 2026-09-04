"""Return metadata for a session-owned Artifact without reading its payload."""

from __future__ import annotations

import json
from typing import Any

from .artifact_access import (
    ArtifactAccessError,
    ArtifactNotActiveError,
    InvalidArtifactReferenceError,
    get_owned_artifact,
)
from .i18n_helper import make_tool_translator
from ..runtime.artifact_manager import ArtifactManagerError

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:artifact_info"


def _json_result(**data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _error(message: str, **extra: Any) -> str:
    return _json_result(ok=False, error=message, **extra)


TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "artifact_info",
        "description": _(
            "tool.description",
            default="Return metadata for a previously stored session-owned artifact without reading its payload.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "artifact_info",
                "artifact metadata",
                "artifact type",
                "artifact size",
            ],
        ),
        "x_search_terms_en": [
            "artifact_info",
            "artifact metadata",
            "artifact type",
            "artifact size",
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
                }
            },
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    manager = None
    try:
        manager, item, _path, _callbacks = get_owned_artifact(args.get("artifact_id"))
        return _json_result(
            ok=True,
            artifact_id=item.artifact_id,
            name=item.name,
            relative_path=item.relative_path,
            stored_path=item.stored_path,
            media_type=item.media_type,
            extension=item.extension,
            size=item.size,
            sha256=item.sha256,
            created_at=item.created_at,
            metadata=item.metadata,
        )
    except ArtifactNotActiveError:
        message = _(
            "error.not_active_session",
            default="artifact does not belong to the active session",
        )
        return _error(message)
    except InvalidArtifactReferenceError:
        message = _(
            "error.invalid_artifact_id",
            default="artifact_id must be a valid artifact ID or artifact:// reference",
        )
        return _error(message)
    except ArtifactAccessError as exc:
        return _error(str(exc))
    except (ArtifactManagerError, OSError) as exc:
        return _error(str(exc))
    finally:
        if manager is not None:
            manager.close()


__all__ = ["TOOL_SPEC", "run_tool"]
