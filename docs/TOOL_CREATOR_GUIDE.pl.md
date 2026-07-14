# Przewodnik po kreatorze narzędzi

Ten przewodnik wyjaśnia, jak dodać własne narzędzia do uag **bez modyfikowania samego uag**.
Jeśli chcesz dodać narzędzie bezpośrednio do drzewa źródeł uag, zobacz
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Spis treści

1. [Podstawowa struktura narzędzia](#1-podstawowa-struktura-narzędzia)
2. [Tworzenie narzędzia Python](#2-creating-a-python-tool)
3. [Tworzenie narzędzia Rust + Python](#3-creating-a-rust--python-tool)
4. [Odniesienie do TOOL_SPEC](#4-odniesienie-do-specyfikacji-narzędzia)
5. [Internacjonalizacja (i18n)](#5-internacjonalizacja-i18n)
6. [Testowanie i debugowanie](#6-testowanie-i-debugowanie)
7. [Przykłady referencyjne](#7-przykłady-referencyjne)

---

## 1. Podstawowa struktura narzędzia

Narzędzie składa się z następujących elementów:

| Element | Wymagane | Opis |
|--------|---------------|------------|
| `TOOL_SPEC` | Tak | Słownik definiujący nazwę, opis i parametry narzędzia |
| `run_tool(args)` | Tak | Funkcja wykonywana w momencie wywołania narzędzia. Args to dyktando, return to ciąg znaków. |
| i18n JSON | Polecane | Tłumaczenie pliku JSON (ta sama nazwa bazowa, `<nazwa>_tool.json`) |

### Minimalne narzędzie Python

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

## 2. Tworzenie narzędzia Python

### Kroki

1. **Ustaw zmienną środowiskową `UAGENT_EXTERNAL_TOOLS_DIRS`** (jeśli jeszcze nie została ustawiona)

 Przykład:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Wiele katalogów można oddzielić znakami `:` (Linux/macOS) lub `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (liczba pojedyncza) jest również obsługiwany w celu zapewnienia kompatybilności wstecznej.

2. **Utwórz plik w języku Python**

 Nazwa pliku jest dowolna, ale zalecane jest nadanie nazwy `<nazwa>_tool.py` (np. `my_tool.py`).

3. **Zaimplementuj wymagane elementy**

 - `TOOL_SPEC` słownik
 - `run_tool(args)` funkcja
 - Opcjonalnie plik JSON i18n

4. **Uruchom ponownie agenta** (lub uruchom narzędzie `system_reload`)

### Pełny szablon

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

Zobacz [Sekcję 5](#5-internationalization-i18n), aby uzyskać szczegółowe informacje na temat i18n.

---

## 3. Tworzenie narzędzia Rust + Python

Implementacja Rusta jest idealna do zadań o krytycznym znaczeniu dla wydajności (przetwarzanie dużych ilości danych, kryptografia, przetwarzanie plików itp.).
uag może bezpośrednio ładować gotowe pliki `.pyd`, więc **użytkownicy końcowi nie muszą instalować pip`**.

### Struktura narzędzia

Narzędzie Rust składa się z następujących elementów pliki:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

W celu dystrybucji umieść pliki `_tool.py` + `_tool.json` + `.pyd` w 
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Kroki

#### Krok 1: Utwórz projekt Rust

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

#### Krok 2: Implementacja Rusta (src/lib.rs)

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

**Kluczowe punkty:**
- Udostępnij funkcje za pomocą `#[pyfunction(name = "run_<name>")]`
- Zwracany typ to `PyResult<String>`
- Nazwa funkcji `#[pymodule]` musi pasować do nazwa skrzynki (`my_rust_tools`)

#### Krok 3: Kompilacja

```bash
cd my_rust_tool
cargo build --release
```

Windows: zmień nazwę `target/release/my_rust_tools.dll` na `my_rust_tools.pyd`
Linux: zmień nazwę `target/release/libmy_rust_tools.so` na `my_rust_tools.so`
macOS: zmień nazwę `target/release/libmy_rust_tools.dylib` na `my_rust_tools.so`

Lub używając maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Krok 4: Utwórz opakowanie Pythona

Utwórz `my_rust_tool.py` w swoim `UAGENT_EXTERNAL_TOOLS_DIRS` katalog:

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

**``load_rust_pyd()`` kolejność rozwiązywania:**

1. Poszukaj `<nazwa_modułu>.pyd` (lub `.so`) w tym samym katalogu co opakowanie `.py`
2. Wróć do modułu zainstalowanego za pomocą pip

#### Krok 5: Dystrybucja

Potrzebne są tylko te 3 pliki. Użytkownicy końcowi **nie** potrzebują żadnej `instalacji pip`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Notatki

- **Tylko w czasie kompilacji:** Wymagany jest zestaw narzędzi Rust i `maturin`
 ```bash
  pip install maturin
  ```
- The Rust nazwa skrzyni (`[lib] name` w `Cargo.toml`) musi odpowiadać pierwszemu argumentowi `load_rust_pyd()`
- Nazwa pliku opakowania i lokalizacja `.pyd` są niezależne, o ile znajdują się w tym samym katalogu

---

## 4. TOOL_SPEC Reference

### Podstawowy Struktura

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

### Właściwości

| Pole | Wpisz | Opis |
|------|------|------------|
| `typ` | str | Zawsze `"funkcja"` |
| `x_build` | str | `"rust"` dla implementacji Rusta (pomiń w Pythonie) |
| `gatunek_narzędzia` | str | Nazwa gatunku (opcjonalnie). Umożliwia kontrolę opartą na gatunku |
| `poziom_narzędzia` | int | 0=włączone, 1=warunkowe (domyślne), -1=wyłączone |
| `nazwa.funkcji` | str | **Wymagany**. Nazwa narzędzia (małe litery + cyfry + podkreślenie) |
| `funkcja.opis` | str | **Wymagany**. Opis |
| `funkcja.x_search_terms` | lista[str] | Słowa kluczowe wyszukiwania obsługujące i18n (zawijane znakiem `_(...)`) |
| `funkcja.x_search_terms_en` | lista[str] | Naprawiono słowa kluczowe wyszukiwania w języku angielskim |
| `parametry.funkcji` | dykt | Definicja parametru (format wywołania funkcji OpenAI) |

---

## 5. Internacjonalizacja (i18n)

### Mechanizm tłumaczenia

Wywołanie `make_tool_translator(__file__)` ładuje tłumaczenia z pliku `.json`
o tej samej nazwie bazowej w tym samym katalog.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Korzystanie z kluczy tłumaczeniowych

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Format pliku JSON

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

Zobacz istniejące Pliki `_tool.json` dla obsługiwanych kodów językowych.

---

## 6. Testowanie i debugowanie

### Sprawdzanie składni

```bash
python -m py_compile my_tool.py
```

### Narzędzie do weryfikacji Ładowanie

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Dzienniki błędów

Błędy podczas ładowania narzędzia są wypisywane na stderr. Jeśli Twoje narzędzie nie jest załadowane,
sprawdź dzienniki uruchamiania uag.

---

## 7. Przykłady referencyjne

### Przykłady narzędzi Pythona

- `date_calc_tool.py` (w `src/uagent/tools/`) — Obliczanie daty. Skopiuj na zewnątrz i dostosuj.
- `calculator_tool.py` (w `src/uagent/tools/`) — Kalkulator.

### Przykłady narzędzi Rust

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (w `src/uagent/tools_rust/`) — Generowanie UUID
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (w `src/uagent/tools_rust/`) — Konwersja ślimaka

Skopiuj pliki `_tool.py` i `.pyd` do `UAGENT_EXTERNAL_TOOLS_DIRS`, aby używać ich jako narzędzi zewnętrznych.

### Konfigurowanie katalogów narzędzi zewnętrznych

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Wiele katalogów można oddzielić znakami `:` (Linux/macOS) lub `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (liczba pojedyncza) jest również obsługiwana w celu zapewnienia kompatybilności wstecznej.