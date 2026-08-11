from __future__ import annotations

import json

from uagent.tools.geodesic_distance_tool import run_tool


def test_geodesic_distance_returns_haversine_distance() -> None:
    result = json.loads(run_tool({"lat_a": 0, "lon_a": 0, "lat_b": 0, "lon_b": 1}))
    assert result["ok"] is True
    assert 111.1 < result["distance_km"] < 111.3
    assert result["method"] == "Haversine"


def test_geodesic_distance_rejects_invalid_coordinates() -> None:
    result = json.loads(run_tool({"lat_a": 91, "lon_a": 0, "lat_b": 0, "lon_b": 0}))
    assert result["ok"] is False
