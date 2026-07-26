

### CSV/DataFrame 入出力詳細

**CSV読込**: `encoding` は `utf-8-sig` → `cp932` → `latin-1` の順で試行し、最初に成功したものを採用。区切り文字は `,` → `\t` の順で試し、列数が1より多い方を採用。

```python
def _read_csv(path: str) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp932", "latin-1"):
        try:
            for sep in (",", "\t"):
                df = pd.read_csv(path, encoding=enc, sep=sep)
                if len(df.columns) > 1:
                    return df
        except Exception:
            continue
    raise ValueError("CSV読込失敗")
```

**DataFrame JSONスキーマ** (data引数にJSON文字列として渡す場合):

```json
{
  "columns": ["date", "value"],
  "data": [
    ["2024-01-01", 100.0],
    ["2024-01-02", 102.5]
  ]
}
```

`load_data()` は文字列がファイルパス（存在するファイル）かJSONかを自動判別する。

**グラフ保存先**: `~/.uag/outputs/forecast_plots/{timestamp}.png` （uagent標準出力構成に準拠）。`output_dir` 引数で任意の保存先を指定可能。戻り値の `"plot"` は相対パス。

### 欠損値処理

| 欠損率 | 方法 |
|--------|------|
| 0% | スキップ |
| 1-20% | 線形補間 (`pandas.interpolate(method='linear')`) |
| 20-50% | 前方補完 (`ffill()`) + 後方補完 (`bfill()`) |
| 50%超 | エラー「欠損率 %.1f%%: 予測不能」 |

日時列に欠損がある行は削除。

### 外れ値処理（オプション）

引数 `outlier`: `"none"` / `"iqr"` / `"zscore"`、既定 `"iqr"`。

- **IQR法**: Q1 - 1.5*IQR 未満、Q3 + 1.5*IQR 超過を中央値で置換
- **Z-score法**: |Z| > 3 の値を中央値で置換。ループで収束するまで繰り返し。

```python
def _replace_outliers_iqr(series: pd.Series) -> pd.Series:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5*iqr, q3 + 1.5*iqr
    median = series.median()
    return series.clip(lo, hi).fillna(median)
```

### frequency自動推測

`pandas.infer_freq()` を実行。失敗時は:

| 試行順 | 方法 |
|--------|------|
| 1 | `pd.infer_freq(index)` |
| 2 | 隣接差の最頻値 → `pd.tseries.frequencies.to_offset()` |
| 3 | デフォルト `"D"` にフォールバック |

戻り値は `pd.DateOffset` 文字列 (`"D"`, `"h"`, `"W"`, `"MS"`, `"QS"`, `"YS"` 等)。

### LightGBM / CatBoost 用特徴量エンジニアリング

モデルが LightGBM または CatBoost の場合のみ実行:

```python
def _engineer_features(df: pd.DataFrame, date_col: str, lags: list[int] = [1, 2, 3, 7, 14, 28]) -> pd.DataFrame:
    df = df.copy()
    for lag in lags:
        df[f"lag_{lag}"] = df["value"].shift(lag)
    for w in [3, 7, 14]:
        df[f"ma_{w}"] = df["value"].rolling(w).mean()
    dates = pd.to_datetime(df[date_col])
    df["dow"] = dates.dt.dayofweek
    df["month"] = dates.dt.month
    df["quarter"] = dates.dt.quarter
    df["woy"] = dates.dt.isocalendar().week.astype(int)
    df["yday"] = dates.dt.dayofyear
    df["weekend"] = df["dow"].isin([5, 6]).astype(int)
    df = df.dropna()
    df = df.select_dtypes(include=["number"])
    return df
```

ターゲット = 元の `value_column`。ラグ特徴の都合上、最初の `max(lags)` 行は欠損になる。

### モデル選択 (auto) の評価方法

1. データを時系列順に分割: 訓練 80% / 検証 20%（時系列CVは行わず単一ホールドアウト）
2. 全利用可能モデルを訓練セットで学習、検証セットで **RMSE** を計算
3. RMSE最小モデルを選択し、全データで再学習 → horizon先まで予測
4. 検証RMSEが同値ならFitting time 短い方を優先

