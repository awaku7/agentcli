"""Web API routes (split from web.py)."""

from __future__ import annotations

import json
import os
import threading

from fastapi import Request
from fastapi.responses import JSONResponse
from ..i18n import _
from .. import core
from ..providers import util_providers as providers
from .. import util_tools as tools_util
from ..tools import long_memory as _long_memory_mod
from .. import profile_manager as _profile_mod
from .agent_worker import run_agent_worker
from .app import app
from .rooms import _handle_mode_command, web_manager

# Tool genre state (initially all disabled; toggled via API)
_genre_enabled: dict[str, bool] = {}


def _web_genre_labels() -> dict[str, str]:
    """Human-readable labels for every genre, kept in sync with _GENRE_BITMAP."""
    return {
        "basic": _("Basic (env, time, prompts, skills, memory, tools control)"),
        "file": _(
            "File (create, delete, read, write, search, zip, rename, hash, grep, list dir)"
        ),
        "comm": _("Communication (Teams, Discord, Bluesky)"),
        "office": _("Office (Excel, Word, PDF, PPT, document extraction)"),
        "devel": _(
            "Development (lint, test, git, DB, screenshot, browser, binary, compile)"
        ),
        "iot": _(
            "IoT (Bluetooth/BLE, ECHONET, Matter, SwitchBot, UPnP, camera, geo-IP)"
        ),
        "exec": _("Execution (cmd, python, pwsh, bash, sub-agent)"),
        "external": _("External (A2A, MCP, fetch, search web)"),
        "media": _("Media (image gen/edit/analyze, audio, QR code)"),
        "index": _(
            "Index (source/document parsers: py2idx, md2idx, excel2idx, csv2idx, ...)"
        ),
        "dev": _("Dev (lint_js_ts, mdformat_check)"),
        "web": _("Web (UCP commerce, public transit route)"),
        "utility": _("Utility (geodesic distance, pdf export, quantities)"),
    }


@app.get("/api/tool-genres")
async def get_tool_genres():
    """Return list of available genres and their current enabled state."""
    from ..tools._genre_control_util import _GENRE_BITMAP

    labels = _web_genre_labels()
    return {
        "genres": [
            {
                "key": genre,
                "label": labels.get(genre, genre),
                "enabled": _genre_enabled.get(genre, False),
            }
            for genre in _GENRE_BITMAP
        ],
        "busy": (
            web_manager.status.get("busy", False)
            if hasattr(web_manager, "status")
            else False
        ),
    }


@app.post("/api/tool-genres")
async def set_tool_genre(req: Request):
    """Toggle a tool genre on/off. Only allowed when idle."""
    from ..tools._genre_control_util import _GENRE_BITMAP
    from ..tools.genre_control_tool import _set_genre_tools_enabled

    body = await req.json()
    genre = str(body.get("genre", "")).strip().lower()
    enabled = bool(body.get("enabled", False))

    # Reject if busy
    busy = bool(getattr(core, "status_busy", False))
    if busy:
        return JSONResponse(
            status_code=409,
            content={
                "error": "Cannot change genres while busy. Wait for the current task to complete."
            },
        )

    if genre not in _GENRE_BITMAP:
        return JSONResponse(
            status_code=400, content={"error": f"Unknown genre: {genre}"}
        )

    try:
        msg = _set_genre_tools_enabled(genre, enabled)
        _genre_enabled[genre] = enabled
        return {"ok": True, "genre": genre, "enabled": enabled, "message": msg}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/tools-enabled")
async def get_tools_enabled():
    """Return whether tool sending to LLM is currently enabled."""
    return {"enabled": bool(getattr(core, "tools_enabled", True))}


@app.post("/api/tools-enabled")
async def set_tools_enabled(req: Request):
    """Toggle tool sending to LLM on/off. Only allowed when idle."""
    if bool(getattr(core, "status_busy", False)):
        return JSONResponse(
            status_code=409,
            content={
                "error": "Cannot change tools-enabled while busy. Wait for the current task to complete."
            },
        )
    body = await req.json()
    enabled = bool(body.get("enabled", True))
    core.tools_enabled = enabled
    state = "ON" if enabled else "OFF"
    return {
        "ok": True,
        "enabled": enabled,
        "message": f"Tool sending to LLM is now {state}",
    }


