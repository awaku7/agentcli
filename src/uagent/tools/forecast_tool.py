"""forecast_tool.py — Time series forecasting via LLM Function Calling."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Callable

import numpy as np
import pandas as pd

from .i18n_helper import make_tool_translator
from .context import get_callbacks
from .._pip_auto import install_with_status as _auto_install_pkg

_ = make_tool_translator(__file__)
_logger = logging.getLogger(__name__)

# ── Custom exceptions ──────────────────────────────────────────────────


class DataTooSmallError(ValueError):
    def __init__(self, min_rows: int, actual: int):
        self.min_rows = min_rows
        self.actual = actual
        super().__init__(f"need >= {min_rows} rows, got {actual}")


class MissingRateHighError(ValueError):
    def __init__(self, rate: float):
        self.rate = rate
        super().__init__(f"missing rate {rate:.1%}")


# ── Constants ──────────────────────────────────────────────────────────

_MIN_ROWS = 10
_TIMEOUT_SEC = 120

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "forecast",
    "function": {
        "name": "forecast",
        "description": _(
            "tool.forecast.description",
            default="Execute time series forecasting. Use this when asked about future predictions, trend analysis, sales forecasts, or any numerical forecasting task.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": _(
                        "param.data.description",
                        default="CSV file path or DataFrame JSON string with columns/rows structure",
                    ),
                },
                "date_column": {
                    "type": "string",
                    "description": _(
                        "param.date_column.description",
                        default="Date/time column name",
                    ),
                },
                "value_column": {
                    "type": "string",
                    "description": _(
                        "param.value_column.description",
                        default="Target column name for forecasting",
                    ),
                },
                "horizon": {
                    "type": "integer",
                    "minimum": 1,
                    "description": _(
                        "param.horizon.description",
                        default="Number of forecast periods",
                    ),
                },
                "model": {
                    "type": "string",
                    "enum": [
                        "auto",
                        "StatsForecast",
                        "AutoARIMA",
                        "AutoETS",
                        "Theta",
                        "MSTL",
                        "Prophet",
                        "LightGBM",
                        "CatBoost",
                        "TimesFM",
                        "Chronos",
                    ],
                    "description": _(
                        "param.model.description",
                        default="Forecast model. auto = automatic selection from available models",
                    ),
                },
                "frequency": {
                    "type": "string",
                    "description": _(
                        "param.frequency.description",
                        default="Frequency: D=daily, H=hourly, M=monthly, W=weekly, auto=infer",
                    ),
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": _(
                        "param.confidence.description",
                        default="Confidence interval (0 to 1)",
                    ),
                },
                "plot": {
                    "type": "boolean",
                    "description": _(
                        "param.plot.description",
                        default="Generate and save forecast plot image",
                    ),
                },
                "include_base64": {
                    "type": "boolean",
                    "description": _("param.include_base64.description", default="Include the forecast plot as base64 for remote clients."),
                    "default": True,
                },
                "output_dir": {
                    "type": "string",
                    "description": _(
                        "param.output_dir.description",
                        default="Directory to save plot image. Defaults to ~/.uag/outputs/forecast_plots",
                    ),
                },
                "outlier": {
                    "type": "string",
                    "enum": ["none", "iqr", "zscore"],
                    "description": _(
                        "param.outlier.description",
                        default="Outlier handling: none/iqr/zscore",
                    ),
                },
            },
            "required": ["data", "date_column", "value_column", "horizon"],
        },
    },
}


# ── CSV / JSON Loading ────────────────────────────────────────────────


def _read_csv(path: str) -> pd.DataFrame:
    """Read CSV with auto-detection of encoding and separator."""
    for enc in ("utf-8-sig", "cp932", "latin-1"):
        try:
            for sep in (",", "\t"):
                df = pd.read_csv(path, encoding=enc, sep=sep)
                if len(df.columns) > 1:
                    return df
        except Exception:
            continue
    raise ValueError(_("error.csv_read_failed", default="CSV read failed"))


def load_data(data: str) -> pd.DataFrame:
    """Load data from CSV file path or JSON string."""
    # If it's a file path, read CSV
    if os.path.isfile(data):
        return _read_csv(data)
    # Otherwise try JSON
    try:
        parsed = json.loads(data)
        if isinstance(parsed, dict) and "columns" in parsed and "data" in parsed:
            return pd.DataFrame(parsed["data"], columns=parsed["columns"])
        # orient="split" format
        if "index" in parsed and "columns" in parsed and "data" in parsed:
            return pd.DataFrame(
                parsed["data"], index=parsed["index"], columns=parsed["columns"]
            )
        return pd.DataFrame(parsed)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"Cannot parse data: {e}")


# ── Date Parsing ──────────────────────────────────────────────────────


def _parse_date_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Convert date column to datetime."""
    if pd.api.types.is_datetime64_any_dtype(df[col]):
        return df
    try:
        df[col] = pd.to_datetime(df[col])
    except Exception as e:
        raise ValueError(f"Cannot parse date column '{col}': {e}")
    return df


# ── Frequency Inference ──────────────────────────────────────────────


def _infer_frequency(index: pd.DatetimeIndex) -> str:
    """Infer frequency from DatetimeIndex."""
    # Method 1: pandas infer_freq
    try:
        freq = pd.infer_freq(index)
        if freq:
            return freq
    except Exception:
        pass
    # Method 2: most common delta
    try:
        deltas = pd.Series(index).diff().dropna()
        if len(deltas) > 1:
            mode_delta = deltas.mode().iloc[0]
            if mode_delta.total_seconds() == 86400:
                return "D"
            elif mode_delta.total_seconds() == 3600:
                return "h"
            elif 28 <= mode_delta.days <= 31:
                return "MS"
            elif 6 <= mode_delta.days <= 8:
                return "W"
    except Exception:
        pass
    # Fallback
    return "D"