```python
def _select_best_model(train, valid, date_col, value_col, freq):
    candidates = _get_available_models()
    results = []
    for name, builder in candidates:
        t0 = time.time()
        try:
            model = builder().fit(train, date_col, value_col, freq)
            preds = model.predict(valid)
            rmse = np.sqrt(np.mean((preds - valid[value_col])**2))
            elapsed = time.time() - t0
            results.append((rmse, elapsed, name, model))
        except Exception:
            continue
    results.sort(key=lambda x: (x[0], x[1]))
    return results[0][2], results[0][3]
```

### ハイパーパラメータ（固定値）

| モデル | パラメータ |
|--------|-----------|
| AutoARIMA | `seasonal=True`, `stepwise=True`, `approximation=False` |
| AutoETS | `seasonal_periods` をfrequencyから自動設定 |
| Theta | `seasonal_periods` 自動設定 |
| MSTL | `season_length` 自動設定 |
| Prophet | `yearly_seasonality=True`, `weekly_seasonality=True`, `daily_seasonality=False` |
| LightGBM | `n_estimators=500`, `learning_rate=0.05`, `max_depth=6`, `subsample=0.8`, `colsample_bytree=0.8`, `random_state=42` |
| CatBoost | `iterations=500`, `learning_rate=0.05`, `depth=6`, `random_seed=42`, `verbose=0` |
| TimesFM | `backend="auto"`、環境依存で `"pytorch"` または `"jax"` |
| Chronos | `device="auto"`, `num_samples=20`（信頼区間用） |

### 信頼区間の導出方法

| モデル | 方法 |
|--------|------|
| StatsForecast系 | ライブラリ標準の `level=[95]` から `lo-95`, `hi-95` を取得 |
| Prophet | `predict()` の `yhat_lower`, `yhat_upper` |
| LightGBM / CatBoost | Quantile回帰: `alpha=0.025/0.975` の2モデルを別途学習 |
| TimesFM / Chronos | サンプリング (`num_samples`) → パーセンタイル (2.5%, 97.5%) |

```python
def _quantile_models(train, features, target, alpha_low=0.025, alpha_high=0.975):
    import lightgbm as lgb
    params = {"objective": "quantile", "alpha": alpha_low, "n_estimators": 500, "random_state": 42}
    model_low = lgb.LGBMRegressor(**params).fit(features, target)
    params["alpha"] = alpha_high
    model_high = lgb.LGBMRegressor(**params).fit(features, target)
    return model_low, model_high
```

### タイムアウト対策

```python
import concurrent.futures
_TIMEOUT_SEC = 120

def run_forecast_safe(*args, **kwargs):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        fut = pool.submit(run_forecast, *args, **kwargs)
        try:
            return fut.result(timeout=_TIMEOUT_SEC)
        except concurrent.futures.TimeoutError:
            return {"error": f"予測タイムアウト ({_TIMEOUT_SEC}秒)"}
```

モデル選択含めて120秒。超過時はエラー返却。

### ツールジャンル

```python
TOOL_SPEC = {
    "type": "function",
    "tool_genre": "forecast",
    "function": { ... }
}
```

`genre: "forecast"` で独立制御。デフォルトマスクに含める場合は `runtime/__init__.py` に追記。

### テスト方針

```
tests/forecast/
    __init__.py
    test_forecast_tool.py   # run_tool() 結合テスト
    test_preprocess.py      # 前処理ユニットテスト
    test_models.py          # 各モデルのモックテスト
    fixtures/
      sample_ts.csv         # 50行サンプル時系列
      sample_tiny.csv       # 3行（エラーケース）
```

**モック戦略**: モデルライブラリは `unittest.mock.patch` でモック化。`pd.read_csv` は `tmp_path` にテスト用CSVを書いてテスト。`conftest.py` に `@pytest.fixture` でサンプルDataFrame定義。

**テストケース一覧**:

