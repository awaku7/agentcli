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
