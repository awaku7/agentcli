# Mwongozo wa Waundaji Zana

Mwongozo huu unaelezea jinsi ya kuongeza zana zako mwenyewe kwenye uag **bila kurekebisha uag yenyewe**.
Kama ungependa kuongeza zana moja kwa moja kwenye mti chanzo cha uag, ona
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Yaliyomo

1. [Muundo wa Zana Msingi](#1-muundo-wa-zana-msingi)
2. [Kuunda Zana ya Python](#2-kuunda-zana-ya-python)
3. [Kuunda Zana ya Rust + Python](#3-kuunda-zana-ya-rust-python)
4. [Marejeleo ya TOOL_SPEC](#4-marejeleo-ya-tool_spec)
5. [Utandawazi (i18n)](#5-utandawazi-i18n)
6. [Kujaribu na Utatuzi](#6-kujaribu-na-utatuzi)
7. [Mifano ya Marejeleo](#7-mifano-ya-marejeleo)

---

## 1. Muundo wa Zana Msingi

Zana ina vipengele vifuatavyo:

| Kipengele | Inahitajika | Maelezo |
|---------|----------|-------------|
| `TOOL_SPEC` | Ndiyo | Kamusi inayofafanua jina la zana, maelezo na vigezo |
| `run_tool(args)` | Ndiyo | Kazi inayotekelezwa wakati zinaitwa. Args ni dict, kurudi ni kamba. |
| i18n JSON | Imependekezwa | Faili ya tafsiri ya JSON (jina la msingi sawa, `<jina>_tool.json`) |

### Zana Ndogo ya Python
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

## 2. Kuunda Zana ya Python

### Hatua

1. **Weka kigezo cha mazingira `UAGENT_EXTERNAL_TOOLS_DIRS`** (kama hakijawekwa tayari)

   Mfano:
   ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

   Saraka nyingi zinaweza kutengwa kwa `:` (Linux/macOS) au `;` (Windows).
   `UAGENT_EXTERNAL_TOOLS_DIR` (umoja) pia inatumika kwa upatanifu wa nyuma.

2. **Unda faili ya Python**

   Jina la faili halilipishwi, lakini kupendekezwa `<jina>_tool.py` (k.m. `my_tool.py`).

3. **Tekeleza vipengele vinavyohitajika**

   - Kamusi ya `TOOL_SPEC`
   - Kazi ya `run_tool(args)`
   - Kwa hiari, faili ya i18n JSON

4. **Anzisha upya wakala** (au endesha zana ya `system_reload`)

### Kiolezo Kamili
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

Angalia [Sehemu ya 5](#5-utandawazi-i18n) kwa maelezo ya i18n.

---

## 3. Kuunda Zana ya Rust + Python

Utekelezaji wa Rust ni bora kwa kazi muhimu za utendakazi (uchakataji mzito wa data, usimbaji fiche, uchakataji wa faili, n.k.).
uag inaweza kupakia faili za `.pyd` zilizojengwa awali moja kwa moja, kwa hivyo **watumiaji wa mwisho hawahitaji `pip install`**.

### Muundo wa Zana

Zana ya Rust ina faili zifuatazo:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Kwa usambazaji, weka faili za `_tool.py` + `_tool.json` + `.pyd` katika
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Hatua

#### Hatua ya 1: Unda mradi wa Rust

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

#### Hatua ya 2: Utekelezaji wa Rust (src/lib.rs)

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

**Mambo muhimu:**
- Onyesha vitendaji kwa `#[pyfunction(name = "run_<name>")]`
- Aina ya kurejesha ni `PyResult<String>`
- Jina la kazi ya `#[pymodule]` lazima lil ingane na jina la crate (`my_rust_tools`)

#### Hatua ya 3: Jenga

```bash
cd my_rust_tool
cargo build --release
```

Windows: badilisha jina la `target/release/my_rust_tools.dll` hadi `my_rust_tools.pyd`
Linux: badilisha jina la `target/release/libmy_rust_tools.so` hadi `my_rust_tools.so`
macOS: badilisha jina la `target/release/libmy_rust_tools.dylib` hadi `my_rust_tools.so`

Au kwa kutumia maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Hatua ya 4: Unda kanga ya Python

Unda `my_rust_tool.py` katika saraka yako ya `UAGENT_EXTERNAL_TOOLS_DIRS`:

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

**``load_rust_pyd()`` mpangilio wa utatuzi:**

1. Tafuta `<module_name>.pyd` (au `.so`) katika saraka sawa na kanga ya `.py`
2. Rudi kwenye moduli iliyosakinishwa kwa pip

#### Hatua ya 5: Usambazaji

Faili hizi 3 pekee ndizo zinahitajika. Watumiaji wa mwisho **hawahitaji** `pip install`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Vidokezo

- **Muda wa kujenga pekee:** Msururu wa zana za Rust na `maturin` zinahitajika
  ```bash
  pip install maturin
  ```
- Jina la crate ya Rust (`[lib] name` katika `Cargo.toml`) lazima lil ingane na hoja ya kwanza ya `load_rust_pyd()`
- Jina la faili ya kanga na eneo la `.pyd` ni huru mradi ziko katika saraka sawa

---

## 4. Marejeleo ya TOOL_SPEC

### Muundo Msingi

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

### Sifa

| Uga | Aina | Maelezo |
|-------|------|-------------|
| `type` | str | Daima `"function"` |
| `x_build` | str | `"rust"` kwa utekelezaji wa Rust (acha kwa Python) |
| `tool_genre` | str | Jina la aina (si lazima). Huwezesha udhibiti wa aina |
| `tool_level` | int | 0=imewezeshwa, 1=ya masharti (chaguomsingi), -1=imezimwa |
| `function.name` | str | **Inahitajika**. Jina la zana (herufi ndogo + tarakimu + chini) |
| `function.description` | str | **Inahitajika**. Maelezo |
| `function.x_search_terms` | list[str] | Maneno muhimu ya utafutaji yanayotambua i18n (funga kwa `_(...)`) |
| `function.x_search_terms_en` | list[str] | Maneno muhimu ya utafutaji ya Kiingereza yaliyowekwa |
| `function.parameters` | dict | Ufafanuzi wa kigezo (umbo la kupiga kazi la OpenAI) |

---

## 5. Utandawazi (i18n)

### Utaratibu wa Tafsiri

Kuita `make_tool_translator(__file__)` hupakia tafsiri kutoka kwa faili ya `.json`
yenye jina la msingi sawa katika saraka hiyo hiyo.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Kutumia Funguo za Tafsiri

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Umbizo la Faili la JSON

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

Tazama faili zilizopo za `_tool.json` kwa misimbo ya lugha inayotumika.

---

## 6. Kujaribu na Utatuzi

### Ukaguzi wa Sintaksia

```bash
python -m py_compile my_tool.py
```

### Thibitisha Kupakia Zana

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Kumbukumbu za Makosa

Makosa wakati wa upakiaji wa zana yanachapishwa kwa stderr. Ikiwa zana yako haijapakiwa,
angalia kumbukumbu za uag.

---

## 7. Mifano ya Marejeleo

### Mifano ya Zana ya Python

- `date_calc_tool.py` (katika `src/uagent/tools/`) — Hesabu ya tarehe. Nakili nje na ubinafsishe.
- `calculator_tool.py` (katika `src/uagent/tools/`) — Kikokotoo.

### Mifano ya Zana ya Rust

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (katika `src/uagent/tools_rust/`) — Uzalishaji UUID
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (katika `src/uagent/tools_rust/`) — Ubadilishaji slug

Nakili faili za `_tool.py` na `.pyd` kwenye `UAGENT_EXTERNAL_TOOLS_DIRS` ili kuzitumia kama zana za nje.

### Kusanidi Saraka za Zana za Nje

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Saraka nyingi zinaweza kutengwa kwa `:` (Linux/macOS) au `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (umoja) pia inatumika kwa upatanifu wa nyuma.

---

*Tafsiri hii imetolewa kiotomatiki. Kwa maudhui sahihi na ya kisasa zaidi, tafadhali rejelea toleo la Kiingereza.*