| テスト | 内容 |
|--------|------|
| `test_csv_input` | CSV → forecast正常実行 |
| `test_json_input` | DataFrame JSON → forecast正常実行 |
| `test_auto_model` | model=autoでRMSE最小モデル選択 |
| `test_horizon_1` | horizon=1の極端値 |
| `test_missing_values_20` | 欠損20% → 補完成功 |
| `test_missing_values_60` | 欠損60% → エラー |
| `test_outlier_iqr` | IQR外れ値処理後 中央値置換確認 |
| `test_timeout` | 強制タイムアウト → エラー文字列 |
| `test_data_too_small` | 3行データ → エラー |
| `test_plot_generated` | plot=True → ファイル作成確認 |
| `test_single_ci_bounds` | 信頼区間lower <= forecast <= upper |

### ダミーデータ生成 (テスト用)

```python
def make_dummy_ts(n=100, freq="D", seed=42):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq=freq)
    trend = np.linspace(0, 5, n)
    season = 2 * np.sin(2 * np.pi * np.arange(n) / 7)
    noise = rng.normal(0, 0.5, n)
    values = 100 + trend + season + noise
    return pd.DataFrame({"date": dates, "value": values})
```

`tests/forecast/fixtures/sample_ts.csv` は `make_dummy_ts(50)` で生成。

## i18n (国際化)

### 方式

ツール側はJSONキー方式 (`make_tool_translator(__file__)`)。`forecast_tool.json` に全キーを定義。

### ファイル構成

```
src/uagent/tools/
  forecast_tool.py          # 実装
  forecast_tool.json        # i18n キー定義
  locales/
    forecast_tool/
      ja.json               # 日本語訳
      zh.json               # 中国語訳 (任意)
```

### forecast_tool.json

```json
{
  "en": {
    "tool.forecast.description": "Execute time series forecasting",
    "param.data.description": "CSV file path or DataFrame JSON string",
    "param.date_column.description": "Date/time column name",
    "param.value_column.description": "Target column name for forecasting",
    "param.horizon.description": "Number of forecast periods",
    "param.horizon.minimum_error": "horizon must be at least 1",
    "param.model.description": "Forecast model. auto = automatic selection",
    "param.model.enum_auto": "auto",
    "param.model.enum_statsforecast": "StatsForecast",
    "param.model.enum_autoarima": "AutoARIMA",
    "param.model.enum_autoets": "AutoETS",
    "param.model.enum_theta": "Theta",
    "param.model.enum_mstl": "MSTL",
    "param.model.enum_prophet": "Prophet",
    "param.model.enum_lightgbm": "LightGBM",
    "param.model.enum_catboost": "CatBoost",
    "param.model.enum_timesfm": "TimesFM",
    "param.model.enum_chronos": "Chronos",
    "param.frequency.description": "Frequency. D/H/M or auto",
    "param.confidence.description": "Confidence interval (0-1)",
    "param.plot.description": "Generate plot image",
    "param.outlier.description": "Outlier handling method. none/iqr/zscore",
    "error.data_too_small": "Insufficient data: need at least %(min_rows)d rows, got %(actual)d",
    "error.missing_rate_high": "Missing rate %.1f%%: cannot forecast",
    "error.csv_read_failed": "CSV read failed after trying utf-8-sig, cp932, latin-1",
    "error.all_models_failed": "All models failed or unavailable",
    "error.timeout": "Forecast timed out (%(seconds)d seconds)",
    "info.best_model": "Best model: %(model)s (RMSE=%(rmse).4f)",
    "info.plot_saved": "Plot saved to %(path)s"
  }
}
```

### TOOL_SPEC i18n 適用例

