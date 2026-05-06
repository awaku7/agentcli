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

_TOOL_ACTIONS = ("init", "load", "update", "append_log", "finalize", "list", "delete")
_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ALLOWED_STATUSES = {"active", "done", "paused", "cancelled", "error"}

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "batch_state",
        "description": _(
            "tool.description",
            default="Manage batch state files for multi-file tasks under ~/.uag/batches/.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Manage batch state. Prefer targets=[{dir, files, next_index}] and current_target. "
                "Advance progress by increasing next_index. current_file is a legacy alias. "
                "Return JSON only."
            ),
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
                            "Action: init/load/update/append_log/finalize/list/delete. "
                            "Use update with patch to change targets/current_target/next_index."
                        ),
                    ),
                },
                "batch_id": {
                    "type": "string",
                    "description": _(
                        "param.batch_id.description",
                        default="Batch ID. Required for load/update/finalize/delete; optional for init/list.",
                    ),
                },
                "task_description": {
                    "type": "string",
                    "description": _(
                        "param.task_description.description",
                        default="Short description of the batch task.",
                    ),
                },
                "instructions": {
                    "type": "string",
                    "description": _(
                        "param.instructions.description",
                        default="Detailed instructions for the batch task.",
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
                            "next_index": {
                                "type": "integer",
                                "minimum": 0,
                            },
                        },
                        "required": ["files"],
                    },
                    "description": _(
                        "param.targets.description",
                        default=(
                            "Target groups. Each entry contains dir, files (dir-relative), and next_index."
                        ),
                    ),
                },
                "target_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.target_files.description",
                        default="Legacy single-target file list. Prefer targets.",
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
                            "Partial state update to merge into the batch state. Prefer patch.targets and "
                            "patch.current_target. For legacy single-target flows, patch.current_file can advance "
                            "the current target, and next_index is derived from the file order."
                        ),
                    ),
                },
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description",
                        default="Log message to append.",
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
        return {"dir": "", "files": files, "next_index": 0}

    if not isinstance(target, dict):
        return {"dir": "", "files": [], "next_index": 0}

    dir_value = _normalize_path_text(target.get("dir"))
    files = _normalize_file_list(target.get("files"))
    next_index = _coerce_int(target.get("next_index"), 0)
    if next_index < 0:
        next_index = 0
    if next_index > len(files):
        next_index = len(files)
    return {"dir": dir_value, "files": files, "next_index": next_index}


