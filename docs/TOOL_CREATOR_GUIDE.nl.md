# Tool Creator Guide

In deze handleiding wordt uitgelegd hoe u uw eigen tools aan uag kunt toevoegen **zonder uag zelf te wijzigen**.
Als u een tool rechtstreeks aan de uag-bronstructuur wilt toevoegen, zie
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Inhoudsopgave
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Basistoolstructuur](#1-basistoolstructuur)
2. [Een Python-tool maken](#2-creating-a-python-tool)
3. [Een Rust- en Python-tool maken](#3-creating-a-rust--python-tool)
4. [TOOL_SPEC-referentie](#4-tool_spec-reference)
5. [Internationalisering (i18n)](#5-internationalisering-i18n)
6. [Testen en foutopsporing](#6-testing-and-debugging)
7. [Referentievoorbeelden](#7-reference-examples)

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


## 1. Basistoolstructuur

Een tool bestaat uit de volgende elementen:

| Element | Vereist | Beschrijving |
|---------|----------|------------|
| `TOOL_SPEC` | Ja | Woordenboek dat de naam, beschrijving en parameters van het gereedschap definieert |
| `run_tool(args)` | Ja | Functie die wordt uitgevoerd wanneer het gereedschap wordt aangeroepen. Args is een dictaat, return is een string. |
| i18n JSON | Aanbevolen | JSON-vertaalbestand (dezelfde basisnaam, `<naam>_tool.json`) |

### Minimale Python-tool

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

## 2. Een Python-tool maken

### Stappen

1. **Stel de omgevingsvariabele `UAGENT_EXTERNAL_TOOLS_DIRS` in (indien nog niet ingesteld)

 Voorbeeld:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Meerdere mappen kunnen worden gescheiden door `:` (Linux/macOS) of `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (enkelvoud) wordt ook ondersteund voor achterwaartse compatibiliteit.

2. **Maak een Python-bestand**

 De bestandsnaam is gratis, maar de naam `<naam>_tool.py` wordt aanbevolen (bijvoorbeeld `my_tool.py`).

3. **Implementeer de vereiste elementen**

 - `TOOL_SPEC` woordenboek
 - `run_tool(args)` functie
 - Optioneel een i18n JSON-bestand

4. **Start de agent opnieuw** (of voer de `system_reload` tool uit)

### Volledige sjabloon

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

Zie [Sectie 5](#5-internationalization-i18n) voor i18n-details.

---

## 3. Een Rust + Python-tool maken

Rust-implementatie is ideaal voor prestatiekritieke taken (zware gegevensverwerking, cryptografie, bestandsverwerking, enz.).
uag kan vooraf gebouwde `.pyd`-bestanden rechtstreeks laden, dus **eindgebruikers hebben geen `pip-installatie`** nodig.

### Toolstructuur

Een Rust-tool bestaat uit het volgende bestanden:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Voor distributie plaatst u de `_tool.py` + `_tool.json` + `.pyd` bestanden in
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Stappen

#### Stap 1: Maak de Rust project

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

#### Stap 2: Rust-implementatie (src/lib.rs)

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

**Belangrijkste punten:**
- Stel functies bloot met `#[pyfunction(name = "run_<naam>")]`
- Retourtype is `PyResult<String>`
 - De functienaam `#[pymodule]` moet overeenkomen met de kratnaam (`my_rust_tools`)

#### Stap 3: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: hernoem `target/release/my_rust_tools.dll` naar `my_rust_tools.pyd`
Linux: hernoem `target/release/libmy_rust_tools.so` naar `my_rust_tools.so`
macOS: hernoem `target/release/libmy_rust_tools.dylib` naar `my_rust_tools.so`

Of gebruik maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Stap 4: Maak de Python-wrapper

Maak `my_rust_tool.py` in uw map `UAGENT_EXTERNAL_TOOLS_DIRS`:

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

**``load_rust_pyd()``resolutievolgorde:**

1. Zoek naar `<module_name>.pyd` (of `.so`) in dezelfde map als de wrapper `.py`
2. Terugvallen op een door pip geïnstalleerde module

#### Stap 5: Distributie

Alleen deze 3 bestanden zijn nodig. Eindgebruikers hebben **geen** een `pip-installatie` nodig.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Opmerkingen

- **Alleen bouwtijd:** Rust toolchain en `maturin` zijn vereist
 ```bash
  pip install maturin
  ```
- De naam van de Rust-krat (`[lib] naam` in `Cargo.toml`) moet overeenkomen met het eerste argument van `load_rust_pyd()`
- De wrapperbestandsnaam en `.pyd` locatie zijn onafhankelijk zolang ze zich in dezelfde map bevinden

---

## 4. TOOL_SPEC-referentie

### Basis Structuur

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

### Eigenschappen

| Veld | Typ | Beschrijving |
|-------|------|-------------|
| `type` | str | Altijd `"functie"` |
| `x_build` | str | `"rust"` voor Rust-implementatie (weglaten voor Python) |
| `tool_genre` | str | Genrenaam (optioneel). Maakt op genre gebaseerde besturing mogelijk |
| `tool_niveau` | int | 0=ingeschakeld, 1=voorwaardelijk (standaard), -1=uitgeschakeld |
| `functie.naam` | str | **Vereist**. Gereedschapsnaam (kleine letters + cijfers + onderstrepingsteken) |
| `functie.beschrijving` | str | **Vereist**. Beschrijving |
| `function.x_search_terms` | lijst[str] | i18n-bewuste zoekwoorden (wrap met `_(...)`) |
| `function.x_search_terms_en` | lijst[str] | Vaste Engelse zoekwoorden |
| `functie.parameters` | dicteer | Parameterdefinitie (OpenAI-functieaanroepformaat) |

---

## 5. Internationalisering (i18n)

### Vertaalmechanisme

Het aanroepen van `make_tool_translator(__file__)` laadt vertalingen uit een `.json`-bestand
met dezelfde basisnaam in dezelfde map.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Vertaalsleutels gebruiken

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON-bestandsindeling

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

Bestaande bekijken `_tool.json`-bestanden voor ondersteunde taalcodes.

---

## 6. Testen en debuggen

### Syntaxiscontrole

```bash
python -m py_compile my_tool.py
```

### Verify Tool Laden

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Foutlogboeken

Fouten tijdens het laden van gereedschap worden afgedrukt naar stderr. Als uw tool niet is geladen,
controleer dan de uag-opstartlogboeken.

---

## 7. Referentievoorbeelden

### Voorbeelden van Python-tools

- `date_calc_tool.py` (in `src/uagent/tools/`) — Datumberekening. Extern kopiëren en aanpassen.
- `calculator_tool.py` (in `src/uagent/tools/`) — Rekenmachine.

### Voorbeelden van Rust Tool

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (in `src/uagent/tools_rust/`) — UUID-generatie
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (in `src/uagent/tools_rust/`) — Slug-conversie

Kopieer de bestanden `_tool.py` en `.pyd` naar `UAGENT_EXTERNAL_TOOLS_DIRS` om ze als externe tools te gebruiken.

### Externe tool instellen Mappen

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Meerdere mappen kunnen worden gescheiden door `:` (Linux/macOS) of `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (enkelvoud) wordt ook ondersteund voor achterwaartse compatibiliteit.