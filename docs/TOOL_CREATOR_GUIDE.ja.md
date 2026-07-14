# Tool Creator Guide — 外部ツール作成ガイド

このガイドでは、**uag 本体を変更せずに**独自ツールを追加する方法を説明します。
uag のソースコードに直接ツールを追加したい場合は、別途
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md)
を参照してください。

---

## 目次

1. [ツールの基本構造](#1-ツールの基本構造)
2. [Python ツールの作成](#2-python-ツールの作成)
3. [Rust + Python ツールの作成](#3-rust--python-ツールの作成)
4. [ツール定義 (TOOL_SPEC) リファレンス](#4-ツール定義-tool_spec-リファレンス)
5. [国際化 (i18n)](#5-国際化-i18n)
6. [テストとデバッグ](#6-テストとデバッグ)
7. [参考: 実装例](#7-参考-実装例)

---

## 1. ツールの基本構造

ツールは以下の要素で構成されます。

| 要素 | 必須 | 説明 |
|------|------|------|
| `TOOL_SPEC` | 必須 | ツールの名前、説明、パラメータを定義する辞書 |
| `run_tool(args)` | 必須 | ツールが呼ばれたときに実行される関数。引数は辞書、戻り値は文字列。 |
| i18n JSON | 推奨 | 翻訳用の JSON ファイル（同名。`<name>_tool.json`） |

### 最小限の Python ツール

```python
# my_tool.py
from typing import Any

def run_tool(args: dict[str, Any]) -> str:
    name = args.get("name", "World")
    return f"Hello, {name}!"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "Says hello.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name to greet",
                },
            },
        },
    },
}
```

---

## 2. Python ツールの作成

### 手順

1. **`UAGENT_EXTERNAL_TOOLS_DIRS` 環境変数を設定する**（未設定の場合）

   例:
   ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

   複数のディレクトリを `:`（Linux/macOS）または `;`（Windows）で区切って指定できます。
   `UAGENT_EXTERNAL_TOOLS_DIR`（単数形）も引き続き使用可能です。

2. **Python ファイルを作成する**

   ファイル名は自由ですが、`<name>_tool.py` の命名を推奨します（例: `my_tool.py`）。

3. **必要な要素を実装する**

   - `TOOL_SPEC` 辞書
   - `run_tool(args)` 関数
   - オプションで i18n JSON ファイル

4. **エージェントを再起動する**（または `system_reload` ツールを実行）

### 完全なテンプレート

```python
from __future__ import annotations

from typing import Any

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def run_tool(args: dict[str, Any]) -> str:
    """Execute the tool."""
    input_text = args.get("input", "")
    result = f"Processed: {input_text}"
    return result


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": _(
            "tool.description",
            default="Description of my_tool",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["my_tool", "keyword1"],
        ),
        "x_search_terms_en": ["my_tool", "keyword1"],
        "parameters": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": _("param.input", default="Input text"),
                },
            },
        },
    },
}
```

i18n の詳細は[セクション5](#5-国際化-i18n)を参照してください。

---

## 3. Rust + Python ツールの作成

Rust で実装すると、パフォーマンスが重要な処理（大量データ処理、暗号化、ファイル処理など）に適しています。
uag はビルド済み `.pyd` を直接ロードできるため、**利用者側に `pip install` は不要**です。

### ツール構成

Rust ツールは以下のファイルで構成されます：

```
my_rust_tool/
├── Cargo.toml          # Rust プロジェクト定義
├── pyproject.toml      # maturin ビルド定義（ビルド時のみ必要）
├── src/
│   └── lib.rs          # Rust 実装
└── my_rust_tool.pyd    # ビルド成果物（配布物に同梱）
```

配布時は `_tool.py` ＋ `_tool.json` ＋ `.pyd` の3ファイルを
`UAGENT_EXTERNAL_TOOLS_DIRS` に配置します。

### 手順

#### ステップ 1: Rust プロジェクトを作成する

**Cargo.toml**
```toml
[package]
name = "my_rust_tools"
version = "0.1.0"
edition = "2021"

[lib]
name = "my_rust_tools"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.29", features = ["extension-module", "abi3-py311"] }
```

**pyproject.toml**
```toml
[build-system]
requires = ["maturin>=1.0"]
build-backend = "maturin"]

[project]
name = "my_rust_tools"
version = "0.1.0"
requires-python = ">=3.11"
```

#### ステップ 2: Rust の実装 (src/lib.rs)

```rust
use pyo3::prelude::*;
use std::collections::HashMap;

#[pyfunction(name = "run_my_operation")]
pub fn run(args: HashMap<String, Py<PyAny>>) -> PyResult<String> {
    let py = unsafe { Python::assume_attached() };

    let input: String = args
        .get("input")
        .and_then(|v: &Py<PyAny>| v.bind(py).extract::<String>().ok())
        .unwrap_or_default();

    let result = format!("Rust says: {}", input);
    Ok(result)
}

#[pymodule]
fn my_rust_tools(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(run, m)?)?;
    Ok(())
}
```

**ポイント:**
- `#[pyfunction(name = "run_<name>")]` の形式で関数を公開する
- 戻り値は `PyResult<String>`
- `#[pymodule]` の関数名はクレート名と同じにする（`my_rust_tools`）

#### ステップ 3: ビルド

```bash
cd my_rust_tool
cargo build --release
```

Windows: `target/release/my_rust_tools.dll` を `my_rust_tools.pyd` にリネーム
Linux: `target/release/libmy_rust_tools.so` を `my_rust_tools.so` に
macOS: `target/release/libmy_rust_tools.dylib` を `my_rust_tools.so` に

または maturin を使う場合：
```bash
pip install maturin     # ビルド時にのみ必要
maturin build --release
# target/wheels/*.whl から .pyd/.so を取り出す
```

#### ステップ 4: Python ラッパーを作成

`UAGENT_EXTERNAL_TOOLS_DIRS` のディレクトリに `my_rust_tool.py` を作成します：

```python
from __future__ import annotations

from typing import Any

from uagent.tools.i18n_helper import make_tool_translator
from uagent.tools.rust_helper import load_rust_pyd

_ = make_tool_translator(__file__)

# .pyd を同じディレクトリに置くだけで自動検出
_rust_mod = load_rust_pyd("my_rust_tools")
run_tool = _rust_mod.run_my_operation

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_build": "rust",
    "function": {
        "name": "my_operation",
        "description": _("tool.description", default="My Rust operation"),
        "x_search_terms": _("x_search_terms", default=["my_operation"]),
        "x_search_terms_en": ["my_operation"],
        "parameters": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": _("param.input", default="Input text"),
                },
            },
        },
    },
}
```

**``load_rust_pyd()`` の解決順序:**

1. ラッパー `.py` と同じディレクトリにある `<module_name>.pyd`（/`.so`）を探す
2. 見つからなければ pip インストールされたモジュールにフォールバック

#### ステップ 5: 配布

配布物は以下の3ファイルのみです。利用者に追加の `pip install` は不要です。

```
my_rust_tool.py         # Python ラッパー（TOOL_SPEC + run_tool）
my_rust_tool.json       # i18n 翻訳（省略可）
my_rust_tools.pyd       # ビルド済みネイティブバイナリ
```

### 注意点

- **ビルド時のみ** Rust ツールチェーンと `maturin` が必要です
  ```bash
  pip install maturin
  ```
- Rust クレート名（`Cargo.toml` の `[lib] name`）と `load_rust_pyd()` の第一引数は一致させる必要があります
- ラッパーファイル名と `.pyd` の配置場所は同じディレクトリであれば自由です

---

## 4. ツール定義 (TOOL_SPEC) リファレンス

### 基本構造

```python
TOOL_SPEC: dict[str, Any] = {
    "type": "function",                     # 固定
    "x_build": "rust",                      # Rust 実装の場合のみ指定
    "tool_genre": "utility",                # ジャンル（省略可）
    "tool_level": 0,                        # 0=有効, 1=条件付き, -1=無効
    "function": {
        "name": "tool_name",                # ツール名（英小文字+数字+アンダースコア）
        "description": "...",               # 説明文
        "x_search_terms": [...],            # 検索キーワード（i18n対応）
        "x_search_terms_en": [...],         # 英語検索キーワード（固定）
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "...",
                },
                "param2": {
                    "type": "integer",
                    "description": "...",
                    "enum": [1, 2, 3],
                },
            },
            "required": ["param1"],
        },
    },
}
```

### プロパティ一覧

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `type` | str | 常に `"function"` |
| `x_build` | str | Rust実装の場合 `"rust"`（Pythonは省略可） |
| `tool_genre` | str | ジャンル名（省略可）。設定するとジャンル制御で管理可能に |
| `tool_level` | int | 0=有効, 1=条件付き（デフォルト）, -1=無効 |
| `function.name` | str | **必須**。ツール名（英小文字+数字+アンダースコア） |
| `function.description` | str | **必須**。説明文 |
| `function.x_search_terms` | list[str] | i18n対応検索キーワード（翻訳ツールの `_(...)` で囲む） |
| `function.x_search_terms_en` | list[str] | 英語固定の検索キーワード |
| `function.parameters` | dict | パラメータ定義（OpenAI function calling 形式） |

---

## 5. 国際化 (i18n)

### 翻訳のメカニズム

`make_tool_translator(__file__)` を呼ぶと、同じディレクトリにある同名の `.json` ファイルから翻訳を読み込みます。

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### 翻訳キーの使い方

```python
description = _(
    "tool.description",                          # キー名
    default="Default English text",              # フォールバック値
)
```

### JSON ファイルの形式

```json
{
    "en": {
        "tool.description": "Default English text",
        "param.input": "Input text"
    },
    "ja": {
        "tool.description": "日本語の説明文",
        "param.input": "入力テキスト"
    }
}
```

対応言語のコード一覧は既存の `_tool.json` ファイルを参照してください。

---

## 6. テストとデバッグ

### 構文チェック

```bash
python -m py_compile my_tool.py
```

### ツールがロードされているか確認

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### エラーログ

ツールロード時のエラーは標準エラー出力に出力されます。ツールがロードされない場合は、
`uag` の起動ログを確認してください。

---

## 7. 参考: 実装例

### 外部 Python ツールの例

- `date_calc_tool.py`（`src/uagent/tools/`）— 日付計算。外部にコピーしてカスタマイズ可能
- `calculator_tool.py`（`src/uagent/tools/`）— 電卓ツール

### 外部 Rust ツールの例

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd`（`src/uagent/tools_rust/`）— UUID生成
- `rust_slugify_tool.py` + `uag_tools_rust.pyd`（`src/uagent/tools_rust/`）— スラグ変換

これらの `_tool.py` と `.pyd` を `UAGENT_EXTERNAL_TOOLS_DIRS` にコピーするだけで
外部ツールとして利用できます。

### 外部ツールディレクトリの設定

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

複数のディレクトリを `:`（Linux/macOS）または `;`（Windows）で区切って指定できます。
後方互換性のため `UAGENT_EXTERNAL_TOOLS_DIR`（単数形）も使用可能です。
