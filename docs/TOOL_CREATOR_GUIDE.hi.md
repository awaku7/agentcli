# टूल क्रिएटर गाइड

यह गाइड बताता है कि यूएजी में अपने टूल कैसे जोड़ें **यूएजी को संशोधित किए बिना**।
यदि आप सीधे यूएजी स्रोत ट्री में एक टूल जोड़ना चाहते हैं, देखें
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## विषय-सूची

1. [बेसिक टूल स्ट्रक्चर](#1-बेसिक-टूल-स्ट्रक्चर)
2. [पायथन टूल बनाना](#2-एक-पायथन-टूल बनाना)
3. [क्रिएटिंग ए रस्ट + पायथन टूल](#3-क्रिएटिंग-ए-रस्ट--पाइथन-टूल)
4. [TOOL_Spec Reference](#4-tool_spec-reference)
5. [अंतर्राष्ट्रीयकरण (i18n)](#5-अंतर्राष्ट्रीयकरण-i18n)
6. [परीक्षण और डिबगिंग](#6-परीक्षण-और-डिबगिंग)
7. [संदर्भ उदाहरण](#7-संदर्भ-उदाहरण)

---

## 1. मूल उपकरण संरचना

एक उपकरण में निम्नलिखित तत्व होते हैं:

| तत्त्व | आवश्यक | विवरण |
|---|--|---|
| `टूल_स्पेक` | हाँ | टूल के नाम, विवरण और पैरामीटर को परिभाषित करने वाला शब्दकोश |
| `run_tool(args)` | हाँ | टूल को कॉल करने पर फ़ंक्शन निष्पादित होता है। Args एक तानाशाही है, रिटर्न एक स्ट्रिंग है। |
| i18n JSON | अनुशंसित | अनुवाद JSON फ़ाइल (समान बेसनाम, `<name>_tool.json`) |

### न्यूनतम पायथन टूल
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

## 2. एक पायथन टूल बनाना

### चरण

1. **'UAGENT_EXTERNAL_TOOLS_DIRS` पर्यावरण चर सेट करें** (यदि पहले से सेट नहीं है)

 उदाहरण:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 एकाधिक निर्देशिकाओं को `:` (Linux/macOS) या `;` (Windows) द्वारा अलग किया जा सकता है।
 `UAGENT_EXTERNAL_TOOLS_DIR` (एकवचन) पश्चगामी अनुकूलता के लिए भी समर्थित है।

2. **पाइथॉन फ़ाइल बनाएं**

 फ़ाइल का नाम मुफ़्त है, लेकिन `<name>_tool.py` नामकरण की अनुशंसा की जाती है (उदाहरण के लिए `my_tool.py`).

3. **आवश्यक तत्वों को लागू करें**

 - `TOOL_SPEC` शब्दकोश
 - `run_tool(args)` फ़ंक्शन
 - वैकल्पिक रूप से, एक i18n JSON फ़ाइल

4. **एजेंट को पुनरारंभ करें** (या `system_reload` टूल चलाएं)

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

i18n विवरण के लिए [धारा 5](#5-अंतर्राष्ट्रीयकरण-i18n) देखें।

---

## 3. एक रस्ट + पायथन बनाना टूल

रस्ट कार्यान्वयन प्रदर्शन-महत्वपूर्ण कार्यों (भारी डेटा प्रोसेसिंग, क्रिप्टोग्राफी, फ़ाइल प्रोसेसिंग इत्यादि) के लिए आदर्श है।
uag पूर्व-निर्मित `.pyd` फ़ाइलों को सीधे लोड कर सकता है, इसलिए **एंड-यूज़र्स को `पिप इंस्टॉल`** की आवश्यकता नहीं है।

### टूल स्ट्रक्चर

एक रस्ट टूल में निम्नलिखित शामिल हैं फ़ाइलें:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

वितरण के लिए, `_tool.py` + `_tool.json` + `.pyd` फ़ाइलों को
`UAGENT_EXTERNAL_TOOLS_DIRS` में रखें।

### चरण

#### चरण 1: जंग बनाएं प्रोजेक्ट

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

#### चरण 2: जंग कार्यान्वयन (src/lib.rs)

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

**कुंजी अंक:**
- `#[pyfunction(name = "run_<name>")]` के साथ फ़ंक्शंस को उजागर करें
- रिटर्न प्रकार `PyResult<String>` है
- `#[pymodule]` फ़ंक्शन का नाम क्रेट नाम (`my_rust_tools`) से मेल खाना चाहिए

#### चरण 3: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: `target/release/my_rust_tools.dll` का नाम बदलें `my_rust_tools.pyd`
Linux: `target/release/libmy_rust_tools.so` का नाम बदलें `my_rust_tools.so`
macOS: नाम बदलें `target/release/libmy_rust_tools.dylib` से `my_rust_tools.so`

या maturin का उपयोग करना:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### चरण 4: पायथन रैपर बनाएं

अपने `UAGENT_EXTERNAL_TOOLS_DIRS` निर्देशिका में `my_rust_tool.py` बनाएं:

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

**``load_rust_pyd()`` रिज़ॉल्यूशन क्रम:**

1. रैपर `.py` के समान निर्देशिका में `<module_name>.pyd` (या `.so`) देखें।
2. पिप-स्थापित मॉड्यूल पर वापस जाएँ

#### चरण 5: वितरण

केवल इन 3 फ़ाइलों की आवश्यकता है। अंतिम-उपयोगकर्ताओं को **नहीं** किसी `पिप इंस्टाल` की आवश्यकता है।

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### नोट्स

- **केवल निर्माण समय:** रस्ट टूलचेन और `मटुरिन` आवश्यक हैं
  ```bash
  pip install maturin
  ```
- रस्ट क्रेट नाम (`Cargo.toml` में `[lib] name`) को `load_rust_pyd()` के पहले तर्क से मेल खाना चाहिए
- रैपर फ़ाइल नाम और `.pyd` स्थान तब तक स्वतंत्र हैं जब तक वे एक ही निर्देशिका में हैं

---

## 4. TOOL_SPEC Reference

### मूल संरचना

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

### Properties

| फ़ील्ड | प्रकार | विवरण |
|-------|------|---|
| `type` | str | हमेशा `"function"` |
| `x_build` | str | जंग कार्यान्वयन के लिए `"rust"` (पायथन के लिए छोड़ें) |
| `tool_genre` | str | शैली का नाम (वैकल्पिक). शैली-आधारित नियंत्रण सक्षम करता है |
| `tool_level` | int | 0=सक्षम, 1=सशर्त (डिफ़ॉल्ट), -1=अक्षम |
| `function.name` | str | **आवश्यक**. टूल का नाम (लोअरकेस + अंक + अंडरस्कोर) |
| `function.description` | str | **आवश्यक**. विवरण |
| `function.x_search_terms` | सूची[str] | i18n-जागरूक खोज कीवर्ड (`_(...)` के साथ लपेटें) |
| `function.x_search_terms_en` | सूची[str] | निश्चित अंग्रेजी खोज कीवर्ड |
| `function.parameters` | dict | पैरामीटर परिभाषा (OpenAI function calling format) |

---

## 5. अंतर्राष्ट्रीयकरण (i18n)

### अनुवाद तंत्र

कॉलिंग `make_tool_translator(__file__)` एक `.json` फ़ाइल से समान बेसनाम के साथ अनुवाद लोड करता है निर्देशिका।

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### अनुवाद कुंजियों का उपयोग करना

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON फ़ाइल प्रारूप

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

समर्थित भाषा कोड के लिए मौजूदा `_tool.json` फ़ाइलें देखें।

---

## 6. परीक्षण और डिबगिंग

### सिंटैक्स जांच

```bash
python -m py_compile my_tool.py
```

### टूल लोडिंग सत्यापित करें

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### त्रुटि लॉग

टूल लोडिंग के दौरान त्रुटियां stderr पर मुद्रित होती हैं। यदि आपका टूल लोड नहीं हुआ है,
uag स्टार्टअप लॉग जांचें।

---

## 7. संदर्भ उदाहरण

### Python Tool Examples

- `date_calc_tool.py` (`src/uagent/tools/` में) — दिनांक गणना। बाहरी रूप से कॉपी करें और कस्टमाइज़ करें।
- `calculator_tool.py` (`src/uagent/tools/` में) — कैलकुलेटर।

### Rust Tool Examples

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/` में) — UUID जनरेशन
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/` में) — स्लग रूपांतरण

`_tool.py` और `.pyd` फ़ाइलों को `UAGENT_EXTERNAL_TOOLS_DIRS` में कॉपी करें बाहरी उपकरण के रूप में उपयोग करने के लिए।

### बाहरी टूल निर्देशिकाओं की स्थापना

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

एकाधिक निर्देशिकाओं को `:` (Linux/macOS) या `;` (Windows) द्वारा अलग किया जा सकता है।
`UAGENT_EXTERNAL_TOOLS_DIR` (एकवचन) पश्चगामी अनुकूलता के लिए भी समर्थित है।

---

*यह अनुवाद स्वचालित रूप से उत्पन्न हुआ था. सबसे सटीक और अद्यतन सामग्री के लिए, कृपया अंग्रेजी संस्करण देखें।*