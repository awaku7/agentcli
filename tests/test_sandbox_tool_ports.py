"""Tests for the host tools ported into the MXC sandbox worker."""

from __future__ import annotations

import base64
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from uagent.runtime import sandbox_worker as worker


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    return tmp_path


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            return self._payload
        return self._payload[:size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _call(name: str, args: dict) -> str:
    return worker._dispatch({"name": name, "args": args})


# ---------------------------------------------------------------------------
# Pure compute tools
# ---------------------------------------------------------------------------


def test_get_current_time_shape():
    out = _call("get_current_time", {})
    assert out.startswith("[get_current_time]\nISO8601 (Local): ")
    assert "Weekday:" in out
    assert "NTP Sync:        N/A" in out


def test_geodesic_distance_tokyo_osaka():
    out = json.loads(
        _call(
            "geodesic_distance",
            {
                "lat_a": 35.6762,
                "lon_a": 139.6503,
                "lat_b": 34.6937,
                "lon_b": 135.5023,
            },
        )
    )
    assert out["ok"] is True
    assert 380 < out["distance_km"] < 420
    assert out["method"] == "Haversine"


def test_geodesic_distance_rejects_bad_coordinates():
    out = json.loads(
        _call(
            "geodesic_distance",
            {"lat_a": 100, "lon_a": 0, "lat_b": 0, "lon_b": 0},
        )
    )
    assert out["ok"] is False


def test_date_calc_month_end_and_holiday():
    out = _call("date_calc", {"base_date": "2026-01-31", "months": 1})
    assert "Result Date: 2026-02-28" in out
    out = _call("date_calc", {"base_date": "2025-12-31", "days": 1})
    assert "2026-01-01" in out
    assert "Holiday" in out  # JP New Year's Day


def test_date_calc_holiday_check_unavailable(monkeypatch):
    real_ensure = worker._ensure_package

    def fake_ensure(name, pip_name=None):
        if name == "holidays":
            return None
        return real_ensure(name, pip_name)

    monkeypatch.setattr(worker, "_ensure_package", fake_ensure)
    out = _call("date_calc", {"base_date": "2026-01-01"})
    assert "Holiday check unavailable" in out
    assert "Holiday Info: Weekday" not in out
    out = _call("date_calc", {"base_date": "2026-01-03"})  # a Saturday
    assert "Saturday (holiday check unavailable)" in out


def test_apply_patch_multi_hunk_displacement(workspace):
    (worker.ROOT / "multi.txt").write_text(
        "pad1\npad2\nunique\nkeep\nold\nkeep\nold\n", encoding="utf-8"
    )
    patch = (
        "--- a/multi.txt\n"
        "+++ b/multi.txt\n"
        "@@ -1 +1 @@\n"
        "-unique\n"
        "+UNIQUE\n"
        "@@ -5 +5 @@\n"
        "-old\n"
        "+NEW\n"
    )
    out = json.loads(_call("apply_patch", {"patch_text": patch, "dry_run": False}))
    assert out["ok"] is True
    assert (worker.ROOT / "multi.txt").read_text(encoding="utf-8") == (
        "pad1\npad2\nUNIQUE\nkeep\nold\nkeep\nNEW\n"
    )


def test_quantities_without_pint_is_a_clear_error(monkeypatch):
    try:
        import pint  # noqa: F401
    except ImportError:
        monkeypatch.setattr(worker, "_ensure_package", lambda name: None)
        out = json.loads(_call("quantities", {"expression": "1 km to m"}))
        assert out["ok"] is False
        assert "Pint is not available" in out["error"]
    else:
        out = json.loads(_call("quantities", {"expression": "1 km to m"}))
        assert out["ok"] is True
        assert out["result"].startswith("1000")


def test_quantities_rejects_unsafe_expression():
    out = json.loads(_call("quantities", {"expression": "__import__('os')"}))
    assert out["ok"] is False


def test_quantities_precision_zero_is_preserved():
    pytest.importorskip("pint")
    out = json.loads(
        _call("quantities", {"expression": "1.23456 meter", "precision": 0})
    )
    assert out["ok"] is True
    assert out["result"] == "1 m"


# ---------------------------------------------------------------------------
# Network tools (mocked / local server)
# ---------------------------------------------------------------------------


def test_reverse_geocode_mocked(monkeypatch):
    payload = json.dumps(
        {
            "display_name": "千代田区, 東京都, 日本",
            "lat": "35.68",
            "lon": "139.69",
            "address": {"city": "千代田区"},
            "osm_type": "relation",
            "osm_id": 1,
        }
    ).encode("utf-8")
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=0: _FakeResponse(payload)
    )
    out = json.loads(_call("reverse_geocode", {"lat": 35.68, "lon": 139.69}))
    assert out["ok"] is True
    assert out["display_name"].startswith("千代田区")
    assert out["address"]["city"] == "千代田区"


