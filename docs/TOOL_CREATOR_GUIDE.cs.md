# Tool Creator Guide

Tato příručka vysvětluje, jak přidat své vlastní nástroje do uag **bez úpravy samotného uag**.
Pokud chcete přidat nástroj přímo do stromu zdroje uag, viz
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Obsah
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Základní struktura nástroje](#1-základní-struktura-nástroje)
2. [Vytvoření nástroje Python](#2-creating-a-python-tool)
3. [Vytvoření nástroje Rust + Python](#3-creating-a-rust--python-tool)
4. [TOOL_SPEC Reference](#4-tool_spec-reference)
5. [Internacionalizace (i18n)](#5-internacionalizace-i18n)
6. [Testování a ladění](#6-testování-a-ladění)
7. [Referenční příklady](#7-reference-examples)

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


## 1. Základní struktura nástroje

Nástroj se skládá z následujících prvků:

| Prvek | Povinné | Popis |
|---------|----------|-------------|
| `TOOL_SPEC` | Ano | Slovník definující název, popis a parametry nástroje |
| `run_tool(args)` | Ano | Funkce provedená při vyvolání nástroje. Args je diktát, return je řetězec. |
| i18n JSON | Doporučeno | Překladový soubor JSON (stejný základní název, `<name>_tool.json`) |

### Minimální nástroj Python

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

## 2. Vytvoření nástroje Python

### Kroky

1. **Nastavte proměnnou prostředí `UAGENT_EXTERNAL_TOOLS_DIRS`** (pokud ještě není nastavena)

 Příklad:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Více adresářů lze oddělit znakem `:` (Linux/macOS) nebo `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (singulární) je také podporován pro zpětnou kompatibilitu.

2. **Vytvořte soubor Python**

 Název souboru je zdarma, ale doporučuje se pojmenování `<name>_tool.py` (např. `my_tool.py`).

3. **Implementujte požadované prvky**

 - Slovník `TOOL_SPEC`
 - Funkce `run_tool(args)`
 - Volitelně soubor i18n JSON

4. **Restartujte agenta** (nebo spusťte nástroj `system_reload`)

### Úplná šablona

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

Podrobnosti o i18n naleznete v [sekci 5](#5-internacionalizace-i18n).

---

## 3. Vytvoření nástroje Rust + Python

Implementace Rust je ideální pro úkoly kritické z hlediska výkonu (náročné zpracování dat, kryptografie, zpracování souborů atd.).
uag může načítat předem vytvořené soubory `.pyd` přímo, takže **koncoví uživatelé nepotřebují `pip instalaci`**.

### Struktura nástroje

Soubory:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Pro distribuci umístěte soubory `_tool.py` + `_tool.json` + `.pyd` do
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Kroky

#### Krok 1: Vytvořte Rust project

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

#### Krok 2: Implementace Rust (src/lib.rs)

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

**Klíčové body:**
- Vystavit funkce s `#[pyfunction(name = "run_<name>")]`
- Typ návratu je `PyResult<String>`
- Název funkce `#[pymodule]` se musí shodovat s názvem bedny (`my_rust_tools`)

#### Krok 3: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: přejmenujte `target/release/my_rust_tools.dll` na `my_rust_tools.pyd`
Linux: přejmenujte `target/release/libmy_rust_tools.so` na `my_rust_tools.so`
macOS: přejmenujte `target/release/libmy_rust_tools.dylib` na `my_rust_tools.so`

Nebo pomocí maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Krok 4: Vytvořte obálku Pythonu

Vytvořte `my_rust_tool.py` ve svém `UAGENT_EXTERNAL_TOOLS_DIRS` adresář:

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

**``load_rust_pyd()`` pořadí rozlišení:**

1. Hledejte `<name>.pyd` (nebo `.so`) ve stejném adresáři jako obal `.py`
2. Vraťte se k modulu nainstalovanému pomocí pipu

#### Krok 5: Distribuce

Jsou potřeba pouze tyto 3 soubory. Koncoví uživatelé **nepotřebují** žádnou `pip instalaci`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Poznámky

- **Pouze doba sestavení:** Je vyžadována sada nástrojů Rust a `maturin`
 ```bash
  pip install maturin
  ```
- Název Rust crate (`[lib] name` v `Cargo.toml`) musí odpovídat prvnímu argumentu `load_rust_pyd()`
- Název souboru obalu a umístění `.pyd` jsou nezávislé, pokud jsou ve stejném adresáři

---

## 4. TOOL_SPEC Reference

### Základní Struktura

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

### Vlastnosti

| Pole | Typ | Popis |
|-------|------|-------------|
| `type` | str | Vždy `"function"` |
| `x_build` | str | `"rust"` pro implementaci Rust (vynechejte pro Python) |
| `tool_genre` | str | Název žánru (volitelné). Umožňuje ovládání podle žánru |
| `tool_level` | int | 0=povoleno, 1=podmíněné (výchozí), -1=vypnuto |
| `function.name` | str | **Požadovaný**. Název nástroje (malá písmena + číslice + podtržítko) |
| `function.description` | str | **Požadovaný**. Popis |
| `function.x_search_terms` | seznam[str] | Klíčová slova pro vyhledávání s podporou i18n (obtékat `_(...)`) |
| `function.x_search_terms_en` | seznam[str] | Opravená anglická klíčová slova pro vyhledávání |
| `function.parameters` | dict | Definice parametru (formát volání funkce OpenAI) |

---

## 5. Internacionalizace (i18n)

### Překladový mechanismus

Volání `make_tool_translator(__file__)` načte překlady ze souboru `.json` se stejným základním názvem
ve stejném adresáři.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Použití překladových klíčů

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Formát souboru JSON

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

Podporované soubory `_tool.json` pro podporované jazykové kódy.

---

## 6. Testování a ladění

### Kontrola syntaxe

```bash
python -m py_compile my_tool.py
```

### Ověřte načítání nástroje

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Protokoly chyb

Chyby při načítání nástroje se tisknou na stderr. Pokud váš nástroj není načten,
zkontrolujte protokoly spuštění uag.

---

## 7. Referenční příklady

### Příklady nástrojů Python

- `date_calc_tool.py` (v `src/uagent/tools/`) — Výpočet data. Externě zkopírujte a přizpůsobte.
- `calculator_tool.py` (v `src/uagent/tools/`) — Kalkulačka.

### Příklady nástrojů pro Rust

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (v `src/uagent/tools_rust/`) — Generování UUID
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (v `src/uagent/tools_rust/`) — Konverze slug

Zkopírujte soubory `_tool.py` a `.pyd` do `UAGENT_EXTERNAL_TOOLS_DIRS` a použijte je jako externí nástroje.

### Nastavení adresářů externích nástrojů

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Více adresářů lze oddělit `:` (Linux/macOS) nebo `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (singulární) je také podporován pro zpětnou kompatibilitu.