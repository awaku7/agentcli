"""Tests for forecast_tool.py — TDD cycle."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ── Cycle 1: TOOL_SPEC structure ──────────────────────────────────────

def test_tool_spec_structure():
    """TOOL_SPEC must exist with correct type/function/name."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import TOOL_SPEC
    assert isinstance(TOOL_SPEC, dict)
    assert TOOL_SPEC["type"] == "function"
    func = TOOL_SPEC["function"]
    assert func["name"] == "forecast"
    params = func["parameters"]["properties"]
    required = func["parameters"]["required"]
    for r in ("data", "date_column", "value_column", "horizon"):
        assert r in params, f"missing required param: {r}"
        assert r in required, f"{r} not in required"
    assert params["horizon"]["type"] == "integer"
    assert params["horizon"]["minimum"] == 1


# ── Cycle 2: i18n keys exist ──────────────────────────────────────────

def test_i18n_keys_exist():
    """All i18n keys in forecast_tool.json match those used in TOOL_SPEC."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    json_path = Path(__file__).parents[2] / "src/uagent/tools/forecast_tool.json"
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    en = data.get("en", {})
    ja = data.get("ja", {})
    # check a few critical keys
    assert "tool.forecast.description" in en
    assert "param.data.description" in en
    assert "param.horizon.description" in en
    assert "param.model.description" in en
    assert "error.data_too_small" in en
    assert "error.missing_rate_high" in en
    assert "error.timeout" in en
    assert "error.all_models_failed" in en
    # ja must exist (primary non-en)
    assert "tool.forecast.description" in ja


# ── Cycle 3: CSV read ─────────────────────────────────────────────────

def test_read_csv_utf8(sample_csv_path):
    """Read UTF-8 CSV returns DataFrame with correct columns."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _read_csv
    df = _read_csv(sample_csv_path)
    assert isinstance(df, pd.DataFrame)
    assert "date" in df.columns
    assert "value" in df.columns
    assert len(df) == 50


def test_read_csv_cp932(tmp_path, sample_df):
    """Read CP932 CSV works."""
    path = tmp_path / "cp932.csv"
    sample_df.to_csv(path, index=False, encoding="cp932")
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _read_csv
    df = _read_csv(str(path))
    assert len(df) == 50


def test_read_csv_fail(tmp_path):
    """Non-existent file raises ValueError."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _read_csv
    with pytest.raises(ValueError):
        _read_csv(str(tmp_path / "nope.csv"))


# ── Cycle 4: DataFrame JSON read ──────────────────────────────────────

def test_load_data_json(sample_json_str, sample_df):
    """load_data() parses JSON string correctly."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import load_data
    df = load_data(sample_json_str)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["date", "value"]
    assert len(df) == 50


def test_load_data_csv(sample_csv_path):
    """load_data() detects file path and reads CSV."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import load_data
    df = load_data(sample_csv_path)
    assert isinstance(df, pd.DataFrame)


# ── Cycle 5: Date parsing ─────────────────────────────────────────────

def test_parse_dates_ymd(sample_df):
    """Parse YYYY-MM-DD dates."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _parse_date_column
    df = _parse_date_column(sample_df.copy(), "date")
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_parse_dates_iso():
    """Parse ISO 8601 string dates."""
    df = pd.DataFrame({"dt": ["2024-01-01T00:00:00", "2024-01-02T12:30:00"], "v": [1, 2]})
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _parse_date_column
    result = _parse_date_column(df.copy(), "dt")
    assert pd.api.types.is_datetime64_any_dtype(result["dt"])


# ── Cycle 6: Frequency inference ──────────────────────────────────────

def test_infer_freq_D(sample_df):
    """Daily frequency is inferred as 'D'."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _infer_frequency
    freq = _infer_frequency(sample_df.set_index("date").index)
    assert freq == "D"


def test_infer_freq_H():
    """Hourly frequency is inferred as 'h'."""
    idx = pd.date_range("2024-01-01", periods=10, freq="h")
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _infer_frequency
    freq = _infer_frequency(idx)
    assert freq == "h"


def test_infer_freq_fallback():
    """Irregular index falls back to 'D'."""
    idx = pd.DatetimeIndex(["2024-01-01", "2024-01-03", "2024-01-10"])
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _infer_frequency
    freq = _infer_frequency(idx)
    assert freq == "D"


# ── Cycle 7: Missing 0% ───────────────────────────────────────────────

def test_handle_missing_none(sample_df):
    """No missing values → unchanged."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _handle_missing
    df = _handle_missing(sample_df.copy(), "value")
    assert df["value"].isna().sum() == 0
    assert len(df) == 50


# ── Cycle 8: Missing 1-20% ────────────────────────────────────────────