def test_zipcode_lookup_mocked(monkeypatch):
    def fake_fetch(path: str):
        if path == "/p/100.json":
            return {
                "1000001": {
                    "prefecture": "東京都",
                    "city": "千代田区",
                    "town": "千代田",
                    "prefecture_code": "13",
                }
            }
        return None

    monkeypatch.setattr(worker, "_zipcode_fetch_json", fake_fetch)
    out = json.loads(_call("zipcode_check", {"zipcode": "100-0001"}))
    assert out["ok"] is True
    assert out["address"]["city"] == "千代田区"
    assert "prefecture_code" not in out["address"]


def test_zipcode_rejects_bad_format():
    out = json.loads(_call("zipcode_check", {"zipcode": "123"}))
    assert out["ok"] is False


class _EchoHandler(BaseHTTPRequestHandler):
    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        if self.path == "/big":
            payload = b"a" * 1_000_000
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        payload = json.dumps(
            {
                "method": self.command,
                "path": self.path,
                "body": body.decode("utf-8", errors="replace"),
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _handle
    do_POST = _handle

    def log_message(self, *args):
        pass


@pytest.fixture()
def echo_server(monkeypatch):
    for var in (
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "all_proxy",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_http_request_get_and_post(echo_server):
    out = json.loads(
        _call(
            "http_request",
            {"url": f"{echo_server}/a", "query": {"x": "1"}, "parse_json": True},
        )
    )
    assert out["ok"] is True
    assert out["status_code"] == 200
    assert out["response_json"]["path"] == "/a?x=1"
    out = json.loads(
        _call(
            "http_request",
            {
                "url": f"{echo_server}/b",
                "method": "POST",
                "body": {"k": "v"},
                "parse_json": True,
            },
        )
    )
    assert out["response_json"]["method"] == "POST"
    assert json.loads(out["response_json"]["body"]) == {"k": "v"}


def test_http_request_rejects_bad_url_and_method():
    out = json.loads(_call("http_request", {"url": "file:///etc/passwd"}))
    assert out["ok"] is False
    out = json.loads(
        _call("http_request", {"url": "https://example.com", "method": "TRACE"})
    )
    assert out["ok"] is False


def test_http_request_large_body_is_bounded(echo_server):
    raw = _call("http_request", {"url": f"{echo_server}/big"})
    out = json.loads(raw)
    assert out["ok"] is True
    assert out["status_code"] == 200
    assert out["truncated"] is True
    assert len(raw.encode("utf-8")) <= worker.MAX_RESULT_BYTES


def test_apply_patch_removed_line_that_looks_like_header(workspace):
    (worker.ROOT / "note.txt").write_text("-- before\n", encoding="utf-8")
    patch = (
        "--- a/note.txt\n" "+++ b/note.txt\n" "@@ -1 +1 @@\n" "--- before\n" "+after\n"
    )
    out = json.loads(_call("apply_patch", {"patch_text": patch, "dry_run": False}))
    assert out["ok"] is True
    assert (worker.ROOT / "note.txt").read_text(encoding="utf-8") == "after\n"


def test_http_request_array_query_params(echo_server):
    out = json.loads(
        _call(
            "http_request",
            {
                "url": f"{echo_server}/items",
                "query": {"tag": ["a", "b"], "q": "x"},
                "parse_json": True,
            },
        )
    )
    assert out["ok"] is True
    assert out["response_json"]["path"] == "/items?tag=a&tag=b&q=x"


def test_expand_aliases_in_args_against_explicit_workspace(workspace):
    (worker.ROOT / "docs").mkdir(exist_ok=True)
    _call("path_alias", {"action": "set", "slot": 2, "path": "docs"})
    expanded = worker.expand_aliases_in_args(
        {"argv": ["git", "status"], "cwd": "@A{2}"}, worker.ROOT
    )
    assert expanded["cwd"] == "docs"
    assert expanded["argv"] == ["git", "status"]
    expanded = worker.expand_aliases_in_args({"cwd": "@A{0}/sub"}, worker.ROOT)
    assert expanded["cwd"] == "sub"
    with pytest.raises(ValueError):
        worker.expand_aliases_in_args({"cwd": "@A{9}"}, worker.ROOT)


def test_svg_to_image_jpeg_flattens_transparency_on_white(workspace):
    pytest.importorskip("cairosvg")
    from PIL import Image

    (worker.ROOT / "half.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<rect x="0" y="0" width="5" height="10" fill="black"/></svg>',
        encoding="utf-8",
    )
    out = json.loads(
        _call(
            "svg_to_image",
            {"svg": "half.svg", "output_path": "half.jpg"},
        )
    )
    assert out["ok"] is True
    image = Image.open(worker.ROOT / "half.jpg").convert("RGB")
    assert image.getpixel((1, 5))[0] < 55
    assert image.getpixel((8, 5))[0] > 200


def test_attach_within_budget_drops_oversized_attachment():
    payload: dict = {"ok": True, "output_path": "big.png", "bytes": 10}
    small = [{"type": "image", "data_base64": "AAAA"}]
    worker._attach_within_budget(payload, small)
    assert payload["attachments"] == small
    payload = {"ok": True, "output_path": "big.png", "bytes": 10}
    huge = [{"type": "image", "data_base64": "A" * (worker.MAX_RESULT_BYTES + 10)}]
    worker._attach_within_budget(payload, huge)
    assert "attachments" not in payload
    assert "attachment_omitted" in payload
    assert len(json.dumps(payload).encode("utf-8")) <= worker.MAX_RESULT_BYTES


# ---------------------------------------------------------------------------
# apply_patch
# ---------------------------------------------------------------------------

_PATCH_MODIFY = """--- a/note.txt
+++ b/note.txt
@@ -1,3 +1,3 @@
 alpha
-beta
+bravo
 gamma
"""

_PATCH_CREATE = """--- /dev/null
+++ b/new.txt
@@ -0,0 +1,2 @@
+one
+two
"""

_PATCH_DELETE = """--- a/new.txt
+++ /dev/null
@@ -1,2 +0,0 @@
-one
-two
"""


def test_apply_patch_modify_create_delete(workspace):
    (workspace / "note.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    out = json.loads(
        _call("apply_patch", {"patch_text": _PATCH_MODIFY, "dry_run": False})
    )
    assert out["ok"] is True
    assert (workspace / "note.txt").read_text(encoding="utf-8") == (
        "alpha\nbravo\ngamma\n"
    )
    out = json.loads(
        _call("apply_patch", {"patch_text": _PATCH_CREATE, "dry_run": False})
    )
    assert out["ok"] is True
    assert (workspace / "new.txt").read_text(encoding="utf-8") == "one\ntwo\n"
    out = json.loads(
        _call("apply_patch", {"patch_text": _PATCH_DELETE, "dry_run": False})
    )
    assert out["ok"] is True
    assert not (workspace / "new.txt").exists()


def test_apply_patch_dry_run_and_context_mismatch(workspace):
    (workspace / "note.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    out = json.loads(
        _call("apply_patch", {"patch_text": _PATCH_MODIFY, "dry_run": True})
    )
    assert out["ok"] is True and out["dry_run"] is True
    assert "beta" in (workspace / "note.txt").read_text(encoding="utf-8")
    bad = _PATCH_MODIFY.replace("beta", "missing")
    out = json.loads(_call("apply_patch", {"patch_text": bad}))
    assert out["ok"] is False


def test_apply_patch_revert(workspace):
    (workspace / "note.txt").write_text("alpha\nbravo\ngamma\n", encoding="utf-8")
    out = json.loads(
        _call(
            "apply_patch",
            {"patch_text": _PATCH_MODIFY, "revert": True, "dry_run": False},
        )
    )
    assert out["ok"] is True
    assert (workspace / "note.txt").read_text(encoding="utf-8") == (
        "alpha\nbeta\ngamma\n"
    )


def test_apply_patch_defaults_to_preview(workspace):
    (workspace / "note.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    out = json.loads(_call("apply_patch", {"patch_text": _PATCH_MODIFY}))
    assert out["ok"] is True and out["dry_run"] is True
    assert "beta" in (workspace / "note.txt").read_text(encoding="utf-8")


_PATCH_PLAIN_HEADERS = """--- note.txt
+++ note.txt
@@ -1,3 +1,3 @@
 alpha
-beta
+bravo
 gamma
"""

_PATCH_INSERT_ONLY = """--- a/note.txt
+++ b/note.txt
@@ -2,0 +3 @@
+inserted
"""


def test_apply_patch_plain_headers_and_strip(workspace):
    (workspace / "note.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    out = json.loads(
        _call(
            "apply_patch",
            {"patch_text": _PATCH_PLAIN_HEADERS, "dry_run": False},
        )
    )
    assert out["ok"] is True
    assert "bravo" in (workspace / "note.txt").read_text(encoding="utf-8")


def test_apply_patch_zero_count_insertion(workspace):
    (workspace / "note.txt").write_text("l1\nl2\nl3\n", encoding="utf-8")
    out = json.loads(
        _call("apply_patch", {"patch_text": _PATCH_INSERT_ONLY, "dry_run": False})
    )
    assert out["ok"] is True
    assert (workspace / "note.txt").read_text(encoding="utf-8") == (
        "l1\nl2\ninserted\nl3\n"
    )


_PATCH_DROP_NEWLINE = """--- a/f.txt
+++ b/f.txt
@@ -1 +1 @@
-old
+new
\\ No newline at end of file
"""

_PATCH_ADD_NEWLINE = """--- a/f.txt
+++ b/f.txt
@@ -1 +1 @@
-old
\\ No newline at end of file
+new
"""


def test_apply_patch_newline_markers(workspace):
    (workspace / "f.txt").write_bytes(b"old\n")
    out = json.loads(
        _call("apply_patch", {"patch_text": _PATCH_DROP_NEWLINE, "dry_run": False})
    )
    assert out["ok"] is True
    assert (workspace / "f.txt").read_bytes() == b"new"
    (workspace / "f.txt").write_bytes(b"old")
    out = json.loads(
        _call("apply_patch", {"patch_text": _PATCH_ADD_NEWLINE, "dry_run": False})
    )
    assert out["ok"] is True
    assert (workspace / "f.txt").read_bytes() == b"new\n"


_PATCH_SHIFTED = """--- a/f.txt
+++ b/f.txt
@@ -5,2 +5,2 @@
 ctx
-old
+new
"""


def test_apply_patch_shifted_hunk_prefers_nearest(workspace):
    # The stated anchor (line 5) no longer lines up: the context pair
    # occurs at lines 1-2 and 4-5. The nearest occurrence to the anchor
    # must win, not the first one in the file.
    (workspace / "f.txt").write_text("ctx\nold\nx\nctx\nold\n", encoding="utf-8")
    out = json.loads(
        _call("apply_patch", {"patch_text": _PATCH_SHIFTED, "dry_run": False})
    )
    assert out["ok"] is True
    assert (workspace / "f.txt").read_text(encoding="utf-8") == (
        "ctx\nold\nx\nctx\nnew\n"
    )


# ---------------------------------------------------------------------------
# Media tools
# ---------------------------------------------------------------------------


def test_svg_to_image_missing_library_is_clear_error(workspace, monkeypatch):
    (workspace / "a.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>',
        encoding="utf-8",
    )
    try:
        import cairosvg  # noqa: F401
    except ImportError:
        monkeypatch.setattr(worker, "_ensure_package", lambda name: None)
        out = json.loads(
            _call("svg_to_image", {"svg": "a.svg", "output_path": "a.png"})
        )
        assert out["ok"] is False
        assert "CairoSVG is not available" in out["error"]
    else:
        out = json.loads(
            _call("svg_to_image", {"svg": "a.svg", "output_path": "a.png"})
        )
        assert out["ok"] is True


def test_svg_to_image_validation(workspace):
    out = json.loads(_call("svg_to_image", {"svg": "nope.svg", "output_path": "a.png"}))
    assert out["ok"] is False


def test_svg_to_image_returns_attachment(workspace):
    pytest.importorskip("cairosvg")
    (workspace / "in.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<rect width="10" height="10" fill="red"/></svg>',
        encoding="utf-8",
    )
    out = json.loads(_call("svg_to_image", {"svg": "in.svg", "output_path": "out.png"}))
    assert out["ok"] is True
    data = (workspace / "out.png").read_bytes()
    assert data[:4] == b"\x89PNG"
    attachment = out["attachments"][0]
    assert attachment["mime"] == "image/png"
    assert attachment["name"] == "out.png"
    assert base64.b64decode(attachment["data_base64"]) == data
    out = json.loads(
        _call(
            "svg_to_image",
            {"svg": "in.svg", "output_path": "out2.png", "include_base64": False},
        )
    )
    assert out["ok"] is True and "attachments" not in out


def test_mermaid_missing_library_is_clear_error(workspace, monkeypatch):
    try:
        import mermaidx  # noqa: F401
    except ImportError:
        monkeypatch.setattr(worker, "_ensure_package", lambda name: None)
        out = json.loads(
            _call(
                "mermaid_render",
                {"source": "flowchart TD; A-->B", "output_path": "d.svg"},
            )
        )
        assert out["ok"] is False
        assert "mermaidx is not available" in out["error"]
    else:
        out = json.loads(
            _call(
                "mermaid_render",
                {"source": "flowchart TD; A-->B", "output_path": "d.svg"},
            )
        )
        assert out["ok"] is True


def test_mermaid_render_arg_validation():
    out = json.loads(
        _call(
            "mermaid_render",
            {"source": "x", "input_path": "y", "output_path": "d.svg"},
        )
    )
    assert out["ok"] is False


def test_mmd_to_svg_validation(workspace):
    (workspace / "d.txt").write_text("x", encoding="utf-8")
    out = json.loads(_call("mmd_to_svg", {"mmd": "d.txt", "output_path": "d.svg"}))
    assert out["ok"] is False


def test_preprocess_image_roundtrip(workspace):
    pytest.importorskip("PIL")
    from PIL import Image

    Image.new("RGB", (40, 20), (200, 30, 30)).save(workspace / "in.png")
    out = json.loads(_call("preprocess_image", {"img": "in.png", "binarize": True}))
    assert out["ok"] is True
    produced = workspace / out["output"]
    assert produced.is_file()
    with Image.open(produced) as image:
        assert image.mode == "L"
    assert "grayscale" in out["applied"]
    assert "binarize" in out["applied"]


def test_preprocess_image_modes(workspace):
    pytest.importorskip("PIL")
    from PIL import Image

    Image.new("RGB", (40, 20), (200, 30, 30)).save(workspace / "in.png")
    # Default (ocr) mode thresholds: output is bilevel grayscale.
    out = json.loads(_call("preprocess_image", {"img": "in.png"}))
    assert out["ok"] is True
    assert "adaptive_threshold" in out["applied"]
    with Image.open(workspace / out["output"]) as image:
        assert image.mode == "L"
        assert set(image.getdata()) <= {0, 255}
    # Photo mode preserves color.
    out = json.loads(_call("preprocess_image", {"img": "in.png", "mode": "photo"}))
    assert out["ok"] is True
    with Image.open(workspace / out["output"]) as image:
        assert image.mode == "RGB"
    # Unknown modes are rejected.
    out = json.loads(_call("preprocess_image", {"img": "in.png", "mode": "bogus"}))
    assert out["ok"] is False
    # A hostile prefix must not write outside the workspace.
    out = json.loads(_call("preprocess_image", {"img": "in.png", "prefix": "../evil"}))
    assert out["ok"] is False
    assert not (workspace.parent / "evil_in.png").exists()
    out = json.loads(
        _call(
            "preprocess_image",
            {"img": "in.png", "prefix": str(workspace.parent / "abs_evil")},
        )
    )
    assert out["ok"] is False
    assert not (workspace.parent / "abs_evil_in.png").exists()


def test_date_calc_installs_python_dateutil(workspace, monkeypatch):
    import importlib

    calls = []

    def recorder(module_name, pip_name=None):
        calls.append((module_name, pip_name))
        try:
            return importlib.import_module(module_name)
        except ImportError:
            return None

    monkeypatch.setattr(worker, "_ensure_package", recorder)
    out = _call("date_calc", {"base_date": "2026-01-31", "months": 1})
    assert "Result Date: 2026-02-28" in out
    assert ("dateutil", "python-dateutil") in calls


# ---------------------------------------------------------------------------
# Alias tools and generate_prompt
# ---------------------------------------------------------------------------


def test_path_alias_roundtrip(workspace):
    (workspace / "sub").mkdir()
    out = json.loads(_call("path_alias", {"action": "list"}))
    assert out["aliases"]["@A{0}"] == str(workspace)
    out = json.loads(_call("path_alias", {"action": "set", "slot": 1, "path": "sub"}))
    assert out == {"ok": True, "alias": "@A{1}"}
    out = json.loads(_call("path_alias", {"action": "list"}))
    assert out["aliases"]["@A{1}"] == str(workspace / "sub")
    out = json.loads(_call("path_alias", {"action": "set", "slot": 1, "path": "sub"}))
    assert out["ok"] is False  # overwrite guard
    out = json.loads(_call("path_alias", {"action": "delete", "slot": 1}))
    assert out == {"ok": True, "deleted": "@A{1}"}
    out = json.loads(
        _call("path_alias", {"action": "set", "slot": 2, "path": "../outside"})
    )
    assert out["ok"] is False  # outside the workspace


def test_alias_expansion_inside_sandbox(workspace, echo_server):
    (workspace / "sub").mkdir()
    (workspace / "sub" / "hello.txt").write_text("aliased\n", encoding="utf-8")
    _call("path_alias", {"action": "set", "slot": 1, "path": "sub"})
    out = _call("read_file", {"path": "@A{1}/hello.txt"})
    assert "aliased" in out
    out = _call("read_file", {"path": "@A{0}/sub/hello.txt"})
    assert "aliased" in out
    _call("url_alias", {"action": "set", "slot": 0, "url": echo_server})
    out = json.loads(
        _call("http_request", {"url": "@B{0}/via-alias", "parse_json": True})
    )
    assert out["ok"] is True
    assert out["response_json"]["path"] == "/via-alias"
    with pytest.raises(ValueError, match="unknown path alias"):
        _call("read_file", {"path": "@A{9}/nope.txt"})


def test_url_alias_roundtrip(workspace):
    out = json.loads(
        _call(
            "url_alias",
            {"action": "set", "slot": 0, "url": "https://example.com/api"},
        )
    )
    assert out == {"ok": True, "alias": "@B{0}"}
    out = json.loads(_call("url_alias", {"action": "list"}))
    assert out["aliases"]["@B{0}"] == "https://example.com/api"
    out = json.loads(_call("url_alias", {"action": "set", "slot": 1, "url": "ftp://x"}))
    assert out["ok"] is False


def test_generate_prompt_expands_template(workspace):
    (workspace / "doc.txt").write_text("hello\nworld\n", encoding="utf-8")
    out = _call(
        "generate_prompt",
        {
            "path": "doc.txt",
            "template": "{basename}: {lines} lines\n{content}",
        },
    )
    assert out == "doc.txt: 2 lines\nhello\nworld\n"


def test_generate_prompt_errors(workspace):
    out = _call("generate_prompt", {"path": "missing.txt", "template": "x"})
    assert out.startswith("[generate_prompt error]")


# ---------------------------------------------------------------------------
# Automatic package installation
# ---------------------------------------------------------------------------


def test_ensure_package_returns_stdlib_without_pip(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("pip must not run for an importable module")

    monkeypatch.setattr(worker.subprocess, "run", _boom)
    assert worker._ensure_package("json") is not None


def test_ensure_package_installs_into_workspace(workspace, monkeypatch):
    import subprocess as real_subprocess
    import sys

    module_name = "uag_stub_pkg_xyz"

    def fake_run(command, **kwargs):
        target = command[command.index("--target") + 1]
        stub = worker.Path(target) / f"{module_name}.py"
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text("MARKER = 42\n", encoding="utf-8")
        return real_subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(worker, "_SANDBOX_SITE_PACKAGES", None)
    monkeypatch.setattr(worker.subprocess, "run", fake_run)
    monkeypatch.delitem(sys.modules, module_name, raising=False)
    try:
        module = worker._ensure_package(module_name)
        assert module is not None
        assert module.MARKER == 42
        assert (workspace / ".uag" / "site-packages").is_dir()
    finally:
        sys.modules.pop(module_name, None)


def test_ensure_package_returns_none_when_install_fails(monkeypatch):
    import subprocess as real_subprocess

    def fake_run(command, **kwargs):
        return real_subprocess.CompletedProcess(command, 1, "", "nope")

    monkeypatch.setattr(worker, "_SANDBOX_SITE_PACKAGES", None)
    monkeypatch.setattr(worker.subprocess, "run", fake_run)
    assert worker._ensure_package("uag_missing_pkg_xyz") is None
