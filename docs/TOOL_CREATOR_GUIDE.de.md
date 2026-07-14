# Tool Creator Guide

In diesem Leitfaden wird erklärt, wie Sie Ihre eigenen Tools zu UAG hinzufügen, **ohne UAG selbst zu ändern**.
Wenn Sie ein Tool direkt zum UAG-Quellbaum hinzufügen möchten, siehe
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Inhaltsverzeichnis

1. [Grundlegende Werkzeugstruktur](#1-grundlegende-Werkzeugstruktur)
2. [Erstellen eines Python-Tools](#2-Erstellen eines Python-Tools)
3. [Ein Rust + Python-Tool erstellen](#3-creating-a-rust--python-tool)
4. [TOOL_SPEC-Referenz](#4-tool_spec-reference)
5. [Internationalisierung (i18n)](#5-internationalisierung-i18n)
6. [Testen und Debuggen](#6-Testen-und-Debuggen)
7. [Referenzbeispiele](#7-reference-examples)

---

## 1. Grundlegende Werkzeugstruktur

Ein Werkzeug besteht aus den folgenden Elementen:

| Element | Erforderlich | Beschreibung |
|---------|----------|-------------|
| `TOOL_SPEC` | Ja | Wörterbuch, das den Namen, die Beschreibung und die Parameter des Tools definiert |
| `run_tool(args)` | Ja | Funktion, die beim Aufruf des Tools ausgeführt wird. Args ist ein Diktat, return ist ein String. |
| i18n JSON | Empfohlen | JSON-Übersetzungsdatei (gleicher Basisname, „<name>_tool.json“) |

### Minimales Python-Tool

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

## 2. Erstellen eines Python-Tools

### Schritte

1. **Legen Sie die Umgebungsvariable „UAGENT_EXTERNAL_TOOLS_DIRS“ fest** (falls nicht bereits festgelegt)

 Beispiel:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Mehrere Verzeichnisse können durch „:“ (Linux/macOS) oder „;“ (Windows) getrennt werden.
 „UAGENT_EXTERNAL_TOOLS_DIR“ (Singular) wird aus Gründen der Abwärtskompatibilität ebenfalls unterstützt.

2. **Erstellen Sie eine Python-Datei**

 Der Dateiname ist frei, aber die Benennung „<name>_tool.py“ wird empfohlen (z. B. „my_tool.py“).

3. **Implementieren Sie die erforderlichen Elemente**

 – „TOOL_SPEC“-Wörterbuch
 – „run_tool(args)“-Funktion
 – Optional eine i18n-JSON-Datei

4. **Starten Sie den Agenten neu** (oder führen Sie das Tool „system_reload“ aus)

### Vollständige Vorlage

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

Siehe [Abschnitt 5](#5-internationalization-i18n) für i18n Details.

---

## 3. Erstellen eines Rust + Python-Tools

Die Rust-Implementierung ist ideal für leistungskritische Aufgaben (intensive Datenverarbeitung, Kryptografie, Dateiverarbeitung usw.).
uag kann vorgefertigte „.pyd“-Dateien direkt laden, sodass **Endbenutzer kein „pip“ benötigen install`**.

### Tool-Struktur

Ein Rust-Tool besteht aus den folgenden Dateien:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Platzieren Sie zur Verteilung die Dateien „_tool.py“ + „_tool.json“ + „.pyd“. in
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Schritte

#### Schritt 1: Erstellen Sie den Rust project

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

#### Schritt 2: Rust-Implementierung (src/lib.rs)

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

**Wichtige Punkte:**
- Funktionen mit „#[pyfunction(name = "run_<name>")]“ verfügbar machen
- Rückgabetyp ist „PyResult<String>“
- Der Funktionsname „#[pymodule]“ muss mit der Kiste übereinstimmen Name (`my_rust_tools`)

#### Schritt 3: Erstellen

```bash
cd my_rust_tool
cargo build --release
```

Windows: „target/release/my_rust_tools.dll“ in „my_rust_tools.pyd“ umbenennen
Linux: umbenennen `target/release/libmy_rust_tools.so` zu `my_rust_tools.so`
macOS: benennen Sie `target/release/libmy_rust_tools.dylib` zu `my_rust_tools.so` um

Oder mit maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Schritt 4: Erstellen Sie den Python-Wrapper

Erstellen Sie `my_rust_tool.py` in Ihrem `UAGENT_EXTERNAL_TOOLS_DIRS`-Verzeichnis:

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

**``load_rust_pyd()`` Auflösungsreihenfolge:**

1. Suchen Sie nach `<module_name>.pyd` (oder `.so`) im selben Verzeichnis wie der Wrapper `.py`
2. Auf ein von pip installiertes Modul zurückgreifen

#### Schritt 5: Verteilung

Nur diese 3 Dateien werden benötigt. Endbenutzer benötigen **keine** „Pip-Installation“.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Hinweise

- **Nur zur Build-Zeit:** Rust-Toolchain und „Maturin“ sind erforderlich.
 ```bash
  pip install maturin
  ```
- Der Name der Rust-Kiste („[lib] Name“ in „Cargo.toml“) muss mit dem ersten Argument von „load_rust_pyd()“ übereinstimmen
- Der Wrapper-Dateiname und der Speicherort „.pyd“ sind unabhängig, solange sie sich im selben Verzeichnis befinden

---

## 4. TOOL_SPEC-Referenz

### Grundlegende Struktur

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

### Eigenschaften

| Feld | Geben Sie | ein Beschreibung |
|-------|------|-------------|
| „Typ“ | str | Immer „Funktion“ |
| `x_build` | str | „rust“ für die Rust-Implementierung (bei Python weglassen) |
| `tool_genre` | str | Genrename (optional). Ermöglicht die genrebasierte Steuerung |
| `tool_level` | int | 0=aktiviert, 1=bedingt (Standard), -1=deaktiviert |
| `Funktionsname` | str | **Erforderlich**. Werkzeugname (Kleinbuchstaben + Ziffern + Unterstrich) |
| `function.description` | str | **Erforderlich**. Beschreibung |
| `function.x_search_terms` | list[str] | i18n-fähige Suchschlüsselwörter (mit „_(...)“ umschließen) |
| `function.x_search_terms_en` | list[str] | Die englischen Suchbegriffe |
| `function.parameters` | diktieren | Parameterdefinition (OpenAI-Funktionsaufrufformat) |

---

## 5. Internationalisierung (i18n)

### Übersetzungsmechanismus

Der Aufruf von „make_tool_translator(__file__)“ lädt Übersetzungen aus einer „.json“-Datei
mit demselben Basisnamen in dieselbe Verzeichnis.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Verwendung von Übersetzungsschlüsseln

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON-Datei Format

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

Unterstützte Sprachcodes finden Sie in den vorhandenen `_tool.json`-Dateien.

---

## 6. Testen und Debuggen

### Syntax Überprüfen Sie

```bash
python -m py_compile my_tool.py
```

### Überprüfen Sie das Laden des Werkzeugs

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Fehlerprotokolle

Fehler beim Laden des Tools werden auf stderr ausgegeben. Wenn Ihr Tool nicht geladen ist,
überprüfen Sie die UAG-Startprotokolle.

---

## 7. Referenzbeispiele

### Python-Tool-Beispiele

- `date_calc_tool.py` (in `src/uagent/tools/`) – Datumsberechnung. Extern kopieren und anpassen.
- `calculator_tool.py` (in `src/uagent/tools/`) – Rechner.

### Rust Tool-Beispiele

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (in `src/uagent/tools_rust/`) – UUID generation
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (in `src/uagent/tools_rust/`) – Slug-Konvertierung

Kopieren Sie die Dateien `_tool.py` und `.pyd` in `UAGENT_EXTERNAL_TOOLS_DIRS`, um sie als extern zu verwenden tools.

### Einrichten externer Tool-Verzeichnisse

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Mehrere Verzeichnisse können durch „:“ (Linux/macOS) oder „;“ (Windows) getrennt werden.
„UAGENT_EXTERNAL_TOOLS_DIR“ (Singular) wird aus Gründen der Abwärtskompatibilität ebenfalls unterstützt.