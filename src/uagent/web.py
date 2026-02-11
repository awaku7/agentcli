import asyncio
import json
import os
import time
import re
import sys
import traceback
import threading
from datetime import datetime
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# scheck module imports
from . import core as core
from . import uagent_llm as llm_util
from . import util_providers as providers
from . import util_tools as tools_util
from . import tools
from .welcome import get_welcome_message
from . import runtime_init as _runtime_init

try:
    from .tools.mcp_servers_shared import ensure_mcp_config_template
except ImportError:

    def ensure_mcp_config_template():
        pass  # type: ignore


# ANSI エスケープシーケンスを削除するための正規表現
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# --- FastAPI Setup ---
app = FastAPI(title="scheck Web")

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATE_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Global State for Web ---
class WebManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.messages: List[Dict[str, Any]] = []
        self.workdir = ""
        self.status = {"busy": False, "label": "IDLE", "workdir": self.workdir}
        self.human_ask_event = asyncio.Event()
        self.human_ask_response = ""
        self.loop = None
        self.original_log_message = None
        self.original_set_status = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # 接続時に現在の状態とメッセージを送信
        # NOTE(Mode A): LLMに渡す履歴(self.history)と表示用(self.messages)がズレないよう、
        # history が存在する場合は history をベースに init payload を構築する。
        msgs = self.messages
        if hasattr(self, "history"):
            try:
                h = getattr(self, "history")
                if isinstance(h, list) and h:
                    msgs = []
                    for m in h:
                        msgs.append(
                            {
                                "role": m.get("role"),
                                "content": m.get("content", ""),
                                "name": m.get("name"),
                                "tool_calls": m.get("tool_calls"),
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
            except Exception:
                msgs = self.messages

        _v = (os.environ.get("UAGENT_WEB_VERBOSE") or "").strip().lower()
        web_verbose = _v in ("1", "true", "yes", "on")
        await websocket.send_json(
            {
                "type": "init",
                "messages": msgs,
                "status": self.status,
                "web_verbose": web_verbose,
            }
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                pass

    def set_status(self, busy: bool, label: str = ""):
        # workdir display update (follow os.chdir())
        try:
            self.workdir = os.getcwd()
        except Exception:
            pass

        self.status = {
            "busy": busy,
            "label": label or ("BUSY" if busy else "IDLE"),
            "workdir": self.workdir,
        }
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({"type": "status", "status": self.status}), self.loop
            )

    def add_message(self, msg: Dict[str, Any]):
        # UI表示用に一部情報を正規化
        display_msg = {
            "role": msg.get("role"),
            "content": msg.get("content", ""),
            "name": msg.get("name"),
            "tool_calls": msg.get("tool_calls"),
            "timestamp": datetime.now().isoformat(),
        }
        self.messages.append(display_msg)
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({"type": "message", "message": display_msg}), self.loop
            )

    def on_log_message(self, message: Dict[str, Any]):
        # core.log_message の代わりに呼ばれる
        # NOTE: suppress noisy stdout logs in Web UI; keep them in server console only.
        if self.original_log_message:
            self.original_log_message(message)

        # Only forward non-log chat messages to UI.
        # Logs are streamed via WebStdout as type='log' and are shown only in WEB_VERBOSE.
        if message.get("type") == "log":
            return

        self.add_message(message)


web_manager = WebManager()


# --- Tool Callbacks for Web ---
def web_human_ask(args: Dict[str, Any]) -> str:
    message = args.get("message", "")
    is_password = bool(args.get("is_password", False))

    # UIに human_ask を通知
    if web_manager.loop:
        asyncio.run_coroutine_threadsafe(
            web_manager.broadcast(
                {"type": "human_ask", "message": message, "is_password": is_password}
            ),
            web_manager.loop,
        )

    global human_ask_sync_event, human_ask_result
    human_ask_sync_event.clear()
    human_ask_sync_event.wait()

    # Align return shape with CLI/GUI human_ask (compat)
    user_reply = human_ask_result
    display_reply = "[SECRET]" if is_password else user_reply

    # Web UI currently does not provide an explicit cancel action; keep compat key.
    cancelled = False

    return json.dumps(
        {
            "user_reply": user_reply,
            "display_reply": display_reply,
            "cancelled": cancelled,
        }
    )


human_ask_sync_event = threading.Event()
human_ask_result = ""


# --- Override core functions ---
def web_set_status(busy: bool, label: str = ""):
    if web_manager.original_set_status:
        web_manager.original_set_status(busy, label)
    web_manager.set_status(busy, label)


def _web_console_log_enabled() -> bool:
    v = (os.environ.get("UAGENT_WEB_CONSOLE_LOG") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


# 標準出力をキャプチャしてWebSocket経由で流す
class WebStdout:
    def __init__(self):
        self.buffer = ""
        self.lock = threading.Lock()

    def write(self, text):
        # コンソールには生のまま即座に出力（必要な場合のみ）
        if _web_console_log_enabled():
            sys.__stdout__.write(text)

        # Web配信用にバッファリングして処理
        # エスケープシーケンスが断片化して渡されるのを防ぐため、行単位で処理する
        with self.lock:
            self.buffer += text
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                clean_line = ANSI_ESCAPE.sub("", line)

                # Suppress CLI-only multiline input mode guidance in Web UI
                if "複数行" in clean_line:
                    continue

                if clean_line.strip() and web_manager.loop:
                    asyncio.run_coroutine_threadsafe(
                        web_manager.broadcast({"type": "log", "content": clean_line}),
                        web_manager.loop,
                    )

    def flush(self):
        with self.lock:
            if self.buffer:
                clean_line = ANSI_ESCAPE.sub("", self.buffer)

                # Suppress CLI-only multiline input mode guidance in Web UI (flush path)
                try:
                    filtered_lines: List[str] = []
                    for ln in clean_line.splitlines():
                        if "複数行" in ln:
                            continue
                        filtered_lines.append(ln)
                    clean_line = "\n".join(filtered_lines)
                except Exception:
                    pass

                if clean_line.strip() and web_manager.loop:
                    asyncio.run_coroutine_threadsafe(
                        web_manager.broadcast({"type": "log", "content": clean_line}),
                        web_manager.loop,
                    )
                self.buffer = ""
        if _web_console_log_enabled():
            sys.__stdout__.flush()

    def isatty(self):
        return sys.__stdout__.isatty()


sys.stdout = WebStdout()


# 標準エラー出力もキャプチャする（WebStdoutを再利用）
class WebStderr(WebStdout):
    def write(self, text):
        # コンソールには生のまま即座に出力（必要な場合のみ）
        if _web_console_log_enabled():
            sys.__stderr__.write(text)

        # Web配信用にバッファリング
        with self.lock:
            self.buffer += text
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                clean_line = ANSI_ESCAPE.sub("", line)
                # Suppress CLI-only multiline guidance in Web UI (stderr path)
                if "複数行" in clean_line:
                    continue
                if clean_line.strip() and web_manager.loop:
                    # エラー出力として送信（必要なら type="error" 等に拡張可だが一旦 log で統一）
                    asyncio.run_coroutine_threadsafe(
                        web_manager.broadcast({"type": "log", "content": clean_line}),
                        web_manager.loop,
                    )

    def flush(self):
        with self.lock:
            if self.buffer:
                clean_line = ANSI_ESCAPE.sub("", self.buffer)

                # Suppress CLI-only multiline guidance in Web UI (stderr flush path)
                try:
                    filtered_lines: List[str] = []
                    for ln in clean_line.splitlines():
                        if "複数行" in ln:
                            continue
                        filtered_lines.append(ln)
                    clean_line = "\n".join(filtered_lines)
                except Exception:
                    pass

                if clean_line.strip() and web_manager.loop:
                    asyncio.run_coroutine_threadsafe(
                        web_manager.broadcast({"type": "log", "content": clean_line}),
                        web_manager.loop,
                    )
                self.buffer = ""
        if _web_console_log_enabled():
            sys.__stderr__.flush()

    def isatty(self):
        return sys.__stderr__.isatty()


sys.stderr = WebStderr()


# --- Worker Logic ---
def run_agent_worker(user_input: str):
    # Mark web mode on core object (avoid env var)
    try:
        setattr(core, "_is_web", True)
    except Exception:
        pass

    # Streaming helpers for Web UI (single growing assistant bubble)
    stream_state: Dict[str, Any] = {"id": None, "active": False}

    def _web_stream_send(payload: Dict[str, Any]) -> None:
        try:
            if web_manager.loop:
                asyncio.run_coroutine_threadsafe(
                    web_manager.broadcast(payload), web_manager.loop
                )
        except Exception:
            pass

    def _stream_start() -> str:
        sid = f"asst_{int(time.time() * 1000)}"
        stream_state["id"] = sid
        stream_state["active"] = True
        _web_stream_send({"type": "assistant_stream_start", "id": sid})
        return sid

    def _stream_delta(delta: str) -> None:
        if not delta:
            return
        if not stream_state.get("active"):
            _stream_start()
        _web_stream_send(
            {
                "type": "assistant_stream_delta",
                "id": stream_state.get("id"),
                "delta": delta,
            }
        )

    def _stream_end() -> None:
        if stream_state.get("active"):
            _web_stream_send(
                {"type": "assistant_stream_end", "id": stream_state.get("id")}
            )
        stream_state["active"] = False

    # Patch core.log_message during this worker run so streaming deltas can go to WebSocket.
    # We do not persist deltas to history; only the final assistant message is logged normally.
    _orig_log_message = getattr(core, "log_message", None)

    def _patched_log_message(msg: Dict[str, Any]) -> None:
        try:
            # Detect streaming delta payload emitted by llm_openai_responses.parse_responses_stream
            if isinstance(msg, dict) and msg.get("type") == "assistant_stream_delta":
                _stream_delta(str(msg.get("delta") or ""))
                return
            if isinstance(msg, dict) and msg.get("type") == "assistant_stream_end":
                _stream_end()
                return
        except Exception:
            pass
        if callable(_orig_log_message):
            _orig_log_message(msg)

    try:
        if callable(_orig_log_message):
            setattr(core, "log_message", _patched_log_message)
    except Exception:
        pass

    # Mark web mode on core object (avoid env var)
    try:
        setattr(core, "_is_web", True)
    except Exception:
        pass
    try:
        # Fail-fast with a clear message in Web UI when env is missing
        if not (os.environ.get("UAGENT_PROVIDER") or "").strip():
            if web_manager.loop:
                asyncio.run_coroutine_threadsafe(
                    web_manager.broadcast(
                        {
                            "type": "message",
                            "message": {
                                "role": "assistant",
                                "content": "[FATAL] 環境変数 UAGENT_PROVIDER が設定されていません。\\nWebサーバ起動時の環境変数を確認してください。",
                            },
                        }
                    ),
                    web_manager.loop,
                )
            return

        provider_name, client, depname = providers.make_client(core)

        print(f"[INFO] model(deployment) = {depname}")
        if (
            provider_name == "openrouter"
            and (depname or "").strip() == "openrouter/auto"
        ):
            raw_fb = (
                os.environ.get("UAGENT_OPENROUTER_FALLBACK_MODELS", "") or ""
            ).strip()
            if raw_fb:
                print("[INFO] open router fallback models enabled")

        # ユーザーメッセージ追加
        user_msg = {"role": "user", "content": user_input}
        # core.log_message が web_manager.on_log_message を通じて add_message を呼ぶため、
        # ここで直接 add_message を呼ぶと二重表示になる。
        core.log_message(user_msg)

        # メッセージ履歴（簡易的に全件または初期化）
        if not hasattr(web_manager, "history"):
            web_manager.history = tools_util.build_initial_messages(core=core)

            # 長期記憶/共有メモを system message として挿入（CLI/GUIに合わせる）
            from .tools import long_memory as personal_long_memory
            from .tools import shared_memory

            print("[INFO] 長期記憶を読み込みました。")
            try:
                before_len = len(web_manager.history)
                flags = _runtime_init.append_long_memory_system_messages(
                    core=core,
                    messages=web_manager.history,
                    build_long_memory_system_message_fn=tools_util.build_long_memory_system_message,
                    personal_long_memory_mod=personal_long_memory,
                    shared_memory_mod=shared_memory,
                )

                # 互換: 共有メモが有効な場合のみ INFO を出す
                if flags.get("shared_enabled"):
                    print("[INFO] 共有長期記憶を読み込みました。")

                # 互換: 追加された system message をすべて log に残す
                for m in web_manager.history[before_len:]:
                    core.log_message(m)

            except Exception as e:
                print(f"[WARN] 共有長期記憶の読み込み中に例外が発生しました: {e}")

        web_manager.history.append(user_msg)

        # LLM実行
        llm_util.run_llm_rounds(
            provider_name,
            client,
            depname,
            web_manager.history,
            core=core,
            make_client_fn=providers.make_client,
            append_result_to_outfile_fn=tools_util.append_result_to_outfile,
            try_open_images_from_text_fn=tools_util.try_open_images_from_text,
        )
    except BaseException as e:
        # Show a clear error in Web UI (also catches SystemExit from sys.exit())
        err = repr(e)
        tb = ""
        try:
            tb = traceback.format_exc()
        except Exception:
            tb = ""

        msg = "[FATAL] Web worker error.\\n" + err
        # Heuristic: common fatal env-missing paths
        if (
            isinstance(e, SystemExit)
            and not (os.environ.get("UAGENT_PROVIDER") or "").strip()
        ):
            msg = "[FATAL] 環境変数 UAGENT_PROVIDER が設定されていません。\\nWebサーバ起動時の環境変数を確認してください。"
        if tb and tb != "NoneType: None\\n":
            msg = msg + "\\n\\n" + tb

        try:
            if web_manager.loop:
                asyncio.run_coroutine_threadsafe(
                    web_manager.broadcast(
                        {
                            "type": "message",
                            "message": {
                                "role": "assistant",
                                "content": msg,
                            },
                        }
                    ),
                    web_manager.loop,
                )
        except Exception:
            pass
    finally:
        # Restore patched core.log_message (avoid leaking patched behavior across runs)
        try:
            if callable(_orig_log_message):
                setattr(core, "log_message", _orig_log_message)
        except Exception:
            pass

        web_manager.set_status(False, "IDLE")


# --- Routes ---
@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(STATIC_DIR, "favicon.ico"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await web_manager.connect(websocket)
    web_manager.loop = asyncio.get_event_loop()
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            if payload["type"] == "user_input":
                user_text = payload["text"]
                # ワーカースレッドで実行
                threading.Thread(
                    target=run_agent_worker, args=(user_text,), daemon=True
                ).start()

            elif payload["type"] == "human_ask_response":
                # Human reply to a tool prompt (human_ask)
                global human_ask_result
                human_ask_result = payload.get("text", "")
                human_ask_sync_event.set()

                # Also emit a log line so the Web UI can show the reply in the log panel
                # (Many UI implementations only append logs/messages, not tool return JSON.)
                try:
                    is_pw = bool(payload.get("is_password", False))
                    display = "[SECRET]" if is_pw else human_ask_result
                    if web_manager.loop:
                        asyncio.run_coroutine_threadsafe(
                            web_manager.broadcast(
                                {"type": "log", "content": f"[REPLY] > {display}"}
                            ),
                            web_manager.loop,
                        )
                except Exception:
                    pass

    except WebSocketDisconnect:
        web_manager.disconnect(websocket)


# --- Initialization ---
def init_web():
    # 起動メッセージを表示
    print(get_welcome_message())

    # scheck_core のステータス更新をフック
    web_manager.original_set_status = core.set_status
    web_manager.original_log_message = core.log_message

    core.set_status = web_set_status
    core.log_message = web_manager.on_log_message

    # ツールコールバックの初期化
    tools_util.init_tools_callbacks(core)

    # 初回の挨拶をメッセージ履歴に追加（接続時に送信される）
    # Web UI ではクイックガイド自体は残しつつ、「複数行」案内行だけ抑制する
    _welcome = get_welcome_message()
    try:
        _filtered: List[str] = []
        for _ln in str(_welcome).splitlines():
            if "複数行" in _ln:
                continue
            _filtered.append(_ln)
        _welcome = "\n".join(_filtered)
    except Exception:
        pass

    web_manager.add_message({"role": "assistant", "content": _welcome})
    cb = tools.context.get_callbacks()
    cb.is_gui = True

    # 既存の human_ask ツールをラップ
    original_run_tool = tools.run_tool

    def web_run_tool_wrapper(name, args):
        if name == "human_ask":
            return web_human_ask(args)
        return original_run_tool(name, args)

    tools.run_tool = web_run_tool_wrapper


def main():
    # 初回だけ README / QUICKSTART を表示（pip/wheel には post-install フックが無いので起動時に表示する）
    try:
        from .readme_util import (
            maybe_print_quickstart_on_first_run,
            maybe_print_readme_on_first_run,
        )

        maybe_print_readme_on_first_run(open_with_os=True)
        maybe_print_quickstart_on_first_run(open_with_os=True)
    except Exception:
        pass

    ensure_mcp_config_template()

    # Workdir init (moved from module import time into main)
    try:
        decision = _runtime_init.decide_workdir(
            env_workdir=os.environ.get("UAGENT_WORKDIR")
        )
        _runtime_init.apply_workdir(decision)
        # Expose workdir to Web UI via status payload
        web_manager.workdir = decision.chosen_expanded
        try:
            web_manager.status["workdir"] = web_manager.workdir
        except Exception:
            pass
        banner = _runtime_init.build_startup_banner(
            core=core,
            workdir=decision.chosen_expanded,
            workdir_source=decision.chosen_source,
        )
        # NOTE: web mode currently streams stdout to UI; keep behavior compatible.
        print(banner, end="")
    except Exception as e:
        print(f"[FATAL] workdir の設定に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    init_web()
    print("Starting server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