# ── Missing Value Handling ────────────────────────────────────────────


def _handle_missing(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Handle missing values based on missing rate."""
    total = len(df)
    missing = df[value_col].isna().sum()
    rate = missing / total

    if rate == 0:
        return df
    if rate <= 0.2:
        df[value_col] = df[value_col].interpolate(method="linear")
        return df
    if rate <= 0.5:
        df[value_col] = df[value_col].ffill().bfill()
        return df
    raise MissingRateHighError(rate)


# ── Outlier Replacement ────────────────────────────────────────────────


def _replace_outliers_iqr(series: pd.Series) -> pd.Series:
    """Replace outliers beyond 1.5*IQR with median."""
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    median = series.median()
    return series.clip(lo, hi).fillna(median)


def _replace_outliers_zscore(series: pd.Series) -> pd.Series:
    """Replace outliers with |Z|>3 with median, iteratively."""
    s = series.copy()
    for _ in range(5):
        z = (s - s.mean()) / s.std()
        mask = z.abs() > 3
        if not mask.any():
            break
        s[mask] = s.median()
    return s


def _handle_outliers(df: pd.DataFrame, value_col: str, method: str) -> pd.DataFrame:
    """Apply chosen outlier handling method."""
    if method == "none" or not method:
        return df
    if method == "iqr":
        df[value_col] = _replace_outliers_iqr(df[value_col])
    elif method == "zscore":
        df[value_col] = _replace_outliers_zscore(df[value_col])
    return df


# ── Metrics ────────────────────────────────────────────────────────────


def _calc_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Calculate MAE, RMSE, MAPE."""
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    # MAPE: avoid division by zero
    nonzero = y_true != 0
    if nonzero.any():
        mape = float(
            np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero])) * 100
        )
    else:
        mape = 0.0
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": round(mape, 4)}


# ── Confidence Intervals (model-specific) ─────────────────────────────


def _get_ci_prophet(model, forecast_horizon: int) -> tuple[list[float], list[float]]:
    """Extract CI from Prophet model's predict() output."""
    try:
        future = model.make_future_dataframe(periods=forecast_horizon)
        fcst = model.predict(future)
        lower = fcst["yhat_lower"].values[-forecast_horizon:].tolist()
        upper = fcst["yhat_upper"].values[-forecast_horizon:].tolist()
        return [round(float(v), 4) for v in lower], [round(float(v), 4) for v in upper]
    except Exception:
        return [], []


def _get_ci_statsforecast(
    model, forecast_horizon: int
) -> tuple[list[float], list[float]]:
    """Extract CI from StatsForecast standard output."""
    try:
        sf = model.sf
        fcst = sf.forecast(h=forecast_horizon, level=[95])
        col_lo = [c for c in fcst.columns if c.startswith("AutoARIMA-lo-")]
        col_hi = [c for c in fcst.columns if c.startswith("AutoARIMA-hi-")]
        if col_lo and col_hi:
            lower = fcst[col_lo[0]].values.tolist()
            upper = fcst[col_hi[0]].values.tolist()
            return [round(float(v), 4) for v in lower], [
                round(float(v), 4) for v in upper
            ]
    except Exception:
        pass
    return [], []


def _get_ci_quantile(
    features_df, value_col, forecast_horizon: int
) -> tuple[list[float], list[float]]:
    """Train two LightGBM quantile models and return CI."""
    try:
        import lightgbm as lgb

        df = features_df.copy()
        y = df[value_col].values
        X = df.drop(columns=[value_col])
        n = len(X)
        if n < 5:
            return [], []
        low_model = lgb.LGBMRegressor(
            objective="quantile",
            alpha=0.025,
            n_estimators=100,
            random_state=42,
            verbose=-1,
        )
        high_model = lgb.LGBMRegressor(
            objective="quantile",
            alpha=0.975,
            n_estimators=100,
            random_state=42,
            verbose=-1,
        )
        low_model.fit(X, y)
        high_model.fit(X, y)
        # Use last row repeated for forecast horizon
        last_row = X.iloc[[-1]].copy()
        lower = []
        upper = []
        for _ in range(forecast_horizon):
            lo = float(low_model.predict(last_row)[0])
            hi = float(high_model.predict(last_row)[0])
            lower.append(round(lo, 4))
            upper.append(round(hi, 4))
        return lower, upper
    except Exception:
        return [], []


def _get_ci_sampling(
    model, forecast_horizon: int, num_samples: int = 20
) -> tuple[list[float], list[float]]:
    """Compute CI from num_samples forecast runs (stochastic models)."""
    samples = []
    for _ in range(num_samples):
        try:
            pred = model.predict(forecast_horizon)
            if len(pred) >= forecast_horizon:
                samples.append(pred[:forecast_horizon])
        except Exception:
            continue
    if not samples:
        return [], []
    arr = np.array(samples)
    lower = np.percentile(arr, 2.5, axis=0)
    upper = np.percentile(arr, 97.5, axis=0)
    return [round(float(v), 4) for v in lower], [round(float(v), 4) for v in upper]


