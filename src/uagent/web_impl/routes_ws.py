"""WebSocket endpoint (split from web.py)."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import threading

from fastapi import WebSocket, WebSocketDisconnect
from ..i18n import _
from .. import core
from ..providers import util_providers as providers
from .. import util_tools as tools_util
from ..tools.pybitchat_shared import forward_to_mesh, is_chat_mode
from .agent_worker import run_agent_worker
from .app import app
from .helpers import _enrich_message_attachments, _load_input_history
from .history import _bootstrap_room_on_connect
from .io import _web_server_log
from .rooms import (
    _broadcast_modes_all,
    _handle_mode_command,
    web_manager,
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    room_id = websocket.query_params.get("room")
    ws_lang = (websocket.query_params.get("lang") or "").lower().strip()
    if ws_lang not in ("ja", "en", "ar"):
        ws_lang = "en"
    if not room_id:
        # require explicit room for safety
        await websocket.close(code=1008)
        return
    room = web_manager.get_room(room_id)
    try:
        room.lang = ws_lang
    except Exception:
        pass
    await room.connect(websocket)
    room.loop = asyncio.get_event_loop()
    # Ask AGENTS.md / init history immediately (no user message required).
    _bootstrap_room_on_connect(room)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("type") == "user_input":
                user_text = payload.get("text")
                if _handle_mode_command(str(user_text or "")):
                    continue
                forward_to_mesh(str(user_text or ""))
                if is_chat_mode() == "on":
                    continue
                threading.Thread(
                    target=run_agent_worker,
                    args=(room, user_text, payload.get("attachments")),
                    daemon=True,
                ).start()

            elif payload.get("type") == "command":
                cmd_text = str(payload.get("text") or "").strip()
                if _handle_mode_command(cmd_text):
                    continue
                # Route all other :commands through handle_command()
                try:
                    _cmd_line = cmd_text if cmd_text.startswith(":") else f":{cmd_text}"
                    # :cd -> room.set_base_dir() (room-scoped, no os.chdir())
                    if _cmd_line.lstrip(":").strip().startswith("cd"):
                        _cd_arg = _cmd_line.lstrip(":").strip()[3:].strip()
                        try:
                            room.set_base_dir(_cd_arg or ".")
                        except Exception as _cd_e:
                            room.add_message(
                                {
                                    "role": "assistant",
                                    "content": _("[Error] :cd failed: %(err)s")
                                    % {"err": _cd_e},
                                }
                            )
                        continue
                    _wc_client, _wc_depname = None, ""
                    try:
                        _wc_pname, _wc_client, _wc_depname = providers.make_client(core)
                    except Exception:
                        pass
                    import io as _io
                    import sys as _sys

                    _capture = _io.StringIO()
                    _old_stdout = _sys.stdout
                    try:
                        _sys.stdout = _capture
                        _result = tools_util.handle_command(
                            _cmd_line, room.history, _wc_client, _wc_depname, core=core
                        )
                    finally:
                        _sys.stdout = _old_stdout
                    # :load replaces the server-side history. Refresh the
                    # browser instead of appending a second copy to it.
                    if _cmd_line.lstrip().lower().startswith(":load"):
                        loaded_display = []
                        for _message in room.history:
                            if not isinstance(_message, dict):
                                continue
                            loaded_display.append(
                                _enrich_message_attachments(
                                    {
                                        "role": _message.get("role"),
                                        "content": _message.get("content", ""),
                                        "name": _message.get("name"),
                                        "tool_calls": _message.get("tool_calls"),
                                        "attachments": _message.get("attachments"),
                                        "saved_path": _message.get("saved_path"),
                                        "saved_files": _message.get("saved_files"),
                                        "timestamp": datetime.now().isoformat(),
                                    }
                                )
                            )
                        room.messages = loaded_display
                        await room.broadcast(
                            {
                                "type": "init",
                                "messages": loaded_display,
                                "input_history": _load_input_history(),
                                "status": room.status,
                                "room_id": room.room_id,
                            }
                        )
                    _output = _capture.getvalue().strip()
                    if (
                        isinstance(_result, tools_util.CommandResult)
                        and _result.run_llm
                    ):
                        threading.Thread(
                            target=run_agent_worker,
                            args=(room, _result.prompt, None),
                            daemon=True,
                        ).start()
                    elif _output:
                        room.add_message(
                            {
                                "role": "assistant",
                                "content": _output,
                            }
                        )
                except Exception as _e:
                    room.add_message(
                        {
                            "role": "assistant",
                            "content": _("[Command Error] %(err)s") % {"err": _e},
                        }
                    )

            elif payload.get("type") == "set_modes":
                r = payload.get("reasoning")
                v = payload.get("verbosity")
                try:
                    if r is not None:
                        tools_util.apply_reasoning_arg(str(r))
                except Exception:
                    pass
                try:
                    if v is not None:
                        tools_util.apply_verbosity_arg(str(v))
                except Exception:
                    pass
                _broadcast_modes_all()

            elif payload.get("type") == "interrupt":
                from uagent import core as _core

                try:
                    _web_server_log(
                        f"[web-interrupt] room={str(room.room_id)[:8]} "
                        f"core_busy={bool(getattr(_core, 'status_busy', False))} "
                        f"ask_pending={bool(getattr(room, 'human_ask_pending', False))} "
                        f"label={getattr(_core, 'status_label', '')}"
                    )
                except Exception:
                    pass

                # Unblock pending human_ask even if status was cleared to WAIT.
                if getattr(room, "human_ask_pending", False):
                    try:
                        room.human_ask_cancelled = True
                        room.human_ask_result = ""
                        room.human_ask_sync_event.set()
                    except Exception:
                        pass

                # NOP if not busy and no pending ask
                if not getattr(_core, "status_busy", False) and not getattr(
                    room, "human_ask_pending", False
                ):
                    # human_ask_pending may already be cleared by the waiter;
                    # still allow interrupt flag for in-flight LLM.
                    if not getattr(room, "human_ask_cancelled", False):
                        continue
                with _core.interrupt_lock:
                    _core.interrupt_requested = True
                try:
                    if room.loop:
                        asyncio.run_coroutine_threadsafe(
                            room.broadcast(
                                {
                                    "type": "log",
                                    "content": "[INTERRUPT] Stop requested by user.",
                                }
                            ),
                            room.loop,
                        )
                except Exception:
                    pass

            elif payload.get("type") == "human_ask_response":
                if not getattr(room, "human_ask_pending", False):
                    try:
                        _web_server_log(
                            f"[web-ask] drop late response room={str(room.room_id)[:8]}"
                        )
                    except Exception:
                        pass
                    continue
                room.human_ask_cancelled = False
                room.human_ask_result = payload.get("text", "")
                try:
                    _web_server_log(
                        f"[web-ask] response room={str(room.room_id)[:8]} "
                        f"len={len(str(room.human_ask_result or ''))}"
                    )
                except Exception:
                    pass
                room.human_ask_sync_event.set()

                try:
                    is_pw = bool(payload.get("is_password", False))
                    display = "[SECRET]" if is_pw else room.human_ask_result
                    if room.loop:
                        asyncio.run_coroutine_threadsafe(
                            room.broadcast(
                                {"type": "log", "content": f"[REPLY] > {display}"}
                            ),
                            room.loop,
                        )
                except Exception:
                    pass

    except WebSocketDisconnect:
        room.disconnect(websocket)
