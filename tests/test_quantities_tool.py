from __future__ import annotations

import json

from uagent.tools.quantities_tool import run_tool


def test_quantities_converts_temperature() -> None:
    result = json.loads(run_tool({"expression": "25 degC to degF"}))
    assert result["ok"] is True
    assert result["result"] == "77 °F"


def test_quantities_calculates_energy() -> None:
    result = json.loads(run_tool({"expression": "2.5 kW * 8 hour to kWh"}))
    assert result["ok"] is True
    assert result["result"] == "20 kWh"


def test_quantities_supports_explicit_target_unit() -> None:
    result = json.loads(
        run_tool({"expression": "1 meter + 20 centimeter", "to_unit": "meter"})
    )
    assert result["ok"] is True
    assert result["result"] == "1.2 m"


def test_quantities_rejects_unsafe_target(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_LANG", "en")
    result = json.loads(
        run_tool({"expression": "1 meter", "to_unit": "__import__('os')"})
    )
    assert result["ok"] is False
    assert "unsupported" in result["error"].lower()


def test_quantities_rejects_unsafe_expression(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_LANG", "en")
    result = json.loads(run_tool({"expression": "__import__('os')"}))
    assert result["ok"] is False
    assert "unsupported" in result["error"].lower()