```python
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "forecast",
    "function": {
        "name": "forecast",
        "description": _("tool.forecast.description", default="Execute time series forecasting"),
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "description": _("param.data.description", default="CSV file path or DataFrame JSON"),
                    "type": "string",
                },
                "date_column": {
                    "description": _("param.date_column.description", default="Date/time column name"),
                    "type": "string",
                },
                "value_column": {
                    "description": _("param.value_column.description", default="Target column name"),
                    "type": "string",
                },
                "horizon": {
                    "description": _("param.horizon.description", default="Number of forecast periods"),
                    "type": "integer",
                    "minimum": 1,
                },
                "model": {
                    "description": _("param.model.description", default="Forecast model"),
                    "type": "string",
                    "enum": ["auto", "StatsForecast", "AutoARIMA", "AutoETS",
                             "Theta", "MSTL", "Prophet", "LightGBM", "CatBoost",
                             "TimesFM", "Chronos"],
                },
                "frequency": {
                    "description": _("param.frequency.description", default="Frequency. D/H/M or auto"),
                    "type": "string",
                },
                "confidence": {
                    "description": _("param.confidence.description", default="Confidence interval"),
                    "type": "number",
                },
                "plot": {
                    "description": _("param.plot.description", default="Generate plot image"),
                    "type": "boolean",
                },
                "outlier": {
                    "description": _("param.outlier.description", default="Outlier handling method"),
                    "type": "string",
                    "enum": ["none", "iqr", "zscore"],
                },
            },
            "required": ["data", "date_column", "value_column", "horizon"],
        },
    },
}
```

### run_tool() 内 i18n エラーメッセージ

```python
def run_tool(args: dict) -> str:
    try:
        # ... メイン処理 ...
    except DataTooSmallError as e:
        return json.dumps({"error": _("error.data_too_small", default="Insufficient data",
                                      min_rows=e.min_rows, actual=e.actual)})
    except MissingRateHighError as e:
        return json.dumps({"error": _("error.missing_rate_high", default="Missing rate too high",
                                      rate=e.rate)})
    except TimeoutError:
        return json.dumps({"error": _("error.timeout", default="Forecast timed out",
                                      seconds=_TIMEOUT_SEC)})
    except Exception:
        return json.dumps({"error": _("error.all_models_failed", default="All models failed")})
```

### 翻訳ファイル例: `locales/forecast_tool/ja.json`

```json
{
  "tool.forecast.description": "時系列予測を実行",
  "param.data.description": "CSVファイルパスまたはDataFrame JSON文字列",
  "param.date_column.description": "日時列名",
  "param.value_column.description": "予測対象列名",
  "param.horizon.description": "予測期間数",
  "param.model.description": "使用モデル。auto=自動選択",
  "param.frequency.description": "頻度。D/H/M/auto",
  "param.confidence.description": "信頼区間 (0-1)",
  "param.plot.description": "グラフ画像を生成",
  "param.outlier.description": "外れ値処理。none/iqr/zscore",
  "error.data_too_small": "データ不足: 最低%(min_rows)d行必要、%(actual)d行",
  "error.missing_rate_high": "欠損率 %.1f%%: 予測不能",
  "error.csv_read_failed": "CSV読込失敗 (utf-8-sig/cp932/latin-1)",
  "error.all_models_failed": "全モデル失敗または利用不可",
  "error.timeout": "予測タイムアウト (%(seconds)d秒)",
  "info.best_model": "最良モデル: %(model)s (RMSE=%(rmse).4f)",
  "info.plot_saved": "グラフ保存: %(path)s"
}
```

### i18n チェック

```bash
# 全キーの過不足チェック
python scripts/i18n_tools_check.py forecast_tool

# 翻訳コンパイル（ツール側はJSONなので .mo 不要。ホスト側は必要）
python scripts/compile_locales.py
```

### 注意点

- `make_tool_translator(__file__)` はツール起動時に `forecast_tool.json` を自動ロード
- LLMに渡すdescriptionは英語（default値）のまま。翻訳が必要なのはエラーメッセージと戻り値の説明文
- `enum` の値自体は英語固定（モデル名は固有名詞のため翻訳しない）
- 新規キー追加時は `forecast_tool.json` と全言語のJSONを同時更新

## TDD (テスト駆動開発) プロセス

### 基本フロー

実装は以下のTDDサイクルで進める。1サイクル = 1機能 = 1コミット。

```
RED    → 失敗テストを書く
GREEN  → テストを通す最小実装
REFACTOR → リファクタリング（テストは通ったまま）
COMMIT → `git add -A && git commit -m "feat: xxx"`
```

### 実装順序（テストファースト）

