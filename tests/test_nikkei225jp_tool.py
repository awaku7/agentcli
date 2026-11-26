from __future__ import annotations

import json

from uagent.tools import nikkei225jp_tool


class _FakeResponse:
    def __init__(self, body: bytes, url: str = "https://nikkei225jp.com/test") -> None:
        self._body = body
        self._url = url

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def geturl(self) -> str:
        return self._url

    def read(self, _size: int = -1) -> bytes:
        return self._body


def test_fetches_and_parses_chart_data(monkeypatch) -> None:
    body = (
        'var Bdata="57899.82",Max="58244.85",Time="11:15";\n'
        "var Cdata = [[1795651200000, 57523.76], [1795651260000, 57495.73]];"
    ).encode()
    calls: list[tuple[str, int]] = []

    def fake_urlopen(request, timeout: int):
        calls.append((request.full_url, timeout))
        return _FakeResponse(body)

    monkeypatch.setattr(nikkei225jp_tool, "urlopen", fake_urlopen)

    result = json.loads(nikkei225jp_tool.run_tool({"max_points": 1}))

    assert result["ok"] is True
    assert result["code"] == 111
    assert result["dataset"] == "168"
    assert result["fields"] == {
        "Bdata": "57899.82",
        "Max": "58244.85",
        "Time": "11:15",
    }
    assert result["points_returned"] == 1
    assert result["points"] == [{"time_ms": 1795651260000, "value": 57495.73}]
    assert calls == [("https://nikkei225jp.com/_data/_nfsDATA/json/111_168.json", 10)]


def test_rejects_invalid_dataset_without_network_call(monkeypatch) -> None:
    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("network should not be used")

    monkeypatch.setattr(nikkei225jp_tool, "urlopen", fail_urlopen)

    result = json.loads(nikkei225jp_tool.run_tool({"dataset": "../../evil"}))

    assert result["ok"] is False
    assert "dataset" in result["error"]


def test_rejects_redirect_outside_site(monkeypatch) -> None:
    monkeypatch.setattr(
        nikkei225jp_tool,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(
            b"var Cdata = [[1, 2]];", "https://example.com/data"
        ),
    )

    result = json.loads(nikkei225jp_tool.run_tool({}))

    assert result["ok"] is False
    assert "redirect" in result["error"]


def test_returns_clear_error_for_changed_response(monkeypatch) -> None:
    monkeypatch.setattr(
        nikkei225jp_tool,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(b"not chart data"),
    )

    result = json.loads(nikkei225jp_tool.run_tool({}))

    assert result["ok"] is False
    assert "format" in result["error"]
