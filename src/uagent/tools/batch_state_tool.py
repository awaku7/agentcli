from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
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
    "finalize",
    "list",
)

_TOOL_ACTIONS = _PUBLIC_TOOL_ACTIONS
_ALL_TOOL_ACTIONS = _PUBLIC_TOOL_ACTIONS
_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ALLOWED_STATUSES = {"active", "done", "paused", "cancelled", "error"}

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "batch_state",
        "description": _(
            "tool.description",
            default="Manage persisted batch state for multi-file tasks under ~/.uag/batches/.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Manage batch state. Prefer targets=[{dir, files, index}] and current_target. "
                "Use current to fetch the current file. After processing it, call complete_file. "
                "Use complete_file, skip_file, or error_file for explicit per-file results. "
                "Return JSON only."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "batch_state",
                "batch state",
            ],
        ),
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
                            "Action: init/load/status/current/complete_file/skip_file/error_file/finalize/list. "
                            "Use current for the current file. Use complete_file after processing it."
                        ),
                    ),
                },
                "batch_id": {
                    "type": "string",
                    "description": _(
                        "param.batch_id.description",
                        default="Batch ID. Required for load/status/finalize; optional for init/list.",
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
    except (TypeError, ValueError):
        return default


def _dedupe_preserve_order(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    out: List[str] = []
    seen = set()
    for item in items:
        value = _normalize_path_text(item)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _normalize_file_list(items: Any) -> List[str]:
    return _dedupe_preserve_order(items)


def _merge_unique_lists(existing: Any, incoming: Any) -> List[str]:
    base = _dedupe_preserve_order(existing)
    for item in _dedupe_preserve_order(incoming):
        if item not in base:
            base.append(item)
    return base


def _join_display_path(dir_value: str, file_value: str) -> str:
    dir_value = _normalize_path_text(dir_value)
    file_value = _normalize_path_text(file_value)
    if dir_value and file_value:
        return f"{dir_value.rstrip('/')}/{file_value.lstrip('/')}"
    return dir_value or file_value


def _normalize_target(target: Any) -> Dict[str, Any]:
    if isinstance(target, str):
        files = _normalize_file_list([target])
        return {"dir": "", "files": files, "index": 0}

    if not isinstance(target, dict):
        return {"dir": "", "files": [], "index": 0}

    dir_value = _normalize_path_text(target.get("dir"))
    files = _normalize_file_list(target.get("files"))
    index = _coerce_int(target.get("index"), 0)
    if index < 0:
        index = 0
    if index > len(files):
        index = len(files)
    return {"dir": dir_value, "files": files, "index": index}


def _normalize_targets(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in value:
        out.append(_normalize_target(item))
    return out


def _single_target_from_files(files: Any) -> Dict[str, Any]:
    return {"dir": "", "files": _normalize_file_list(files), "index": 0}


def _legacy_index(
    files: List[str],
    processed_files: Any,
    file: Any,
    pending_files: Any,
) -> int:
    current = _normalize_path_text(file)
    if current and current in files:
        return files.index(current)

    for item in _normalize_file_list(pending_files):
        if item in files:
            return files.index(item)

    done_set = set(_normalize_file_list(processed_files))
    if done_set:
        for idx, file_name in enumerate(files):
            if file_name not in done_set:
                return idx
        return len(files)

    return 0


def _target_paths(target: Dict[str, Any]) -> List[str]:
    dir_value = _normalize_path_text(target.get("dir"))
    files = _normalize_file_list(target.get("files"))
    return [_join_display_path(dir_value, file_name) for file_name in files]


def _record_candidates(target: Dict[str, Any], index: int) -> set[str]:
    files = _normalize_file_list(target.get("files"))
    display_files = _target_paths(target)
    candidates = set()
    if 0 <= index < len(files):
        candidates.add(_normalize_path_text(files[index]))
    if 0 <= index < len(display_files):
        candidates.add(_normalize_path_text(display_files[index]))
    return {item for item in candidates if item}


def _record_set(value: Any) -> set[str]:
    return set(_normalize_file_list(value))


def _processed_record_set(state: Dict[str, Any]) -> set[str]:
    return (
        _record_set(state.get("completed_files"))
        | _record_set(state.get("skipped_files"))
        | _record_set(state.get("error_files"))
    )


def _recorded_in(candidates: set[str], records: set[str]) -> bool:
    return bool(candidates & records)


def _move_target_to_next_pending(
    target: Dict[str, Any], processed_records: set[str]
) -> Dict[str, Any]:
    target = _normalize_target(target)
    files = _normalize_file_list(target.get("files"))
    index = _coerce_int(target.get("index"), 0)
    if index < 0:
        index = 0
    while index < len(files):
        if not _recorded_in(_record_candidates(target, index), processed_records):
            break
        index += 1
    target["index"] = index
    return target


def _view_target(
    target: Dict[str, Any],
    completed_records: Any = None,
    skipped_records: Any = None,
    error_records: Any = None,
) -> Dict[str, Any]:
    target = _normalize_target(target)
    files = _normalize_file_list(target.get("files"))
    index = _coerce_int(target.get("index"), 0)
    if index < 0:
        index = 0
    if index > len(files):
        index = len(files)

    completed_set = _record_set(completed_records)
    skipped_set = _record_set(skipped_records)
    error_set = _record_set(error_records)
    display_files = _target_paths(target)

    statuses: List[Dict[str, Any]] = []
    pending_files: List[str] = []
    file = ""
    completed_count = 0
    skipped_count = 0
    error_count = 0

    for idx, display_file in enumerate(display_files):
        candidates = _record_candidates(target, idx)
        is_skipped = _recorded_in(candidates, skipped_set)
        is_error = _recorded_in(candidates, error_set)
        is_completed = idx < index or _recorded_in(candidates, completed_set)

        if is_error:
            status = "error"
            error_count += 1
        elif is_skipped:
            status = "skipped"
            skipped_count += 1
        elif is_completed:
            status = "completed"
            completed_count += 1
        else:
            status = "pending"
            pending_files.append(display_file)
            if not file:
                file = display_file

        statuses.append(
            {
                "index": idx,
                "file": files[idx] if idx < len(files) else display_file,
                "display_file": display_file,
                "status": status,
            }
        )

    processed_count = completed_count + skipped_count + error_count
    return {
        "dir": _normalize_path_text(target.get("dir")),
        "files": files,
        "index": index,
        "file": file,
        "pending_files": pending_files,
        "total_count": len(display_files),
        "done_count": processed_count,
        "completed_count": completed_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "pending_count": len(display_files) - processed_count,
        "file_statuses": statuses,
    }


def _normalize_status(value: Any, fallback: str = "active") -> str:
    status = _normalize_text(value)
    if not status:
        return fallback
    if status not in _ALLOWED_STATUSES:
        return fallback
    return status


def _normalize_persisted_state(state: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(state)
    out["batch_id"] = _normalize_text(out.get("batch_id"))
    out["status"] = _normalize_status(out.get("status"), "active")
    out["task_description"] = _normalize_text(out.get("task_description"))
    out["instructions"] = _normalize_text(out.get("instructions"))
    out["workdir"] = _normalize_path_text(out.get("workdir")) or str(Path.cwd())
    out["style_rules"] = _dedupe_preserve_order(out.get("style_rules"))
    out["term_rules"] = _dedupe_preserve_order(out.get("term_rules"))
    out["notes"] = _dedupe_preserve_order(out.get("notes"))
    out["completed_files"] = _normalize_file_list(out.get("completed_files"))
    out["skipped_files"] = _normalize_file_list(out.get("skipped_files"))
    out["error_files"] = _normalize_file_list(out.get("error_files"))

    targets = out.get("targets")
    if isinstance(targets, list):
        normalized_targets = _normalize_targets(targets)
    elif out.get("remaining_files") is not None:
        legacy_target = _single_target_from_files(out.get("remaining_files"))
        legacy_target["index"] = _legacy_index(
            legacy_target["files"],
            out.get("processed_files"),
            out.get("file"),
            out.get("pending_files"),
        )
        normalized_targets = [legacy_target]
    else:
        normalized_targets = []

    processed_records = _processed_record_set(out)
    normalized_targets = [
        _move_target_to_next_pending(target, processed_records)
        for target in normalized_targets
    ]

    out["targets"] = normalized_targets
    current_target = _coerce_int(out.get("current_target"), 0)
    if normalized_targets:
        if current_target < 0:
            current_target = 0
        if current_target >= len(normalized_targets):
            current_target = len(normalized_targets) - 1
        current_view = _view_target(
            normalized_targets[current_target],
            out.get("completed_files"),
            out.get("skipped_files"),
            out.get("error_files"),
        )
        if current_view["pending_count"] <= 0:
            for idx in range(current_target + 1, len(normalized_targets)):
                view = _view_target(
                    normalized_targets[idx],
                    out.get("completed_files"),
                    out.get("skipped_files"),
                    out.get("error_files"),
                )
                if view["pending_count"] > 0:
                    current_target = idx
                    break
    else:
        current_target = 0
    out["current_target"] = current_target
    return out


def _load_state(batch_id: str) -> Dict[str, Any]:
    path = _path_for_batch_id(batch_id)
    if not path.exists():
        raise FileNotFoundError(f"batch not found: {batch_id}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("invalid batch state")
    return data


def _save_state(batch_id: str, state: Dict[str, Any]) -> None:
    path = _path_for_batch_id(batch_id)
    state = _normalize_persisted_state(state)
    state = dict(state)
    state["batch_id"] = batch_id
    now = _now_iso()
    state.setdefault("created_at", now)
    state["updated_at"] = now
    state["last_updated"] = now

    tmp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, path)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def _file_can_move_forward(state: Dict[str, Any], file: str, candidate: str) -> bool:
    if candidate == "":
        return True
    if not file or file == candidate:
        return True

    remaining_files = state.get("remaining_files")
    if not isinstance(remaining_files, list):
        return True

    try:
        current_index = remaining_files.index(file)
        candidate_index = remaining_files.index(candidate)
    except ValueError:
        return True

    return candidate_index >= current_index


def _collect_state_patch(args: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "task_description",
        "instructions",
        "targets",
        "current_target",
        "remaining_files",
        "processed_files",
        "file",
        "status",
        "style_rules",
        "term_rules",
        "notes",
        "workdir",
    )
    patch: Dict[str, Any] = {}
    for key in keys:
        if key in args and args.get(key) is not None:
            patch[key] = args.get(key)
    return patch


def _state_with_progress_view(state: Dict[str, Any]) -> Dict[str, Any]:
    state = _normalize_persisted_state(state)
    completed_files = state.get("completed_files", [])
    skipped_files = state.get("skipped_files", [])
    error_files = state.get("error_files", [])
    target_views = [
        _view_target(target, completed_files, skipped_files, error_files)
        for target in state.get("targets", [])
    ]
    total_count = sum(item["total_count"] for item in target_views)
    done_count = sum(item["done_count"] for item in target_views)
    completed_count = sum(item.get("completed_count", 0) for item in target_views)
    skipped_count = sum(item.get("skipped_count", 0) for item in target_views)
    error_count = sum(item.get("error_count", 0) for item in target_views)
    pending_count = sum(item["pending_count"] for item in target_views)
    pending_files = [item for view in target_views for item in view["pending_files"]]
    remaining_files = pending_files[:]
    current_target = _coerce_int(state.get("current_target"), 0)
    if target_views:
        if current_target < 0:
            current_target = 0
        if current_target >= len(target_views):
            current_target = len(target_views) - 1
        if target_views[current_target]["pending_count"] <= 0:
            for idx, view in enumerate(target_views):
                if view["pending_count"] > 0:
                    current_target = idx
                    break
        current_target_view = target_views[current_target]
    else:
        current_target_view = None
        current_target = 0

    file = current_target_view["file"] if current_target_view else ""
    recommendation = _recommended_next_action(state, file, pending_count)
    return {
        **state,
        "current_target": current_target,
        "current_target_dir": current_target_view["dir"] if current_target_view else "",
        "file": file,
        "remaining_files": remaining_files,
        "pending_files": pending_files,
        "total_count": total_count,
        "done_count": done_count,
        "completed_count": completed_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "pending_count": pending_count,
        "progress_ratio": round(done_count / total_count, 3) if total_count else 0.0,
        "recommended_next_action": recommendation,
        "target_views": target_views,
    }


def _apply_legacy_file(state: Dict[str, Any], candidate: Any) -> Dict[str, Any]:
    candidate_text = _normalize_path_text(candidate)
    if not candidate_text:
        return state

    targets = _normalize_targets(state.get("targets"))
    if not targets:
        return state

    current_target = _coerce_int(state.get("current_target"), 0)
    search_order = list(range(current_target, len(targets))) + list(
        range(0, current_target)
    )
    for idx in search_order:
        target = targets[idx]
        display_files = _target_paths(target)
        if candidate_text in display_files:
            candidate_index = display_files.index(candidate_text)
            if candidate_index < target["index"]:
                return state
            target["index"] = candidate_index
            state["targets"] = targets
            state["current_target"] = idx
            return state
        if candidate_text in target["files"]:
            candidate_index = target["files"].index(candidate_text)
            if candidate_index < target["index"]:
                return state
            target["index"] = candidate_index
            state["targets"] = targets
            state["current_target"] = idx
            return state
    return state


def _apply_legacy_processed_files(
    state: Dict[str, Any], processed_files: Any
) -> Dict[str, Any]:
    targets = _normalize_targets(state.get("targets"))
    if not targets or not isinstance(processed_files, list):
        return state
    done_set = set(_normalize_file_list(processed_files))
    if len(targets) == 1:
        target = targets[0]
        files = target["files"]
        index = 0
        for file_name in files:
            if file_name in done_set:
                index += 1
            else:
                break
        target["index"] = index
        state["targets"] = targets
        return state
    return state


def _merge_state(state: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(state)

    if "workdir" in patch and patch.get("workdir") is not None:
        out["workdir"] = _normalize_path_text(patch.get("workdir")) or out.get(
            "workdir", ""
        )

    if "targets" in patch and patch.get("targets") is not None:
        out["targets"] = _normalize_targets(patch.get("targets"))
    elif "remaining_files" in patch and patch.get("remaining_files") is not None:
        out["targets"] = [_single_target_from_files(patch.get("remaining_files"))]

    if "current_target" in patch and patch.get("current_target") is not None:
        out["current_target"] = _coerce_int(patch.get("current_target"), 0)

    if "file" in patch and patch.get("file") is not None:
        out = _apply_legacy_file(out, patch.get("file"))

    if "processed_files" in patch and patch.get("processed_files") is not None:
        out = _apply_legacy_processed_files(out, patch.get("processed_files"))

    for key, value in patch.items():
        if key in {
            "workdir",
            "targets",
            "current_target",
            "remaining_files",
            "file",
            "processed_files",
            "batch_id",
        }:
            continue
        if key in {"task_description", "instructions"}:
            out[key] = _normalize_text(value)
        elif key == "status":
            out[key] = _normalize_status(
                value, str(out.get("status") or state.get("status") or "active")
            )
        elif key in {"style_rules", "term_rules", "notes"}:
            if value is not None:
                out[key] = _merge_unique_lists(out.get(key), value)
        else:
            out[key] = value
    return out


def _recommended_next_action(
    state: Dict[str, Any], file: str, pending_count: int
) -> Dict[str, Any]:
    batch_id = _normalize_text(state.get("batch_id"))
    if file:
        return {
            "action": "current",
            "batch_id": batch_id,
            "file": file,
            "after": "processing file",
            "allowed_after_processing": [
                "complete_file",
                "skip_file",
                "error_file",
            ],
        }
    if pending_count <= 0 and state.get("targets"):
        return {"action": "finalize", "batch_id": batch_id}
    return {"action": "status", "batch_id": batch_id}


def _list_item(state: Dict[str, Any]) -> Dict[str, Any]:
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
        "recommended_next_action": snapshot.get("recommended_next_action", {}),
        "updated_at": snapshot.get("updated_at", ""),
    }


def _append_log_entry(
    state: Dict[str, Any], message: str, **extra: Any
) -> Dict[str, Any]:
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


def _remove_file_record(records: Any, file_value: str) -> List[str]:
    needle = _normalize_path_text(file_value)
    if not needle:
        return _normalize_file_list(records)
    return [item for item in _normalize_file_list(records) if item != needle]


def _resolve_record_file(
    state: Dict[str, Any], file_value: Any = None
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
    state: Dict[str, Any],
    result_key: str,
    file_value: Any = None,
    reason: Any = None,
) -> Dict[str, Any]:
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


def _batch_overview(state: Dict[str, Any]) -> Dict[str, Any]:
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
        "recommended_next_action": snapshot.get("recommended_next_action", {}),
        "updated_at": snapshot.get("updated_at", ""),
    }


def _default_state(batch_id: str) -> Dict[str, Any]:
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


def run_tool(args: Dict[str, Any]) -> str:
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
            items: List[Dict[str, Any]] = []
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
        if action == "load":
            state = _load_state(batch_id)
            return _result(
                True,
                action="load",
                batch_id=batch_id,
                path=str(_path_for_batch_id(batch_id)),
                state=_batch_overview(state),
            )

        if action == "status":
            state = _load_state(batch_id)
            return _result(
                True,
                action="status",
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

        if action == "update":
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
            state = _normalize_persisted_state(state)
            _save_state(batch_id, state)
            return _result(
                True,
                action="update",
                batch_id=batch_id,
                path=str(_path_for_batch_id(batch_id)),
                state=_batch_overview(state),
            )

        if action == "reset":
            state = _load_state(batch_id)
            targets = _normalize_targets(state.get("targets"))
            for target in targets:
                if isinstance(target, dict):
                    target["index"] = 0
            state["targets"] = targets
            state["current_target"] = 0
            state["status"] = "active"
            state["completed_files"] = []
            state["skipped_files"] = []
            state["error_files"] = []
            state = _normalize_persisted_state(state)
            _save_state(batch_id, state)
            return _result(
                True,
                action="reset",
                batch_id=batch_id,
                path=str(_path_for_batch_id(batch_id)),
                state=_batch_overview(state),
            )

        if action == "append_log":
            state = _load_state(batch_id)
            message = str(args.get("message") or "").strip()
            if not message:
                return _result(
                    False,
                    error=_(
                        "err.message_empty",
                        default="[batch_state error] message is empty",
                    ),
                    batch_id=batch_id,
                )
            logs = state.get("logs")
            if not isinstance(logs, list):
                logs = []
            logs.append({"ts": _now_iso(), "message": message})
            state["logs"] = logs
            _save_state(batch_id, state)
            return _result(
                True,
                action="append_log",
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
        if action == "delete":
            path = _path_for_batch_id(batch_id)
            if not path.exists():
                return _result(
                    False,
                    error=_(
                        "err.not_found",
                        default=f"[batch_state error] batch not found: {batch_id}",
                    ),
                    batch_id=batch_id,
                )
            path.unlink()
            return _result(True, action=action, batch_id=batch_id, path=str(path))

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
