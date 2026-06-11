from __future__ import annotations

import json

import pytest


def test_fetch_url_success_with_mocked_urlopen(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import fetch_url_tool

    class DummyResp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _n: int) -> bytes:
            return b"hello"

    monkeypatch.setattr(fetch_url_tool, "urlopen", lambda _req: DummyResp())

    out = fetch_url_tool.run_tool({"url": "https://example.com"})
    assert out == "hello"


def test_fetch_url_fallback_latin1_decode(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import fetch_url_tool

    class DummyResp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _n: int) -> bytes:
            return b"\xff"

    monkeypatch.setattr(fetch_url_tool, "urlopen", lambda _req: DummyResp())

    out = fetch_url_tool.run_tool({"url": "https://example.com"})
    assert out == "ÿ"


def test_fetch_url_returns_json_error_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import fetch_url_tool

    def boom(_req):
        raise RuntimeError("network down")

    monkeypatch.setattr(fetch_url_tool, "urlopen", boom)

    out = fetch_url_tool.run_tool({"url": "https://example.com"})
    payload = json.loads(out)
    assert payload["ok"] is False
    assert "network down" in payload["error"]


def test_search_web_missing_query_returns_error_json() -> None:
    from uagent.tools import search_web_tool

    out = search_web_tool.run_tool({"query": "", "q": ""})
    payload = json.loads(out)
    assert "error" in payload


def test_search_web_uses_alias_and_parses_n(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import search_web_tool

    called: list[tuple[str, int]] = []

    def fake_search_web(query: str, max_results: int):
        called.append((query, max_results))
        return [{"title": "t", "href": "u", "text": "s"}]

    monkeypatch.setattr(search_web_tool, "search_web", fake_search_web)

    out = search_web_tool.run_tool({"query": "", "q": "abc", "n": "3"})
    payload = json.loads(out)

    assert called == [("abc", 3)]
    assert isinstance(payload.get("results"), list)
    assert payload["results"][0]["title"] == "t"


def test_search_web_returns_error_json_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import search_web_tool

    def boom(_q: str, _n: int):
        raise RuntimeError("ddg failed")

    monkeypatch.setattr(search_web_tool, "search_web", boom)

    out = search_web_tool.run_tool({"query": "abc", "max_results": 2})
    payload = json.loads(out)
    assert "error" in payload
    assert "ddg failed" in payload["error"]


def test_get_geoip_rejects_invalid_format() -> None:
    from uagent.tools import get_geoip_tool

    out = get_geoip_tool.run_tool({"format": "xml"})
    assert out.startswith("[get_geoip error]")


def test_get_geoip_json_output_from_mocked_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import get_geoip_tool

    sample = {
        "ip": "1.2.3.4",
        "city": "Tokyo",
        "region": "Tokyo",
        "country": "JP",
        "loc": "35,139",
        "org": "ASX",
        "postal": "100-0001",
        "timezone": "Asia/Tokyo",
    }
    monkeypatch.setattr(
        get_geoip_tool, "fetch_url_run", lambda _args: json.dumps(sample)
    )

    out = get_geoip_tool.run_tool({"format": "json"})
    payload = json.loads(out)

    assert payload["ip"] == "1.2.3.4"
    assert payload["country"] == "JP"


def test_get_geoip_parses_payload_after_prefix_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import get_geoip_tool

    raw = 'meta line\n{"ip":"1.1.1.1","country":"JP"}'
    monkeypatch.setattr(get_geoip_tool, "fetch_url_run", lambda _args: raw)

    out = get_geoip_tool.run_tool({"format": "json"})
    payload = json.loads(out)
    assert payload["ip"] == "1.1.1.1"


def test_get_geoip_returns_parse_error_with_raw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import get_geoip_tool

    monkeypatch.setattr(get_geoip_tool, "fetch_url_run", lambda _args: "not-json")

    out = get_geoip_tool.run_tool({"format": "text"})
    assert out.startswith("[get_geoip error]")
    assert "not-json" in out


def test_fetch_url_extract_text_from_html(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import fetch_url_tool

    class DummyHeaders:
        def get_content_charset(self):
            return "utf-8"

    class DummyResp:
        headers = DummyHeaders()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _n: int) -> bytes:
            return b"<html><body><main><h1>Hello</h1><p>World</p></main></body></html>"

    monkeypatch.setattr(fetch_url_tool, "urlopen", lambda _req: DummyResp())

    out = fetch_url_tool.run_tool({"url": "https://example.com", "extract": "text"})
    assert out == "Hello\nWorld"


def test_fetch_url_extract_text_with_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import fetch_url_tool

    class DummyHeaders:
        def get_content_charset(self):
            return "utf-8"

    class DummyResp:
        headers = DummyHeaders()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _n: int) -> bytes:
            return b"<html><body><main><h1>Hello</h1><p>World</p></main></body></html>"

    monkeypatch.setattr(fetch_url_tool, "urlopen", lambda _req: DummyResp())

    out = fetch_url_tool.run_tool(
        {"url": "https://example.com", "extract": "text", "selector": "h1"}
    )
    assert out == "Hello"