def _normalize_targets(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in value:
        out.append(_normalize_target(item))
    return out


def _single_target_from_files(files: Any) -> Dict[str, Any]:
    return {"dir": "", "files": _normalize_file_list(files), "next_index": 0}


def _legacy_next_index(
    files: List[str],
    done_files: Any,
    current_file: Any,
    pending_files: Any,
) -> int:
    current = _normalize_path_text(current_file)
    if current and current in files:
        return files.index(current)

    for item in _normalize_file_list(pending_files):
        if item in files:
            return files.index(item)

    done_set = set(_normalize_file_list(done_files))
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


def _view_target(target: Dict[str, Any]) -> Dict[str, Any]:
    files = _normalize_file_list(target.get("files"))
    next_index = _coerce_int(target.get("next_index"), 0)
    if next_index < 0:
        next_index = 0
    if next_index > len(files):
        next_index = len(files)
    display_files = _target_paths(target)
    return {
        "dir": _normalize_path_text(target.get("dir")),
        "files": files,
        "next_index": next_index,
        "current_file": (
            display_files[next_index] if next_index < len(display_files) else ""
        ),
        "pending_files": display_files[next_index:],
        "total_count": len(display_files),
        "done_count": next_index,
        "pending_count": len(display_files) - next_index,
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

    targets = out.get("targets")
    if isinstance(targets, list):
        normalized_targets = _normalize_targets(targets)
    elif out.get("target_files") is not None:
        legacy_target = _single_target_from_files(out.get("target_files"))
        legacy_target["next_index"] = _legacy_next_index(
            legacy_target["files"],
            out.get("done_files"),
            out.get("current_file"),
            out.get("pending_files"),
        )
        normalized_targets = [legacy_target]
    else:
        normalized_targets = []

    out["targets"] = normalized_targets
    current_target = _coerce_int(out.get("current_target"), 0)
    if normalized_targets:
        if current_target < 0:
            current_target = 0
        if current_target >= len(normalized_targets):
            current_target = len(normalized_targets) - 1
        if normalized_targets[current_target]["next_index"] >= len(
            normalized_targets[current_target]["files"]
        ):
            for idx in range(current_target + 1, len(normalized_targets)):
                if normalized_targets[idx]["next_index"] < len(
                    normalized_targets[idx]["files"]
                ):
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
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _current_file_can_move_forward(
    state: Dict[str, Any], current_file: str, candidate: str
) -> bool:
    if candidate == "":
        return True
    if not current_file or current_file == candidate:
        return True

    target_files = state.get("target_files")
    if not isinstance(target_files, list):
        return True

    try:
        current_index = target_files.index(current_file)
        candidate_index = target_files.index(candidate)
    except ValueError:
        return True

    return candidate_index >= current_index


def _collect_state_patch(args: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "task_description",
        "instructions",
        "targets",
        "current_target",
        "target_files",
        "done_files",
        "current_file",
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
    target_views = [_view_target(target) for target in state.get("targets", [])]
    total_count = sum(item["total_count"] for item in target_views)
    done_count = sum(item["done_count"] for item in target_views)
    pending_count = sum(item["pending_count"] for item in target_views)
    target_files = [
        item
        for view in target_views
        for item in view["pending_files"] + [view["current_file"]]
        if item
    ]
    pending_files = [item for view in target_views for item in view["pending_files"]]
    current_target = _coerce_int(state.get("current_target"), 0)
    if target_views:
        if current_target < 0:
            current_target = 0
        if current_target >= len(target_views):
            current_target = len(target_views) - 1
        current_target_view = target_views[current_target]
    else:
        current_target_view = None
        current_target = 0

    current_file = current_target_view["current_file"] if current_target_view else ""
    return {
        **state,
        "current_target": current_target,
        "current_target_dir": current_target_view["dir"] if current_target_view else "",
        "current_file": current_file,
        "target_files": target_files,
        "pending_files": pending_files,
        "total_count": total_count,
        "done_count": done_count,
        "pending_count": pending_count,
        "progress_ratio": round(done_count / total_count, 3) if total_count else 0.0,
        "target_views": target_views,
    }


def _apply_legacy_current_file(state: Dict[str, Any], candidate: Any) -> Dict[str, Any]:
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
            if candidate_index < target["next_index"]:
                return state
            target["next_index"] = candidate_index
            state["targets"] = targets
            state["current_target"] = idx
            return state
        if candidate_text in target["files"]:
            candidate_index = target["files"].index(candidate_text)
            if candidate_index < target["next_index"]:
                return state
            target["next_index"] = candidate_index
            state["targets"] = targets
            state["current_target"] = idx
            return state
    return state


def _apply_legacy_done_files(state: Dict[str, Any], done_files: Any) -> Dict[str, Any]:
    targets = _normalize_targets(state.get("targets"))
    if not targets or not isinstance(done_files, list):
        return state
    done_set = set(_normalize_file_list(done_files))
    if len(targets) == 1:
        target = targets[0]
        files = target["files"]
        next_index = 0
        for file_name in files:
            if file_name in done_set:
                next_index += 1
            else:
                break
        target["next_index"] = next_index
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
    elif "target_files" in patch and patch.get("target_files") is not None:
        out["targets"] = [_single_target_from_files(patch.get("target_files"))]

    if "current_target" in patch and patch.get("current_target") is not None:
        out["current_target"] = _coerce_int(patch.get("current_target"), 0)

    if "current_file" in patch and patch.get("current_file") is not None:
        out = _apply_legacy_current_file(out, patch.get("current_file"))

    if "done_files" in patch and patch.get("done_files") is not None:
        out = _apply_legacy_done_files(out, patch.get("done_files"))

    for key, value in patch.items():
        if key in {
            "workdir",
            "targets",
            "current_target",
            "target_files",
            "current_file",
            "done_files",
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


def _batch_overview(state: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = _state_with_progress_view(state)
    target_views = snapshot.get("target_views", [])
    return {
        "batch_id": snapshot.get("batch_id", ""),
        "status": snapshot.get("status", ""),
        "task_description": snapshot.get("task_description", ""),
        "workdir": snapshot.get("workdir", ""),
        "current_target": snapshot.get("current_target", 0),
        "current_target_dir": snapshot.get("current_target_dir", ""),
        "current_file": snapshot.get("current_file", ""),
        "targets": snapshot.get("targets", []),
        "target_views": target_views,
        "target_files": snapshot.get("target_files", []),
        "pending_files": snapshot.get("pending_files", []),
        "total_count": snapshot.get("total_count", 0),
        "done_count": snapshot.get("done_count", 0),
        "pending_count": snapshot.get("pending_count", 0),
        "progress_ratio": snapshot.get("progress_ratio", 0.0),
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
    if action not in _TOOL_ACTIONS:
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
                    items.append(_batch_overview(state))
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
            state = _state_with_progress_view(_load_state(batch_id))
            return _result(
                True,
                action="load",
                batch_id=batch_id,
                path=str(_path_for_batch_id(batch_id)),
                state=state,
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
