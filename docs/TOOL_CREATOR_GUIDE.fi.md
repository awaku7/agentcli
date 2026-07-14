# Tool Creator Guide

Tämä opas selittää, kuinka voit lisätä omia työkaluja uag:iin **muokkamatta itse uag:ia**.
Jos haluat lisätä työkalun suoraan uag-lähdepuuhun, katso
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Sisällysluettelo
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Basic Tool Structure](#1-basic-tool-structure)
2. [Python-työkalun luominen](#2-creating-a-python-tool)
3. [Creating a Rust + Python Tool](#3-creating-a-rust--python-tool)
4. [TOOL_SPEC Reference](#4-tool_spec-reference)
5. [Kansainvälistyminen (i18n)](#5-internationalization-i18n)
6. [Testaus ja virheenkorjaus](#6-testing-and-debugging)
7. [Viiteesimerkit](#7-reference-examples)

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


## 1. Perustyökalurakenne

Työkalu koostuu seuraavista elementeistä:

| Elementti | Pakollinen | Kuvaus |
|---------|-----------|--------------|
| TOOL_SPEC | Kyllä | Sanakirja, joka määrittää työkalun nimen, kuvauksen ja parametrit |
| "run_tool(args)" | Kyllä | Toiminto suoritetaan, kun työkalua kutsutaan. Args on sanelu, paluu on merkkijono. |
| i18n JSON | Suositeltava | Käännös JSON-tiedosto (sama perusnimi, `<nimi>_tool.json`) |

### Minimaalinen Python-työkalu
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

## 2. Python-työkalun luominen

#### Vaiheet1. **Aseta `UAGENT_EXTERNAL_TOOLS_DIRS`-ympäristömuuttuja** (jos sitä ei ole jo asetettu)

 Esimerkki:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Useita hakemistoja voidaan erottaa `:` (Linux/macOS) tai `;` (Windows) merkillä.
 (yksikkö) tukee myös taaksepäin yhteensopivuutta.

2. **Luo Python-tiedosto**

 Tiedoston nimi on ilmainen, mutta `<nimi>_tool.py`-nimeämistä suositellaan (esim. `my_tool.py`).

3. **Ota käyttöön vaaditut elementit**

 - TOOL_SPEC-sanakirja
 - Run_tool(args) -toiminto
 - Valinnaisesti i18n JSON-tiedosto

4. **Käynnistä agentti uudelleen** (tai suorita `system_reload`-työkalu)

### Täysi malli
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

Katso [osio 5](#5-internationalization-i18n) saadaksesi Pyynnön tiedot. Tool

Rust-toteutus sopii erinomaisesti suorituskykykriittisiin tehtäviin (raskas tietojenkäsittely, kryptografia, tiedostojen käsittely jne.).
uag voi ladata valmiita .pyd-tiedostoja suoraan, joten **loppukäyttäjät eivät tarvitse pip-asennusta**.

### Tool Structure
-työkalu koostuu seuraavasta Rust-työkalusta tiedostot:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Jakelua varten sijoita tiedostot `_tool.py` + `_tool.json` + `.pyd` kansioon
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Vaiheet
### Vaihe 1: Luo Rust ###
# projekti

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

#### Vaihe 2: Rust-toteutus (src/lib.rs)

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
- Paljasta funktiot komennolla `#[pyfunction(name = "run_<name>")]`
- Palautustyyppi on `PyResult<String>`
- `#[pymodule]`-funktion nimen on vastattava laatikon nimeä (`my_rust_tools`)

#### Vaihe 3: Koonti

```bash
cd my_rust_tool
cargo build --release
```

Windows: nimeä `target/release/my_rust_tools.dll` uudelleen muotoon my_rust_tools.pyd`
Linux: nimeä `target/release/libmy_rust_tools.so` uudelleen `my_rust_tools.so`
macOS: nimeä `target/release/libmy_rust_tools.dylib` uudelleen muotoon `my_rust_tools.so`

Tai käytä maturiinia:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```


Create Step
4:#### `my_rust_tool.py` UAGENT_EXTERNAL_TOOLS_DIRS-hakemistossasi:

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

**``load_rust_pyd()`` resoluutiojärjestys:**

1. Etsi `<moduulin_nimi>.pyd` (tai `.so`) samasta hakemistosta kuin kääre `.py`
2. Palaa takaisin pip-asennettuun moduuliin

#### Vaihe 5: Jakelu

Vain nämä 3 tiedostoa tarvitaan. Loppukäyttäjät **eivät** tarvitse `pip-asennusta`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Huomautuksia

- **Vain rakennusaika:** Ruostetyökaluketju ja `maturiini` vaaditaan
 ```bash
  pip install maturin
  ```
`-nimi `Cargo.toml`) on vastattava parametrin `load_rust_pyd()
 ensimmäistä argumenttia. Kääritystiedoston nimi ja .pyd-sijainti ovat riippumattomia, kunhan ne ovat samassa hakemistossa

---

## 4. TOOL_SPEC Reference

### Basic Rakenne

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

### Ominaisuudet

| Kenttä | Tyyppi | Kuvaus |
|-------|------|--------------|
| "tyyppi" | str | Aina `"toiminto"` |
| "x_build" | str | `"rust"` Rust-toteutukseen (jätä pois Pythonille) |
| työkalu_genre | str | Genren nimi (valinnainen). Ottaa käyttöön genrepohjaisen ohjauksen |
| `työkalutaso` | int | 0=käytössä, 1=ehdollinen (oletus), -1=pois käytöstä |
| `funktio.nimi` | str | **Pakollinen**. Työkalun nimi (pienet kirjaimet + numerot + alaviiva) |
| `function.description` | str | **Pakollinen**. Kuvaus |
| `function.x_search_terms` | lista[str] | i18n-aware hakusanat (wrap with `_(...)`) |
| `function.x_search_terms_en` | lista[str] | Kiinteät englanninkieliset hakusanat |
| `function.parameters` | sanella | Parametrimäärittely (OpenAI-funktion kutsumuoto) |

---

## 5. Kansainvälistäminen (i18n)

### Käännösmekanismi

Kutsumalla `make_tool_translator(__file__)` ladataan käännökset perustiedostosta
samassa nimellä.json hakemistoon.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Käännösavaimien käyttäminen

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON-tiedostomuoto

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

Katso tuetut kielitiedostot. koodit.

---

## 6. Testaus ja virheenkorjaus

### Syntaksin tarkistus

```bash
python -m py_compile my_tool.py
```

### Tarkista työkalun lataus

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Virhelokit

Työkalun lataus tulostetaan stderr-tiedostoon. Jos työkaluasi ei ole ladattu,
tarkista uag-käynnistyslokit.

---

## 7. Viiteesimerkit

### Python-työkaluesimerkit

- `date_calc_tool.py` (kohdassa `src/uagent) — Dateooltes. Kopioi ulkoisesti ja mukauta.
- `calculator_tool.py` (kohdassa `src/uagent/tools/`) — Laskin.

### Rust Tool Esimerkkejä

- `rust_uuid_gen_tool.py` + `uag_tools`_rust.pyd `src/uagent/tools_rust/`) — UUID-sukupolvi
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (kansiossa `src/uagent/tools_rust/`) — Slug-muunnos

Kopioi `_tool.pyd- ja `_tool.pyd-tiedostot. `UAGENT_EXTERNAL_TOOLS_DIRS' käyttääksesi niitä ulkoisina työkaluina.

### Ulkoisten työkaluhakemistojen määrittäminen

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Useita hakemistoja voidaan erottaa merkillä `:` (Linux/macOS) tai `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (yksikkö) tukee myös taaksepäin yhteensopivuutta.

---

*Tämä käännös luotiin automaattisesti. Tarkimman ja ajantasaisimman sisällön saat englanninkielisestä versiosta.*