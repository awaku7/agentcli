# Tool Creator Guide

Den här guiden förklarar hur du lägger till dina egna verktyg i uag **utan att ändra uag själv**.
Om du vill lägga till ett verktyg direkt i uag-källträdet, se
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Innehållsförteckning
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Grundläggande verktygsstruktur](#1-grundläggande verktygsstruktur)
2. [Creating a Python Tool](#2-creating-a-python-tool)
3. [Creating a Rust + Python Tool](#3-creating-a-rust--python-tool)
4. [TOOL_SPEC Reference](#4-tool_spec-reference)
5. [Internationalisering (i18n)](#5-internationalisering-i18n)
6. [Testing and Debugging](#6-testing-and-debugging)
7. [Referensexempel](#7-referensexempel)

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


## 1. Grundläggande verktygsstruktur

Ett verktyg består av följande element:

| Element | Krävs | Beskrivning |
|--------|--------|-------------------|
| `TOOL_SPEC` | Ja | Ordbok som definierar verktygets namn, beskrivning och parametrar |
| `run_tool(args)` | Ja | Funktion exekveras när verktyget anropas. Args är ett dikt, retur är en sträng. |
| i18n JSON | Rekommenderas | Översättning av JSON-fil (samma basnamn, `<name>_tool.json`) |

### Minimal Python Tool

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

## 2. Skapa ett Python Tool

### Steg

1. **Ställ in miljövariabeln `UAGENT_EXTERNAL_TOOLS_DIRS`** (om den inte redan är inställd)

 Exempel:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Flera kataloger kan separeras med `:` (Linux/macOS) eller `;` (Windows). kompatibilitet.

2. **Skapa en Python-fil**

 Filnamnet är gratis, men namngivning av `<name>_tool.py` rekommenderas (t.ex. `my_tool.py`).

3. **Implementera de nödvändiga elementen**

 - `TOOL_SPEC` ordbok
 - `run_tool(args)`-funktionen
 - Valfritt, en i18n JSON-fil

4. **Starta om agenten** (eller kör verktyget `system_reload`)

### Fullständig mall

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

Se [Avsnitt 5](#5-internationalization-i18n) för detaljer om i18n. idealisk för prestandakritiska uppgifter (tung databearbetning, kryptografi, filbehandling, etc.).
uag kan ladda förbyggda `.pyd`-filer direkt, så **slutanvändare behöver inte `pipinstallation`**.

### Verktygsstruktur

Ett Rustverktyg består av följande filer:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

För distribution, placera filerna `_tool.py` + `_tool.json` + `.pyd` i
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Steg

#### Steg 1: Skapa Rust project

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

#### Steg 2: Rustimplementering (src/lib.rs)

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
Expose function:-# "run_<name>")]`
- Returtypen är `PyResult<String>`
- Funktionsnamnet `#[pymodule]` måste matcha lådans namn (`my_rust_tools`)

#### Steg 3: Build

```bash
cd my_rust_tool
cargo build --release
```

get_dll: re `my_rust_tools.pyd`
Linux: byt namn på `target/release/libmy_rust_tools.so` till `my_rust_tools.so`
macOS: byt namn på `target/release/libmy_rust_tools.dylib` till `my_rust_tools.so`
 maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Steg 4: Skapa Python-omslaget

Skapa `my_rust_tool.py` i din `UAGENT_EXTERNAL_TOOLS_DIRS`-katalog:

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
`load_rust_`py` beställning:**

1. Leta efter `<modulnamn>.pyd` (eller `.so`) i samma katalog som omslaget `.py`
2. Gå tillbaka till en pip-installerad modul

#### Steg 5: Distribution

Endast dessa 3 filer behövs. Slutanvändare behöver **inte** någon `pip-installation`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Notes

- **Endast byggtid:** Rust verktygskedja och `maturin` krävs
 ```bash
  pip install maturin
  ```
- Rust-lådans namn (`[lib] namnet" i första argumentet i `Cargo) `load_rust_pyd()`
- Omslagsfilens namn och `.pyd`-platsen är oberoende så länge de finns i samma katalog

---

## 4. TOOL_SPEC Reference

### Grundläggande struktur

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
| Fält | Skriv | Beskrivning |
|-------|------|--------------------|
| `typ` | str | Alltid `"funktion"` |
| `x_build` | str | `"rust"` för Rust-implementering (utelämna för Python) |
| `verktygsgenre` | str | Genrenamn (valfritt). Aktiverar genrebaserad kontroll |
| `verktygsnivå` | int | 0=aktiverad, 1=villkorlig (standard), -1=avaktiverad |
| `funktion.namn` | str | **Nödvändig**. Verktygets namn (gemener + siffror + understreck) |
| `function.description` | str | **Nödvändig**. Kuvaus |
| `function.x_search_terms` | lista[str] | i18n-aware sökord (omslut med `_(...)`) |
| `function.x_search_terms_en` | lista[str] | Fixade engelska sökord |
| `function.parameters` | dikt | Parameterdefinition (OpenAI-funktionsanropsformat) |

---

## 5. Internationalisering (i18n)

### Translation Mechanism

Anropar `make_tool_translator(__file__)` laddar översättningar från en `.json samma` fil
med samma basnamn katalog.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Använda översättningsnycklar

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON-filformat

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

Se befintliga `_tool.json`-filer för språkkoder som stöds.⎏-#.⎏-# Felsökning

### Syntaxkontroll

```bash
python -m py_compile my_tool.py
```

### Verifiera verktygsladdning

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Felloggar

Fel under verktygsladdning skrivs ut till stderr. Om ditt verktyg inte är laddat,
kontrollera uags startloggar.

---

## 7. Referensexempel

### Python Tool Exempel

- `date_calc_tool.py` (i `src/uagent/Datecalculation.) — Kopiera externt och anpassa.
- `calculator_tool.py` (i `src/uagent/tools/`) — Calculator.

### Exempel på Rustverktyg

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (i `rust-/src/)-ID (i `rust/src/) `rust_slugify_tool.py` + `uag_tools_rust.pyd` (i `src/uagent/tools_rust/`) — Slug conversion

Kopiera `_tool.py` och `.pyd`-filerna till `UAGENT_EXTERNAL_TOOLS_DIRS` för att använda dem som externa verktyg.#l# Kataloger

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Flera kataloger kan separeras med `:` (Linux/macOS) eller `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (singular) stöds också för bakåtkompatibilitet.