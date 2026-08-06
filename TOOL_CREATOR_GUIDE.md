# Tool Creator Guide

This guide explains how to add your own tools to uag **without modifying uag itself**.
If you want to add a tool directly to the uag source tree, see
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

______________________________________________________________________

## Table of Contents

0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)
1. [Basic Tool Structure](#1-basic-tool-structure)
1. [Creating a Python Tool](#2-creating-a-python-tool)
1. [Creating a Rust + Python Tool](#3-creating-a-rust--python-tool)
1. [TOOL_SPEC Reference](#4-tool_spec-reference)
1. [Internationalization (i18n)](#5-internationalization-i18n)
1. [Testing and Debugging](#6-testing-and-debugging)
1. [Reference Examples](#7-reference-examples)

______________________________________________________________________

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

______________________________________________________________________

## 1. Basic Tool Structure

A tool consists of the following elements:

| Element | Required | Description |
|---------|----------|-------------|
| `TOOL_SPEC` | Yes | Dictionary defining the tool's name, description, and parameters |
| `run_tool(args)` | Yes | Function executed when the tool is called. Args is a dict, return is a string. |
| i18n JSON | Recommended | Translation JSON file (same basename, `<name>_tool.json`) |

### Minimal Python Tool

```python
# my_tool.py
from typing import Any

def run_tool(args: dict[str, Any]) -> str:
    name = args.get("name", "World")
    return f"Hello, {name}!"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": True,       # Safe to run concurrently when True
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

______________________________________________________________________

## 2. Creating a Python Tool

### Steps

1. **Set the `UAGENT_EXTERNAL_TOOLS_DIRS` environment variable** (if not already set)

   Example:

   ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

   Multiple directories can be separated by `:` (Linux/macOS) or `;` (Windows).
   `UAGENT_EXTERNAL_TOOLS_DIR` (singular) is also supported for backward compatibility.

1. **Create a Python file**

   File name is free, but `<name>_tool.py` naming is recommended (e.g. `my_tool.py`).

1. **Implement the required elements**

   - `TOOL_SPEC` dictionary
   - `run_tool(args)` function
   - Optionally, an i18n JSON file

1. **Restart the agent** (or run the `system_reload` tool)

### Full Template

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

See [Section 5](#5-internationalization-i18n) for i18n details.

______________________________________________________________________

## 3. Creating a Rust + Python Tool

Rust implementation is ideal for performance-critical tasks (heavy data processing, cryptography, file processing, etc.).
uag can load pre-built `.pyd` files directly, so **end-users don't need `pip install`**.

### Tool Structure

A Rust tool consists of the following files:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

For distribution, place the `_tool.py` + `_tool.json` + `.pyd` files in
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Steps

#### Step 1: Create the Rust project

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

#### Step 2: Rust implementation (src/lib.rs)

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

**Key points:**

- Expose functions with `#[pyfunction(name = "run_<name>")]`
- Return type is `PyResult<String>`
- The `#[pymodule]` function name must match the crate name (`my_rust_tools`)

#### Step 3: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: rename `target/release/my_rust_tools.dll` to `my_rust_tools.pyd`
Linux: rename `target/release/libmy_rust_tools.so` to `my_rust_tools.so`
macOS: rename `target/release/libmy_rust_tools.dylib` to `my_rust_tools.so`

Or using maturin:

```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Step 4: Create the Python wrapper

Create `my_rust_tool.py` in your `UAGENT_EXTERNAL_TOOLS_DIRS` directory:

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

**`load_rust_pyd()` resolution order:**

1. Look for `<module_name>.pyd` (or `.so`) in the same directory as the wrapper `.py`
1. Fall back to a pip-installed module

#### Step 5: Distribution

Only these 3 files are needed. End-users do **not** need any `pip install`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Notes

- **Build-time only:** Rust toolchain and `maturin` are required
  ```bash
  pip install maturin
  ```
- The Rust crate name (`[lib] name` in `Cargo.toml`) must match the first argument of `load_rust_pyd()`
- The wrapper file name and `.pyd` location are independent as long as they are in the same directory

______________________________________________________________________

## 4. TOOL_SPEC Reference

### Basic Structure

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

### Properties

| Field | Type | Description |
|-------|------|-------------|
| `type` | str | Always `"function"` |
| `x_build` | str | `"rust"` for Rust implementation (omit for Python) |
| `tool_genre` | str | Genre name (optional). Enables genre-based control |
| `tool_level` | int | 0=enabled, 1=conditional (default), -1=disabled |
| `x_parallel_safe` | bool | Whether independent calls may run concurrently |
| `function.name` | str | **Required**. Tool name (lowercase + digits + underscore) |
| `function.description` | str | **Required**. Description |
| `function.x_search_terms` | list[str] | i18n-aware search keywords (wrap with `_(...)`) |
| `function.x_search_terms_en` | list[str] | Fixed English search keywords |
| `function.parameters` | dict | Parameter definition (OpenAI function calling format) |

______________________________________________________________________

## 5. Internationalization (i18n)

### Translation Mechanism

Calling `make_tool_translator(__file__)` loads translations from a `.json` file
with the same basename in the same directory.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Using Translation Keys

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON File Format

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

See existing `_tool.json` files for supported language codes.

______________________________________________________________________

## 6. Testing and Debugging

### Syntax Check

```bash
python -m py_compile my_tool.py
```

### Verify Tool Loading

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Error Logs

Errors during tool loading are printed to stderr. If your tool isn't loaded,
check the uag startup logs.

______________________________________________________________________

## 7. Reference Examples

### Python Tool Examples

- `date_calc_tool.py` (in `src/uagent/tools/`) — Date calculation. Copy externally and customize.
- `calculator_tool.py` (in `src/uagent/tools/`) — Calculator.

### Rust Tool Examples

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (in `src/uagent/tools_rust/`) — UUID generation
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (in `src/uagent/tools_rust/`) — Slug conversion

Copy the `_tool.py` and `.pyd` files into `UAGENT_EXTERNAL_TOOLS_DIRS` to use them as external tools.

### Setting Up External Tool Directories

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Multiple directories can be separated by `:` (Linux/macOS) or `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (singular) is also supported for backward compatibility.

## Detailed Japanese guide

The former `docs/TOOL_CREATOR_GUIDE.ja.md` content is retained below. The English guide above remains the primary reference; this section preserves the Japanese guide without maintaining a separate duplicate file.

このガイドでは、**uag 自体を変更することなく**、独自のツールを uag に追加する方法について説明します。
ツールを uag ソース ツリーに直接追加する場合は、
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md)を参照してください。

______________________________________________________________________

## 目次

0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [基本ツール構造](#1-%E5%9F%BA%E6%9C%AC%E3%83%84%E3%83%BC%E3%83%AB%E6%A7%8B%E9%80%A0)

1. [Python ツールの作成](#2-creating-a-python-tool)

1. [Rust + Python ツールの作成](#3-creating-a-rust--python-tool)

1. [TOOL_SPEC リファレンス](#4-tool_spec-reference)

1. [国際化 (i18n)](#5-%E5%9B%BD%E9%9A%9B%E5%8C%96-i18n)

1. [テストとデバッグ](#6-%E3%83%86%E3%82%B9%E3%83%88%E3%81%A8%E3%83%87%E3%83%90%E3%83%83%E3%82%B0)

1. [参考例](#7-%E5%8F%82%E8%80%83%E4%BE%8B)

______________________________________________________________________

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

______________________________________________________________________

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
    "x_parallel_safe": True,       # Safe to run concurrently when True
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

______________________________________________________________________

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

Multiple directories can be separated by `:` (Linux/macOS) or `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (singular) is also supported for backward compatibility.

2. **Create a Python file**

   File name is free, but `<name>_tool.py` naming is recommended (e.g. `my_tool.py`).

1. **Implement the required elements**

   - `TOOL_SPEC` dictionary
   - `run_tool(args)` function
   - Optionally, an i18n JSON file

1. **Restart the agent** (or run the `system_reload` tool)

### Full Template

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

See [Section 5](#5-internationalization-i18n) for i18n details.

______________________________________________________________________

## 3. Creating a Rust + Python Tool

Rust implementation is ideal for performance-critical tasks (heavy data processing, cryptography, file processing, etc.).
uag can load pre-built `.pyd` files directly, so **end-users don't need `pip install`**.

### Tool Structure

A Rust tool consists of the following files:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

For distribution, place the `_tool.py` + `_tool.json` + `.pyd` files in
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Steps

#### Step 1: Create the Rust project

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

#### Step 2: Rust implementation (src/lib.rs)

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

**Key points:**

- Expose functions with `#[pyfunction(name = "run_<name>")]`
- Return type is `PyResult<String>`
- The `#[pymodule]` function name must match the crate name (`my_rust_tools`)

#### Step 3: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: rename `target/release/my_rust_tools.dll` to `my_rust_tools.pyd`
Linux: rename `target/release/libmy_rust_tools.so` to `my_rust_tools.so`
macOS: rename `target/release/libmy_rust_tools.dylib` to `my_rust_tools.so`

Or using maturin:

```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Step 4: Create the Python wrapper

Create `my_rust_tool.py` in your `UAGENT_EXTERNAL_TOOLS_DIRS` directory:

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

**`load_rust_pyd()` resolution order:**

1. Look for `<module_name>.pyd` (or `.so`) in the same directory as the wrapper `.py`
1. Fall back to a pip-installed module

#### Step 5: Distribution

Only these 3 files are needed. End-users do **not** need any `pip install`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Notes

- **Build-time only:** Rust toolchain and `maturin` are required
  ```bash
  pip install maturin
  ```
- The Rust crate name (`[lib] name` in `Cargo.toml`) must match the first argument of `load_rust_pyd()`
- The wrapper file name and `.pyd` location are independent as long as they are in the same directory

______________________________________________________________________

## 4. TOOL_SPEC Reference

### Basic Structure

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

### Properties

| Field | Type | Description |
|-------|------|-------------|
| `type` | str | Always `"function"` |
| `x_build` | str | `"rust"` for Rust implementation (omit for Python) |
| `tool_genre` | str | Genre name (optional). Enables genre-based control |
| `tool_level` | int | 0=enabled, 1=conditional (default), -1=disabled |
| `x_parallel_safe` | bool | Whether independent calls may run concurrently |
| `function.name` | str | **Required**. Tool name (lowercase + digits + underscore) |
| `function.description` | str | **Required**. Description |
| `function.x_search_terms` | list[str] | i18n-aware search keywords (wrap with `_(...)`) |
| `function.x_search_terms_en` | list[str] | Fixed English search keywords |
| `function.parameters` | dict | Parameter definition (OpenAI function calling format) |

______________________________________________________________________

## 5. Internationalization (i18n)

### Translation Mechanism

Calling `make_tool_translator(__file__)` loads translations from a `.json` file
with the same basename in the same directory.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Using Translation Keys

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON File Format

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

See existing `_tool.json` files for supported language codes.

______________________________________________________________________

## 6. Testing and Debugging

### Syntax Check

```bash
python -m py_compile my_tool.py
```

### Verify Tool Loading

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Error Logs

Errors during tool loading are printed to stderr. If your tool isn't loaded,
check the uag startup logs.

______________________________________________________________________

## 7. Reference Examples

### Python Tool Examples

- `date_calc_tool.py` (in `src/uagent/tools/`) — Date calculation. Copy externally and customize.
- `calculator_tool.py` (in `src/uagent/tools/`) — Calculator.

### Rust Tool Examples

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (in `src/uagent/tools_rust/`) — UUID generation
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (in `src/uagent/tools_rust/`) — Slug conversion

Copy the `_tool.py` and `.pyd` files into `UAGENT_EXTERNAL_TOOLS_DIRS` to use them as external tools.

### Setting Up External Tool Directories

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
