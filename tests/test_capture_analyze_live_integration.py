from __future__ import annotations

import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from uagent.tools import capture_analyze_tool as tool


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


@pytest.mark.skipif(
    os.environ.get("UAGENT_RUN_LIVE_CAPTURE_TEST") != "1",
    reason="Set UAGENT_RUN_LIVE_CAPTURE_TEST=1 for a local loopback capture test.",
)
def test_real_loopback_capture_and_analysis() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = int(server.server_address[1])
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    def generate_loopback_traffic() -> None:
        time.sleep(0.5)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3).read()
        except Exception:
            pass

    sender = threading.Thread(target=generate_loopback_traffic, daemon=True)
    sender.start()
    try:
        captured = tool._capture_loopback(
            {
                "interface": "loopback",
                "duration": 3,
                "max_packets": 500,
            }
        )
        if not captured.get("ok"):
            pytest.skip(str(captured.get("error")))

        pcap_path = Path(str(captured["pcap_path"]))
        assert pcap_path.is_file()
        result = tool.run_tool(
            {
                "pcap_path": str(pcap_path),
                "operations": ["summary", "flows"],
                "correlate": False,
            }
        )
        assert '"ok": true' in result.lower()
    finally:
        server.shutdown()
        server.server_close()
        sender.join(timeout=1)
        captured_path = locals().get("captured", {}).get("pcap_path")
        if captured_path:
            Path(str(captured_path)).unlink(missing_ok=True)
