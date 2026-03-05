from __future__ import annotations

import json

import pytest

from uagent.tools.fetch_url_tool import run_tool as fetch_url
from uagent.tools.get_geoip_tool import run_tool as get_geoip
from uagent.tools.search_web_tool import run_tool as search_web


def _loads(s: str) -> dict:
    obj = json.loads(s)
    assert isinstance(obj, dict)
    return obj


def test_get_geoip_smoke() -> None:
    out = get_geoip({"format": "json"})
    payload = _loads(out)

    # Tool may fail depending on network; accept both.
    if payload.get("ok") is False:
        assert payload.get("error")
        return

    # success shape is not strictly guaranteed; just assert it's a dict.
    assert payload


def test_fetch_url_smoke() -> None:
    # Use a local HTTP server so the test does not depend on external network/SSL/proxy.
    import http.server
    import socket
    import threading

    body = b"<html><body>OK</body></html>"

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            # silence server logs in test output
            return

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        host, port = s.getsockname()

    httpd = http.server.HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        out = fetch_url({"url": f"http://127.0.0.1:{port}/"})
        assert isinstance(out, str)
        assert "OK" in out
    finally:
        httpd.shutdown()
        httpd.server_close()



def test_search_web_smoke() -> None:
    out = search_web({"query": "example.com", "max_results": 3, "q": "", "n": 0})
    payload = _loads(out)

    # The tool currently returns {"results": [...]}.
    results = payload.get("results")
    assert isinstance(results, list)

    # Environment/network/DDG HTML changes can yield 0 results. That's acceptable.
    if not results:
        # If the tool provides an error field, that's also acceptable.
        if payload.get("ok") is False:
            assert payload.get("error")
        return

    # If results exist, sanity-check element shape.
    first = results[0]
    assert isinstance(first, dict)
    assert any(k in first for k in ("title", "link", "snippet"))


@pytest.mark.skip(reason="External process/GUI dependent")
def test_playwright_inspector_skipped() -> None:
    raise AssertionError("should not run")
