"""Shared fixtures for forecast tool tests."""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
import pytest


def make_dummy_ts(n: int = 50, freq: str = "D", seed: int = 42) -> pd.DataFrame:
    """Generate dummy time series for testing."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq=freq)
    trend = np.linspace(0, 5, n)
    season = 2 * np.sin(2 * np.pi * np.arange(n) / 7)
    noise = rng.normal(0, 0.5, n)
    values = 100 + trend + season + noise
    return pd.DataFrame({"date": dates, "value": values})


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """50-row daily time series."""
    return make_dummy_ts(50)


@pytest.fixture
def tiny_df() -> pd.DataFrame:
    """3-row DataFrame (too small for forecasting)."""
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=3, freq="D"),
        "value": [100.0, 102.0, 101.0],
    })


@pytest.fixture
def sample_csv_path(tmp_path, sample_df) -> str:
    """Write sample_df to a temp CSV and return path."""
    path = tmp_path / "sample.csv"
    sample_df.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


@pytest.fixture
def sample_json_str(sample_df) -> str:
    """Return sample_df as JSON string in the expected schema."""
    return sample_df.to_json(orient="split", index=False)


@pytest.fixture
def missing_df() -> pd.DataFrame:
    """Daily series with 20% missing values."""
    df = make_dummy_ts(50)
    rng = np.random.default_rng(99)
    missing_idx = rng.choice(df.index, size=10, replace=False)
    df.loc[missing_idx, "value"] = np.nan
    return df


@pytest.fixture
def high_missing_df() -> pd.DataFrame:
    """Daily series with 60% missing values."""
    df = make_dummy_ts(50)
    rng = np.random.default_rng(99)
    missing_idx = rng.choice(df.index, size=30, replace=False)
    df.loc[missing_idx, "value"] = np.nan
    return df


@pytest.fixture
def outlier_df() -> pd.DataFrame:
    """Series with obvious outliers."""
    df = make_dummy_ts(50)
    df.loc[10, "value"] = 200.0   # outlier high
    df.loc[25, "value"] = 10.0    # outlier low
    return df
