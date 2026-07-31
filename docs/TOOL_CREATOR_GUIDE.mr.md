# टूल क्रिएटर मार्गदर्शक

हे मार्गदर्शक स्पष्ट करते की uag मध्ये तुमची स्वतःची साधने कशी जोडावीत **uag मध्ये बदल न करता**.
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md) पहा.

---

## सामग्री सारणी
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [बेसिक टूल स्ट्रक्चर](#1-बेसिक-टूल-स्ट्रक्चर)
2. [पायथन टूल तयार करणे](#2-पायथन-टूल-तयार-करणे)
3. [रस्ट + पायथन टूल तयार करणे](#3-रस्ट-पायथन-टूल-तयार-करणे)
4. [TOOL_SPEC संदर्भ](#4-tool_spec-संदर्भ)
5. [आंतरराष्ट्रीयकरण (i18n)](#5-आंतरराष्ट्रीयकरण-i18n)
6. [चाचणी आणि डीबगिंग](#6-चाचणी-आणि-डीबगिंग)
7. [संदर्भ उदाहरणे](#7-संदर्भ-उदाहरणे)

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


## 1. मूल उपकरण संरचना

एक उपकरण खालील घटकांपासून बनलेले आहे:

| घटक | आवश्यक | वर्णन |
|---------|----------|-------------|
| `TOOL_SPEC` | होय | टूलचे नाव, वर्णन आणि पॅरामीटर्स परिभाषित करणारा शब्दकोश |
| `run_tool(args)` | होय | टूल कॉल केल्यावर फंक्शन अंमलात आणले जाते. Args एक dict आहे, return एक string आहे. |
| i18n JSON | शिफारस केलेले | भाषांतर JSON फाइल (समान बेसनाव, `<name>_tool.json`) |

### किमान पायथन टूल
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

## 2. पायथन टूल तयार करणे

### चरण

1. **`UAGENT_EXTERNAL_TOOLS_DIRS` पर्यावरण व्हेरिएबल सेट करा** (आधीच सेट केलेले नसल्यास)

   उदाहरण:
   ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

   एकाधिक डिरेक्टरी `:` (Linux/macOS) किंवा `;` (Windows) द्वारे विभक्त केल्या जाऊ शकतात.
   `UAGENT_EXTERNAL_TOOLS_DIR` (एकवचन) मागास सुसंगततेसाठी देखील समर्थित आहे.

2. **पायथन फाइल तयार करा**

   फाइलचे नाव विनामूल्य आहे, परंतु `<name>_tool.py` नाव देण्याची शिफारस केली जाते (उदा. `my_tool.py`).

3. **आवश्यक घटक अंमलात आणा**

   - `TOOL_SPEC` शब्दकोश
   - `run_tool(args)` फंक्शन
   - वैकल्पिकरित्या, i18n JSON फाइल

4. **एजंट रीस्टार्ट करा** (किंवा `system_reload` टूल चालवा)

### पूर्ण टेम्पलेट
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

i18n तपशीलांसाठी [विभाग 5](#5-आंतरराष्ट्रीयकरण-i18n) पहा.

---

## 3. रस्ट + पायथन टूल तयार करणे

रस्ट अंमलबजावणी कार्यप्रदर्शन-गंभीर कार्यांसाठी आदर्श आहे (हेवी डेटा प्रोसेसिंग, क्रिप्टोग्राफी, फाइल प्रोसेसिंग इ.).
uag पूर्व-निर्मित `.pyd` फाइल्स थेट लोड करू शकते, त्यामुळे **अंतिम वापरकर्त्यांना `pip install` ची आवश्यकता नाही**.

### टूल स्ट्रक्चर

रस्ट टूलमध्ये खालील फाइल्स असतात:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

वितरणासाठी, `_tool.py` + `_tool.json` + `.pyd` फायली
`UAGENT_EXTERNAL_TOOLS_DIRS` मध्ये ठेवा.

### चरण

#### पायरी 1: रस्ट प्रोजेक्ट तयार करा

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

#### पायरी 2: रस्ट अंमलबजावणी (src/lib.rs)

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

**मुख्य मुद्दे:**
- `#[pyfunction(name = "run_<name>")]` सह फंक्शन्स उघड करा
- रिटर्न प्रकार `PyResult<String>` आहे
- `#[pymodule]` फंक्शनचे नाव क्रेटच्या नावाशी (`my_rust_tools`) जुळले पाहिजे

#### पायरी 3: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: `target/release/my_rust_tools.dll` चे नाव बदलून `my_rust_tools.pyd` करा
Linux: `target/release/libmy_rust_tools.so` चे नाव बदलून `my_rust_tools.so` करा
macOS: `target/release/libmy_rust_tools.dylib` चे नाव बदलून `my_rust_tools.so` करा

किंवा maturin वापरून:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### पायरी 4: पायथन रॅपर तयार करा

तुमच्या `UAGENT_EXTERNAL_TOOLS_DIRS` निर्देशिकेत `my_rust_tool.py` तयार करा:

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

**``load_rust_pyd()`` रिझोल्यूशन ऑर्डर:**

1. रॅपर `.py` सारख्याच निर्देशिकेत `<module_name>.pyd` (किंवा `.so`) शोधा
2. पिप-इंस्टॉल केलेल्या मॉड्यूलवर परत जा

#### पायरी 5: वितरण

केवळ या 3 फाइल्सची आवश्यकता आहे. अंतिम वापरकर्त्यांना **कोणत्याही `pip install` ची आवश्यकता नाही**.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### नोट्स

- **केवळ बिल्ड-टाइम:** रस्ट टूलचेन आणि `maturin` आवश्यक आहेत
  ```bash
  pip install maturin
  ```
- रस्ट क्रेटचे नाव (`Cargo.toml` मधील `[lib] name`) `load_rust_pyd()` च्या पहिल्या आर्ग्युमेंटशी जुळले पाहिजे
- रॅपर फाईलचे नाव आणि `.pyd` स्थान स्वतंत्र आहेत जोपर्यंत ते एकाच निर्देशिकेत आहेत

---

## 4. TOOL_SPEC संदर्भ

### मूलभूत रचना

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

### गुणधर्म

| फील्ड | प्रकार | वर्णन |
|-------|------|-------------|
| `type` | str | नेहमी `"function"` |
| `x_build` | str | रस्ट अंमलबजावणीसाठी `"rust"` (पायथनसाठी वगळा) |
| `tool_genre` | str | शैलीचे नाव (पर्यायी). शैली-आधारित नियंत्रण सक्षम करते |
| `tool_level` | int | 0=सक्षम, 1=सशर्त (डीफॉल्ट), -1=अक्षम |
| `function.name` | str | **आवश्यक**. टूलचे नाव (लोअरकेस + अंक + अंडरस्कोर) |
| `function.description` | str | **आवश्यक**. वर्णन |
| `function.x_search_terms` | list[str] | i18n-जागरूक शोध कीवर्ड (`_(...)` ने लपेटा) |
| `function.x_search_terms_en` | list[str] | निश्चित इंग्रजी शोध कीवर्ड |
| `function.parameters` | dict | पॅरामीटर डेफिनिशन (OpenAI फंक्शन कॉलिंग फॉरमॅट) |

---

## 5. आंतरराष्ट्रीयकरण (i18n)

### भाषांतर यंत्रणा

`make_tool_translator(__file__)` कॉल केल्याने समान बेसनाव असलेल्या `.json` फाईलमधून त्याच निर्देशिकेत भाषांतर लोड होते.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### भाषांतर की वापरणे

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON फाइल स्वरूप

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

समर्थित भाषा कोडसाठी विद्यमान `_tool.json` फाइल पहा.

---

## 6. चाचणी आणि डीबगिंग

### सिंटॅक्स तपासणी

```bash
python -m py_compile my_tool.py
```

### टूल लोडिंग सत्यापित करा

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### त्रुटी लॉग

टूल लोडिंग दरम्यानच्या त्रुटी stderr वर मुद्रित केल्या जातात. तुमचे टूल लोड केलेले नसल्यास,
uag स्टार्टअप लॉग तपासा.

---

## 7. संदर्भ उदाहरणे

### पायथन टूल उदाहरणे

- `date_calc_tool.py` (`src/uagent/tools/` मध्ये) — तारीख गणना. बाहेरून कॉपी करा आणि सानुकूलित करा.
- `calculator_tool.py` (`src/uagent/tools/` मध्ये) — कॅल्क्युलेटर.

### रस्ट टूल उदाहरणे

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/` मध्ये) — UUID जनरेशन
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/` मध्ये) — स्लग रूपांतरण

`_tool.py` आणि `.pyd` फायली `UAGENT_EXTERNAL_TOOLS_DIRS` मध्ये कॉपी करा बाह्य साधने म्हणून वापरण्यासाठी.

### बाह्य टूल निर्देशिका सेट करणे

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

एकाधिक निर्देशिका `:` (Linux/macOS) किंवा `;` (Windows) द्वारे विभक्त केल्या जाऊ शकतात.
`UAGENT_EXTERNAL_TOOLS_DIR` (एकवचन) मागास सुसंगततेसाठी देखील समर्थित आहे.

---

*हे भाषांतर आपोआप निर्माण झाले. सर्वात अचूक आणि अद्ययावत सामग्रीसाठी, कृपया इंग्रजी आवृत्ती पहा.*