@app.get("/api/memories")
async def get_memories():
    """Return all long-term memory entries as structured JSON."""
    records = _long_memory_mod.load_long_memory_records()
    result = []
    for idx, rec in enumerate(records):
        ts = rec.get("ts")
        if isinstance(ts, (int, float)):
            import time as _t

            dt = _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(ts))
        else:
            dt = None
        result.append(
            {
                "idx": idx,
                "ts": ts,
                "datetime": dt,
                "note": str(rec.get("note", "")),
            }
        )
    return {"ok": True, "memories": result}


@app.post("/api/memories")
async def add_memory(req: Request):
    """Append a long-term memory entry."""
    body = await req.json()
    note = str(body.get("note", "")).strip()
    if not note:
        return JSONResponse(status_code=400, content={"error": "note is required"})
    _long_memory_mod.append_long_memory(note)
    return {"ok": True}


@app.put("/api/memories/{index}")
async def update_memory(index: int, req: Request):
    """Update a long-term memory entry in-place (preserves order)."""
    body = await req.json()
    new_note = str(body.get("note", "")).strip()
    if not new_note:
        return JSONResponse(status_code=400, content={"error": "note is required"})
    ok = _long_memory_mod.update_long_memory_entry(index, new_note)
    if not ok:
        return JSONResponse(
            status_code=404, content={"error": f"index {index} out of range"}
        )
    return {"ok": True}


@app.delete("/api/memories/{index}")
async def delete_memory(index: int):
    """Delete a long-term memory entry."""
    ok = _long_memory_mod.delete_long_memory_entry(index)
    if not ok:
        return JSONResponse(
            status_code=404, content={"error": f"index {index} out of range"}
        )
    return {"ok": True}


@app.get("/api/profile")
async def get_profile():
    """Return current profile data."""
    profile = _profile_mod.load_profile()
    return {"ok": True, "profile": profile}


