"""Local fake OpenAI-compatible streaming server for interrupt tests.

Serves ``/v1/responses`` (SSE) and ``/v1/chat/completions`` (SSE or JSON).
Each stream sends ``N_CHUNKS`` text deltas, one every ``DT`` seconds, and
records how many it sent and whether the client disconnected.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

N_CHUNKS = 60
DT = 0.03
TOOL_CALL_FIRST_REQUEST = False

STATS: list[dict] = []
_LOCK = threading.Lock()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep test output quiet
        pass

    def _write(self, text: str) -> None:
        self.wfile.write(text.encode())
        self.wfile.flush()

    def _start_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        req = json.loads(self.rfile.read(length) or b"{}")
        stat = {
            "path": self.path,
            "stream": bool(req.get("stream")),
            "request_index": len(STATS),
            "sent": 0,
            "started": time.time(),
            "ended": None,
            "client_gone": False,
        }
        with _LOCK:
            STATS.append(stat)
        try:
            if self.path.endswith("/responses"):
                self._responses(req, stat)
            elif self.path.endswith("/chat/completions"):
                self._chat(req, stat)
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", "2")
                self.end_headers()
                self._write("{}")
        except OSError:
            stat["client_gone"] = True
        finally:
            stat["ended"] = time.time()

    def _chat(self, req, stat) -> None:
        model = req.get("model", "fake-model")
        self._start_sse()
        for i in range(N_CHUNKS):
            chunk = {
                "id": "c1",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": f"tok{i} "},
                        "finish_reason": None,
                    }
                ],
            }
            self._write(f"data: {json.dumps(chunk)}\n\n")
            stat["sent"] = i + 1
            time.sleep(DT)
        self._write("data: [DONE]\n\n")

    def _event(self, name: str, payload: dict) -> None:
        self._write(f"event: {name}\ndata: {json.dumps(payload)}\n\n")

    def _responses(self, req, stat) -> None:
        model = req.get("model", "fake-model")
        self._start_sse()
        if TOOL_CALL_FIRST_REQUEST and stat["request_index"] == 0:
            name = _tool_name(req.get("tools") or ())
            if name:
                self._responses_tool_call(model, name, stat)
                return
        resp = {
            "id": "resp_1",
            "object": "response",
            "created_at": 0,
            "model": model,
            "status": "in_progress",
            "output": [],
        }
        self._event(
            "response.created",
            {"type": "response.created", "sequence_number": 0, "response": resp},
        )
        item = {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "status": "in_progress",
            "content": [],
        }
        self._event(
            "response.output_item.added",
            {
                "type": "response.output_item.added",
                "sequence_number": 1,
                "output_index": 0,
                "item": item,
            },
        )
        text = ""
        for i in range(N_CHUNKS):
            delta = f"tok{i} "
            text += delta
            self._event(
                "response.output_text.delta",
                {
                    "type": "response.output_text.delta",
                    "sequence_number": i + 2,
                    "item_id": "msg_1",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": delta,
                    "logprobs": [],
                },
            )
            stat["sent"] = i + 1
            time.sleep(DT)
        done = dict(
            item,
            status="completed",
            content=[{"type": "output_text", "text": text, "annotations": []}],
        )
        self._event(
            "response.output_item.done",
            {
                "type": "response.output_item.done",
                "sequence_number": N_CHUNKS + 2,
                "output_index": 0,
                "item": done,
            },
        )
        final = dict(resp, status="completed", output=[done])
        self._event(
            "response.completed",
            {
                "type": "response.completed",
                "sequence_number": N_CHUNKS + 3,
                "response": final,
            },
        )

    def _responses_tool_call(self, model: str, name: str, stat: dict) -> None:
        resp = {
            "id": "resp_tool_1",
            "object": "response",
            "created_at": 0,
            "model": model,
            "status": "in_progress",
            "output": [],
        }
        self._event(
            "response.created",
            {"type": "response.created", "sequence_number": 0, "response": resp},
        )
        item = {
            "id": "fc_item_1",
            "type": "function_call",
            "status": "in_progress",
            "call_id": "call_tool_1",
            "name": name,
            "arguments": "",
        }
        self._event(
            "response.output_item.added",
            {
                "type": "response.output_item.added",
                "sequence_number": 1,
                "output_index": 0,
                "item": item,
            },
        )
        self._event(
            "response.function_call_arguments.delta",
            {
                "type": "response.function_call_arguments.delta",
                "sequence_number": 2,
                "item_id": "fc_item_1",
                "output_index": 0,
                "delta": "{}",
            },
        )
        self._event(
            "response.function_call_arguments.done",
            {
                "type": "response.function_call_arguments.done",
                "sequence_number": 3,
                "item_id": "fc_item_1",
                "arguments": "{}",
            },
        )
        completed_item = dict(item, status="completed", arguments="{}")
        self._event(
            "response.output_item.done",
            {
                "type": "response.output_item.done",
                "sequence_number": 4,
                "output_index": 0,
                "item": completed_item,
            },
        )
        final = dict(resp, status="completed", output=[completed_item])
        self._event(
            "response.completed",
            {
                "type": "response.completed",
                "sequence_number": 5,
                "response": final,
            },
        )
        stat["sent"] = 6


def _tool_name(tools) -> str:
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        function = tool.get("function")
        name = tool.get("name")
        if not name and isinstance(function, dict):
            name = function.get("name")
        if isinstance(name, str) and name:
            return name
    return ""


def start() -> int:
    """Start the server on a free localhost port and return the port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address[1]
