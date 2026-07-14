# টুল ক্রিয়েটর গাইড

এই নির্দেশিকা ব্যাখ্যা করে কিভাবে uag-এ আপনার নিজের টুলগুলি যোগ করতে হয় **uag নিজে পরিবর্তন না করে**।
আপনি যদি uag সোর্স ট্রিতে সরাসরি একটি টুল যোগ করতে চান, দেখুন
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md)।

---

## বিষয়বস্তুর সারণী

১. [বেসিক টুল স্ট্রাকচার](#1-বেসিক-টুল-স্ট্রাকচার)
2. [একটি পাইথন টুল তৈরি করা](#2-creating-a-python-tool)
3. [একটি মরিচা + পাইথন টুল তৈরি করা](#3-creating-a-rust--python-tool)
4. [TOOL_SPEC রেফারেন্স](#4-tool_spec-রেফারেন্স)
5. [আন্তর্জাতিককরণ (i18n)](#5-আন্তর্জাতিককরণ-i18n)
6. [টেস্টিং এবং ডিবাগিং](#6-টেস্টিং-এন্ড-ডিবাগিং)
7. [রেফারেন্স উদাহরণ](#7-উদাহরণ-উদাহরণ)

---

## 1. বেসিক টুল স্ট্রাকচার

একটি টুল নিম্নলিখিত উপাদান নিয়ে গঠিত:

| উপাদান | প্রয়োজনীয় | বর্ণনা |
|---------|---------|-------------|
| `TOOL_SPEC` | হ্যাঁ | টুলের নাম, বর্ণনা এবং প্যারামিটার সংজ্ঞায়িত করা অভিধান |
| `run_tool(args)` | হ্যাঁ | টুল কল করা হলে ফাংশন নির্বাহ করা হয়। Args একটি dict, রিটার্ন একটি স্ট্রিং. |
| i18n JSON | প্রস্তাবিত | অনুবাদ JSON ফাইল (একই বেসনাম, `<name>_tool.json`) |

### ন্যূনতম পাইথন টুল

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

## 2. একটি পাইথন টুল তৈরি করা হচ্ছে

### ধাপ

**`UAGENT_EXTERNAL_TOOLS_DIRS` এনভায়রনমেন্ট ভেরিয়েবল সেট করুন** (যদি আগে থেকেই সেট করা না থাকে)

 উদাহরণ:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 একাধিক ডিরেক্টরি `:` (Linux/macOS) বা `;` (Windows) দ্বারা আলাদা করা যেতে পারে।
 `UAGENT_EXTERNAL_TOOLS_DIR` (একবচন) পশ্চাদগামী সামঞ্জস্যের জন্যও সমর্থিত।

2. **একটি পাইথন ফাইল তৈরি করুন**

 ফাইলের নাম বিনামূল্যে, কিন্তু `<name>_tool.py` নামকরণ সুপারিশ করা হয় (যেমন `my_tool.py`)।

৩. **প্রয়োজনীয় উপাদানগুলি প্রয়োগ করুন**

 - `TOOL_SPEC` অভিধান
 - `run_tool(args)` ফাংশন
 - ঐচ্ছিকভাবে, একটি i18n JSON ফাইল

৪. **এজেন্টটি পুনরায় চালু করুন** (বা `system_reload` টুলটি চালান)

### সম্পূর্ণ টেমপ্লেট

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

i18n বিশদ বিবরণের জন্য [বিভাগ 5](#5-আন্তর্জাতিককরণ-i18n) দেখুন।

---

## 3. একটি মরিচা + পাইথন টুল তৈরি করা

মরিচা বাস্তবায়ন কর্মক্ষমতা-গুরুত্বপূর্ণ কাজগুলির জন্য আদর্শ (ভারী ডেটা প্রসেসিং, ক্রিপ্টোগ্রাফি, ফাইল প্রসেসিং, ইত্যাদি)।
uag পূর্ব-নির্মিত `.pyd` ফাইলগুলি সরাসরি লোড করতে পারে, তাই **শেষ-ব্যবহারকারীদের `পিপ ইনস্টল`** প্রয়োজন হয় না।

### টুল স্ট্রাকচার

একটি মরিচা টুল নিম্নলিখিত ফাইলগুলি নিয়ে গঠিত:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

ডিস্ট্রিবিউশনের জন্য, `_tool.py` + `_tool.json` + `.pyd` ফাইলগুলিকে এতে রাখুন
`UAGENT_EXTERNAL_TOOLS_DIRS`।

### ধাপ

#### ধাপ 1: রাস্ট প্রকল্প তৈরি করুন

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

#### ধাপ ২: মরিচা বাস্তবায়ন (src/lib.rs)

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

**মূল পয়েন্ট:**
- `#[pyfunction(name = "run_<name>")]` এর সাথে ফাংশন প্রকাশ করুন
- রিটার্নের ধরন হল `PyResult<String>`
- `#[pymodule]` ফাংশনের নাম অবশ্যই ক্রেট নামের (`my_rust_tools`) সাথে মিলতে হবে

#### ধাপ 3: বিল্ড করুন

```bash
cd my_rust_tool
cargo build --release
```

Windows: `target/release/my_rust_tools.dll` এর নাম `my_rust_tools.pyd` এ পরিবর্তন করুন
Linux: `target/release/libmy_rust_tools.so` এর নাম পরিবর্তন করুন `my_rust_tools.so`
macOS: `target/release/libmy_rust_tools.dylib` এর নাম পরিবর্তন করে `my_rust_tools.so` এ

অথবা ম্যাটুরিন ব্যবহার করুন:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### ধাপ 4: পাইথন র্যাপার তৈরি করুন

আপনার `UAGENT_EXTERNAL_TOOLS_DIRS` ডিরেক্টরিতে `my_rust_tool.py` তৈরি করুন:

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

**``load_rust_pyd()`` রেজোলিউশন অর্ডার:**

১. র্যাপার `.py` হিসাবে একই ডিরেক্টরিতে `<module_name>.pyd` (বা `.so`) সন্ধান করুন।
2. একটি পিপ-ইনস্টল করা মডিউলে ফিরে যান

#### ধাপ 5: বিতরণ

শুধুমাত্র এই 3টি ফাইল প্রয়োজন৷ শেষ-ব্যবহারকারীদের **কোনও `পিপ ইন্সটল` এর প্রয়োজন নেই।

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### নোট

- **বিল্ড-টাইম শুধুমাত্র:** মরিচা টুলচেন এবং `ম্যাটুরিন` প্রয়োজন
 ```bash
  pip install maturin
  ```
- রাস্ট ক্রেট নাম (`Cargo.toml`-এর মধ্যে `[lib] name`) অবশ্যই `load_rust_pyd()` এর প্রথম আর্গুমেন্টের সাথে মিলতে হবে
- র‍্যাপার ফাইলের নাম এবং `.pyd` অবস্থান স্বতন্ত্র যতক্ষণ না তারা একই ডিরেক্টরিতে থাকে

---

## 4. TOOL_SPEC রেফারেন্স

### বেসিক গঠন

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

### বৈশিষ্ট্য

| মাঠ | প্রকার | বর্ণনা |
|-------|------|-------------|
| `টাইপ` | str | সর্বদা `"ফাংশন"` |
| `x_build` | str | মরিচা বাস্তবায়নের জন্য `"মরিচা"` (পাইথনের জন্য বাদ দিন) |
| `tool_genre` | str | জেনার নাম (ঐচ্ছিক)। জেনার-ভিত্তিক নিয়ন্ত্রণ সক্ষম করে |
| `tool_level` | int | 0=সক্ষম, 1=শর্তাধীন (ডিফল্ট), -1=অক্ষম |
| `function.name` | str | **প্রয়োজনীয়**। টুলের নাম (ছোট হাতের + সংখ্যা + আন্ডারস্কোর) |
| `function.description` | str | **প্রয়োজনীয়**। বর্ণনা |
| `function.x_search_terms` | তালিকা[str] | i18n-সচেতন অনুসন্ধান কীওয়ার্ড (`_(...)` দিয়ে মোড়ানো) |
| `function.x_search_terms_en` | তালিকা[str] | স্থির ইংরেজি অনুসন্ধান কীওয়ার্ড |
| `function.parameters` | dict | প্যারামিটার সংজ্ঞা (ওপেনএআই ফাংশন কলিং ফরম্যাট) |

---

## 5. আন্তর্জাতিকীকরণ (i18n)

### অনুবাদ প্রক্রিয়া

`make_tool_translator(__file__)` কল করা `.json` ফাইল থেকে অনুবাদগুলি লোড করে
একই বেসনাম একই ডিরেক্টরিতে।

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### অনুবাদ কী ব্যবহার করা হচ্ছে

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON ফাইল ফর্ম্যাট

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

সমর্থিত ভাষা কোডের জন্য বিদ্যমান `_tool.json` ফাইলগুলি দেখুন।

---

## 6. টেস্টিং এবং ডিবাগিং

### সিনট্যাক্স চেক

```bash
python -m py_compile my_tool.py
```

### টুল লোডিং যাচাই

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### ত্রুটি লগ

টুল লোড করার সময় ত্রুটি stderr এ প্রিন্ট করা হয়। যদি আপনার টুল লোড না হয়,
uag স্টার্টআপ লগগুলি পরীক্ষা করুন।

---

## 7. রেফারেন্স উদাহরণ

### পাইথন টুলের উদাহরণ

- `date_calc_tool.py` (`src/uagent/tools/`-এ) — তারিখ গণনা। বাহ্যিকভাবে অনুলিপি করুন এবং কাস্টমাইজ করুন।
- `calculator_tool.py` (`src/uagent/tools/`-এ) — ক্যালকুলেটর।

### মরিচা টুলের উদাহরণ

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/`-এ) — UUID জেনারেশন
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/`-এ) — স্লাগ রূপান্তর

`_tool.py` এবং `.pyd` ফাইলগুলিকে `UAGENT_EXTERNAL_TOOLS_DIRS` এ কপি করুন বহিরাগত টুল হিসাবে ব্যবহার করতে।

### এক্সটার্নাল টুল ডিরেক্টরি সেট আপ করা হচ্ছে

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

একাধিক ডিরেক্টরিকে `:` (Linux/macOS) বা `;` (Windows) দ্বারা আলাদা করা যেতে পারে।
`UAGENT_EXTERNAL_TOOLS_DIR` (একবচন) পশ্চাদগামী সামঞ্জস্যের জন্যও সমর্থিত।