def _compute_ci(
    model,
    model_name: str,
    df,
    value_col,
    forecast_horizon: int,
    base_forecast: np.ndarray,
    confidence: float = 0.95,
) -> tuple[list[float], list[float]]:
    """Dispatch CI computation based on model type."""
    z = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence, 1.96)
    # Try model-specific CI first
    if model_name == "Prophet":
        lo, hi = _get_ci_prophet(model, forecast_horizon)
        if lo:
            return lo, hi
    if model_name in ("AutoARIMA", "AutoETS", "Theta", "MSTL", "StatsForecast"):
        lo, hi = _get_ci_statsforecast(model, forecast_horizon)
        if lo:
            return lo, hi
    if model_name in ("LightGBM", "CatBoost"):
        lo, hi = _get_ci_quantile(df, value_col, forecast_horizon)
        if lo:
            return lo, hi
    if model_name in ("TimesFM", "Chronos"):
        lo, hi = _get_ci_sampling(model, forecast_horizon)
        if lo:
            return lo, hi
    # Fallback: residual-based approximation
    residual_std = float(df[value_col].std() * 0.1)
    if residual_std < 1e-9:
        residual_std = float(df[value_col].mean() * 0.05) or 1.0
    lo = [round(float(v - z * residual_std), 4) for v in base_forecast]
    hi = [round(float(v + z * residual_std), 4) for v in base_forecast]
    return lo, hi


# ── Preprocessing ─────────────────────────────────────────────────────


def preprocess(df: pd.DataFrame, date_col: str, value_col: str) -> pd.DataFrame:
    """Full preprocessing pipeline: validate, parse dates, handle missing."""
    if len(df) < _MIN_ROWS:
        raise DataTooSmallError(_MIN_ROWS, len(df))
    df = _parse_date_column(df, date_col)
    df = df.sort_values(date_col).reset_index(drop=True)
    df = _handle_missing(df, value_col)
    return df


# ── Timeout guard ──────────────────────────────────────────────────────

import concurrent.futures as _cf


def _run_with_timeout(func, timeout_sec: int, *args, **kwargs):
    """Run func in a thread with timeout."""
    with _cf.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(func, *args, **kwargs)
        try:
            return fut.result(timeout=timeout_sec)
        except _cf.TimeoutError:
            raise TimeoutError(f"Forecast timed out ({timeout_sec}s)")


# ── Model Selection ────────────────────────────────────────────────────


