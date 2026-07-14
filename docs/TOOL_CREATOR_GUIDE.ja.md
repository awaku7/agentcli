# ツール作成者ガイド

このガイドでは、**uag 自体を変更することなく**、独自のツールを uag に追加する方法について説明します。
ツールを uag ソース ツリーに直接追加する場合は、 
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md)を参照してください。

---

## 目次
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [基本ツール構造](#1-基本ツール構造)
2. [Python ツールの作成](#2-creating-a-python-tool)
3. [Rust + Python ツールの作成](#3-creating-a-rust--python-tool)
4. [TOOL_SPEC リファレンス](#4-tool_spec-reference)
5. [国際化 (i18n)](#5-国際化-i18n)
6. [テストとデバッグ](#6-テストとデバッグ)
7. [参考例](#7-参考例)

---

## 0. Quick Start: Scaffold Command

The easiest way to create a new tool is to use the **`:tool create`** command
from the CLI prompt. It generates the boilerplate files automatically.

### Usage

```
:tool create <name> --lang python|rust [--description '...'] [--output-dir <dir>]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `<name>` | Yes | Tool name (e.g., `my_search`, `file_processor`) |
| `--lang` | No | `python` (default) or `rust` |
| `--description` | No | Short description of the tool |
| `--output-dir` | No | Output directory (default: first path in `UAGENT_EXTERNAL_TOOLS_DIRS`, or current directory) |

### Examples

```text
# Python tool
:tool create my_search --lang python --description "Custom search tool"

# Rust tool
:tool create heavy_processor --lang rust --description "Heavy data processor"
```

### What Gets Generated

**Python (`--lang python`)**:
- `<name>_tool.py` — Tool implementation with `TOOL_SPEC` and `run_tool()`
- `<name>_tool.json` — i18n translation template

Both files are ready to use. Place them in your `UAGENT_EXTERNAL_TOOLS_DIRS`
and restart the agent (or run `system_reload`).

**Rust (`--lang rust`)**:
- `<name>/` — Cargo project directory with `Cargo.toml`, `pyproject.toml`, and `src/lib.rs`
- `<name>_tool.py` — Python wrapper that loads the compiled `.pyd`

After scaffolding, build and install:

```bash
cd <name>
maturin build --release
pip install target/wheels/*.whl
```

Then place `<name>_tool.py` and the built `.pyd` in your
`UAGENT_EXTERNAL_TOOLS_DIRS` and restart the agent.

---


## 1. ツールの基本構造

ツールは次の要素で構成されます。

|要素 |必須 |説明 |
|----------|----------|-------------|
| `ツールスペック` |はい |ツールの名前、説明、パラメータを定義する辞書 |
| `run_tool(args)` |はい |ツールが呼び出されたときに実行される関数。 Args は辞書、return は文字列です。 |
| i18n JSON |おすすめ |翻訳 JSON ファイル (同じベース名、`<name>_tool.json`) |

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

###手順

1. **`UAGENT_EXTERNAL_TOOLS_DIRS` 環境変数を設定します** (まだ設定されていない場合)

 例:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 複数のディレクトリは、`:` (Linux/macOS) または `;` (Windows) で区切ることができます。
 `UAGENT_EXTERNAL_TOOLS_DIR` (単数形) も下位互換性のためにサポートされています。

2。 **Python ファイルを作成します**

 ファイル名は自由ですが、`<name>_tool.py` という名前を付けることをお勧めします (例: `my_tool.py`)。

3. **必要な要素を実装します**

 - `TOOL_SPEC` 辞書
 - `run_tool(args)` 関数
 - オプションで、i18n JSON ファイル

4。 **エージェントを再起動します** (または `system_reload` ツールを実行します)

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

i18n については [セクション 5](#5-internationalization-i18n) を参照してください。詳細.

---

## 3. Rust + Python ツールの作成

Rust の実装は、パフォーマンスが重要なタスク (大量のデータ処理、暗号化、ファイル処理など) に最適です。
uag は事前に構築された `.pyd` ファイルを直接ロードできるため、**エンドユーザーは `pip を必要としませんinstall`**.

### ツールの構造

Rust ツールは次のファイルで構成されます:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

配布用に、`_tool.py` + `_tool.json` + `.pyd` ファイルを配置します。 in
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### ステップ

#### ステップ 1: Rust を作成するproject

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

#### ステップ 2: Rust の実装(src/lib.rs)

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

**重要なポイント:**
- `#[pyfunction(name = "run_<name>")]`を使用して関数を公開します。
- 戻り値の型は `PyResult<String>`
- `#[pymodule]` 関数名はクレート名 (`my_rust_tools`)

#### ステップ 3: ビルド

```bash
cd my_rust_tool
cargo build --release
```

Windows: `target/release/my_rust_tools.dll` の名前を `my_rust_tools.pyd` に変更します
Linux: 名前を変更します`target/release/libmy_rust_tools.so` を `my_rust_tools.so` に変更
macOS: `target/release/libmy_rust_tools.dylib` を `my_rust_tools.so` に名前変更します

またはmaturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### ステップ 4: Python ラッパーを作成する

`UAGENT_EXTERNAL_TOOLS_DIRS` に `my_rust_tool.py` を作成しますディレクトリ:

```python
from __future__ import annotations

from typing import Any

from uagent.tools.i18n_helper import make_tool_translator
from uagent.tools.rust_helper import load_rust_pyd

_ = make_tool_translator(__file__)

# Place .pyd in the same directory — auto-detected
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

**``load_rust_pyd()`` 解決順序:**

1.ラッパー `.py`
2 と同じディレクトリで `<module_name>.pyd` (または `.so`) を探します。 pip でインストールされたモジュールにフォールバックします

#### ステップ 5: 配布

これら 3 つのファイルのみが必要です。エンドユーザーは、`pip install` を **必要ありません**。

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### 注意事項

- **ビルド時のみ:** Rust ツールチェーンと `maturin` が必要です
 ```bash
  pip install maturin
  ```
- Rust クレートname (`Cargo.toml` の `[lib] name`) は `load_rust_pyd()` の最初の引数と一致する必要があります
 - ラッパー ファイル名と `.pyd` の場所は、同じディレクトリ内にある限り独立しています

---

## 4. TOOL_SPEC リファレンス

### 基本構造

```python
TOOL_SPEC: dict[str, Any] = {
    "type": "function",                     # Fixed
    "x_build": "rust",                      # Only for Rust implementation
    "tool_genre": "utility",                # Genre (optional)
    "tool_level": 0,                        # 0=enabled, 1=conditional, -1=disabled
    "function": {
        "name": "tool_name",                # Tool name (snake_case)
        "description": "...",               # Description
        "x_search_terms": [...],            # Search keywords (i18n-aware)
        "x_search_terms_en": [...],         # English search keywords (fixed)
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

### プロパティ

|フィールド |タイプ |説明 |
|------|------|-------------|
| `タイプ` | str |常に `"関数"` |
| `x_build` | str | Rust 実装の場合は `"rust"` (Python の場合は省略) |
| `ツールのジャンル` | str |ジャンル名（オプション）。ジャンルベースの制御を有効にします |
| `ツールレベル` |整数 | 0=有効、1=条件付き (デフォルト)、-1=無効 |
| `関数.名前` | str | **必須**。ツール名 (小文字 + 数字 + アンダースコア) |
| `関数.説明` | str | **必須**。説明 |
| `function.x_search_terms` |リスト[文字列] | i18n 対応の検索キーワード (`_(...)` で囲む) |
| `function.x_search_terms_ja` |リスト[文字列] |英語の検索キーワードを修正 |
| `関数.パラメータ` |辞書 |パラメータ定義 (OpenAI 関数呼び出し形式) |

---

## 5. 国際化 (i18n)

### 翻訳メカニズム

`make_tool_translator(__file__)` を呼び出すと、同じベース名の `.json` ファイルから翻訳が読み込まれます
。 directory.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### 翻訳キーの使用

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON ファイル形式

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

既存のファイルを参照サポートされている言語コードの `_tool.json` ファイル。

---

## 6. テストとデバッグ

### 構文チェック

```bash
python -m py_compile my_tool.py
```

### 検証ツール読み込み中

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### エラー ログ

ツールの読み込み中のエラーは標準エラー出力に出力されます。ツールが読み込まれていない場合は、
uag 起動ログを確認してください。

---

## 7. 参考例

### Python ツールの例

- `date_calc_tool.py` (`src/uagent/tools/` 内) — 日付の計算。外部にコピーしてカスタマイズします。
- `calculator_tool.py` (`src/uagent/tools/` 内) — Calculator.

### Rust ツールの例

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/` 内) — UUID 生成
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/` 内) — スラグ変換

`_tool.py` ファイルと `.pyd` ファイルを `UAGENT_EXTERNAL_TOOLS_DIRS` にコピーして、外部ファイルとして使用しますtools.

### 外部ツール ディレクトリのセットアップ

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

複数のディレクトリは、`:` (Linux/macOS) または `;` (Windows) で区切ることができます。
`UAGENT_EXTERNAL_TOOLS_DIR` (単数形) も下位互換性のためにサポートされています。