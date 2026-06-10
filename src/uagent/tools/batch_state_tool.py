from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..env_utils import env_get
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False

_PUBLIC_TOOL_ACTIONS = (
    "init",
    "load",
    "status",
    "current",
    "complete_file",
    "skip_file",
    "error_file",
    "reset",
    "finalize",
    "list",
)

_TOOL_ACTIONS = _PUBLIC_TOOL_ACTIONS
_ALL_TOOL_ACTIONS = _PUBLIC_TOOL_ACTIONS
_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ALLOWED_STATUSES = {"active", "done", "paused", "cancelled", "error"}

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "batch_state",
        "description": _(
            "tool.description",
            default="Manage batch state for multi-file tasks under ~/.uag/batches/.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Manage batch state. Prefer targets=[{dir, files, index}] and current_target. "
                "Use current to fetch the current file. After processing it, call complete_file. "
                "Use reset to restore the batch to its original pending state while preserving metadata. "
                "Use complete_file, skip_file, or error_file for explicit per-file results. "
                "Return JSON only."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "batch_state",
                "batch state",
                "batch manager",
                "batch progress",
                "process files",
                "file queue",
                "next file",
                "batch overview",
                "continue batch",
                "task queue",
            ],
        ),
        "x_search_terms_en": [
            "batch_state",
            "batch state",
            "batch manager",
            "batch progress",
            "process files",
            "file queue",
            "next file",
            "batch overview",
            "continue batch",
            "task queue",
        ],
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "action": {
                    "type": "string",
                    "enum": list(_TOOL_ACTIONS),
                    "description": _(
                        "param.action.description",
                        default=(
                            "Action: init/load/status/current/complete_file/skip_file/error_file/reset/finalize/list. "
                            "Use current for the current file. After processing it, call complete_file. "
                            "Use complete_file, skip_file, or error_file for explicit per-file results."
                        ),
                    ),
                },
                "batch_id": {
                    "type": "string",
                    "description": _(
                        "param.batch_id.description",
                        default="Batch ID. Required for load/status/reset/finalize; optional for init/list.",
                    ),
                },
                "task_description": {
                    "type": "string",
                    "description": _(
                        "param.task_description.description",
                        default="Short description of the batch task. Keep the user's original language; do not translate.",
                    ),
                },
                "instructions": {
                    "type": "string",
                    "description": _(
                        "param.instructions.description",
                        default="Detailed instructions for the batch task. Keep the user's original language; do not translate.",
                    ),
                },
                "targets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "dir": {"type": "string"},
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "index": {
                                "type": "integer",
                                "minimum": 0,
                            },
                        },
                        "required": ["files"],
                    },
                    "description": _(
                        "param.targets.description",
                        default=(
                            "Target groups. Each entry contains dir, files (dir-relative), and index."
                        ),
                    ),
                },
                "remaining_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.remaining_files.description",
                        default="Files in the current target group. Prefer targets.",
                    ),
                },
                "current_target": {
                    "type": "integer",
                    "minimum": 0,
                    "description": _(
                        "param.current_target.description",
                        default="Index of the current target group.",
                    ),
                },
                "patch": {
                    "type": "object",
                    "description": _(
                        "param.patch.description",
                        default=(
                            "Partial update to merge into the batch state. Prefer patch.targets and patch.current_target."
                        ),
                    ),
                },
                "file": {
                    "type": "string",
                    "description": _(
                        "param.file.description",
                        default="Target file for complete_file/skip_file/error_file. If omitted, the current file is used.",
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": _(
                        "param.reason.description",
                        default="Reason for skip_file/error_file, or a short note for completion.",
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": sorted(_ALLOWED_STATUSES),
                    "description": _(
                        "param.status.description",
                        default="Batch status: active/done/paused/cancelled/error.",
                    ),
                },
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description",
                        default="Log message to append. Keep the user's original language; do not translate.",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": _(
                        "param.overwrite.description",
                        default="If true, init overwrites an existing batch file.",
                    ),
                },
            },
            "required": ["action"],
        },
    },
    "is_agent_content": False,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _state_root() -> Path:
    override = env_get("UAGENT_BATCHES_DIR")
    if override:
        return Path(os.path.expanduser(str(override))).expanduser()
    return Path(os.path.expanduser("~/.uag/batches")).expanduser()