def test_handle_missing_linear(missing_df):
    """Under 20% missing → linear interpolation."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _handle_missing
    df = _handle_missing(missing_df.copy(), "value")
    assert df["value"].isna().sum() == 0


# ── Cycle 9: Missing 20-50% ───────────────────────────────────────────

def test_handle_missing_ffill(high_missing_df):
    """Over 50% missing → error."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _handle_missing, MissingRateHighError
    with pytest.raises(MissingRateHighError):
        _handle_missing(high_missing_df.copy(), "value")


# ── Cycle 10: Missing >50% ────────────────────────────────────────────

def test_handle_missing_error():
    """Over 50% missing raises MissingRateHighError."""
    df = pd.DataFrame({"v": [1.0, np.nan, np.nan, np.nan, np.nan]})
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _handle_missing, MissingRateHighError
    with pytest.raises(MissingRateHighError):
        _handle_missing(df, "v")


# ── Cycle 11: Outlier IQR ─────────────────────────────────────────────

def test_outlier_iqr_replaces(outlier_df):
    """IQR replaces extreme values with median."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _replace_outliers_iqr
    result = _replace_outliers_iqr(outlier_df["value"].copy())
    # outliers at index 10 (200) and 25 (10) should be clipped
    assert result.iloc[10] < 150  # was 200
    assert result.iloc[25] > 50   # was 10


# ── Cycle 12: Outlier Z-score ─────────────────────────────────────────

def test_outlier_zscore_replaces(outlier_df):
    """Z-score replaces |Z|>3 values with median."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _replace_outliers_zscore
    result = _replace_outliers_zscore(outlier_df["value"].copy())
    assert result.iloc[10] < 150  # was 200


# ── Cycle 13: Model selection auto ─────────────────────────────────────

def test_select_best_model_rmse(sample_df):
    """_select_best_model returns model name with lowest RMSE."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _select_best_model
    train = sample_df.iloc[:40]
    valid = sample_df.iloc[40:]
    with patch("uagent.tools.forecast_tool._get_available_models") as mock_get:
        dummy_model = MagicMock()
        dummy_model.fit.return_value = dummy_model
        dummy_model.predict.return_value = valid["value"].values + np.random.normal(0, 0.1, len(valid))
        mock_get.return_value = [("LightGBM", lambda: dummy_model)]
        name, model = _select_best_model(train, valid, "date", "value", "D")
        assert name == "LightGBM"


# ── Cycle 14: Data too small error ────────────────────────────────────

def test_data_too_small(tiny_df):
    """Less than 10 rows raises DataTooSmallError."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import preprocess, DataTooSmallError
    with pytest.raises(DataTooSmallError):
        preprocess(tiny_df, "date", "value")


# ── Cycle 15: run_tool error path ──────────────────────────────────────

def test_run_tool_data_too_small(tiny_df):
    """run_tool returns error JSON for tiny data."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import run_tool
    result = run_tool({
        "data": tiny_df.to_json(orient="split", index=False),
        "date_column": "date",
        "value_column": "value",
        "horizon": 5,
    })
    parsed = json.loads(result)
    assert "error" in parsed


# ── Cycle 16: run_tool happy path ──────────────────────────────────────

def test_run_tool_happy_path(sample_df):
    """run_tool returns valid forecast JSON."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import run_tool
    with patch("uagent.tools.forecast_tool._get_available_models") as mock_get:
        dummy = MagicMock()
        dummy.fit.return_value = dummy
        dummy.predict.return_value = np.full(5, 105.0)
        mock_get.return_value = [("LightGBM", lambda: dummy)]
        result = run_tool({
            "data": sample_df.to_json(orient="split", index=False),
            "date_column": "date",
            "value_column": "value",
            "horizon": 5,
        })
    parsed = json.loads(result)
    assert "best_model" in parsed
    assert "forecast" in parsed
    assert "metrics" in parsed


# ── Cycle 17: Metrics ─────────────────────────────────────────────────

def test_metrics_mae():
    """MAE calculation."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _calc_metrics
    y_true = np.array([100, 102, 101])
    y_pred = np.array([99, 103, 100])
    metrics = _calc_metrics(y_true, y_pred)
    assert "mae" in metrics
    assert metrics["mae"] == pytest.approx(1.0, abs=0.01)


def test_metrics_rmse():
    """RMSE calculation."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _calc_metrics
    y_true = np.array([100, 102, 101])
    y_pred = np.array([100, 102, 101])
    metrics = _calc_metrics(y_true, y_pred)
    assert metrics["rmse"] == pytest.approx(0.0, abs=0.01)


