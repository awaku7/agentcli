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

_TOOL_ACTIONS = ("init", "load", "update", "append_log", "finalize", "list", "delete", "purge")
_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

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
                        default="Action: init/load/update/append_log/finalize/list/delete/purge",
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


def _merge_state(state: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(state)
    target_files = patch.get("target_files")
    if not isinstance(target_files, list):
        target_files = state.get("target_files")

    for key, value in patch.items():
        if key in {"target_files", "done_files", "pending_files", "style_rules", "term_rules", "notes", "logs"}:
            if value is None:
                continue
            if isinstance(value, list):
                out[key] = value
            else:
                out[key] = [value]
        elif key == "current_file":
            if value is not None:
                current_file = str(out.get("current_file") or state.get("current_file") or "")
                candidate = str(value)
                effective_state = dict(out)
                if isinstance(target_files, list):
                    effective_state["target_files"] = target_files
                if _current_file_can_move_forward(effective_state, current_file, candidate):
                    out[key] = candidate
        elif key in {"task_description", "instructions", "status"}:
            if value is not None:
                out[key] = str(value)
        elif key == "batch_id":
            continue
        else:
            out[key] = value
    return out


def _batch_overview(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "batch_id": state.get("batch_id", ""),
        "status": state.get("status", ""),
        "task_description": state.get("task_description", ""),
        "current_file": state.get("current_file", ""),
        "target_files": state.get("target_files", []),
        "done_files": state.get("done_files", []),
        "pending_files": state.get("pending_files", []),
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
            patch = {
                k: args.get(k)
                for k in ("task_description", "instructions", "target_files", "style_rules", "term_rules", "notes", "current_file", "status")
                if args.get(k) is not None
            }
            if patch:
                state = _merge_state(state, patch)
            if isinstance(state.get("target_files"), list) and not state.get("pending_files"):
                state["pending_files"] = list(state.get("target_files") or [])
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
            return _result(True, action="list", root=str(root), count=len(items), batches=items)

        batch_id = _validate_batch_id(_normalize_batch_id(args.get("batch_id")))

        if action == "load":
            state = _load_state(batch_id)
            return _result(True, action="load", batch_id=batch_id, path=str(_path_for_batch_id(batch_id)), state=state)

        if action == "update":
            state = _load_state(batch_id)
            patch = args.get("patch") or {}
            if not isinstance(patch, dict):
                return _result(False, error=_(
                    "err.invalid_patch",
                    default="[batch_state error] patch must be an object",
                ), batch_id=batch_id)
            state = _merge_state(state, patch)
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
            patch = args.get("patch") or {}
            if patch:
                if not isinstance(patch, dict):
                    return _result(False, error=_(
                        "err.invalid_patch",
                        default="[batch_state error] patch must be an object",
                    ), batch_id=batch_id)
                state = _merge_state(state, patch)
            state["status"] = str(args.get("status") or state.get("status") or "done")
            _save_state(batch_id, state)
            return _result(True, action="finalize", batch_id=batch_id, path=str(_path_for_batch_id(batch_id)), state=_batch_overview(state))

        if action in {"delete", "purge"}:
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
