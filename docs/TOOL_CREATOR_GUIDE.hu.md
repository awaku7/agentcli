# Tool Creator Guide

Ez az útmutató elmagyarázza, hogyan adhat hozzá saját eszközöket az uag-hoz **magának az uagnak a módosítása nélkül**.
Ha egy eszközt közvetlenül az uag forrásfához szeretne hozzáadni, lásd:
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Tartalomjegyzék
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Basic Tool Structure](#1-basic-tool-structure)
2. [Python-eszköz létrehozása](#2-creating-a-python-tool)
3. [Creating a Rust + Python Tool](#3-creating-a-rust--python-tool)
4. [TOOL_SPEC Reference](#4-tool_spec-reference)
5. [Internationalization (i18n)](#5-internationalization-i18n)
6. [Tesztelés és hibakeresés](#6-testing-and-debugging)
7. [Referencia példák](#7-reference-examples)

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


## 1. Alapvető eszközstruktúra

Egy eszköz a következő elemekből áll:

| Elem | Kötelező | Leírás |
|---------|-----------|-------------|
| `TOOL_SPEC` | Igen | Az eszköz nevét, leírását és paramétereit meghatározó szótár |
| `run_tool(args)` | Igen | A funkció a szerszám meghívásakor kerül végrehajtásra. Az Args egy diktatúra, a return egy szál. |
| i18n JSON | Ajánlott | JSON-fájl fordítása (ugyanaz az alapnév, `<név>_tool.json`) |

### Minimális Python-eszköz
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

## 2. Python-eszköz létrehozása

### Lépések

1. **Állítsa be az `UAGENT_EXTERNAL_TOOLS_DIRS` környezeti változót** (ha még nincs beállítva)

   Példa:
   ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

   Több könyvtár is elválasztható a `:` (Linux/macOS) vagy `;` (Windows) karakterekkel.
   `UAGENT_EXTERNAL_TOOLS_DIR` (egyes szám) is támogatott a visszafelé kompatibilitás érdekében.

2. **Hozzon létre Python-fájlt**

   A fájlnév ingyenes, de a `<név>_tool.py` elnevezés javasolt (pl. `my_tool.py`).

3. **Végezze be a szükséges elemeket**

   - `TOOL_SPEC` szótár
   - `run_tool(args)` függvény
   - Opcionálisan i18n JSON fájl

4. **Indítsa újra az ügynököt** (vagy futtassa a `system_reload` eszközt)

### Teljes sablon
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

Az i18n részleteiért lásd az [5. szakaszt](#5-internationalization-i18n).

---

## 3. Creating a Rust + Python Tool

Rust implementáció ideális a teljesítménykritikus feladatokhoz (nehéz adatfeldolgozás, kriptográfia, fájlfeldolgozás stb.).
Az uag közvetlenül képes betölteni előre elkészített `.pyd` fájlokat, így a **végfelhasználóknak nincs szükségük `pip install`**-ra.

### Eszközstruktúra

A Rust eszköz a következő fájlokból áll:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

A terjesztéshez helyezze el a `_tool.py` + `_tool.json` + `.pyd` fájlokat a 
`UAGENT_EXTERNAL_TOOLS_DIRS` mappába.

### Lépések

#### 1. lépés: A Rust projekt létrehozása

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

#### 2. lépés: Rust implementáció (src/lib.rs)

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

**Fontos pontok:**
- Tegye közzé a függvényeket a következővel: `#[pyfunction(name = "run_<name>")]`
- A visszatérési típus: `PyResult<String>`
- A `#[pymodule]` függvény nevének meg kell egyeznie a láda nevével (`my_rust_tools`)

#### 3. lépés: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: nevezze át a `target/release/my_rust_tools.dll` fájlt `my_rust_tools.pyd`-re.
Linux: nevezze át a `target/release/libmy_rust_tools.so` fájlt `my_rust_tools.so`
macOS: nevezze át a `target/release/libmy_rust_tools.dylib`-et `my_rust_tools.so`

Vagy a maturin használatával:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### 4. lépés: A Python burkoló létrehozása

Hozza létre a `my_rust_tool.py` fájlt az `UAGENT_EXTERNAL_TOOLS_DIRS` könyvtárában:

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

**``load_rust_pyd()`` felbontási sorrend:**

1. Keresse a `<modul_name>.pyd` (vagy `.so`) könyvtárat ugyanabban a könyvtárban, mint a `.py`
2. Térjen vissza egy pip-telepített modulhoz

#### 5. lépés: Terjesztés

Csak erre a 3 fájlra van szükség. A végfelhasználóknak **nincs** szükségük `pip telepítésre`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Megjegyzések

- **Csak építési idő:** A Rust toolchain és a `maturin` szükséges
  ```bash
  pip install maturin
  ```
- A Rust láda nevének (`[lib] name` a `Cargo.toml`-ban) meg kell egyeznie a `load_rust_pyd()` első argumentumával
- A burkolófájl neve és a `.pyd` helye független mindaddig, amíg ugyanabban a könyvtárban vannak

---

## 4. TOOL_SPEC Reference

### Alapvető szerkezet

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

### Tulajdonságok

| Mező | Típus | Leírás |
|-------|------|--------------|
| `type` | str | Mindig `"function"` |
| `x_build` | str | `"rust"` Rust implementációhoz (Python esetén kihagyja) |
| `tool_genre` | str | Műfaj neve (nem kötelező). Műfajalapú vezérlést tesz lehetővé |
| `tool_level` | int | 0=engedélyezett, 1=feltételes (alapértelmezett), -1=letiltva |
| `function.name` | str | **Kötelező**. Eszköz neve (kisbetű + számjegyek + aláhúzás) |
| `function.description` | str | **Kötelező**. Leírás |
| `function.x_search_terms` | lista[str] | i18n-aware keresési kulcsszavak (wrap with `_(...)`) |
| `function.x_search_terms_en` | lista[str] | Javított angol keresési kulcsszavak |
| `function.parameters` | dict | Paraméter definíció (OpenAI függvényhívási formátum) |

---

## 5. Nemzetköziesítés (i18n)

### Fordítási mechanizmus

A `make_tool_translator(__file__)` meghívása betölti a fordításokat egy `.json` fájlból
ugyanazzal az alapnévvel ugyanabban a könyvtárban.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Fordítási kulcsok használata

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON fájlformátum

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

A támogatott nyelvkódokért tekintse meg a meglévő `_tool.json` fájlokat.

---

## 6. Tesztelés és hibakeresés

### Szintaxis ellenőrzés

```bash
python -m py_compile my_tool.py
```

### Az eszköz betöltésének ellenőrzése

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Hibanaplók

Az eszközbetöltés során fellépő hibák az stderr-be kerülnek. Ha az eszköz nincs betöltve,
ellenőrizze az uag indítási naplóit.

---

## 7. Referencia példák

### Python Tool Példák

- `date_calc_tool.py` (a `src/uagent/tools/` könyvtárban) — Dátum számítás. Másolja ki és testreszabhatja.
- `calculator_tool.py` (az `src/uagent/tools/` könyvtárban) — Számológép.

### Rust Tool Példák

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (a `src/uagent/tools_rust/` könyvtárban) — UUID generálás
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (az `src/uagent/tools_rust/` könyvtárban) — Slug konverzió

Másolja a `_tool.py` és `.pyd` fájlokat a `UAGENT_EXTERNAL_TOOLS_DIRS`-be, hogy külső eszközként használhassa őket.

### Külső eszközkönyvtárak beállítása

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Több könyvtárat elválaszthat `:` (Linux/macOS) vagy `;` karakterrel. (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (egyes szám) szintén támogatott a visszafelé kompatibilitás érdekében.

---

*Ez a fordítás automatikusan létrejött. A legpontosabb és legfrissebb tartalomért kérjük, olvassa el az angol verziót.*