@app.post("/api/profile/clear")
async def clear_profile():
    """Clear profile file."""
    try:
        path = _profile_mod.get_profile_file_path()
        if os.path.exists(path):
            os.remove(path)
        return {"ok": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/profile/fromlog")
async def profile_from_logs():
    """Rebuild profile from past logs."""
    from .. import core as _core_mod

    result = _profile_mod.profile_from_logs(_core_mod, max_log_files=100)
    if result:
        return {"ok": True, "profile": result}
    return {"ok": False, "error": "Failed to build profile from logs"}


@app.put("/api/profile")
async def update_profile(req: Request):
    """Update profile in-place. Body: {"environment": {...}, "preferences": [...], "constraints": [...]}"""
    body = await req.json()
    current = _profile_mod.load_profile()
    # Merge: only update provided keys
    for key in ("environment", "preferences", "constraints"):
        if key in body:
            current[key] = body[key]
    _profile_mod.save_profile(current)
    return {"ok": True, "profile": current}


def _log_first_user_message(path: str, limit: int = 120) -> str:
    """Return an existing log summary, falling back to the first user message."""
    first_user = ""
    existing_summary = ""
    try:
        with open(path, encoding="utf-8") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if not isinstance(record, dict):
                    continue
                # Prefer metadata already present in the log.
                if not existing_summary:
                    for key in ("summary", "session_summary", "title"):
                        value = record.get(key)
                        if isinstance(value, str) and value.strip():
                            existing_summary = (
                                value.replace("\r", " ").replace("\n", " ").strip()
                            )
                            break
                if record.get("role") == "user" and not first_user:
                    text = (
                        str(record.get("content") or "")
                        .replace("\r", " ")
                        .replace("\n", " ")
                        .strip()
                    )
                    if text:
                        first_user = text
    except Exception:
        pass
    title = existing_summary or first_user
    return title[:limit] + ("…" if len(title) > limit else "") if title else ""


@app.get("/api/logs")
async def get_logs(page: int = 1, per_page: int = 15):
    """Return paginated JSONL logs or SQLite sessions."""
    if (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() == "sqlite"
        and getattr(core, "session_store", None) is not None
    ):
        store = core.session_store
        current_id = getattr(core, "session_id", None)
        rows = [r for r in store.list_sessions() if r["session_id"] != current_id]
        items = []
        for row in rows:
            state = store.latest_response_state(row["session_id"])
            items.append(
                {
                    "path": row["session_id"],
                    "name": row["session_id"],
                    "project": row.get("project"),
                    "entry_point": row.get("entry_point"),
                    "summary": row.get("summary") or "",
                    "first_message": row.get("first_message") or "",
                    "last_message": row.get("last_message") or "",
                    "size": 0,
                    "mtime": row.get("created_at"),
                    "has_responses_state": state is not None,
                    "response_count": 1 if state else 0,
                    "response_status": (
                        state.get("status", "unknown") if state else "none"
                    ),
                    "latest_response_id": state.get("response_id", "") if state else "",
                    "response_provider": state.get("provider", "") if state else "",
                    "response_model": state.get("model", "") if state else "",
                }
            )
        total = len(items)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        return {
            "ok": True,
            "logs": items[start : start + per_page],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }

    files = core.find_log_files(exclude_current=True)
    items = []
    for f in files:
        try:
            st = os.stat(f)
            items.append(
                {
                    "path": f,
                    "name": os.path.basename(f),
                    "summary": _log_first_user_message(f),
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                }
            )
            state_records = core.read_responses_state_records(f)
            latest_state = state_records[-1] if state_records else None
            items[-1].update(
                {
                    "has_responses_state": bool(state_records),
                    "response_count": len(state_records),
                    "response_status": (
                        str(latest_state.get("status") or "unknown")
                        if latest_state
                        else "none"
                    ),
                    "latest_response_id": (
                        str(latest_state.get("response_id") or "")
                        if latest_state
                        else ""
                    ),
                    "response_provider": (
                        str(latest_state.get("provider") or "") if latest_state else ""
                    ),
                    "response_model": (
                        str(latest_state.get("model") or "") if latest_state else ""
                    ),
                }
            )
        except Exception:
            pass
    # Sort by mtime descending
    items.sort(key=lambda x: x.get("mtime", 0) or 0, reverse=True)  # type: ignore[return-value]
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "ok": True,
        "logs": items[start:end],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


@app.get("/api/logs/preview-by-path")
async def get_log_preview_by_path(path: str = ""):
    """Return first/last messages of a log file by path."""
    if not path:
        return JSONResponse(status_code=400, content={"error": _("path is required")})
    if (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() == "sqlite"
        and getattr(core, "session_store", None) is not None
    ):
        rows = [
            r
            for r in core.session_store.list_sessions()
            if r["session_id"] != getattr(core, "session_id", None)
        ]
        matches = [i for i, row in enumerate(rows) if row["session_id"] == path]
        if not matches:
            return JSONResponse(status_code=404, content={"error": _("File not found")})
        return await get_log_preview(matches[0])
    files = core.find_log_files(exclude_current=True)
    norm = os.path.normpath(path)
    matches = [i for i, f in enumerate(files) if os.path.normpath(f) == norm]
    if not matches:
        return JSONResponse(status_code=404, content={"error": _("File not found")})
    idx = matches[0]
    return await get_log_preview(idx)


@app.get("/api/logs/{index}/preview")
async def get_log_preview(index: int):
    """Return first/last messages of a JSONL log or SQLite session."""
    if (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() == "sqlite"
        and getattr(core, "session_store", None) is not None
    ):
        store = core.session_store
        rows = [
            r
            for r in store.list_sessions()
            if r["session_id"] != getattr(core, "session_id", None)
        ]
        if index < 0 or index >= len(rows):
            return JSONResponse(
                status_code=404, content={"error": _("Index out of range")}
            )
        row = rows[index]
        messages = store.list_messages(row["session_id"])
        users = [
            str(m.get("content") or "").strip()
            for m in messages
            if m.get("role") == "user"
        ]
        return {
            "ok": True,
            "index": index,
            "path": row["session_id"],
            "name": row["session_id"],
            "mtime": row.get("created_at"),
            "summary": row.get("summary") or "",
            "total_user": sum(m.get("role") == "user" for m in messages),
            "total_assistant": sum(m.get("role") == "assistant" for m in messages),
            "total_tool": sum(m.get("role") == "tool" for m in messages),
            "preserved_system": sum(m.get("role") == "system" for m in messages),
            "total_messages": len(messages),
            "first_user": users[0][:200] if users else "",
            "last_user": users[-1][:200] if users else "",
        }

    files = core.find_log_files(exclude_current=True)
    if index < 0 or index >= len(files):
        return JSONResponse(status_code=404, content={"error": _("Index out of range")})
    path = files[index]
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = None
    first_user = ""
    last_user = ""
    total_user = 0
    total_assistant = 0
    total_tool = 0
    preserved_system = 0
    last_cwd_path = None
    try:
        with open(path, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = json.loads(ln)
                except Exception:
                    continue
                role = obj.get("role")
                if role == "user":
                    total_user += 1
                    content = str(obj.get("content") or "").strip()
                    if content:
                        if not first_user:
                            first_user = content[:200]
                        last_user = content[:200]
                elif role == "assistant":
                    total_assistant += 1
                elif role == "tool":
                    total_tool += 1
                elif role == "system":
                    content = obj.get("content")
                    if isinstance(content, str):
                        if content.startswith("[SKILL] ") or content.startswith(
                            "[HOOK] "
                        ):
                            preserved_system += 1
                        if content.startswith("[CWD] "):
                            try:
                                cobj = json.loads(content[len("[CWD] ") :].strip())
                            except Exception:
                                cobj = None
                            if isinstance(cobj, dict):
                                p = cobj.get("path")
                                if isinstance(p, str) and p.strip():
                                    last_cwd_path = p
    except Exception:
        pass
    # Match CLI :logs / :load "Conversation message count":
    # 1 (re-inserted SYSTEM_PROMPT) + preserved [SKILL]/[HOOK] system messages
    # + user/assistant/tool messages + [CWD] marker when auto-restored.
    cwd_bonus = 1 if (last_cwd_path and os.path.isdir(last_cwd_path)) else 0
    total_messages = (
        1 + preserved_system + total_user + total_assistant + total_tool + cwd_bonus
    )
    return {
        "ok": True,
        "index": index,
        "path": path,
        "name": os.path.basename(path),
        "mtime": mtime,
        "total_user": total_user,
        "total_assistant": total_assistant,
        "total_tool": total_tool,
        "preserved_system": preserved_system,
        "total_messages": total_messages,
        "first_user": first_user,
        "last_user": last_user,
    }


@app.post("/api/command")
async def api_command(req: Request):
    """Execute a :command via REST API. Body: {"room_id": "...", "command": ":cd /path"}"""
    try:
        body = await req.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": _("Invalid JSON body")})
    room_id = str(body.get("room_id", "")).strip()
    cmd_line = str(body.get("command", "")).strip()
    if not room_id or not cmd_line:
        return JSONResponse(
            status_code=400,
            content={"error": _("room_id and command are required")},
        )
    room = web_manager.get_room(room_id)
    if not cmd_line.startswith(":"):
        cmd_line = f":{cmd_line}"
    if _handle_mode_command(cmd_line):
        return {"ok": True, "command": cmd_line, "result": "mode_changed"}
    # :cd -> room.set_base_dir() (room-scoped, no os.chdir())
    if cmd_line.lstrip(":").strip().startswith("cd"):
        _cd_arg = cmd_line.lstrip(":").strip()[3:].strip()
        try:
            room.set_base_dir(_cd_arg or ".")
            return {"ok": True, "command": "cd", "workdir": room.base_dir}
        except Exception as _cd_e:
            return JSONResponse(status_code=400, content={"error": str(_cd_e)})
    try:
        _client, _depname = None, ""
        try:
            _pname, _client, _depname = providers.make_client(core)
        except Exception:
            pass
        import io as _io
        import sys as _sys

        _capture = _io.StringIO()
        _old_stdout = _sys.stdout
        try:
            _sys.stdout = _capture
            _result = tools_util.handle_command(
                cmd_line, room.history, _client, _depname, core=core
            )
        finally:
            _sys.stdout = _old_stdout
        _output = _capture.getvalue().strip()
        if isinstance(_result, tools_util.CommandResult) and _result.run_llm:
            threading.Thread(
                target=run_agent_worker,
                args=(room, _result.prompt, None),
                daemon=True,
            ).start()
            return {
                "ok": True,
                "command": cmd_line,
                "run_llm": True,
                "prompt": _result.prompt,
            }
        if _output:
            room.add_message(
                {
                    "role": "assistant",
                    "content": _output,
                }
            )
        return {"ok": True, "command": cmd_line, "run_llm": False}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