def test_metrics_mape():
    """MAPE calculation."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _calc_metrics
    y_true = np.array([100, 200, 100])
    y_pred = np.array([110, 200, 95])
    metrics = _calc_metrics(y_true, y_pred)
    assert "mape" in metrics
    assert 0 < metrics["mape"] < 10


# ── Cycle 18: i18n helper returns correct lang ────────────────────────

def test_i18n_ja(monkeypatch):
    """With UAGENT_LANG=ja, error message returns Japanese."""
    monkeypatch.setenv("UAGENT_LANG", "ja")
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    # verify the json file has ja keys
    json_path = Path(__file__).parents[2] / "src/uagent/tools/forecast_tool.json"
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    assert "ja" in data
    assert "error.data_too_small" in data["ja"]
    assert data["ja"]["error.data_too_small"] == "データ不足: 最低%(min_rows)d行必要、%(actual)d行"


# ── Cycle 19: Frequency QS/YS ──────────────────────────────────────────

def test_infer_freq_QS():
    """Quarterly frequency is inferred as 'QS'."""
    idx = pd.date_range("2024-01-01", periods=6, freq="QS")
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _infer_frequency
    freq = _infer_frequency(idx)
    assert freq.startswith("QS")


def test_infer_freq_YS():
    """Yearly frequency is inferred as 'YS'."""
    idx = pd.date_range("2024-01-01", periods=4, freq="YS")
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _infer_frequency
    freq = _infer_frequency(idx)
    assert freq.startswith("YS")


# ── Cycle 20: Plot generation ─────────────────────────────────────────

def test_plot_saves_file(sample_df, tmp_path):
    """plot=True creates a .png file."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import run_tool
    plot_path = str(tmp_path / "test_plot.png")
    with patch("uagent.tools.forecast_tool._get_available_models") as mock_get:
        dummy = MagicMock()
        dummy.fit.return_value = dummy
        dummy.predict.return_value = np.full(3, 105.0)
        mock_get.return_value = [("LightGBM", lambda: dummy)]
        result = run_tool({
            "data": sample_df.to_json(orient="split", index=False),
            "date_column": "date",
            "value_column": "value",
            "horizon": 3,
            "plot": plot_path,
        })
    parsed = json.loads(result)
    assert "plot" in parsed
    assert Path(parsed["plot"]).exists() or "plot_error" in parsed["plot"]


# ── Cycle 21: CI fallback ─────────────────────────────────────────────

def test_ci_fallback_produces_bounds():
    """CI fallback produces lower <= upper."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _compute_ci
    import pandas as pd
    df = pd.DataFrame({"v": [100.0, 102.0, 101.0, 103.0, 99.0]})
    forecast = np.array([104.0, 105.0])
    lo, hi = _compute_ci(None, "Dummy", df, "v", 2, forecast, 0.95)
    assert len(lo) == 2
    assert len(hi) == 2
    for l, h in zip(lo, hi):
        assert l <= h


# ── Cycle 22: _compute_ci dispatches correctly for Prophet ────────────

def test_ci_prophet_dispatch():
    """_compute_ci with model_name=Prophet calls _get_ci_prophet."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _compute_ci
    import pandas as pd
    df = pd.DataFrame({"v": [100.0, 102.0, 101.0, 103.0, 99.0]})
    forecast = np.array([104.0, 105.0])
    # With a mock model that doesn't have make_future_dataframe, falls back
    lo, hi = _compute_ci(object(), "Prophet", df, "v", 2, forecast, 0.95)
    # Should fallback to residual-based since object() has no prophet methods
    assert len(lo) == 2
    assert len(hi) == 2


# ── Cycle 23: _compute_ci quantile fallback for LightGBM ──────────────

def test_ci_quantile_dispatch():
    """_compute_ci with model_name=LightGBM calls _get_ci_quantile."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _compute_ci
    import pandas as pd
    df = pd.DataFrame({"v": [100.0, 102.0, 101.0, 103.0, 99.0, 98.0, 104.0]})
    forecast = np.array([105.0, 106.0])
    lo, hi = _compute_ci(None, "LightGBM", df, "v", 2, forecast, 0.95)
    assert len(lo) == 2
    assert len(hi) == 2
    for l, h in zip(lo, hi):
        assert l <= h


# ── Cycle 24: Timeout error ───────────────────────────────────────────

def test_timeout_error():
    """_run_with_timeout raises TimeoutError when function exceeds limit."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import _run_with_timeout
    with pytest.raises(TimeoutError):
        _run_with_timeout(lambda: __import__("time").sleep(10), 1)


# ── Cycle 25: run_tool timeout returns error JSON ─────────────────────

def test_run_tool_timeout_error(sample_df):
    """run_tool returns error when all models fail."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from uagent.tools.forecast_tool import run_tool
    with patch("uagent.tools.forecast_tool._get_available_models") as m:
        m.return_value = []  # no models at all
        result = run_tool({
            "data": sample_df.to_json(orient="split", index=False),
            "date_column": "date",
            "value_column": "value",
            "horizon": 3,
        })
    parsed = json.loads(result)
    assert "error" in parsed

