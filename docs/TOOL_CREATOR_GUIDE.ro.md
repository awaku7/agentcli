# Ghid pentru creatorul de instrumente

Acest ghid explică cum să adăugați propriile instrumente la uag **fără a modifica uag în sine**.
Dacă doriți să adăugați un instrument direct în arborele sursă uag, vezi
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Cuprins

1. [Structură de bază a instrumentului](#1-structură-de-bază-instrument)
2. [Crearea unui instrument Python](#2-crearea-un-instrument-python)
3. [Crearea unui instrument Rust + Python](#3-crearea-o-rugină--python-tool)
4. [TOOL_SPEC Reference](#4-tool_spec-reference)
5. [Internaționalizare (i18n)](#5-internaționalizare-i18n)
6. [Testare și depanare](#6-testare-și-depanare)
7. [Exemple de referință](#7-exemple-de-referință)

---

## 1. Structura de bază a instrumentului

Un instrument este format din următoarele elemente:

| Element | Necesar | Descriere |
|----------|----------|--------------|
| `TOOL_SPEC` | Da | Dicționar care definește numele instrumentului, descrierea și parametrii |
| `run_tool(args)` | Da | Funcție executată atunci când instrumentul este apelat. Args este un dict, return este un șir. |
| i18n JSON | Recomandat | Traducere fișier JSON (același nume de bază, `<name>_tool.json`) |

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

## 2. Crearea unui instrument Python

### Pași

1. **Setați variabila de mediu `UAGENT_EXTERNAL_TOOLS_DIRS`** (dacă nu este deja setată)

   Exemplu:
   ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

   Mai multe directoare pot fi separate prin `:` (Linux/macOS) sau `;` (Windows).
   `UAGENT_EXTERNAL_TOOLS_DIR` (singular) este de asemenea acceptat pentru compatibilitate cu versiunea anterioară.

2. **Creați un fișier Python**

   Numele fișierului este gratuit, dar se recomandă denumirea `<name>_tool.py` (de exemplu, `my_tool.py`).

3. **Implementați elementele necesare**

   - Dicționar `TOOL_SPEC`
   - Funcția `run_tool(args)`
   - Opțional, un fișier JSON i18n

4. **Reporniți agentul** (sau rulați instrumentul `system_reload`)

### Șablon complet
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

Consultați [Secțiunea 5](#5-internationalization-i18n) pentru detalii i18n.

---

## 3. Crearea unui instrument Rust + Python

Implementarea Rust este ideală pentru sarcini critice pentru performanță (procesare grea de date, criptare, procesare fișiere etc.).
uag poate încărca fișiere `.pyd` pre-construite direct, astfel încât **utilizatorii finali nu au nevoie de `pip install`**.

### Structura instrumentului

Un instrument Rust constă din următoarele fișiere:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Pentru distribuire, plasați fișierele `_tool.py` + `_tool.json` + `.pyd` în 
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Pași

#### Pasul 1: Creați proiectul Rust

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

#### Pasul 2: Implementarea Rust (src/lib.rs)

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

**Puncte cheie:**
- Expune funcțiile cu `#[pyfunction(name = "run_<name>")]`
- Tipul de returnare este `PyResult<String>`
- Numele funcției `#[pymodule]` trebuie să se potrivească cu numele cutiei (`my_rust_tools`)

#### Pasul 3: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: redenumiți `target/release/my_rust_tools.dll` în `my_rust_tools.pyd`
Linux: redenumiți `target/release/libmy_rust_tools.so` în `my_rust_tools.so`
macOS: redenumiți `target/release/libmy_rust_tools.dylib` în `my_rust_tools.so`

Sau utilizând maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Pasul 4: Creați wrapper-ul Python

Creați `my_rust_tool.py` în directorul `UAGENT_EXTERNAL_TOOLS_DIRS`:

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

**``load_rust_pyd()`` ordine de rezoluție:**

1. Căutați `<module_name>.pyd` (sau `.so`) în același director cu wrapper-ul `.py`
2. Reveniți la un modul instalat prin pip

#### Pasul 5: Distribuție

Sunt necesare doar aceste 3 fișiere. Utilizatorii finali **nu** au nevoie de nicio `pip install`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Note

- **Numai în timpul construirii:** Rust toolchain și `maturin` sunt necesare
  ```bash
  pip install maturin
  ```
- Numele cutiei Rust (`[lib] name` în `Cargo.toml`) trebuie să se potrivească cu primul argument al lui `load_rust_pyd()`
- Numele fișierului wrapper și locația `.pyd` sunt independente atâta timp cât se află în același director

---

## 4. TOOL_SPEC Reference

### Structura de bază

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

### Proprietăți

| Câmp | Tip | Descriere |
|--------|------|--------------|
| `type` | str | Întotdeauna `"function"` |
| `x_build` | str | `"rust"` pentru implementarea Rust (omiteți pentru Python) |
| `tool_genre` | str | Numele genului (opțional). Activează controlul bazat pe gen |
| `tool_level` | int | 0=activat, 1=condițional (implicit), -1=dezactivat |
| `function.name` | str | **Necesar**. Numele instrumentului (minuscule + cifre + literă de subliniere) |
| `function.description` | str | **Necesar**. Descriere |
| `function.x_search_terms` | list[str] | Cuvinte cheie de căutare i18n-aware (înfășurați cu `_(...)`) |
| `function.x_search_terms_en` | list[str] | Cuvinte cheie de căutare în engleză fixate |
| `function.parameters` | dict | Definiție parametru (format de apelare a funcției OpenAI) |

---

## 5. Internaționalizare (i18n)

### Mecanism de traducere

Apelarea `make_tool_translator(__file__)` încarcă traduceri dintr-un fișier `.json`
cu același nume de bază în același director.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Utilizarea tastelor de traducere

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Format fișier JSON

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

Consultați fișierele `_tool.json` existente pentru codurile de limbă acceptate.

---

## 6. Testare și depanare

### Verificare sintaxă

```bash
python -m py_compile my_tool.py
```

### Verificați încărcarea instrumentului

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Jurnale de erori

Erorile în timpul încărcării instrumentului sunt tipărite în stderr. Dacă instrumentul dvs. nu este încărcat,
verificați jurnalele de pornire uag.

---

## 7. Exemple de referință

### Exemple de instrumente Python

- `date_calc_tool.py` (în `src/uagent/tools/`) — Calcul date. Copiați extern și personalizați.
- `calculator_tool.py` (în `src/uagent/tools/`) — Calculator.

### Exemple de instrumente Rust

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (în `src/uagent/tools_rust/`) — Generare UUID
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (în `src/uagent/tools_rust/`) — Conversie slug

Copiați fișierele `_tool.py` și `.pyd` în `UAGENT_EXTERNAL_TOOLS_DIRS` pentru a le utiliza ca instrumente externe.

### Configurarea directoarelor de instrumente externe

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Mai multe directoare pot fi separate prin `:` (Linux/macOS) sau `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (singular) este de asemenea acceptat pentru compatibilitate cu versiunea anterioară.

---

*Această traducere a fost generată automat. Pentru conținutul cel mai exact și actualizat, vă rugăm să consultați versiunea în limba engleză.*