def _get_available_models() -> list[tuple[str, Callable]]:
    """Return list of (model_name, builder_function) tuples.

    Models that cannot be imported are silently skipped.
    """
    models: list[tuple[str, Callable]] = []

    # Dummy model for testing / fallback
    class _DummyModel:
        def fit(self, df, date_col, value_col, freq):
            self.df = df
            self.date_col = date_col
            self.value_col = value_col
            self.freq = freq
            return self

        def predict(self, horizon_or_valid):
            if isinstance(horizon_or_valid, int):
                n = horizon_or_valid
            else:
                n = len(horizon_or_valid)
            last_val = self.df[self.value_col].iloc[-1]
            return np.full(n, last_val)

    models.append(("Dummy", lambda: _DummyModel()))

    # StatsForecast family
    try:
        from statsforecast import StatsForecast
        from statsforecast.models import AutoARIMA, AutoETS, Theta, MSTL as _MSTL

        class _StatsForecastWrapper:
            def __init__(self, model_class, **kwargs):
                self.model_class = model_class
                self.kwargs = kwargs

            def fit(self, df, date_col, value_col, freq):
                self.value_col = value_col
                self.date_col = date_col
                self.freq = freq
                model = self.model_class(**self.kwargs)
                pdf = df[[date_col, value_col]].rename(
                    columns={date_col: "ds", value_col: "y"}
                )
                pdf["unique_id"] = "ts1"
                self.sf = StatsForecast(
                    models=[model],
                    freq=freq,
                    n_jobs=1,
                )
                self.sf.fit(df=pdf)
                self._fitted_df = pdf
                return self

            def predict(self, horizon_or_valid):
                if isinstance(horizon_or_valid, int):
                    h = horizon_or_valid
                else:
                    h = len(horizon_or_valid)
                preds = self.sf.forecast(h=h, df=self._fitted_df)
                # Get first model's prediction column
                model_cols = [
                    c for c in preds.columns if c != "ds" and c != "unique_id"
                ]
                if model_cols:
                    return preds[model_cols[0]].values
                return np.full(h, 0.0)

        def _make_arima():
            return _StatsForecastWrapper(
                AutoARIMA, seasonal=True, stepwise=True, approximation=False
            )

        def _make_ets():
            return _StatsForecastWrapper(AutoETS)

        def _make_theta():
            return _StatsForecastWrapper(Theta)

        def _make_mstl():
            return _StatsForecastWrapper(_MSTL, season_length=7)

        def _make_sf():
            return _StatsForecastWrapper(
                AutoARIMA, seasonal=True, stepwise=True, approximation=False
            )

        models.append(("AutoARIMA", _make_arima))
        models.append(("AutoETS", _make_ets))
        models.append(("Theta", _make_theta))
        models.append(("MSTL", _make_mstl))
        models.append(("StatsForecast", _make_sf))
    except ImportError:
        # Auto-install statsforecast
        if _auto_install_pkg("statsforecast"):
            try:
                from statsforecast import StatsForecast
                from statsforecast.models import (
                    AutoARIMA,
                    AutoETS,
                    Theta,
                    MSTL as _MSTL,
                )

                class _StatsForecastWrapper:
                    def __init__(self, model_class, **kwargs):
                        self.model_class = model_class
                        self.kwargs = kwargs

                    def fit(self, df, date_col, value_col, freq):
                        self.value_col = value_col
                        self.date_col = date_col
                        self.freq = freq
                        model = self.model_class(**self.kwargs)
                        pdf = df[[date_col, value_col]].rename(
                            columns={date_col: "ds", value_col: "y"}
                        )
                        pdf["unique_id"] = "ts1"
                        self.sf = StatsForecast(
                            models=[model],
                            freq=freq,
                            n_jobs=1,
                        )
                        self.sf.fit(df=pdf)
                        self._fitted_df = pdf
                        return self

                    def predict(self, horizon_or_valid):
                        if isinstance(horizon_or_valid, int):
                            h = horizon_or_valid
                        else:
                            h = len(horizon_or_valid)
                        preds = self.sf.forecast(h=h, df=self._fitted_df)
                        model_cols = [
                            c for c in preds.columns if c != "ds" and c != "unique_id"
                        ]
                        if model_cols:
                            return preds[model_cols[0]].values
                        return np.full(h, 0.0)

                def _make_arima2():
                    return _StatsForecastWrapper(
                        AutoARIMA, seasonal=True, stepwise=True, approximation=False
                    )

                def _make_ets2():
                    return _StatsForecastWrapper(AutoETS)

                def _make_theta2():
                    return _StatsForecastWrapper(Theta)

                def _make_mstl2():
                    return _StatsForecastWrapper(_MSTL, season_length=7)

                def _make_sf2():
                    return _StatsForecastWrapper(
                        AutoARIMA, seasonal=True, stepwise=True, approximation=False
                    )

                models.append(("AutoARIMA", _make_arima2))
                models.append(("AutoETS", _make_ets2))
                models.append(("Theta", _make_theta2))
                models.append(("MSTL", _make_mstl2))
                models.append(("StatsForecast", _make_sf2))
            except ImportError:
                pass

    # Prophet
    try:
        from prophet import Prophet as _Prophet

        class _ProphetWrapper:
            def fit(self, df, date_col, value_col, freq):
                self.date_col = date_col
                pdf = df[[date_col, value_col]].rename(
                    columns={date_col: "ds", value_col: "y"}
                )
                self.model = _Prophet(
                    yearly_seasonality=False,
                    weekly_seasonality=True,
                    daily_seasonality=False,
                )
                self.model.fit(pdf)
                return self

            def predict(self, horizon_or_valid):
                if isinstance(horizon_or_valid, int):
                    h = horizon_or_valid
                    future = self.model.make_future_dataframe(periods=h)
                    fcst = self.model.predict(future)
                    return fcst["yhat"].values[-h:]
                else:
                    # valid DataFrame has columns [date_col, value_col]
                    future = (
                        horizon_or_valid[[self.date_col]]
                        .rename(columns={self.date_col: "ds"})
                        .reset_index(drop=True)
                    )
                    fcst = self.model.predict(future)
                    return fcst["yhat"].values

        models.append(("Prophet", lambda: _ProphetWrapper()))
    except ImportError:
        # Auto-install prophet
        if _auto_install_pkg("prophet"):
            try:
                from prophet import Prophet as _Prophet

                class _ProphetWrapper:
                    def fit(self, df, date_col, value_col, freq):
                        self.date_col = date_col
                        pdf = df[[date_col, value_col]].rename(
                            columns={date_col: "ds", value_col: "y"}
                        )
                        self.model = _Prophet(
                            yearly_seasonality=False,
                            weekly_seasonality=True,
                            daily_seasonality=False,
                        )
                        self.model.fit(pdf)
                        return self

                    def predict(self, horizon_or_valid):
                        if isinstance(horizon_or_valid, int):
                            h = horizon_or_valid
                            future = self.model.make_future_dataframe(periods=h)
                            fcst = self.model.predict(future)
                            return fcst["yhat"].values[-h:]
                        else:
                            future = (
                                horizon_or_valid[[self.date_col]]
                                .rename(columns={self.date_col: "ds"})
                                .reset_index(drop=True)
                            )
                            fcst = self.model.predict(future)
                            return fcst["yhat"].values

                models.append(("Prophet", lambda: _ProphetWrapper()))
            except ImportError:
                pass

    # LightGBM
    try:
        import lightgbm as lgb

        class _LightGBMWrapper:
            def fit(self, df, date_col, value_col, freq):
                self.date_col = date_col
                self.value_col = value_col
                feats = self._engineer(df)
                y = feats[self.value_col]
                X = feats.drop(columns=[self.value_col])
                self.model = lgb.LGBMRegressor(
                    n_estimators=500,
                    learning_rate=0.05,
                    max_depth=6,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42,
                    verbose=-1,
                )
                self.model.fit(X, y)
                self.last_feats = X
                return self

            def predict(self, horizon_or_valid):
                if isinstance(horizon_or_valid, int):
                    h = horizon_or_valid
                    row = self.last_feats.iloc[[-1]].copy()
                    preds = []
                    for i in range(h):
                        p = float(self.model.predict(row)[0])
                        preds.append(p)
                        # Update lag features: shift existing lags forward
                        existing_lags = sorted(
                            [
                                int(c.replace("lag_", ""))
                                for c in row.columns
                                if c.startswith("lag_")
                            ],
                            reverse=True,
                        )
                        old_vals = {
                            lag: row[f"lag_{lag}"].iloc[0] for lag in existing_lags
                        }
                        for lag in existing_lags:
                            if lag == 1:
                                row[f"lag_{lag}"] = p
                            else:
                                prev = [x for x in existing_lags if x < lag]
                                if prev:
                                    row[f"lag_{lag}"] = old_vals.get(max(prev), p)
                        for w in [14, 7, 3]:
                            col = f"ma_{w}"
                            if col in row.columns:
                                row[col] = p
                    return np.array(preds)
                else:
                    valid = horizon_or_valid
                    feats = self._engineer(valid)
                    X = feats.drop(columns=[self.value_col], errors="ignore")
                    return self.model.predict(X)

            def _engineer(self, df):
                df = df.copy()
                dates = pd.to_datetime(df[self.date_col])
                df["dow"] = dates.dt.dayofweek
                df["month"] = dates.dt.month
                df["quarter"] = dates.dt.quarter
                df["woy"] = dates.dt.isocalendar().week.astype(int)
                df["yday"] = dates.dt.dayofyear
                df["weekend"] = df["dow"].isin([5, 6]).astype(int)
                for lag in [1, 2, 3, 7, 14, 28]:
                    df[f"lag_{lag}"] = df[self.value_col].shift(lag)
                for w in [3, 7, 14]:
                    df[f"ma_{w}"] = df[self.value_col].rolling(w).mean()
                df = df.dropna()
                df = df.drop(columns=[self.date_col], errors="ignore")
                return df

        models.append(("LightGBM", lambda: _LightGBMWrapper()))
    except ImportError:
        # Auto-install lightgbm
        if _auto_install_pkg("lightgbm"):
            try:
                import lightgbm as lgb

                class _LightGBMWrapper:
                    def fit(self, df, date_col, value_col, freq):
                        self.date_col = date_col
                        self.value_col = value_col
                        feats = self._engineer(df)
                        y = feats[self.value_col]
                        X = feats.drop(columns=[self.value_col])
                        self.model = lgb.LGBMRegressor(
                            n_estimators=500,
                            learning_rate=0.05,
                            max_depth=6,
                            subsample=0.8,
                            colsample_bytree=0.8,
                            random_state=42,
                            verbose=-1,
                        )
                        self.model.fit(X, y)
                        self.last_feats = X
                        return self

                    def predict(self, horizon_or_valid):
                        if isinstance(horizon_or_valid, int):
                            h = horizon_or_valid
                            row = self.last_feats.iloc[[-1]].copy()
                            preds = []
                            for i in range(h):
                                p = float(self.model.predict(row)[0])
                                preds.append(p)
                                existing_lags = sorted(
                                    [
                                        int(c.replace("lag_", ""))
                                        for c in row.columns
                                        if c.startswith("lag_")
                                    ],
                                    reverse=True,
                                )
                                old_vals = {
                                    lag: row[f"lag_{lag}"].iloc[0]
                                    for lag in existing_lags
                                }
                                for lag in existing_lags:
                                    if lag == 1:
                                        row[f"lag_{lag}"] = p
                                    else:
                                        prev = [x for x in existing_lags if x < lag]
                                        if prev:
                                            row[f"lag_{lag}"] = old_vals.get(
                                                max(prev), p
                                            )
                                for w in [14, 7, 3]:
                                    col = f"ma_{w}"
                                    if col in row.columns:
                                        row[col] = p
                            return np.array(preds)
                        else:
                            feats = self._engineer(horizon_or_valid)
                            X = feats.drop(columns=[self.value_col], errors="ignore")
                            return self.model.predict(X)

                    def _engineer(self, df):
                        df = df.copy()
                        dates = pd.to_datetime(df[self.date_col])
                        df["dow"] = dates.dt.dayofweek
                        df["month"] = dates.dt.month
                        df["quarter"] = dates.dt.quarter
                        df["woy"] = dates.dt.isocalendar().week.astype(int)
                        df["yday"] = dates.dt.dayofyear
                        df["weekend"] = df["dow"].isin([5, 6]).astype(int)
                        for lag in [1, 2, 3, 7, 14, 28]:
                            df[f"lag_{lag}"] = df[self.value_col].shift(lag)
                        for w in [3, 7, 14]:
                            df[f"ma_{w}"] = df[self.value_col].rolling(w).mean()
                        df = df.dropna()
                        df = df.drop(columns=[self.date_col], errors="ignore")
                        return df

                models.append(("LightGBM", lambda: _LightGBMWrapper()))
            except ImportError:
                pass

    # CatBoost
    try:
        from catboost import CatBoostRegressor

        class _CatBoostWrapper:
            def fit(self, df, date_col, value_col, freq):
                self.date_col = date_col
                self.value_col = value_col
                feats = self._engineer(df)
                y = feats[self.value_col]
                X = feats.drop(columns=[self.value_col])
                self.model = CatBoostRegressor(
                    iterations=500,
                    learning_rate=0.05,
                    depth=6,
                    random_seed=42,
                    verbose=0,
                )
                self.model.fit(X, y)
                self.last_feats = X
                return self

            def predict(self, horizon_or_valid):
                if isinstance(horizon_or_valid, int):
                    h = horizon_or_valid
                    row = self.last_feats.iloc[[-1]].copy()
                    preds = []
                    for i in range(h):
                        p = float(self.model.predict(row)[0])
                        preds.append(p)
                        existing_lags = sorted(
                            [
                                int(c.replace("lag_", ""))
                                for c in row.columns
                                if c.startswith("lag_")
                            ],
                            reverse=True,
                        )
                        old_vals = {
                            lag: row[f"lag_{lag}"].iloc[0] for lag in existing_lags
                        }
                        for lag in existing_lags:
                            if lag == 1:
                                row[f"lag_{lag}"] = p
                            else:
                                prev = [x for x in existing_lags if x < lag]
                                if prev:
                                    row[f"lag_{lag}"] = old_vals.get(max(prev), p)
                        for w in [14, 7, 3]:
                            col = f"ma_{w}"
                            if col in row.columns:
                                row[col] = p
                    return np.array(preds)
                else:
                    feats = self._engineer(horizon_or_valid)
                    X = feats.drop(columns=[self.value_col], errors="ignore")
                    return self.model.predict(X)

            def _engineer(self, df):
                df = df.copy()
                dates = pd.to_datetime(df[self.date_col])
                df["dow"] = dates.dt.dayofweek
                df["month"] = dates.dt.month
                df["quarter"] = dates.dt.quarter
                df["woy"] = dates.dt.isocalendar().week.astype(int)
                df["yday"] = dates.dt.dayofyear
                df["weekend"] = df["dow"].isin([5, 6]).astype(int)
                for lag in [1, 2, 3, 7, 14, 28]:
                    df[f"lag_{lag}"] = df[self.value_col].shift(lag)
                for w in [3, 7, 14]:
                    df[f"ma_{w}"] = df[self.value_col].rolling(w).mean()
                df = df.dropna()
                df = df.drop(columns=[self.date_col], errors="ignore")
                return df

        models.append(("CatBoost", lambda: _CatBoostWrapper()))
    except ImportError:
        # Auto-install catboost
        if _auto_install_pkg("catboost"):
            try:
                from catboost import CatBoostRegressor

                class _CatBoostWrapper:
                    def fit(self, df, date_col, value_col, freq):
                        self.date_col = date_col
                        self.value_col = value_col
                        feats = self._engineer(df)
                        y = feats[self.value_col]
                        X = feats.drop(columns=[self.value_col])
                        self.model = CatBoostRegressor(
                            iterations=500,
                            learning_rate=0.05,
                            depth=6,
                            random_seed=42,
                            verbose=0,
                        )
                        self.model.fit(X, y)
                        self.last_feats = X
                        return self

                    def predict(self, horizon_or_valid):
                        if isinstance(horizon_or_valid, int):
                            h = horizon_or_valid
                            row = self.last_feats.iloc[[-1]].copy()
                            preds = []
                            for i in range(h):
                                p = float(self.model.predict(row)[0])
                                preds.append(p)
                                existing_lags = sorted(
                                    [
                                        int(c.replace("lag_", ""))
                                        for c in row.columns
                                        if c.startswith("lag_")
                                    ],
                                    reverse=True,
                                )
                                old_vals = {
                                    lag: row[f"lag_{lag}"].iloc[0]
                                    for lag in existing_lags
                                }
                                for lag in existing_lags:
                                    if lag == 1:
                                        row[f"lag_{lag}"] = p
                                    else:
                                        prev = [x for x in existing_lags if x < lag]
                                        if prev:
                                            row[f"lag_{lag}"] = old_vals.get(
                                                max(prev), p
                                            )
                                for w in [14, 7, 3]:
                                    col = f"ma_{w}"
                                    if col in row.columns:
                                        row[col] = p
                            return np.array(preds)
                        else:
                            feats = self._engineer(horizon_or_valid)
                            X = feats.drop(columns=[self.value_col], errors="ignore")
                            return self.model.predict(X)

                    def _engineer(self, df):
                        df = df.copy()
                        dates = pd.to_datetime(df[self.date_col])
                        df["dow"] = dates.dt.dayofweek
                        df["month"] = dates.dt.month
                        df["quarter"] = dates.dt.quarter
                        df["woy"] = dates.dt.isocalendar().week.astype(int)
                        df["yday"] = dates.dt.dayofyear
                        df["weekend"] = df["dow"].isin([5, 6]).astype(int)
                        for lag in [1, 2, 3, 7, 14, 28]:
                            df[f"lag_{lag}"] = df[self.value_col].shift(lag)
                        for w in [3, 7, 14]:
                            df[f"ma_{w}"] = df[self.value_col].rolling(w).mean()
                        df = df.dropna()
                        df = df.drop(columns=[self.date_col], errors="ignore")
                        return df

                models.append(("CatBoost", lambda: _CatBoostWrapper()))
            except ImportError:
                pass

    # TimesFM (foundation model, priority 4)
    try:
        from timesfm import TimesFM_2p5_200M_torch as _TFMCls

        class _TimesFMWrapper:
            def fit(self, df, date_col, value_col, freq):
                self.value_col = value_col
                self.freq = freq
                vals = df[value_col].values.astype(np.float64)
                self.vals = vals
                try:
                    self.model = _TFMCls.from_pretrained()
                except Exception:
                    self.model = None
                return self

            def predict(self, horizon_or_valid):
                if isinstance(horizon_or_valid, int):
                    h = horizon_or_valid
                else:
                    h = len(horizon_or_valid)
                if self.model is None:
                    return np.full(h, float(self.vals[-1]))
                try:
                    fcst = self.model.forecast(
                        input_context=self.vals,
                        freq=self.freq,
                        horizon=h,
                    )
                    return fcst["mean"].values[:h]
                except Exception:
                    return np.full(h, float(self.vals[-1]))

        models.append(("TimesFM", lambda: _TimesFMWrapper()))
    except Exception:
        pass

    # Chronos
    try:
        import torch
        from chronos import ChronosPipeline

        class _ChronosWrapper:
            def fit(self, df, date_col, value_col, freq):
                self.value_col = value_col
                vals = df[value_col].values.astype(np.float32)
                pipeline = ChronosPipeline.from_pretrained(
                    "amazon/chronos-t5-small",
                    device_map="auto",
                )
                self.pipeline = pipeline
                self.vals = vals
                return self

            def predict(self, horizon_or_valid):
                if isinstance(horizon_or_valid, int):
                    h = horizon_or_valid
                else:
                    h = len(horizon_or_valid)
                try:
                    forecast = self.pipeline.predict(torch.tensor(self.vals), h)
                    return forecast.numpy().flatten()[:h]
                except Exception:
                    return np.full(h, self.vals[-1])

        models.append(("Chronos", lambda: _ChronosWrapper()))
    except (ImportError, OSError):
        # Auto-install chronos
        if _auto_install_pkg("chronos"):
            try:
                import torch
                from chronos import ChronosPipeline

                class _ChronosWrapper:
                    def fit(self, df, date_col, value_col, freq):
                        self.value_col = value_col
                        vals = df[value_col].values.astype(np.float32)
                        pipeline = ChronosPipeline.from_pretrained(
                            "amazon/chronos-t5-small",
                            device_map="auto",
                        )
                        self.pipeline = pipeline
                        self.vals = vals
                        return self

                    def predict(self, horizon_or_valid):
                        if isinstance(horizon_or_valid, int):
                            h = horizon_or_valid
                        else:
                            h = len(horizon_or_valid)
                        try:
                            forecast = self.pipeline.predict(torch.tensor(self.vals), h)
                            return forecast.numpy().flatten()[:h]
                        except Exception:
                            return np.full(h, self.vals[-1])

                models.append(("Chronos", lambda: _ChronosWrapper()))
            except (ImportError, OSError):
                pass

    return models


