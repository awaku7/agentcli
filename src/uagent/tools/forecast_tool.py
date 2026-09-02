"""forecast_tool.py — Time series forecasting via LLM Function Calling."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Callable

from .i18n_helper import make_tool_translator
from .context import get_callbacks
from .._pip_auto import install_with_status as _auto_install_pkg

_ = make_tool_translator(__file__)
_logger = logging.getLogger(__name__)


def _ensure_forecast_dependencies() -> None:
    """Load forecasting data dependencies only when the tool is executed."""
    global np, pd
    if "np" in globals() and "pd" in globals():
        return

    if not _auto_install_pkg("numpy", "numpy"):
        raise ModuleNotFoundError("No module named 'numpy'")
    if not _auto_install_pkg("pandas", "pandas"):
        raise ModuleNotFoundError("No module named 'pandas'")

    import numpy as np
    import pandas as pd


def _disable_huggingface_ssl_verification() -> None:
    """Use an insecure HF client for an explicitly requested model download.

    This is intentionally opt-in because it disables certificate validation for
    Hugging Face traffic in the current process.
    """
    import httpx
    from huggingface_hub.utils._http import hf_request_event_hook, set_client_factory

    set_client_factory(
        lambda: httpx.Client(
            event_hooks={"request": [hf_request_event_hook]},
            follow_redirects=True,
            timeout=None,
            verify=False,
        )
    )


def _restore_huggingface_ssl_verification() -> None:
    """Restore Hugging Face's default verified HTTP client."""
    from huggingface_hub.utils._http import default_client_factory, set_client_factory

    set_client_factory(default_client_factory)


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


class ModelUnavailableError(ValueError):
    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(
            f"{model_name} is unavailable; install the current timesfm[torch] package"
        )


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
                "target_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.target_columns.description",
                        default="Optional additional target columns for TimesFM-3 native multivariate forecasting. The primary value_column is included automatically.",
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
                        "LinearRegression",
                        "Ridge",
                        "Lasso",
                        "TimesFM",
                        "TimesFM-3",
                        "Chronos",
                    ],
                    "description": _(
                        "param.model.description",
                        default="Forecast model. TimesFM-3 uses the TimesFM 3.0 checkpoint (google/timesfm-3.0-pytorch). auto = automatic selection from available models; LinearRegression/Ridge/Lasso use explanatory variables and future_data for multiple regression.",
                    ),
                },
                "insecure_ssl": {
                    "type": "boolean",
                    "description": _(
                        "param.insecure_ssl.description",
                        default="Disable TLS certificate verification for the TimesFM-3 Hugging Face download (unsafe; opt-in only).",
                    ),
                    "default": False,
                },
                "frequency": {
                    "type": "string",
                    "description": _(
                        "param.frequency.description",
                        default="Frequency: D=daily, H=hourly, M=monthly, W=weekly, auto=infer",
                    ),
                },
                "feature_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.feature_columns.description",
                        default="Explanatory variable columns for regression models. If omitted, use all numeric columns except the date and target columns.",
                    ),
                },
                "future_data": {
                    "type": "string",
                    "description": _(
                        "param.future_data.description",
                        default="CSV path or DataFrame JSON containing future dates and explanatory variables for regression models.",
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
                    "description": _(
                        "param.include_base64.description",
                        default="Include the forecast plot as base64 for remote clients.",
                    ),
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
                "rolling_evaluation": {
                    "type": "boolean",
                    "description": _(
                        "param.rolling_evaluation.description",
                        default="Evaluate forecasts with rolling-origin validation.",
                    ),
                    "default": True,
                },
                "rolling_folds": {
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 10,
                    "description": _(
                        "param.rolling_folds.description",
                        default="Number of rolling-origin validation folds.",
                    ),
                    "default": 3,
                },
                "drift_window": {
                    "type": "integer",
                    "minimum": 3,
                    "description": _(
                        "param.drift_window.description",
                        default="Recent observations used for distribution-drift diagnostics.",
                    ),
                    "default": 10,
                },
                "conformal": {
                    "type": "boolean",
                    "description": _(
                        "param.conformal.description",
                        default="Calibrate prediction intervals from rolling residuals.",
                    ),
                    "default": True,
                },
            },
            "required": ["data", "date_column", "value_column", "horizon"],
        },
    },
}


