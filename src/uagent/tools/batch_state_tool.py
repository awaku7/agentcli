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
            default="Manage batch state. Return JSON only.",
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
                        default="Action: init/load/update/append_log/finalize/list/delete",
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
                "target_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.target_files.description",
                        default="Target files for the batch task.",
                    ),
                },
                "patch": {
                    "type": "object",
                    "description": _(
                        "param.patch.description",
                        default="Partial state update to merge into the batch state.",
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


def _default_state(batch_id: str) -> Dict[str, Any]:
    now = _now_iso()
    return {
        "batch_id": batch_id,
        "status": "active",
        "task_description": "",
        "instructions": "",
        "target_files": [],
        "done_files": [],
        "pending_files": [],
        "current_file": "",
        "style_rules": [],
        "term_rules": [],
        "notes": [],
        "logs": [],
        "created_at": now,
        "updated_at": now,
        "last_updated": now,
    }


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
    state = dict(state)
    state["batch_id"] = batch_id
    now = _now_iso()
    state.setdefault("created_at", now)
    state["updated_at"] = now
    state["last_updated"] = now
    state = _reconcile_progress_state(state)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _current_file_can_move_forward(state: Dict[str, Any], current_file: str, candidate: str) -> bool:
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


def _dedupe_preserve_order(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    out: List[str] = []
    seen = set()
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _merge_unique_lists(existing: Any, incoming: Any) -> List[str]:
    base = _dedupe_preserve_order(existing)
    for item in _dedupe_preserve_order(incoming):
        if item not in base:
            base.append(item)
    return base


_STATE_PATCH_KEYS = (
    "task_description",
    "instructions",
    "target_files",
    "done_files",
    "pending_files",
    "current_file",
    "status",
    "style_rules",
    "term_rules",
    "notes",
    "logs",
)


def _collect_state_patch(args: Dict[str, Any]) -> Dict[str, Any]:
    patch: Dict[str, Any] = {}
    for key in _STATE_PATCH_KEYS:
        if key in args and args.get(key) is not None:
            patch[key] = args.get(key)
    return patch


def _normalize_status(value: Any, fallback: str = "active") -> str:
    status = str(value or "").strip()
    if not status:
        return fallback
    if status not in _ALLOWED_STATUSES:
        return fallback
    return status



def _reconcile_progress_state(state: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(state)
    out["status"] = _normalize_status(out.get("status"), "active")

    target_files = _dedupe_preserve_order(out.get("target_files"))
    if not target_files:
        out["target_files"] = []
        out["done_files"] = _dedupe_preserve_order(out.get("done_files"))
        out["pending_files"] = _dedupe_preserve_order(out.get("pending_files"))
        current_file = str(out.get("current_file") or "").strip()
        out["current_file"] = current_file if current_file in out["target_files"] else current_file
        return out

    out["target_files"] = target_files
    done_files = [item for item in _dedupe_preserve_order(out.get("done_files")) if item in target_files]
    out["done_files"] = done_files
    out["pending_files"] = [item for item in target_files if item not in done_files]

    current_file = str(out.get("current_file") or "").strip()
    if current_file not in target_files:
        current_file = out["pending_files"][0] if out["pending_files"] else ""
    elif current_file in done_files:
        current_index = target_files.index(current_file)
        current_file = next((item for item in target_files[current_index + 1 :] if item not in done_files), "")
    out["current_file"] = current_file
    return out


def _merge_state(state: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(state)
    target_files = patch.get("target_files")
    if not isinstance(target_files, list):
        target_files = state.get("target_files")

    for key, value in patch.items():
        if key == "target_files":
            if value is None:
                continue
            out[key] = _merge_unique_lists(out.get(key), value)
        elif key == "done_files":
            if value is None:
                continue
            out[key] = _merge_unique_lists(out.get(key), value)
        elif key == "pending_files":
            continue
        elif key in {"style_rules", "term_rules", "notes", "logs"}:
            if value is None:
                continue
            out[key] = _merge_unique_lists(out.get(key), value)
        elif key == "current_file":
            if value is not None:
                current_file = str(out.get("current_file") or state.get("current_file") or "").strip()
                candidate = str(value).strip()
                effective_state = dict(out)
                if isinstance(target_files, list):
                    effective_state["target_files"] = target_files
                if _current_file_can_move_forward(effective_state, current_file, candidate):
                    if current_file and current_file != candidate:
                        done_files = _dedupe_preserve_order(out.get("done_files"))
                        effective_targets = _dedupe_preserve_order(effective_state.get("target_files"))
                        if current_file in effective_targets and current_file not in done_files:
                            done_files.append(current_file)
                            out["done_files"] = done_files
                    out[key] = candidate
        elif key in {"task_description", "instructions"}:
            if value is not None:
                out[key] = str(value)
        elif key == "status":
            if value is not None:
                out[key] = _normalize_status(value, str(out.get("status") or state.get("status") or "active"))
        elif key == "batch_id":
            continue
        else:
            out[key] = value
    return out


def _batch_overview(state: Dict[str, Any]) -> Dict[str, Any]:
    state = _reconcile_progress_state(state)
    target_files = state.get("target_files", [])
    done_files = state.get("done_files", [])
    pending_files = state.get("pending_files", [])
    total_count = len(target_files) if isinstance(target_files, list) else 0
    done_count = len(done_files) if isinstance(done_files, list) else 0
    pending_count = len(pending_files) if isinstance(pending_files, list) else 0
    return {
        "batch_id": state.get("batch_id", ""),
        "status": state.get("status", ""),
        "task_description": state.get("task_description", ""),
        "current_file": state.get("current_file", ""),
        "target_files": target_files,
        "done_files": done_files,
        "pending_files": pending_files,
        "total_count": total_count,
        "done_count": done_count,
        "pending_count": pending_count,
        "progress_ratio": round(done_count / total_count, 3) if total_count else 0.0,
        "updated_at": state.get("updated_at", ""),
    }


def _result(ok: bool, **payload: Any) -> str:
    return json.dumps({"ok": ok, **payload}, ensure_ascii=False, indent=2, sort_keys=True)


def run_tool(args: Dict[str, Any]) -> str:
    action = str(args.get("action") or "").strip()
    if action not in _TOOL_ACTIONS:
        return _result(False, error=_(
            "err.unknown_action",
            default=f"[batch_state error] unknown action: {action!r}",
        ), allowed_actions=list(_TOOL_ACTIONS))

    try:
        if action == "init":
            batch_id = _normalize_batch_id(args.get("batch_id")) or f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
            batch_id = _validate_batch_id(batch_id)
            path = _path_for_batch_id(batch_id)
            if path.exists() and not bool(args.get("overwrite", False)):
                return _result(False, error=_(
                    "err.batch_exists",
                    default=f"[batch_state error] batch already exists: {batch_id}",
                ), batch_id=batch_id, path=str(path))

            state = _default_state(batch_id)
            patch = _collect_state_patch(args)
            if patch:
                state = _merge_state(state, patch)
            if isinstance(state.get("target_files"), list) and not state.get("pending_files"):
                state["pending_files"] = list(state.get("target_files") or [])
            state = _reconcile_progress_state(state)
            _save_state(batch_id, state)
            return _result(True, action="init", batch_id=batch_id, path=str(path), state=_batch_overview(state))

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
                "active_count": sum(1 for item in items if item.get("status") == "active"),
                "done_count": sum(1 for item in items if item.get("status") == "done"),
                "paused_count": sum(1 for item in items if item.get("status") == "paused"),
                "error_count": sum(1 for item in items if item.get("status") == "error"),
            }
            return _result(True, action="list", root=str(root), count=len(items), summary=summary, batches=items)

        batch_id = _validate_batch_id(_normalize_batch_id(args.get("batch_id")))

        if action == "load":
            state = _reconcile_progress_state(_load_state(batch_id))
            return _result(True, action="load", batch_id=batch_id, path=str(_path_for_batch_id(batch_id)), state=state)

        if action == "update":
            state = _load_state(batch_id)
            patch_arg = args.get("patch")
            if patch_arg is None:
                patch = {}
            elif not isinstance(patch_arg, dict):
                return _result(False, error=_(
                    "err.invalid_patch",
                    default="[batch_state error] patch must be an object",
                ), batch_id=batch_id)
            else:
                patch = dict(patch_arg)
            patch = {**_collect_state_patch(args), **patch}
            state = _merge_state(state, patch)
            state = _reconcile_progress_state(state)
            _save_state(batch_id, state)
            return _result(True, action="update", batch_id=batch_id, path=str(_path_for_batch_id(batch_id)), state=_batch_overview(state))

        if action == "append_log":
            state = _load_state(batch_id)
            message = str(args.get("message") or "").strip()
            if not message:
                return _result(False, error=_(
                    "err.message_empty",
                    default="[batch_state error] message is empty",
                ), batch_id=batch_id)
            logs = state.get("logs")
            if not isinstance(logs, list):
                logs = []
            logs.append({"ts": _now_iso(), "message": message})
            state["logs"] = logs
            _save_state(batch_id, state)
            return _result(True, action="append_log", batch_id=batch_id, path=str(_path_for_batch_id(batch_id)), state=_batch_overview(state))

        if action == "finalize":
            state = _load_state(batch_id)
            patch_arg = args.get("patch")
            if patch_arg is None:
                patch = {}
            elif not isinstance(patch_arg, dict):
                return _result(False, error=_(
                    "err.invalid_patch",
                    default="[batch_state error] patch must be an object",
                ), batch_id=batch_id)
            else:
                patch = dict(patch_arg)
            patch = {**_collect_state_patch(args), **patch}
            if patch:
                state = _merge_state(state, patch)
            state["status"] = _normalize_status(args.get("status") or state.get("status") or "done", "done")
            state = _reconcile_progress_state(state)
            _save_state(batch_id, state)
            return _result(True, action="finalize", batch_id=batch_id, path=str(_path_for_batch_id(batch_id)), state=_batch_overview(state))

        if action == "delete":
            path = _path_for_batch_id(batch_id)
            if not path.exists():
                return _result(False, error=_(
                    "err.not_found",
                    default=f"[batch_state error] batch not found: {batch_id}",
                ), batch_id=batch_id)
            path.unlink()
            return _result(True, action=action, batch_id=batch_id, path=str(path))

        return _result(False, error=_(
            "err.unknown_action",
            default=f"[batch_state error] unknown action: {action!r}",
        ), allowed_actions=list(_TOOL_ACTIONS))
    except Exception as e:
        return _result(False, error=_(
            "err.exception",
            default=f"[batch_state error] exception: {e!r}",
        ), exception=repr(e))


if __name__ == "__main__":
    print(run_tool({"action": "list"}))
