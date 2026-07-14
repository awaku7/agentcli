# Verktøyskaperveiledning

Denne veiledningen forklarer hvordan du legger til dine egne verktøy i uag **uten å endre uag selv**.
Hvis du vil legge til et verktøy direkte i uag-kildetreet, se
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Innholdsfortegnelse
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Grunnleggende verktøystruktur](#1-grunnleggende verktøystruktur)
2. [Creating a Python Tool](#2-creating-a-python-tool)
3. [Creating a Rust + Python Tool](#3-creating-a-rust--python-tool)
4. [TOOL_SPEC Reference](#4-tool_spec-reference)
5. [Internationalization (i18n)](#5-internationalization-i18n)
6. [Testing and Debugging](#6-testing-and-debugging)
7. [Referanseeksempler](#7-referanseeksempler)

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


## 1. Grunnleggende verktøystruktur

Et verktøy består av følgende elementer:

| Element | Påkrevd | Beskrivelse |
|--------|--------|-------------------|
| `TOOL_SPEC` | Ja | Ordbok som definerer verktøyets navn, beskrivelse og parametere |
| `run_tool(args)` | Ja | Funksjon utført når verktøyet kalles. Args er en diktat, retur er en streng. |
| i18n JSON | Anbefalt | Oversettelse JSON-fil (samme basenavn, `<name>_tool.json`) |

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

## 2. Opprette et Python-verktøy

### Trinn

1. **Angi miljøvariabelen `UAGENT_EXTERNAL_TOOLS_DIRS`** (hvis den ikke allerede er angitt)

 Eksempel:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Flere kataloger kan skilles fra hverandre med `:` (Linux/macOS) eller `;` (Windows). kompatibilitet.

2. **Opprett en Python-fil**

 Filnavnet er gratis, men «<name>_tool.py»-navngivning anbefales (f.eks. «my_tool.py»).

3. **Implementer de nødvendige elementene**

 - `TOOL_SPEC` ordbok
 - `run_tool(args)` funksjon
 - Eventuelt en i18n JSON-fil

4. **Start agenten på nytt** (eller kjør `system_reload`-verktøyet)

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

Se [Seksjon 5](#5-internationalization-i18n) for detaljer om i18n. ideell for ytelseskritiske oppgaver (tung databehandling, kryptografi, filbehandling osv.).
uag kan laste inn forhåndsbygde `.pyd`-filer direkte, så **sluttbrukere trenger ikke `pip install`**.

### Verktøystruktur

Et Rust-verktøy består av følgende filer:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

For distribution, plasser `_tool.py` + `_tool.json` + `.pyd`-filer i
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Trinn

#### Trinn 1: Lag rusten project

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

#### Trinn 2: Rustimplementering (src/lib.rs)

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
=Expose function:-# "run_<name>")]`
- Returtypen er `PyResult<String>`
- Funksjonsnavnet `#[pymodule]` må samsvare med kassenavnet (`my_rust_tools`)

#### Trinn 3: Build

```bash
cd my_rust_tool
cargo build --release
```

get_dll: rename 'e/tar_dll: rename' `my_rust_tools.pyd`
Linux: endre navn på `target/release/libmy_rust_tools.so` til `my_rust_tools.so`
macOS: endre navn på `target/release/libmy_rust_tools.dylib` til `my_rust_tools.so`
 maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Trinn 4: Lag Python-omslaget

Opprett `my_rust_tool.py` i `UAGENT_EXTERNAL_TOOLS_DIRS`-katalogen din:

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
`load_rust_`py bestilling:**

1. Se etter `<module_name>.pyd` (eller `.so`) i samme katalog som innpakningen `.py`
2. Gå tilbake til en pip-installert modul

#### Trinn 5: Distribusjon

Bare disse 3 filene er nødvendige. Sluttbrukere trenger **ikke** noen `pip-installasjon`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Merknader

- **Kun byggetid:** Rust-verktøykjede og `maturin` er påkrevd
 ```bash
  pip install maturin
  ```
- Rust-kassenavnet (`[lib]-navnet) må samsvare med tom i `Cargo`) `load_rust_pyd()`
- Innpakningsfilnavnet og `.pyd`-plasseringen er uavhengige så lenge de er i samme katalog

---

## 4. TOOL_SPEC Reference

### Grunnleggende struktur

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
| Felt | Skriv | Beskrivelse |
|-------|------|-------------------|
| `type` | str | Alltid `"funksjon"` |
| `x_build` | str | `"rust"` for Rust-implementering (utelat for Python) |
| `verktøysjanger` | str | Sjangernavn (valgfritt). Aktiverer sjangerbasert kontroll |
| `verktøynivå` | int | 0=aktivert, 1=betinget (standard), -1=deaktivert |
| `funksjonsnavn` | str | **Obligatorisk**. Verktøynavn (små bokstaver + sifre + understrek) |
| `function.description` | str | **Obligatorisk**. Beskrivelse |
| `function.x_search_terms` | liste[str] | i18n-bevisste søkeord (omslutt med `_(...)`) |
| `function.x_search_terms_en` | liste[str] | Fikset engelske søkeord |
| `function.parameters` | dikt | Parameterdefinisjon (OpenAI-funksjonsoppkallingsformat) |

---

## 5. Internasjonalisering (i18n)

### Oversettelsesmekanisme

Å kalle `make_tool_translator(__file__)` laster oversettelser fra en `.json det samme filnavnet
med samme basenavn katalog.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Bruke oversettelsesnøkler

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

Se eksisterende `_tool.json`-filer for støttede språkkoder.⎏-#.⎏-# Feilsøking

### Syntakskontroll

```bash
python -m py_compile my_tool.py
```

### Bekreft verktøyinnlasting

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Feillogger

Feil under verktøyinnlasting skrives ut til stderr. Hvis verktøyet ditt ikke er lastet,
sjekk uag-oppstartsloggene.

---

## 7. Referanser Eksempler

### Python Tool Eksempler

- `date_calc_tool.py` (i `src/uagent/Datecalculation) —. Kopier eksternt og tilpass.
- `calculator_tool.py` (i `src/uagent/tools/`) — Calculator.

### Rustverktøyeksempler

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (in `rust-/src/) `rust_slugify_tool.py` + `uag_tools_rust.pyd` (i `src/uagent/tools_rust/`) — Slug-konvertering

Kopier filene `_tool.py` og `.pyd` til `UAGENT_EXTERNAL_TOOLS_DIRS` for å bruke dem som eksterne verktøy.
#
 Oppsettverktøy. Kataloger

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Flere kataloger kan skilles med `:` (Linux/macOS) eller `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (entall) støttes også for bakoverkompatibilitet.