# ── CSV / JSON Loading ────────────────────────────────────────────────


def _read_csv(path: str) -> pd.DataFrame:
    """Read CSV with auto-detection of encoding and separator."""
    _ensure_forecast_dependencies()
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
    _ensure_forecast_dependencies()
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
    _ensure_forecast_dependencies()
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


def _rolling_diagnostics(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    freq: str,
    model_name: str,
    horizon: int,
    folds: int,
) -> tuple[dict[str, float], np.ndarray]:
    """Evaluate a model family with chronological rolling origins."""
    builder = dict(_get_available_models()).get(model_name)
    if builder is None:
        return {}, np.asarray([], dtype=float)
    step = max(1, horizon)
    min_train = max(_MIN_ROWS, step * 2)
    origins = list(range(min_train, len(df) - step + 1, step))[-max(2, folds) :]
    actuals: list[float] = []
    predictions: list[float] = []
    for origin in origins:
        try:
            model = builder().fit(df.iloc[:origin], date_col, value_col, freq)
            pred = np.asarray(model.predict(step), dtype=float).reshape(-1)[:step]
            if len(pred) < step:
                pred = np.pad(pred, (0, step - len(pred)), mode="edge")
            actual = df[value_col].to_numpy(dtype=float)[origin : origin + step]
            actuals.extend(actual.tolist())
            predictions.extend(pred.tolist())
        except Exception:
            _logger.debug("Rolling evaluation failed: %s", model_name, exc_info=True)
    if not actuals:
        return {}, np.asarray([], dtype=float)
    y_true = np.asarray(actuals)
    y_pred = np.asarray(predictions)
    return _calc_metrics(y_true, y_pred), np.abs(y_true - y_pred)