def _select_best_model(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    date_col: str,
    value_col: str,
    freq: str,
    horizon: int = 1,
) -> tuple[str, Any]:
    """Try all available models and return (best_name, best_model).

    Priority order for auto-selection:
      1. StatsForecast family (AutoARIMA, AutoETS, Theta, MSTL, StatsForecast)
      2. Prophet
      3. TimesFM / Chronos (foundation models)
      4. LightGBM / CatBoost (tree-based, recursive)
      5. Dummy (last-value fallback)

    Within each priority tier, the model with lowest RMSE is selected.
    Higher-priority tiers are tried first; falls to next tier only if all fail.
    Each model evaluation is guarded by _TIMEOUT_SEC."""
    candidates = _get_available_models()
    # Group models by priority tier
    tiers = [
        # Priority 1: statsforecast (statistical, recommended)
        {"AutoARIMA", "AutoETS", "Theta", "MSTL", "StatsForecast"},
        # Priority 2: mlforecast (machine learning, recommended)
        {"LightGBM", "CatBoost"},
        # Priority 3: neuralforecast — TODO
        # Priority 4: timesfm (foundation model, recommended)
        {"TimesFM"},
        # Priority 5: chronos (foundation model, recommended)
        {"Chronos"},
        # Priority 6-10: prophet, statsmodels, pmdarima, darts, sktime — some implemented
        {"Prophet"},
    ]

    for tier in tiers:
        tier_results = []
        tier_names = [n for n, b in candidates if n in tier]
        if not tier_names:
            continue
        for name, builder in candidates:
            if name not in tier:
                continue
            t0 = time.time()
            try:

                def _eval():
                    model = builder().fit(train, date_col, value_col, freq)
                    h = min(len(valid), max(horizon, 1))
                    preds = model.predict(h)
                    actual = valid[value_col].values[:h]
                    if len(preds) < h:
                        preds = np.pad(preds, (0, h - len(preds)), mode="edge")
                    preds = preds[:h]
                    rmse_val = float(np.sqrt(np.mean((preds - actual) ** 2)))
                    elapsed = time.time() - t0
                    return rmse_val, elapsed, name, model

                rmse_val, elapsed, _, model = _run_with_timeout(_eval, _TIMEOUT_SEC)
                tier_results.append((rmse_val, elapsed, name, model))
            except Exception:
                _logger.debug("Forecast model evaluation failed: %s", name, exc_info=True)
                continue
        if tier_results:
            tier_results.sort(key=lambda x: (x[0], x[1]))
            best = tier_results[0]
            return best[2], best[3]  # (best_name, best_model)

    # All tiers failed → Dummy fallback
    for name, builder in candidates:
        if name == "Dummy":
            return name, builder().fit(train, date_col, value_col, freq)

    raise RuntimeError(
        _("error.all_models_failed", default="All models failed or unavailable")
    )


