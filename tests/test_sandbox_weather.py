"""Sandbox-side get_weather_wttr: parsing, fallback, and validation.

The HTTP fetch is stubbed; no network is touched.
"""

from __future__ import annotations

import pytest

from uagent.runtime import sandbox_worker

_WTTR_PAYLOAD = {
    "current_condition": [
        {
            "temp_C": "21",
            "FeelsLikeC": "20",
            "humidity": "55",
            "weatherDesc": [{"value": "Sunny"}],
        }
    ],
    "nearest_area": [{"areaName": [{"value": "Tokyo"}]}],
    "weather": [
        {
            "date": "2026-11-20",
            "maxtempC": "24",
            "mintempC": "15",
            "hourly": [
                {},
                {},
                {"weatherDesc": [{"value": "Clear"}]},
            ],
        }
    ],
}

_GEOCODING_PAYLOAD = {
    "results": [{"latitude": 35.68, "longitude": 139.69, "name": "Tokyo"}]
}

_OPEN_METEO_PAYLOAD = {
    "current": {
        "temperature_2m": 21.5,
        "apparent_temperature": 20.1,
        "relative_humidity_2m": 55,
        "weather_code": 0,
    },
    "daily": {
        "time": ["2026-11-20"],
        "temperature_2m_max": [24.0],
        "temperature_2m_min": [15.0],
        "weather_code": [2],
    },
}


def _stub_fetch(monkeypatch, *, wttr=None, geocoding=None, forecast=None):
    def fake_fetch(url: str):
        if "wttr.in" in url:
            if isinstance(wttr, Exception):
                raise wttr
            return wttr
        if "geocoding-api" in url:
            if isinstance(geocoding, Exception):
                raise geocoding
            return geocoding
        if "api.open-meteo.com" in url:
            if isinstance(forecast, Exception):
                raise forecast
            return forecast
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(sandbox_worker, "_fetch_weather_json", fake_fetch)


def test_weather_from_wttr(monkeypatch):
    _stub_fetch(monkeypatch, wttr=_WTTR_PAYLOAD)
    result = sandbox_worker._get_weather_wttr({"city": "Tokyo"})
    assert "### Weather for Tokyo" in result
    assert "- **Temp**: 21°C (feels like 20°C)" in result
    assert "- **Condition**: Sunny" in result
    assert "- **2026-11-20**: 15°C / 24°C (Clear)" in result


def test_weather_falls_back_to_open_meteo(monkeypatch):
    _stub_fetch(
        monkeypatch,
        wttr=RuntimeError("wttr down"),
        geocoding=_GEOCODING_PAYLOAD,
        forecast=_OPEN_METEO_PAYLOAD,
    )
    result = sandbox_worker._get_weather_wttr({"city": "Tokyo"})
    assert "[via Open-Meteo fallback]" in result
    assert "### Weather for Tokyo" in result
    assert "- **Condition**: Clear sky" in result
    assert "- **2026-11-20**: 15.0°C / 24.0°C (Partly cloudy)" in result


def test_weather_with_coordinates_skips_geocoding(monkeypatch):
    _stub_fetch(
        monkeypatch,
        wttr=RuntimeError("wttr down"),
        geocoding=AssertionError("geocoding must not be called"),
        forecast=_OPEN_METEO_PAYLOAD,
    )
    result = sandbox_worker._get_weather_wttr({"lat": 35.68, "lon": 139.69})
    assert "### Weather for 35.68,139.69" in result


def test_weather_requires_a_location():
    with pytest.raises(ValueError, match="city name, or lat"):
        sandbox_worker._get_weather_wttr({})
    with pytest.raises(ValueError, match="city name, or lat"):
        sandbox_worker._get_weather_wttr({"lat": 35.0})


def test_weather_validates_coordinate_ranges():
    with pytest.raises(ValueError, match="lat must be a number"):
        sandbox_worker._get_weather_wttr({"lat": 123.0, "lon": 0.0})
    with pytest.raises(ValueError, match="lon must be a number"):
        sandbox_worker._get_weather_wttr({"lat": 0.0, "lon": -999.0})


def test_weather_reports_when_both_providers_fail(monkeypatch):
    _stub_fetch(
        monkeypatch,
        wttr=RuntimeError("wttr down"),
        geocoding=RuntimeError("geocoding down"),
        forecast=RuntimeError("unused"),
    )
    with pytest.raises(ValueError, match="both providers"):
        sandbox_worker._get_weather_wttr({"city": "Tokyo"})