def test_fetch_url_extract_json_with_pointer(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import fetch_url_tool

    class DummyHeaders:
        def get_content_charset(self):
            return "utf-8"

    class DummyResp:
        headers = DummyHeaders()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _n: int) -> bytes:
            return b'{"a":{"b":[{"c":1},{"c":2}]}}'

    monkeypatch.setattr(fetch_url_tool, "urlopen", lambda _req: DummyResp())

    out = fetch_url_tool.run_tool(
        {
            "url": "https://example.com",
            "extract": "json",
            "json_pointer": "/a/b/1/c",
        }
    )
    assert out == "2"


def test_fetch_url_extract_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import fetch_url_tool

    class DummyHeaders:
        def get_content_charset(self):
            return "utf-8"

    class DummyResp:
        headers = DummyHeaders()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _n: int) -> bytes:
            return b"<html><body><main><h1>Hello</h1><p>World with <a href='http://link'>link</a> and <strong>bold</strong></p><ul><li>item 1</li><li>item 2</li></ul></main></body></html>"

    monkeypatch.setattr(fetch_url_tool, "urlopen", lambda _req: DummyResp())

    out = fetch_url_tool.run_tool(
        {
            "url": "https://example.com",
            "extract": "markdown",
        }
    )
    assert "# Hello" in out
    assert "[link](http://link)" in out
    assert "**bold**" in out
    assert "- item 1" in out


def test_fetch_url_http_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import fetch_url_tool
    import urllib.error

    def boom_http(_req, **kwargs):
        raise urllib.error.HTTPError(
            "https://example.com/404", 404, "Not Found", {}, None
        )

    # Mock urllib.request.urlopen to be the standard one so that our opener is used
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", urllib.request.urlopen)

    # We mock opener.open instead
    class DummyOpener:
        def open(self, req, timeout=10):
            raise urllib.error.HTTPError(
                "https://example.com/404", 404, "Not Found", {}, None
            )

    monkeypatch.setattr(fetch_url_tool, "build_opener", lambda *args: DummyOpener())

    out = fetch_url_tool.run_tool({"url": "https://example.com/404"})
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["status_code"] == 404
    assert "HTTP Error 404" in payload["error"]


def test_fetch_url_url_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import fetch_url_tool
    import urllib.error

    class DummyOpener:
        def open(self, req, timeout=10):
            raise urllib.error.URLError("connection timed out")

    monkeypatch.setattr(fetch_url_tool, "build_opener", lambda *args: DummyOpener())

    out = fetch_url_tool.run_tool({"url": "https://example.com"})
    payload = json.loads(out)
    assert payload["ok"] is False
    assert "URL Error" in payload["error"]


def test_fetch_url_redirect_loop_prevention() -> None:
    from uagent.tools.fetch_url_tool import SafeRedirectHandler
    import urllib.request
    import urllib.error

    handler = SafeRedirectHandler(max_redirects=2)
    req = urllib.request.Request("https://example.com")
    req._redirect_count = 2

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        handler.redirect_request(req, None, 302, "Found", {}, "https://example.com/new")
    assert "Too many redirects" in str(excinfo.value)