# ── Main run_tool ─────────────────────────────────────────────────────


def run_tool(args: dict[str, Any]) -> str:
    """Execute forecast based on provided arguments."""
    cb = get_callbacks()

    def _execute() -> str:
        nonlocal cb
        data = args["data"]
        date_col = args["date_column"]
        value_col = args["value_column"]
        horizon = int(args["horizon"])
        model_name = args.get("model", "auto")
        freq_arg = args.get("frequency", "auto")
        confidence = float(args.get("confidence", 0.95))
        plot_flag = bool(args.get("plot", False))
        plot_output_dir = args.get("output_dir", None)
        outlier_method = args.get("outlier", "iqr")

        # 2. Load & preprocess
        df = load_data(data)
        df = preprocess(df, date_col, value_col)
        df = _handle_outliers(df, value_col, outlier_method)

        # 3. Frequency
        if freq_arg == "auto":
            freq = _infer_frequency(pd.DatetimeIndex(df[date_col]))
        else:
            freq = freq_arg

        # 4. Model selection / training
        if model_name == "auto":
            train = df.iloc[: -max(horizon, 1)]
            valid = df.iloc[-max(horizon, 1) :]
            if len(train) < _MIN_ROWS:
                train = df
                valid = df.iloc[-min(horizon, len(df) // 2) :]
            best_name, best_model = _select_best_model(
                train, valid, date_col, value_col, freq, horizon
            )
            # Retrain on full data
            best_model = best_model.fit(df, date_col, value_col, freq)
            model_used = best_name
        else:
            candidates = _get_available_models()
            found = False
            for name, builder in candidates:
                if name == model_name:
                    best_model = builder().fit(df, date_col, value_col, freq)
                    model_used = name
                    found = True
                    break
            if not found:
                # Fallback to dummy
                for name, builder in candidates:
                    if name == "Dummy":
                        best_model = builder().fit(df, date_col, value_col, freq)
                        model_used = "Dummy"
                        break

        # 5. Forecast
        forecast_vals = best_model.predict(horizon)
        if len(forecast_vals) < horizon:
            forecast_vals = np.pad(
                forecast_vals, (0, horizon - len(forecast_vals)), mode="edge"
            )
        forecast_vals = forecast_vals[:horizon]

        # 6. Confidence intervals (model-specific dispatch)
        ci_lower, ci_upper = _compute_ci(
            best_model,
            model_used,
            df,
            value_col,
            horizon,
            forecast_vals,
            confidence,
        )

        # 7. Metrics (on training fit)
        last_n = min(len(df), horizon)
        if last_n > 1:
            in_sample = df[value_col].values[-last_n:]
            try:
                in_pred = best_model.predict(last_n)
                if len(in_pred) != last_n:
                    in_pred = np.full(
                        last_n, in_pred[0] if len(in_pred) > 0 else in_sample[0]
                    )
            except Exception:
                in_pred = np.full(last_n, in_sample[-1])
            metrics = _calc_metrics(in_sample, in_pred)
        else:
            metrics = {"mae": 0.0, "rmse": 0.0, "mape": 0.0}

        # 8. Plot
        plot_path = ""
        if plot_flag:
            try:
                import matplotlib

                matplotlib.use("Agg")
                import matplotlib.pyplot as plt

                from ..utils.paths import get_outputs_dir

                if plot_output_dir:
                    plot_dir = plot_output_dir
                else:
                    plot_dir = str(get_outputs_dir() / "forecast_plots")
                os.makedirs(plot_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                plot_path = os.path.join(plot_dir, f"forecast_{ts}.png")

                fig, ax = plt.subplots(figsize=(10, 5))
                ax.plot(df[date_col], df[value_col], label="Actual", color="blue")
                last_date = pd.to_datetime(df[date_col].iloc[-1])
                future_dates = pd.date_range(
                    start=last_date + pd.DateOffset(days=1),
                    periods=horizon,
                    freq=freq if freq in ("D", "h", "W", "MS") else "D",
                )
                ax.plot(future_dates, forecast_vals, label="Forecast", color="red")
                ax.fill_between(
                    future_dates,
                    ci_lower,
                    ci_upper,
                    alpha=0.2,
                    color="red",
                    label=f"{confidence*100:.0f}% CI",
                )
                ax.set_title(f"Forecast ({model_used})")
                ax.legend()
                fig.tight_layout()
                fig.savefig(plot_path, dpi=100)
                plt.close(fig)
                try:
                    from .openers import open_image_with_default_app

                    open_image_with_default_app(os.path.abspath(plot_path))
                except Exception:
                    pass
            except Exception as e:
                plot_path = f"plot_error: {e}"

        # 9. Build result
        result = {
            "best_model": model_used,
            "forecast": [round(float(v), 4) for v in forecast_vals],
            "confidence_interval": {
                "lower": ci_lower,
                "upper": ci_upper,
            },
            "metrics": metrics,
        }
        if plot_path:
            result["plot"] = plot_path
            if os.path.isfile(plot_path):
                attachment: dict[str, Any] = {
                    "type": "image",
                    "mime": "image/png",
                    "name": os.path.basename(plot_path),
                    "path": plot_path,
                }
                if bool(args.get("include_base64", True)):
                    with open(plot_path, "rb") as plot_file:
                        attachment["data_base64"] = base64.b64encode(plot_file.read()).decode("ascii")
                result["attachments"] = [attachment]

        output = json.dumps(result, ensure_ascii=False, default=str)
        if cb.truncate_output:
            return cb.truncate_output("forecast", output, limit=10000)
        return output

    try:
        return _run_with_timeout(_execute, _TIMEOUT_SEC)
    except DataTooSmallError as e:
        return json.dumps(
            {
                "error": _(
                    "error.data_too_small",
                    default="Insufficient data: need at least %(min_rows)d rows, got %(actual)d",
                    min_rows=e.min_rows,
                    actual=e.actual,
                )
            }
        )
    except MissingRateHighError as e:
        return json.dumps(
            {
                "error": _(
                    "error.missing_rate_high",
                    default="Missing rate %.1f%%: cannot forecast",
                    rate=e.rate * 100,
                )
            }
        )
    except TimeoutError:
        return json.dumps(
            {
                "error": _(
                    "error.timeout",
                    default="Forecast timed out (%(seconds)d seconds)",
                    seconds=_TIMEOUT_SEC,
                )
            }
        )
    except Exception:
        _logger.exception("Forecast execution failed")
        return json.dumps(
            {
                "error": _(
                    "error.all_models_failed",
                    default="All models failed or unavailable",
                )
            }
        )
