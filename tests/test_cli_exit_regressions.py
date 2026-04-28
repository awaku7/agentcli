from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest


def test_search_web_main_raises_runtime_error_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import search_web_tool

    monkeypatch.setattr(sys, "argv", ["search_web_tool.py", "example"])

    def boom(_query: str, _max_results: int):
        raise RuntimeError("ddg failed")

    monkeypatch.setattr(search_web_tool, "search_web", boom)

    with pytest.raises(RuntimeError, match="Search failed: ddg failed"):
        search_web_tool.main()


def test_playwright_inspector_returns_error_when_child_process_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import playwright_inspector_tool

    monkeypatch.setattr(
        playwright_inspector_tool.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="boom from child",
        ),
    )

    out = playwright_inspector_tool.run_playwright_inspector(
        url="https://example.com",
        prefix="pytest_capture",
    )

    assert "boom from child" in out
    assert "error" in out.lower()


def test_playwright_inspector_passes_json_payload_to_child_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import playwright_inspector_tool

    captured: dict[str, object] = {}

    def fake_run(argv, capture_output, text):
        captured["argv"] = argv
        captured["capture_output"] = capture_output
        captured["text"] = text
        return SimpleNamespace(returncode=0, stdout="child ok", stderr="")

    monkeypatch.setattr(playwright_inspector_tool.subprocess, "run", fake_run)

    out = playwright_inspector_tool.run_playwright_inspector(
        url="https://example.com",
        prefix="pytest_capture",
    )

    assert "child ok" in out
    argv = captured["argv"]
    assert isinstance(argv, list)
    assert len(argv) >= 3
    payload = json.loads(argv[2])
    assert payload["url"] == "https://example.com"
    assert payload["prefix"] == "pytest_capture"
    assert captured["capture_output"] is True
    assert captured["text"] is True

