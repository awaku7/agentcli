"""Opt-in tool-discovery diagnostics (UAGENT_DEBUG_TOOL_DISCOVERY)."""

from __future__ import annotations

import json

import pytest

from uagent.runtime import tool_discovery as td


@pytest.fixture()
def debug_file(tmp_path, monkeypatch):
    path = tmp_path / "tool_discovery.jsonl"
    monkeypatch.setattr(td, "_tool_discovery_debug_path", lambda: path)
    return path


def _decision(mode: td.ToolDiscoveryMode, reason: str) -> td.ToolDiscoveryDecision:
    return td.ToolDiscoveryDecision(mode, reason)


def test_disabled_by_default_records_nothing(debug_file, monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_DEBUG_TOOL_DISCOVERY", raising=False)
    td.record_tool_discovery_debug(
        _decision(td.ToolDiscoveryMode.SELECTED_SCHEMAS, "tool_search_unavailable"),
        provider="openai",
        depname="gpt-x",
        tool_names=["tool_catalog", "read_file"],
    )
    assert not debug_file.exists()


def test_enabled_records_mode_reason_and_catalog_flag(debug_file, monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_DEBUG_TOOL_DISCOVERY", "1")
    td.record_tool_discovery_debug(
        _decision(td.ToolDiscoveryMode.SELECTED_SCHEMAS, "tool_search_unavailable"),
        provider="openai",
        depname="gpt-x",
        use_responses_api=True,
        tool_names=["tool_catalog", "read_file"],
        where="responses",
        session_id="20261117_170000",
    )
    td.record_tool_discovery_debug(
        _decision(td.ToolDiscoveryMode.NATIVE_SEARCH, "native_mode"),
        provider="openai",
        depname="gpt-5.4",
        use_responses_api=True,
        tool_names=["read_file"],
        where="responses",
    )
    lines = debug_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["mode"] == "selected_schemas"
    assert first["reason"] == "tool_search_unavailable"
    assert first["catalog_sent"] is True
    assert first["tool_count"] == 2
    assert first["session_id"] == "20261117_170000"
    second = json.loads(lines[1])
    assert second["mode"] == "native_search"
    assert second["catalog_sent"] is False


def test_enabled_flag_accepts_common_truthy_values(monkeypatch) -> None:
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv("UAGENT_DEBUG_TOOL_DISCOVERY", value)
        assert td.tool_discovery_debug_enabled() is True
    for value in ("", "0", "off", "2"):
        monkeypatch.setenv("UAGENT_DEBUG_TOOL_DISCOVERY", value)
        assert td.tool_discovery_debug_enabled() is False
