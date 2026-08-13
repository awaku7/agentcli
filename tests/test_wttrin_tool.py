from __future__ import annotations

from uagent.tools import wttrin_tool


def test_weather_rejects_partial_coordinates_without_network(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_LANG", "en")

    def fail_get(*args, **kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr(wttrin_tool.requests, "get", fail_get)

    result = wttrin_tool.run_tool({"lat": 35.6812})

    assert "city" in result.lower()
    assert "lat+lon" in result.lower()


def test_weather_allows_city_when_partial_coordinates_are_present(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_LANG", "en")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "current_condition": [
                    {
                        "temp_C": "20",
                        "FeelsLikeC": "20",
                        "humidity": "50",
                        "weatherDesc": [{"value": "Clear"}],
                    }
                ],
                "nearest_area": [{"areaName": [{"value": "Tokyo"}]}],
                "weather": [],
            }

    monkeypatch.setattr(wttrin_tool.requests, "get", lambda *args, **kwargs: Response())

    result = wttrin_tool.run_tool({"city": " Tokyo ", "lat": 35.6812})

    assert "Tokyo" in result
    assert "20" in result