| # | サイクル | テスト | 実装内容 |
|---|---------|--------|----------|
| 1 | `forecast_tool.py` 雛形 | `test_tool_spec_structure` — TOOL_SPEC が正しい構造か | 空の `TOOL_SPEC` + `run_tool()` ダミー |
| 2 | `make_tool_translator` | `test_i18n_keys_exist` — 全キーが JSON にある | `forecast_tool.json` + `ja.json` |
| 3 | CSV読込 | `test_read_csv_utf8`, `test_read_csv_cp932`, `test_read_csv_fail` | `_read_csv()` |
| 4 | DataFrame JSON読込 | `test_read_json_dataframe` | `load_data()` 分岐 |
| 5 | 日時パース | `test_parse_dates_ymd`, `test_parse_dates_iso` | `_parse_date_column()` |
| 6 | frequency推測 | `test_infer_freq_D`, `test_infer_freq_H`, `test_infer_freq_fallback` | `_infer_frequency()` |
| 7 | 欠損値処理 0% | `test_handle_missing_none` | スキップ |
| 8 | 欠損値処理 1-20% | `test_handle_missing_linear` | `pandas.interpolate` |
| 9 | 欠損値処理 20-50% | `test_handle_missing_ffill` | `ffill()+bfill()` |
| 10 | 欠損値処理 50%超 | `test_handle_missing_error` | `raise MissingRateHighError` |
| 11 | 外れ値 IQR | `test_outlier_iqr_replaces` | `_replace_outliers_iqr()` |
| 12 | 外れ値 Z-score | `test_outlier_zscore_replaces` | `_replace_outliers_zscore()` |
| 13 | モデル選択 auto | `test_select_best_model_rmse` | `_select_best_model()` + モック |
| 14 | StatsForecast 系 | `test_statsforecast_forecast` | StatsForecast ラッパー |
| 15 | Prophet | `test_prophet_forecast` | Prophet ラッパー |
| 16 | LightGBM 特徴量 | `test_engineer_features_lag`, `test_engineer_features_calendar` | `_engineer_features()` |
| 17 | LightGBM 予測 | `test_lightgbm_forecast` | LightGBM ラッパー |
| 18 | CatBoost 予測 | `test_catboost_forecast` | CatBoost ラッパー |
| 19 | TimesFM / Chronos | `test_timesfm_forecast`, `test_chronos_forecast` | TimesFM / Chronos ラッパー |
| 20 | 信頼区間 (StatsForecast) | `test_ci_statsforecast` | `_get_ci()` 分岐 |
| 21 | 信頼区間 (Prophet) | `test_ci_prophet` | Prophet CI |
| 22 | 信頼区間 (Quantile) | `test_ci_quantile` | LightGBM quantile 2モデル |
| 23 | 信頼区間 (Sampling) | `test_ci_sampling` | パーセンタイル計算 |
| 24 | グラフ生成 | `test_plot_saves_file` | matplotlib + 保存 |
| 25 | 評価指標 | `test_metrics_mae`, `test_metrics_rmse`, `test_metrics_mape` | `_calc_metrics()` |
| 26 | run_tool 結合 | `test_run_tool_csv_happy_path` | `run_tool()` 全結合 |
| 27 | run_tool エラー: データ不足 | `test_run_tool_data_too_small` | エラーハンドリング |
| 28 | run_tool エラー: タイムアウト | `test_run_tool_timeout` | タイムアウト処理 |
| 29 | run_tool エラー: 全モデル失敗 | `test_run_tool_all_models_fail` | フォールバック |
| 30 | i18n エラーメッセージ | `test_i18n_error_messages_ja` | 日本語メッセージ確認 |

### ルール

- 各サイクル開始前に **RED** のテストを先に書き、失敗確認してから実装
- 1サイクルに複数の実装を詰め込まない。テスト1つ or 関連テストグループだけ
- `tests/forecast/test_xxx.py` はテスト関数ごとに独立。`conftest.py` に共通fixture
- モックは `unittest.mock.patch` で。実依存はCIでのみ使用（ローカルではスキップ）
- 実装完了後: `python -m py_compile src/uagent/tools/forecast_tool.py` で文法チェック
- 全サイクル終了後: `pytest -q tests/forecast/` で全テスト通過確認