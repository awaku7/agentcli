from __future__ import annotations

import json

from uagent.tools import public_transit_route_tool as route_tool


def _html() -> str:
    data = {
        "props": {
            "pageProps": {
                "naviSearchParam": {
                    "featureInfoList": [
                        {
                            "summaryInfo": {
                                "departureTime": "09:00",
                                "arrivalTime": "10:00",
                                "totalTime": "1時間0分",
                                "totalPrice": "500",
                                "totalPriceDetail": "（乗車券500円）",
                                "transferCount": "1",
                                "distance": "42.0km",
                                "calendarData": {
                                    "description": "09:00 A\nLine 1\n10:00 B"
                                },
                            },
                            "edgeInfoList": [
                                {
                                    "stationName": "A",
                                    "railName": "Line 1",
                                    "destination": "B",
                                    "timeInfo": [{"time": "09:00"}],
                                }
                            ],
                        }
                    ]
                }
            }
        }
    }
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'


def test_build_params_maps_time_sort_ticket_and_avoid() -> None:
    params = route_tool._build_params(
        {
            "origin": "A",
            "destination": "B",
            "departure": "2026-08-11T09:34:00+09:00",
            "sort_by": "cheapest",
            "ticket": "normal",
            "avoid": ["shinkansen", "ship"],
        }
    )
    assert params["y"] == "2026"
    assert params["hh"] == "09"
    assert params["m1"] == "3"
    assert params["m2"] == "4"
    assert params["s"] == "1"
    assert params["ticket"] == "normal"
    assert params["shin"] == "0"
    assert params["sr"] == "0"


def test_parse_next_data_and_route() -> None:
    data = route_tool._parse_next_data(_html())
    feature = data["props"]["pageProps"]["naviSearchParam"]["featureInfoList"][0]
    route = route_tool._route_from_feature(feature, 1)
    assert route["fare_yen"] == 500
    assert route["duration_minutes"] == 60
    assert route["segments"][0]["line"] == "Line 1"


def test_resolve_ambiguous_origin_from_destination() -> None:
    assert route_tool._resolve_origin("郡山", "堺筋本町") == "郡山(奈良県)"
    assert route_tool._resolve_origin("郡山駅", "大阪駅") == "郡山(奈良県)"
    assert route_tool._resolve_origin("郡山", "仙台駅") == "郡山(福島県)"
    assert route_tool._resolve_origin("郡山", "東京駅") == "郡山(福島県)"


def test_run_tool_normalizes_yahoo_result(monkeypatch) -> None:
    class Response:
        text = _html()

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(route_tool.requests, "get", lambda *args, **kwargs: Response())
    result = json.loads(route_tool.run_tool({"origin": "A", "destination": "B"}))
    assert result["ok"] is True
    assert result["source"] == "Yahoo! Japan Transit"
    assert result["routes"][0]["fare_yen"] == 500
