# Guida alla creazione degli strumenti

Questa guida spiega come aggiungere i tuoi strumenti a uag **senza modificare uag stesso**.
Se desideri aggiungere uno strumento direttamente all'albero dei sorgenti di uag, vedere
[DEVELOP_TOOL.md](../src/uagent/docs/DEVELOP_TOOL.md).

---

## Sommario
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Struttura dello strumento di base](#1-struttura-dello-strumento-di-base)
2. [Creazione di uno strumento Python](#2-creazione-di-uno-strumento-python)
3. [Creazione di uno strumento Rust + Python](#3-creare-un-rust--strumento-python)
4. [Riferimento TOOL_SPEC](#4-riferimento-spec_utensile)
5. [Internazionalizzazione (i18n)](#5-internazionalizzazione-i18n)
6. [Test e debug](#6-test-e-debug)
7. [Esempi di riferimento](#7-esempi-di-riferimento)

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


## 1. Struttura di base dello strumento

Uno strumento è costituito dai seguenti elementi:

| Elemento | Obbligatorio | Descrizione |
|---------|----------|-------------|
| `SPEC_UTENSILE` | Sì | Dizionario che definisce il nome, la descrizione e i parametri dello strumento |
| `run_tool(args)` | Sì | Funzione eseguita quando viene richiamato lo strumento. Args è un dict, return è una stringa. |
| i18n JSON | Consigliato | File JSON di traduzione (stesso nome base, `<nome>_tool.json`) |

### Strumento Python minimo

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

---

## 2. Creazione di uno strumento Python

### Passaggi

1. **Imposta la variabile di ambiente `UAGENT_EXTERNAL_TOOLS_DIRS`** (se non è già impostata)

 Esempio:
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

3. **Implement the required elements**

   - `TOOL_SPEC` dictionary
   - `run_tool(args)` function
   - Optionally, an i18n JSON file

4. **Restart the agent** (or run the `system_reload` tool)

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

---

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

**``load_rust_pyd()`` resolution order:**

1. Look for `<module_name>.pyd` (or `.so`) in the same directory as the wrapper `.py`
2. Fall back to a pip-installed module

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

---

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

---

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

---

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

---

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

Più directory possono essere separate da `:` (Linux/macOS) o `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (singolare) è supportato anche per compatibilità con le versioni precedenti.