def _drift_diagnostics(values: np.ndarray, window: int) -> dict[str, Any]:
    """Detect a level or scale shift without assuming a distribution."""
    window = max(3, min(int(window), len(values) // 2))
    if len(values) < window * 2:
        return {"detected": False, "reason": "insufficient_window"}
    recent = values[-window:]
    reference = values[-2 * window : -window]
    ref_mean = float(np.mean(reference))
    ref_std = float(np.std(reference))
    recent_mean = float(np.mean(recent))
    recent_std = float(np.std(recent))
    scale = max(ref_std, float(np.std(values)) * 0.01, 1e-12)
    mean_shift = abs(recent_mean - ref_mean) / scale
    std_ratio = recent_std / max(ref_std, 1e-12)
    return {
        "detected": bool(mean_shift >= 2.0 or std_ratio >= 2.0 or std_ratio <= 0.5),
        "window": window,
        "reference_mean": round(ref_mean, 6),
        "recent_mean": round(recent_mean, 6),
        "reference_std": round(ref_std, 6),
        "recent_std": round(recent_std, 6),
        "standardized_mean_shift": round(float(mean_shift), 6),
        "std_ratio": round(float(std_ratio), 6),
    }


def _conformal_interval(
    forecast: np.ndarray, residuals: np.ndarray, confidence: float
) -> tuple[list[float], list[float]]:
    """Calibrate a symmetric interval from held-out absolute residuals."""
    if residuals.size == 0:
        return [], []
    alpha = max(0.0, min(1.0, 1.0 - confidence))
    width = float(np.quantile(residuals, min(1.0, 1.0 - alpha)))
    return (
        [round(float(v - width), 4) for v in forecast],
        [round(float(v + width), 4) for v in forecast],
    )


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


def _get_ci_timesfm3(
    model, forecast_horizon: int, confidence: float
) -> tuple[list[float], list[float]]:
    """Approximate requested bounds from TimesFM-3's q10..q90 output."""
    quantiles = getattr(model, "last_quantiles", None)
    if quantiles is None:
        return [], []
    arr = np.asarray(quantiles, dtype=float)
    if arr.ndim == 3:
        arr = arr[0]
    if arr.ndim != 2 or arr.shape[0] < forecast_horizon or arr.shape[1] < 9:
        return [], []
    median = arr[:forecast_horizon, 4]
    low_width = median - arr[:forecast_horizon, 0]
    high_width = arr[:forecast_horizon, 8] - median
    # TimesFM-3 exposes q10..q90. Extrapolate symmetrically when a wider
    # interval (for example 95%) is requested.
    tail = max(0.0, (1.0 - confidence) / 2.0)
    scale = (0.5 - tail) / 0.4 if tail < 0.5 else 1.0
    lower = median - low_width * scale
    upper = median + high_width * scale
    return (
        [round(float(v), 4) for v in lower],
        [round(float(v), 4) for v in upper],
    )


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
    if model_name == "TimesFM-3":
        lo, hi = _get_ci_timesfm3(model, forecast_horizon, confidence)
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


def _run_regression_forecast(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    horizon: int,
    model_name: str,
    feature_columns: list[str] | None,
    future_data: str | None,
    confidence: float,
) -> tuple[np.ndarray, list[float], list[float], dict[str, float], dict[str, Any]]:
    """Run a supervised regression forecast with explicit future regressors."""
    try:
        from sklearn.linear_model import Lasso, LinearRegression, Ridge
        from sklearn.metrics import r2_score
    except ImportError:
        if not _auto_install_pkg("scikit-learn"):
            raise ValueError("scikit-learn is required for regression models")
        from sklearn.linear_model import Lasso, LinearRegression, Ridge
        from sklearn.metrics import r2_score

    if feature_columns is None or not feature_columns:
        feature_columns = [
            c for c in df.select_dtypes(include=[np.number]).columns if c != value_col
        ]
    if not feature_columns:
        raise ValueError("Regression models require numeric feature_columns")
    missing = [c for c in feature_columns if c not in df.columns]
    if missing:
        raise ValueError(f"Feature columns not found: {', '.join(missing)}")
    if not future_data:
        raise ValueError("future_data is required for regression forecasts")

    train = (
        df[feature_columns + [value_col]].apply(pd.to_numeric, errors="coerce").dropna()
    )
    if len(train) < _MIN_ROWS:
        raise DataTooSmallError(_MIN_ROWS, len(train))
    future = load_data(future_data)
    if date_col not in future.columns:
        raise ValueError(f"Future data is missing date column '{date_col}'")
    _parse_date_column(future, date_col)
    missing_future = [c for c in feature_columns if c not in future.columns]
    if missing_future:
        raise ValueError(
            f"Future data is missing feature columns: {', '.join(missing_future)}"
        )
    future = future.sort_values(date_col).reset_index(drop=True).head(horizon)
    if len(future) < horizon:
        raise ValueError(f"Future data needs at least {horizon} rows")
    x_future = future[feature_columns].apply(pd.to_numeric, errors="coerce")
    if x_future.isna().any().any():
        raise ValueError(
            "Future feature columns must contain numeric, non-missing values"
        )

    estimators = {
        "LinearRegression": LinearRegression(),
        "Ridge": Ridge(alpha=1.0),
        "Lasso": Lasso(alpha=0.001, max_iter=10000),
    }
    estimator = estimators[model_name]
    x_train = train[feature_columns]
    y_train = train[value_col]
    estimator.fit(x_train, y_train)
    predictions = np.asarray(estimator.predict(x_future), dtype=float)[:horizon]
    fitted = np.asarray(estimator.predict(x_train), dtype=float)
    residual_std = (
        float(np.std(y_train.to_numpy() - fitted, ddof=1)) if len(train) > 2 else 0.0
    )
    if not np.isfinite(residual_std) or residual_std <= 0:
        residual_std = float(np.std(y_train.to_numpy(), ddof=1) * 0.05) or 1.0
    from statistics import NormalDist

    z = NormalDist().inv_cdf((1.0 + max(0.0, min(1.0, confidence))) / 2.0)
    lower = [round(float(v - z * residual_std), 4) for v in predictions]
    upper = [round(float(v + z * residual_std), 4) for v in predictions]
    coefficients = {
        name: round(float(coef), 6)
        for name, coef in zip(feature_columns, np.asarray(estimator.coef_).ravel())
    }
    diagnostics = {
        "coefficients": coefficients,
        "intercept": round(float(estimator.intercept_), 6),
        "r2": round(float(r2_score(y_train, fitted)), 6),
        "feature_columns": feature_columns,
    }
    return (
        predictions,
        lower,
        upper,
        _calc_metrics(y_train.to_numpy(), fitted),
        diagnostics,
    )


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


def _get_available_models(
    requested_model: str | None = None,
) -> list[tuple[str, Callable]]:
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
        if requested_model in {
            "StatsForecast",
            "AutoARIMA",
            "AutoETS",
            "Theta",
            "MSTL",
        } and _auto_install_pkg("statsforecast"):
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
        if requested_model == "Prophet" and _auto_install_pkg("prophet"):
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
        if requested_model == "LightGBM" and _auto_install_pkg("lightgbm"):
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
        if requested_model == "CatBoost" and _auto_install_pkg("catboost"):
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

    # TimesFM 2.5 (legacy univariate foundation model)
    try:
        from timesfm import TimesFM_2p5_200M_torch as _TFMCls

        try:
            from timesfm import ForecastConfig as _TFMForecastConfig
        except ImportError:
            _TFMForecastConfig = None

        class _TimesFMWrapper:
            def fit(self, df, date_col, value_col, freq):
                self.value_col = value_col
                self.freq = freq
                self.vals = df[value_col].values.astype(np.float32)
                try:
                    self.model = _TFMCls.from_pretrained(
                        "google/timesfm-2.5-200m-pytorch"
                    )
                    self._compiled_max_horizon = 0
                except Exception:
                    self.model = None
                return self

            def _compile(self, horizon: int) -> None:
                if self.model is None or _TFMForecastConfig is None:
                    return
                if horizon <= self._compiled_max_horizon:
                    return
                self.model.compile(
                    _TFMForecastConfig(
                        max_context=len(self.vals),
                        max_horizon=horizon,
                        per_core_batch_size=1,
                    )
                )
                self._compiled_max_horizon = horizon

            def predict(self, horizon_or_valid):
                h = (
                    horizon_or_valid
                    if isinstance(horizon_or_valid, int)
                    else len(horizon_or_valid)
                )
                if self.model is None:
                    return np.full(h, float(self.vals[-1]))
                try:
                    # Current timesfm distributions use this newer API;
                    # retain the older API for older timesfm installations.
                    if _TFMForecastConfig is not None:
                        self._compile(h)
                        point_forecast, _ = self.model.forecast(
                            horizon=h,
                            inputs=[self.vals],
                        )
                        return np.asarray(point_forecast).reshape(-1)[:h]
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

    # TimesFM 3.0 (native univariate/multivariate foundation model)
    # The current timesfm distribution exposes this implementation as the
    # separate ``timesfm3`` module while keeping the package distribution name.
    try:
        from timesfm3 import ModelConfig as _TFM3Config
        from timesfm3 import TimesFM3Evaluator as _TFM3Evaluator
    except ImportError:
        _TFM3Config = None
        _TFM3Evaluator = None
    except Exception:
        _TFM3Config = None
        _TFM3Evaluator = None

    if _TFM3Config is not None and _TFM3Evaluator is not None:

        class _TimesFM3Wrapper:
            def fit(
                self,
                df,
                date_col,
                value_col,
                freq,
                target_columns: list[str] | None = None,
            ):
                self.value_col = value_col
                self.freq = freq
                self.target_columns = target_columns or [value_col]
                self.vals = np.stack(
                    [
                        df[column].values.astype(np.float32)
                        for column in self.target_columns
                    ]
                )
                if len(self.target_columns) == 1:
                    self.vals = self.vals[0]
                self.last_multivariate_forecast = None
                self.last_quantiles = None
                try:
                    import torch

                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except Exception:
                    device = "cpu"
                config = _TFM3Config(
                    checkpoint_path="google/timesfm-3.0-pytorch",
                    per_core_batch_size=1,
                    device=device,
                )
                self.model = _TFM3Evaluator(config)
                return self

            def predict(self, horizon_or_valid):
                h = (
                    horizon_or_valid
                    if isinstance(horizon_or_valid, int)
                    else len(horizon_or_valid)
                )
                outputs = list(
                    self.model.predict_batch(
                        [self.vals],
                        horizon=h,
                        return_quantiles=True,
                        use_symmetric_averaging=False,
                    )
                )
                if not outputs:
                    raise RuntimeError("TimesFM-3 returned no forecast")
                forecast = getattr(outputs[0], "forecast", outputs[0])
                self.last_quantiles = getattr(outputs[0], "quantiles", None)
                if isinstance(forecast, dict):
                    forecast = forecast.get("mean", forecast)
                forecast_array = np.asarray(forecast, dtype=float)
                if len(self.target_columns) == 1:
                    self.last_multivariate_forecast = None
                    return forecast_array.reshape(-1)[:h]
                if forecast_array.ndim != 2:
                    raise RuntimeError(
                        "TimesFM-3 returned an invalid multivariate shape"
                    )
                self.last_multivariate_forecast = forecast_array[..., :h]
                return forecast_array[0, :h]

        models.append(("TimesFM-3", lambda: _TimesFM3Wrapper()))

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
        # The correct package is chronos-forecasting; the unrelated `chronos`
        # package does not provide ChronosPipeline.
        if requested_model == "Chronos" and _auto_install_pkg("chronos-forecasting"):
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
    _ensure_forecast_dependencies()
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

                rmse_val, elapsed, _model_name, model = _run_with_timeout(
                    _eval, _TIMEOUT_SEC
                )
                tier_results.append((rmse_val, elapsed, name, model))
            except Exception:
                _logger.debug(
                    "Forecast model evaluation failed: %s", name, exc_info=True
                )
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
    _ensure_forecast_dependencies()
    cb = get_callbacks()
    insecure_ssl_requested = args.get("model", "auto") == "TimesFM-3" and (
        args.get("insecure_ssl") is True
        or os.getenv("UAGENT_TIMESFM_INSECURE_SSL", "").lower()
        in {"1", "true", "yes", "on"}
    )

    def _execute() -> str:
        nonlocal cb
        data = args["data"]
        date_col = args["date_column"]
        value_col = args["value_column"]
        horizon = int(args["horizon"])
        model_name = args.get("model", "auto")
        requested_targets = args.get("target_columns") or []
        if not isinstance(requested_targets, list) or any(
            not isinstance(column, str) or not column.strip()
            for column in requested_targets
        ):
            raise ValueError("target_columns must be a list of column names")
        target_columns = [value_col]
        for column in requested_targets:
            if column not in target_columns:
                target_columns.append(column)
        if model_name != "TimesFM-3":
            target_columns = [value_col]
        insecure_ssl = args.get("insecure_ssl") is True or os.getenv(
            "UAGENT_TIMESFM_INSECURE_SSL", ""
        ).lower() in {"1", "true", "yes", "on"}
        if model_name == "TimesFM-3" and insecure_ssl:
            _disable_huggingface_ssl_verification()
        freq_arg = args.get("frequency", "auto")
        confidence = float(args.get("confidence", 0.95))
        plot_flag = bool(args.get("plot", False))
        plot_output_dir = args.get("output_dir", None)
        outlier_method = args.get("outlier", "iqr")
        rolling_enabled = bool(args.get("rolling_evaluation", True))
        rolling_folds = max(2, min(int(args.get("rolling_folds", 3)), 10))
        drift_window = max(3, int(args.get("drift_window", 10)))
        conformal_enabled = bool(args.get("conformal", True))

        # 2. Load & preprocess
        df = load_data(data)
        df = preprocess(df, date_col, value_col)
        df = _handle_outliers(df, value_col, outlier_method)
        if len(target_columns) > 1:
            missing_columns = [column for column in target_columns if column not in df]
            if missing_columns:
                raise ValueError(
                    "TimesFM-3 target columns not found: " + ", ".join(missing_columns)
                )
            for column in target_columns[1:]:
                if not pd.api.types.is_numeric_dtype(df[column]):
                    raise ValueError(
                        f"TimesFM-3 target column is not numeric: {column}"
                    )
                df = _handle_missing(df, column)
                df = _handle_outliers(df, column, outlier_method)

        # 3. Frequency
        if freq_arg == "auto":
            freq = _infer_frequency(pd.DatetimeIndex(df[date_col]))
        else:
            freq = freq_arg

        def _fit_selected_model(builder):
            if model_name == "TimesFM-3" and len(target_columns) > 1:
                return builder().fit(
                    df,
                    date_col,
                    value_col,
                    freq,
                    target_columns=target_columns,
                )
            return builder().fit(df, date_col, value_col, freq)

        # 4. Explicit regression with future explanatory variables
        if model_name in {"LinearRegression", "Ridge", "Lasso"}:
            forecast_vals, ci_lower, ci_upper, metrics, diagnostics = (
                _run_regression_forecast(
                    df,
                    date_col,
                    value_col,
                    horizon,
                    model_name,
                    args.get("feature_columns"),
                    args.get("future_data"),
                    confidence,
                )
            )
            result = {
                "best_model": model_name,
                "forecast": [round(float(v), 4) for v in forecast_vals],
                "confidence_interval": {"lower": ci_lower, "upper": ci_upper},
                "metrics": metrics,
                "regression": diagnostics,
            }
            return json.dumps(result, ensure_ascii=False, default=str)

        # 5. Model selection / training
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
            candidates = _get_available_models(
                model_name if model_name != "auto" else None
            )
            found = False
            for name, builder in candidates:
                if name == model_name:
                    best_model = _fit_selected_model(builder)
                    model_used = name
                    found = True
                    break
            if not found and model_name == "TimesFM-3":
                if _auto_install_pkg(
                    "timesfm[torch]",
                    module_name="timesfm3",
                    display_name="TimesFM 3",
                ):
                    candidates = _get_available_models(model_name)
                    for name, builder in candidates:
                        if name == model_name:
                            best_model = _fit_selected_model(builder)
                            model_used = name
                            found = True
                            break
            if not found:
                if model_name == "TimesFM-3":
                    raise ModelUnavailableError(model_name)
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
        multivariate_forecast = getattr(best_model, "last_multivariate_forecast", None)
        if multivariate_forecast is not None:
            multivariate_forecast = np.asarray(
                multivariate_forecast, dtype=float
            ).copy()

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

        rolling_metrics: dict[str, float] = {}
        rolling_residuals = np.asarray([], dtype=float)
        if rolling_enabled:
            rolling_metrics, rolling_residuals = _rolling_diagnostics(
                df,
                date_col,
                value_col,
                freq,
                model_used,
                horizon,
                rolling_folds,
            )
        if conformal_enabled and rolling_residuals.size:
            conformal_lower, conformal_upper = _conformal_interval(
                np.asarray(forecast_vals, dtype=float), rolling_residuals, confidence
            )
            if conformal_lower and conformal_upper:
                ci_lower, ci_upper = conformal_lower, conformal_upper
        drift = _drift_diagnostics(df[value_col].to_numpy(dtype=float), drift_window)

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
            "rolling_metrics": rolling_metrics,
            "interval_diagnostics": {
                "method": (
                    "rolling_conformal" if rolling_residuals.size else "model_default"
                ),
                "calibration_residuals": int(rolling_residuals.size),
                "nominal_confidence": confidence,
                "mean_width": (
                    round(
                        float(np.mean(np.asarray(ci_upper) - np.asarray(ci_lower))), 4
                    )
                    if ci_upper and ci_lower
                    else 0.0
                ),
                "empirical_calibration_coverage": (
                    round(
                        float(
                            np.mean(
                                rolling_residuals
                                <= float(
                                    np.mean(
                                        np.asarray(ci_upper)
                                        - np.asarray(forecast_vals, dtype=float)
                                    )
                                )
                            )
                        ),
                        4,
                    )
                    if rolling_residuals.size and ci_upper
                    else None
                ),
            },
            "drift": drift,
        }
        if multivariate_forecast is not None:
            result["multivariate_forecast"] = {
                column: [round(float(value), 4) for value in values]
                for column, values in zip(target_columns, multivariate_forecast)
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
                        attachment["data_base64"] = base64.b64encode(
                            plot_file.read()
                        ).decode("ascii")
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
    except ModelUnavailableError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
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
    finally:
        if insecure_ssl_requested:
            try:
                _restore_huggingface_ssl_verification()
            except Exception:
                _logger.debug(
                    "Could not restore Hugging Face SSL verification", exc_info=True
                )