def _ensure_dir() -> Path:
    root = _state_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _normalize_batch_id(batch_id: Any) -> str:
    if batch_id is None:
        return ""
    s = str(batch_id).strip()
    if not s:
        return ""
    return s


def _validate_batch_id(batch_id: str) -> str:
    if not batch_id:
        raise ValueError("batch_id is required")
    if not _BATCH_ID_RE.fullmatch(batch_id):
        raise ValueError("invalid batch_id")
    return batch_id


def _path_for_batch_id(batch_id: str) -> Path:
    root = _ensure_dir()
    return root / f"{batch_id}.json"


def _normalize_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_path_text(value: Any) -> str:
    text = _normalize_text(value)
    return text.replace("\\", "/")


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except TypeError, ValueError:
        return default


def _dedupe_preserve_order(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    seen = set()
    for item in items:
        value = _normalize_path_text(item)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _normalize_file_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    seen = set()
    for item in items:
        value = _normalize_path_text(item)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _merge_unique_lists(existing: Any, new_items: Any) -> list[str]:
    out: list[str] = []
    seen = set()
    for source in (_normalize_file_list(existing), _normalize_file_list(new_items)):
        for item in source:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
    return out


def _normalize_targets(targets: Any) -> list[dict[str, Any]]:
    if not isinstance(targets, list):
        return []
    normalized: list[dict[str, Any]] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        files = _normalize_file_list(target.get("files"))
        if not files:
            files = _normalize_file_list(target.get("remaining_files"))
        normalized.append(
            {
                "dir": _normalize_path_text(target.get("dir")),
                "files": files,
                "index": max(_coerce_int(target.get("index"), len(normalized)), 0),
            }
        )
    return normalized


def _target_paths(target: dict[str, Any]) -> list[str]:
    target_dir = _normalize_path_text(target.get("dir"))
    files = _normalize_file_list(target.get("files"))
    if not target_dir:
        return files
    prefix = target_dir.rstrip("/") + "/"
    out: list[str] = []
    for file in files:
        if file == target_dir or file.startswith(prefix):
            out.append(file)
        else:
            out.append(_normalize_path_text(f"{target_dir}/{file}"))
    return out


def _normalize_status(value: Any, default: str = "active") -> str:
    status = _normalize_text(value).lower()
    return status if status in _ALLOWED_STATUSES else default


def _state_with_progress_view(state: dict[str, Any]) -> dict[str, Any]:
    base = dict(state) if isinstance(state, dict) else {}
    targets = _normalize_targets(base.get("targets"))
    completed_files = _normalize_file_list(base.get("completed_files"))
    skipped_files = _normalize_file_list(base.get("skipped_files"))
    error_files = _normalize_file_list(base.get("error_files"))

    result_lists = [completed_files, skipped_files, error_files]
    done_files = _merge_unique_lists(
        [], [item for group in result_lists for item in group]
    )
    all_files: list[str] = []
    for target in targets:
        all_files = _merge_unique_lists(all_files, _target_paths(target))

    total_count = len(all_files)
    done_count = len(done_files)
    pending_files = [item for item in all_files if item not in done_files]
    pending_count = len(pending_files)

    raw_current_target = _coerce_int(base.get("current_target"), 0)
    current_target = 0
    current_target_dir = ""
    file = ""
    search_order = list(range(raw_current_target, len(targets))) + list(
        range(0, raw_current_target)
    )
    if targets:
        if raw_current_target < 0:
            raw_current_target = 0
        if raw_current_target >= len(targets):
            raw_current_target = len(targets) - 1
        current_target = raw_current_target
        current_target_dir = _normalize_path_text(targets[current_target].get("dir"))
        for target_index in search_order:
            target = targets[target_index]
            target_pending = [
                item for item in _target_paths(target) if item not in done_files
            ]
            if target_pending:
                current_target = target_index
                current_target_dir = _normalize_path_text(target.get("dir"))
                file = target_pending[0]
                break

    target_views: list[dict[str, Any]] = []
    for index, target in enumerate(targets):
        target_files = _target_paths(target)
        target_done = [item for item in target_files if item in done_files]
        target_pending = [item for item in target_files if item not in done_files]
        target_views.append(
            {
                "index": index,
                "dir": _normalize_path_text(target.get("dir")),
                "files": target_files,
                "pending_files": target_pending,
                "completed_files": target_done,
                "pending_count": len(target_pending),
                "done_count": len(target_done),
            }
        )

    status = _normalize_status(base.get("status"), "active")
    if pending_count == 0 and total_count > 0 and status == "active":
        status = "done"

    recommended_next_action = {
        "action": "current" if file else "finalize",
        "batch_id": _normalize_batch_id(base.get("batch_id")),
        "file": file,
        "current_target": current_target,
    }
    if not file:
        recommended_next_action["file"] = ""

    return {
        **base,
        "status": status,
        "targets": targets,
        "completed_files": completed_files,
        "skipped_files": skipped_files,
        "error_files": error_files,
        "completed_count": len(completed_files),
        "skipped_count": len(skipped_files),
        "error_count": len(error_files),
        "done_count": done_count,
        "total_count": total_count,
        "pending_count": pending_count,
        "pending_files": pending_files,
        "remaining_files": pending_files,
        "current_target": current_target,
        "current_target_dir": current_target_dir,
        "file": file,
        "target_views": target_views,
        "progress_ratio": (done_count / total_count) if total_count else 0.0,
        "must_process_current_file_first": bool(file),
        "allowed_after_processing": (
            ["complete_file", "skip_file", "error_file"] if file else ["finalize"]
        ),
        "recommended_next_action": recommended_next_action,
    }


def _collect_state_patch(args: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for key in (
        "task_description",
        "instructions",
        "targets",
        "current_target",
        "workdir",
        "style_rules",
        "term_rules",
        "notes",
        "status",
    ):
        if key in args and args.get(key) is not None:
            patch[key] = args.get(key)
    return patch


def _merge_state(state: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(state) if isinstance(state, dict) else {}
    if not isinstance(patch, dict):
        return _normalize_persisted_state(merged)
    for key, value in patch.items():
        merged[key] = value
    return _normalize_persisted_state(merged)


def _normalize_persisted_state(state: dict[str, Any]) -> dict[str, Any]:
    base = _default_state(_normalize_batch_id(state.get("batch_id")))
    if not isinstance(state, dict):
        state = {}

    normalized = dict(base)
    for key in (
        "task_description",
        "instructions",
        "workdir",
        "created_at",
        "updated_at",
        "last_updated",
    ):
        if key in state and state.get(key) not in (None, ""):
            normalized[key] = (
                _normalize_text(state.get(key))
                if key not in {"created_at", "updated_at", "last_updated"}
                else str(state.get(key))
            )

    normalized["batch_id"] = (
        _normalize_batch_id(state.get("batch_id")) or base["batch_id"]
    )
    normalized["status"] = _normalize_status(state.get("status"), base["status"])
    normalized["targets"] = _normalize_targets(state.get("targets"))
    normalized["current_target"] = (
        0
        if not normalized["targets"]
        else min(
            max(_coerce_int(state.get("current_target"), 0), 0),
            len(normalized["targets"]) - 1,
        )
    )
    normalized["style_rules"] = _normalize_file_list(state.get("style_rules"))
    normalized["term_rules"] = _normalize_file_list(state.get("term_rules"))
    normalized["notes"] = _normalize_file_list(state.get("notes"))
    normalized["completed_files"] = _merge_unique_lists(
        [], state.get("completed_files")
    )
    normalized["skipped_files"] = _merge_unique_lists([], state.get("skipped_files"))
    normalized["error_files"] = _merge_unique_lists([], state.get("error_files"))
    normalized["logs"] = (
        list(state.get("logs", [])) if isinstance(state.get("logs"), list) else []
    )
    for key in state:
        if key not in normalized:
            normalized[key] = state[key]

    normalized.update(_state_with_progress_view(normalized))
    return normalized


def _load_state(batch_id: str) -> dict[str, Any]:
    path = _path_for_batch_id(batch_id)
    if not path.exists():
        raise FileNotFoundError(f"batch not found: {batch_id}")
    with path.open("r", encoding="utf-8") as f:
        state = json.load(f)
    if not isinstance(state, dict):
        raise ValueError("batch state must be a JSON object")
    state.setdefault("batch_id", batch_id)
    return _normalize_persisted_state(state)


def _save_state(batch_id: str, state: dict[str, Any]) -> Path:
    path = _path_for_batch_id(batch_id)
    normalized = _normalize_persisted_state(state)
    normalized["batch_id"] = batch_id
    now = _now_iso()
    normalized["updated_at"] = now
    normalized["last_updated"] = now
    with path.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return path


def _list_item(state: dict[str, Any]) -> dict[str, Any]:
    snapshot = _state_with_progress_view(state)
    return {
        "batch_id": snapshot.get("batch_id", ""),
        "status": snapshot.get("status", ""),
        "task_description": snapshot.get("task_description", ""),
        "file": snapshot.get("file", ""),
        "total_count": snapshot.get("total_count", 0),
        "done_count": snapshot.get("done_count", 0),
        "pending_count": snapshot.get("pending_count", 0),
        "completed_count": snapshot.get("completed_count", 0),
        "skipped_count": snapshot.get("skipped_count", 0),
        "error_count": snapshot.get("error_count", 0),
        "progress_ratio": snapshot.get("progress_ratio", 0.0),
        "must_process_current_file_first": snapshot.get(
            "must_process_current_file_first", False
        ),
        "allowed_after_processing": snapshot.get("allowed_after_processing", []),
        "recommended_next_action": snapshot.get("recommended_next_action", {}),
        "updated_at": snapshot.get("updated_at", ""),
    }


def _append_log_entry(
    state: dict[str, Any], message: str, **extra: Any
) -> dict[str, Any]:
    logs = state.get("logs")
    if not isinstance(logs, list):
        logs = []
    entry = {"ts": _now_iso(), "message": message}
    for key, value in extra.items():
        if value not in (None, "", []):
            entry[key] = value
    logs.append(entry)
    state["logs"] = logs
    return state


def _remove_file_record(records: Any, file_value: str) -> list[str]:
    needle = _normalize_path_text(file_value)
    if not needle:
        return _normalize_file_list(records)
    return [item for item in _normalize_file_list(records) if item != needle]


def _resolve_record_file(
    state: dict[str, Any], file_value: Any = None
) -> tuple[int, int, str]:
    snapshot = _state_with_progress_view(state)
    candidate = _normalize_path_text(file_value) or _normalize_path_text(
        snapshot.get("file")
    )
    if not candidate:
        raise ValueError("no current file")

    targets = _normalize_targets(state.get("targets"))
    current_target = _coerce_int(snapshot.get("current_target"), 0)
    search_order = list(range(current_target, len(targets))) + list(
        range(0, current_target)
    )
    for target_index in search_order:
        target = targets[target_index]
        files = _normalize_file_list(target.get("files"))
        display_files = _target_paths(target)
        for file_index, display_file in enumerate(display_files):
            relative_file = (
                files[file_index] if file_index < len(files) else display_file
            )
            candidates = {
                _normalize_path_text(display_file),
                _normalize_path_text(relative_file),
            }
            if candidate in candidates:
                return target_index, file_index, display_file
    raise ValueError(f"file not found in batch targets: {candidate}")


def _record_file_result(
    state: dict[str, Any],
    result_key: str,
    file_value: Any = None,
    reason: Any = None,
) -> dict[str, Any]:
    state = _normalize_persisted_state(state)
    target_index, _file_index, display_file = _resolve_record_file(state, file_value)
    display_file = _normalize_path_text(display_file)

    if result_key == "completed_files":
        for other_key in ("skipped_files", "error_files"):
            state[other_key] = _remove_file_record(state.get(other_key), display_file)
    elif result_key == "skipped_files":
        for other_key in ("completed_files", "error_files"):
            state[other_key] = _remove_file_record(state.get(other_key), display_file)
    elif result_key == "error_files":
        for other_key in ("completed_files", "skipped_files"):
            state[other_key] = _remove_file_record(state.get(other_key), display_file)

    state[result_key] = _merge_unique_lists(state.get(result_key), [display_file])
    state["current_target"] = target_index
    state = _normalize_persisted_state(state)
    snapshot = _state_with_progress_view(state)
    state["current_target"] = snapshot.get("current_target", target_index)

    action_name = {
        "completed_files": "complete_file",
        "skipped_files": "skip_file",
        "error_files": "error_file",
    }.get(result_key, "record_file")
    state = _append_log_entry(
        state,
        f"{action_name}: {display_file}",
        file=display_file,
        reason=_normalize_text(reason),
    )

    final_snapshot = _state_with_progress_view(state)
    if (
        final_snapshot.get("pending_count", 0) == 0
        and state.get("status") == "active"
        and state.get("targets")
    ):
        state["status"] = "done"
    return _normalize_persisted_state(state)


def _batch_overview(state: dict[str, Any]) -> dict[str, Any]:
    snapshot = _state_with_progress_view(state)
    target_views = snapshot.get("target_views", [])
    return {
        "batch_id": snapshot.get("batch_id", ""),
        "status": snapshot.get("status", ""),
        "task_description": snapshot.get("task_description", ""),
        "instructions": snapshot.get("instructions", ""),
        "workdir": snapshot.get("workdir", ""),
        "current_target": snapshot.get("current_target", 0),
        "current_target_dir": snapshot.get("current_target_dir", ""),
        "file": snapshot.get("file", ""),
        "targets": snapshot.get("targets", []),
        "target_views": target_views,
        "remaining_files": snapshot.get("remaining_files", []),
        "pending_files": snapshot.get("pending_files", []),
        "total_count": snapshot.get("total_count", 0),
        "done_count": snapshot.get("done_count", 0),
        "pending_count": snapshot.get("pending_count", 0),
        "completed_count": snapshot.get("completed_count", 0),
        "skipped_count": snapshot.get("skipped_count", 0),
        "error_count": snapshot.get("error_count", 0),
        "completed_files": snapshot.get("completed_files", []),
        "skipped_files": snapshot.get("skipped_files", []),
        "error_files": snapshot.get("error_files", []),
        "progress_ratio": snapshot.get("progress_ratio", 0.0),
        "must_process_current_file_first": snapshot.get(
            "must_process_current_file_first", False
        ),
        "allowed_after_processing": snapshot.get("allowed_after_processing", []),
        "recommended_next_action": snapshot.get("recommended_next_action", {}),
        "updated_at": snapshot.get("updated_at", ""),
    }


def _default_state(batch_id: str) -> dict[str, Any]:
    now = _now_iso()
    return {
        "batch_id": batch_id,
        "status": "active",
        "task_description": "",
        "instructions": "",
        "workdir": str(Path.cwd()),
        "targets": [],
        "current_target": 0,
        "style_rules": [],
        "term_rules": [],
        "notes": [],
        "completed_files": [],
        "skipped_files": [],
        "error_files": [],
        "logs": [],
        "created_at": now,
        "updated_at": now,
        "last_updated": now,
    }


def _result(ok: bool, **payload: Any) -> str:
    return json.dumps(
        {"ok": ok, **payload}, ensure_ascii=False, indent=2, sort_keys=True
    )


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "").strip()
    if action not in _ALL_TOOL_ACTIONS:
        return _result(
            False,
            error=_(
                "err.unknown_action",
                default=f"[batch_state error] unknown action: {action!r}",
            ),
            allowed_actions=list(_TOOL_ACTIONS),
        )

    try:
        if action == "init":
            batch_id = (
                _normalize_batch_id(args.get("batch_id"))
                or f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
            )
            batch_id = _validate_batch_id(batch_id)
            path = _path_for_batch_id(batch_id)
            if path.exists() and not bool(args.get("overwrite", False)):
                return _result(
                    False,
                    error=_(
                        "err.batch_exists",
                        default=f"[batch_state error] batch already exists: {batch_id}",
                    ),
                    batch_id=batch_id,
                    path=str(path),
                )

            state = _default_state(batch_id)
            patch = _collect_state_patch(args)
            if patch:
                state = _merge_state(state, patch)
            state = _normalize_persisted_state(state)
            _save_state(batch_id, state)
            return _result(
                True,
                action="init",
                batch_id=batch_id,
                path=str(path),
                state=_batch_overview(state),
            )

        if action == "list":
            root = _ensure_dir()
            items: list[dict[str, Any]] = []
            for path in sorted(root.glob("*.json")):
                try:
                    with path.open("r", encoding="utf-8") as f:
                        state = json.load(f)
                    if not isinstance(state, dict):
                        continue
                    items.append(_list_item(state))
                except Exception:
                    continue

            summary = {
                "batch_count": len(items),
                "active_count": sum(
                    1 for item in items if item.get("status") == "active"
                ),
                "done_count": sum(1 for item in items if item.get("status") == "done"),
                "paused_count": sum(
                    1 for item in items if item.get("status") == "paused"
                ),
                "error_count": sum(
                    1 for item in items if item.get("status") == "error"
                ),
            }
            return _result(
                True,
                action="list",
                root=str(root),
                count=len(items),
                summary=summary,
                batches=items,
            )

        batch_id = _validate_batch_id(_normalize_batch_id(args.get("batch_id")))

        if action == "reset":
            state = _load_state(batch_id)
            reset_state = _default_state(batch_id)
            reset_state["task_description"] = state.get("task_description", "")
            reset_state["instructions"] = state.get("instructions", "")
            reset_state["workdir"] = state.get("workdir", reset_state["workdir"])
            reset_state["targets"] = state.get("targets", [])
            reset_state["created_at"] = state.get(
                "created_at", reset_state["created_at"]
            )
            reset_state["style_rules"] = state.get("style_rules", [])
            reset_state["term_rules"] = state.get("term_rules", [])
            reset_state["notes"] = state.get("notes", [])
            reset_state["logs"] = (
                list(state.get("logs", []))
                if isinstance(state.get("logs"), list)
                else []
            )
            reset_state = _normalize_persisted_state(reset_state)
            reset_state = _append_log_entry(reset_state, "reset")
            _save_state(batch_id, reset_state)
            return _result(
                True,
                action="reset",
                batch_id=batch_id,
                path=str(_path_for_batch_id(batch_id)),
                state=_batch_overview(reset_state),
            )

        if action in {"load", "status"}:
            state = _load_state(batch_id)
            return _result(
                True,
                action=action,
                batch_id=batch_id,
                path=str(_path_for_batch_id(batch_id)),
                state=_batch_overview(state),
            )

        if action == "current":
            state = _load_state(batch_id)
            overview = _batch_overview(state)
            return _result(
                True,
                action=action,
                batch_id=batch_id,
                path=str(_path_for_batch_id(batch_id)),
                file=overview.get("file", ""),
                current_target=overview.get("current_target", 0),
                current_target_dir=overview.get("current_target_dir", ""),
                pending_count=overview.get("pending_count", 0),
                total_count=overview.get("total_count", 0),
                done_count=overview.get("done_count", 0),
                progress_ratio=overview.get("progress_ratio", 0.0),
                must_process_current_file_first=overview.get(
                    "must_process_current_file_first", False
                ),
                allowed_after_processing=overview.get("allowed_after_processing", []),
                recommended_next_action=overview.get("recommended_next_action", {}),
                state=overview,
            )

        if action in {"complete_file", "skip_file", "error_file"}:
            state = _load_state(batch_id)
            result_key = {
                "complete_file": "completed_files",
                "skip_file": "skipped_files",
                "error_file": "error_files",
            }[action]
            try:
                state = _record_file_result(
                    state,
                    result_key,
                    args.get("file"),
                    args.get("reason") or args.get("message"),
                )
            except ValueError as e:
                return _result(False, action=action, batch_id=batch_id, error=str(e))
            _save_state(batch_id, state)
            return _result(
                True,
                action=action,
                batch_id=batch_id,
                path=str(_path_for_batch_id(batch_id)),
                state=_batch_overview(state),
            )

        if action == "finalize":
            state = _load_state(batch_id)
            patch_arg = args.get("patch")
            if patch_arg is None:
                patch = {}
            elif not isinstance(patch_arg, dict):
                return _result(
                    False,
                    error=_(
                        "err.invalid_patch",
                        default="[batch_state error] patch must be an object",
                    ),
                    batch_id=batch_id,
                )
            else:
                patch = dict(patch_arg)
            patch = {**_collect_state_patch(args), **patch}
            if patch:
                state = _merge_state(state, patch)
            state["status"] = _normalize_status(
                args.get("status") or state.get("status") or "done", "done"
            )
            state = _normalize_persisted_state(state)
            _save_state(batch_id, state)
            return _result(
                True,
                action="finalize",
                batch_id=batch_id,
                path=str(_path_for_batch_id(batch_id)),
                state=_batch_overview(state),
            )
        return _result(
            False,
            error=_(
                "err.unknown_action",
                default=f"[batch_state error] unknown action: {action!r}",
            ),
            allowed_actions=list(_TOOL_ACTIONS),
        )
    except Exception as e:
        return _result(
            False,
            error=_(
                "err.exception",
                default=f"[batch_state error] exception: {e!r}",
            ),
            exception=repr(e),
        )


if __name__ == "__main__":
    print(run_tool({"action": "list"}))
