# Guida alla creazione degli strumenti

Questa guida spiega come aggiungere i tuoi strumenti a uag **senza modificare uag stesso**.
Se desideri aggiungere uno strumento direttamente all'albero dei sorgenti di uag, vedere
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Sommario

1. [Struttura dello strumento di base](#1-struttura-dello-strumento-di-base)
2. [Creazione di uno strumento Python](#2-creazione-di-uno-strumento-python)
3. [Creazione di uno strumento Rust + Python](#3-creare-un-rust--strumento-python)
4. [Riferimento TOOL_SPEC](#4-riferimento-spec_utensile)
5. [Internazionalizzazione (i18n)](#5-internazionalizzazione-i18n)
6. [Test e debug](#6-test-e-debug)
7. [Esempi di riferimento](#7-esempi-di-riferimento)

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

 Più directory possono essere separate da `:` (Linux/macOS) o `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (singolare) è supportato anche per compatibilità con le versioni precedenti.

2. **Crea un file Python**

 Il nome del file è gratuito, ma è consigliata la denominazione `<nome>_tool.py` (ad esempio `my_tool.py`).

3. **Implementa gli elementi richiesti**

 - Dizionario `TOOL_SPEC`
 - Funzione `run_tool(args)`
 - Facoltativamente, un file JSON i18n

4. **Riavviare l'agente** (o eseguire lo strumento `system_reload`)

### Modello completo

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

Vedere la [Sezione 5](#5-internationalization-i18n) per i dettagli i18n.

---

## 3. Creazione di uno strumento Rust + Python

L'implementazione di Rust è ideale per attività critiche in termini di prestazioni (elaborazione di dati pesanti, crittografia, elaborazione di file, ecc.).
uag può caricare direttamente file `.pyd` precostruiti, quindi **gli utenti finali non hanno bisogno di `pip install`**.

### Struttura dello strumento

Uno strumento Rust è costituito da quanto segue files:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Per la distribuzione, posiziona i file `_tool.py` + `_tool.json` + `.pyd` in
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Passaggi

#### Passaggio 1: crea Rust project

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

#### Passaggio 2: implementazione di Rust (src/lib.rs)

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

**Punti chiave:**
- Espone le funzioni con `#[pyfunction(name = "run_<name>")]`
- Il tipo restituito è `PyResult<String>`
- Il nome della funzione `#[pymodule]` deve corrispondere al nome del crate (`my_rust_tools`)

#### Passo 3: Compila

```bash
cd my_rust_tool
cargo build --release
```

Windows: rinomina `target/release/my_rust_tools.dll` in `my_rust_tools.pyd`
Linux: rinomina `target/release/libmy_rust_tools.so` in `my_rust_tools.so`
macOS: rinominare `target/release/libmy_rust_tools.dylib` in `my_rust_tools.so`

Oppure usando maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Passo 4: Crea il wrapper Python

Crea `my_rust_tool.py` nella tua directory `UAGENT_EXTERNAL_TOOLS_DIRS`:

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

**``load_rust_pyd()`` ordine di risoluzione:**

1. Cerca `<nome_modulo>.pyd` (o `.so`) nella stessa directory del wrapper `.py`
2. Torna a un modulo installato su pip

#### Passaggio 5: distribuzione

Sono necessari solo questi 3 file. Gli utenti finali **non** necessitano di `pip install`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Note

- **Solo in fase di compilazione:** sono richiesti la toolchain Rust e `maturin`
 ```bash
  pip install maturin
  ```
- Il nome della cassa Rust (`[lib] name` in `Cargo.toml`) deve corrispondere al primo argomento di `load_rust_pyd()`
- Il nome del file wrapper e la posizione `.pyd` sono indipendenti purché si trovino nella stessa directory

---

## 4. TOOL_SPEC Reference

### Base Struttura

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

### Proprietà

| Campo | Digitare | Descrizione |
|-------|------|-------------|
| "tipo" | stra | Sempre `"funzione"` |
| `x_build` | stra | `"rust"` per l'implementazione Rust (omettere per Python) |
| `tool_genre` | stra | Nome del genere (facoltativo). Abilita il controllo basato sul genere |
| `livello_strumento` | int | 0=abilitato, 1=condizionale (predefinito), -1=disabilitato |
| `nome.funzione` | stra | **Necessario**. Nome dello strumento (minuscolo + cifre + carattere di sottolineatura) |
| `descrizione.funzione` | stra | **Necessario**. Descrizione |
| `function.x_search_terms` | lista[str] | Parole chiave di ricerca compatibili con i18n (a capo con `_(...)`) |
| `function.x_search_terms_en` | lista[str] | Risolte le parole chiave di ricerca in inglese |
| `parametri.funzione` | detto | Definizione dei parametri (formato di chiamata della funzione OpenAI) |

---

## 5. Internazionalizzazione (i18n)

### Meccanismo di traduzione

La chiamata a `make_tool_translator(__file__)` carica le traduzioni da un file `.json`
con lo stesso nome base nello stesso directory.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Utilizzo delle chiavi di traduzione

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Formato file JSON

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

Visualizza esistente File `_tool.json` per i codici lingua supportati.

---

## 6. Test e debug

### Controllo sintassi

```bash
python -m py_compile my_tool.py
```

### Strumento di verifica Caricamento

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Registri errori

Gli errori durante il caricamento dello strumento vengono stampati su stderr. Se il tuo strumento non è caricato,
controlla i log di avvio di uag.

---

## 7. Esempi di riferimento

### Esempi di strumenti Python

- `date_calc_tool.py` (in `src/uagent/tools/`) — Calcolo della data. Copia esternamente e personalizza.
- `calculator_tool.py` (in `src/uagent/tools/`) — Calcolatrice.

### Esempi di strumenti Rust

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (in `src/uagent/tools_rust/`) — UUID generation
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (in `src/uagent/tools_rust/`) — Conversione slug

Copia i file `_tool.py` e `.pyd` in `UAGENT_EXTERNAL_TOOLS_DIRS` per usarli come strumenti esterni.

### Configurazione esterna Directory degli strumenti

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