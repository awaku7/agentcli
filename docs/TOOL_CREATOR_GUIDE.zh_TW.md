# 工具創建者指南

本指南解釋如何將自己的工具添加到 uag **而不修改 uag 本身**。
如果您想將工具直接加入 uag 原始碼樹中，請參閱
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md)。

---

##目錄
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [基本工具結構](#1-基本工具結構)
2. [創建Python工具](#2-創建-python-工具)
3. [創建 Rust + Python 工具](#3-creating-python-工具)
3. [創建 Rust + Python 工具](#3-creating-a-tust--pythonon. [工具規格參考](#4-工具規格參考)
5. [國際化 (i18n)](#5-國際化-i18n)
6. [測試與除錯](#6-測試與除錯)
7. [參考範例](#7-參考-範例)

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



## 1. 工具基本結構

一個工具由以下元素組成：

|元素|必填 |說明 |
|---------|----------|-------------|
| `TOOL_SPEC` |是的 |定義工具名稱、描述和參數的字典|
| `run_tool(args)` |是的 |工具被調用時執行的函數。 Args 是一個字典，return 是一個字串。 |
| i18n JSON |推薦|翻譯 JSON 檔案（相同的基本名稱，`<name>_tool.json`） |

### 最小 Python 工具
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

## 2. 創建 Python 工具

### 步驟

1. **設定 `UAGENT_EXTERNAL_TOOLS_DIRS` 環境變數**（如果尚未設定）

   範例：
   ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

   多個目錄可以用 `:`（Linux/macOS）或 `;`（Windows）分隔。
   `UAGENT_EXTERNAL_TOOLS_DIR`（單數）也支援向後相容性。

2. **建立 Python 檔案**

   檔案名稱隨意，但建議使用 `<name>_tool.py` 命名（例如 `my_tool.py`）。

3. **實現所需的元素**

   - `TOOL_SPEC` 字典
   - `run_tool(args)` 函數
   - 可選的 i18n JSON 檔案

4. **重新啟動代理**（或執行 `system_reload` 工具）

### 完整模板
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

有關 i18n 詳細信息，請參閱[第 5 節](#5-internationalization-i18n)。

---

## 3. 創建 Rust + Python 工具

Rust 實作非常適合效能關鍵型任務（大量資料處理、加密、檔案處理等）。
uag 可以直接載入預先建置的 `.pyd` 文件，因此 **最終使用者不需要 `pip install`**。

### 工具結構

Rust 工具由以下文件組成：

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

要進行分發，請將 `_tool.py` + `_tool.json` + `.pyd` 檔案放在
`UAGENT_EXTERNAL_TOOLS_DIRS` 中。

### 步驟

#### 步驟 1：創建 Rust 專案

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

#### 步驟 2：Rust 實現 (src/lib.rs)

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

**重點：**
- 使用 `#[pyfunction(name = "run_<name>")]` 公開函數
- 傳回型別為 `PyResult<String>`
- `#[pymodule]` 函式名稱必須與 crate 名稱相符 (`my_rust_tools`)

#### 步驟 3：建構

```bash
cd my_rust_tool
cargo build --release
```

Windows：將 `target/release/my_rust_tools.dll` 重新命名為 `my_rust_tools.pyd`
Linux：將 `target/release/libmy_rust_tools.so` 重新命名為 `my_rust_tools.so`
macOS：將 `target/release/libmy_rust_tools.dylib` 重新命名為 `my_rust_tools.so`

或使用 maturin：
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### 步驟 4：創建 Python 包裝器

在 `UAGENT_EXTERNAL_TOOLS_DIRS` 目錄中創建 `my_rust_tool.py`：

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

**``load_rust_pyd()`` 解析順序：**

1. 在與包裝器 `.py` 相同的目錄中尋找 `<module_name>.pyd`（或 `.so`）
2. 回退到 pip 安裝的模組

#### 步驟 5：分發

只需要這 3 個檔案。最終使用者 **不需要** 任何 `pip install`。

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### 注意

- **僅建構時：** 需要 Rust 工具鍊和 `maturin`
  ```bash
  pip install maturin
  ```
- Rust crate 名稱（`Cargo.toml` 中的 `[lib] name`）必須與 `load_rust_pyd()` 的第一個參數匹配
- 包裝器檔案名稱和 `.pyd` 位置是獨立的，只要它們位於同一目錄中即可

---

## 4. TOOL_SPEC 參考

### 基本結構

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

### 屬性

| 欄位 | 類型 | 說明 |
|-------|------|-------------|
| `type` | str | 總是 `"function"` |
| `x_build` | str | `"rust"` 用於 Rust 實作（Python 可省略） |
| `tool_genre` | str | 類型名稱（可選）。啟用基於類型的控制 |
| `tool_level` | int | 0=啟用，1=有條件（預設），-1=停用 |
| `function.name` | str | **必需的**。工具名稱（小寫+數字+底線） |
| `function.description` | str | **必需的**。描述 |
| `function.x_search_terms` | list[str] | i18n 感知搜尋關鍵字（用 `_(...)` 包裹） |
| `function.x_search_terms_en` | list[str] | 固定的英文搜尋關鍵字 |
| `function.parameters` | dict | 參數定義（OpenAI 函數調用格式） |

---

## 5. 國際化 (i18n)

### 翻譯機制

調用 `make_tool_translator(__file__)` 從同一目錄中具有相同基本名稱的 `.json` 檔案載入翻譯。

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### 使用翻譯鍵

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON 檔案格式

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

請參閱現有的 `_tool.json` 檔案以了解支援的語言代碼。

---

## 6. 測試與除錯

### 語法檢查

```bash
python -m py_compile my_tool.py
```

### 驗證工具載入

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### 錯誤日誌

工具載入期間的錯誤會輸出到 stderr。如果您的工具未載入，
請檢查 uag 啟動日誌。

---

## 7. 參考範例

### Python 工具範例

- `date_calc_tool.py`（在 `src/uagent/tools/` 中）— 日期計算。外部複製並自訂。
- `calculator_tool.py`（在 `src/uagent/tools/` 中）— 計算器。

### Rust 工具範例

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd`（在 `src/uagent/tools_rust/` 中）— UUID 產生
- `rust_slugify_tool.py` + `uag_tools_rust.pyd`（在 `src/uagent/tools_rust/` 中）— Slug 轉換

將 `_tool.py` 和 `.pyd` 檔案複製到 `UAGENT_EXTERNAL_TOOLS_DIRS` 以將它們用作外部工具。

### 設定外部工具目錄

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

多個目錄可以用 `:`（Linux/macOS）或 `;`（Windows）分隔。
`UAGENT_EXTERNAL_TOOLS_DIR`（單數）也支援向後相容性。

---

*此翻譯是自動產生的。如需最準確和最新的內容，請參閱英文版本。*