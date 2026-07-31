# دليل منشئ الأدوات

يشرح هذا الدليل كيفية إضافة أدواتك الخاصة إلى uag **دون تعديل uag نفسه**.
إذا كنت تريد إضافة أداة مباشرةً إلى شجرة مصدر uag، راجع
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## جدول المحتويات
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [بنية الأداة الأساسية](#1-basic-tool-structure)
2. [إنشاء أداة بايثون](#2-أداة-إنشاء-بايثون)
3. [إنشاء أداة Rust + Python](#3-creating-a-rust--python-tool)
4. [TOOL_SPEC مرجع](#4-tool_spec-reference)
5. [التدويل (i18n)](#5-التدويل-i18n)
6. [الاختبار والتصحيح](#6-الاختبار-والتصحيح)
7. [أمثلة مرجعية](#7-reference-examples)

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


## 1. البنية الأساسية للأداة

تتكون الأداة من العناصر التالية:

| العنصر | مطلوب | الوصف |
|---------|----------|-------------|
| `TOOL_SPEC` | نعم | قاموس يحدد اسم الأداة ووصفها ومعلماتها |
| `run_tool(args)` | نعم | يتم تنفيذ الوظيفة عند استدعاء الأداة. Args عبارة عن إملاء، والعودة عبارة عن سلسلة. |
| i18n جسون | موصى به | ملف الترجمة JSON (نفس الاسم الأساسي، `<name>_tool.json`) |

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

## 2. إنشاء أداة Python

### الخطوات

1. **قم بتعيين متغير البيئة `UAGENT_EXTERNAL_TOOLS_DIRS`** (إذا لم يتم تعيينه بالفعل)

 مثال:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 يمكن فصل الدلائل المتعددة بواسطة `:` (Linux/macOS) أو `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (المفرد) مدعوم أيضًا للتوافق مع الإصدارات السابقة.

2. **إنشاء ملف بايثون**

 اسم الملف مجاني، ولكن يوصى بتسمية `<name>_tool.py` (على سبيل المثال `my_tool.py`).

3. **تنفيذ العناصر المطلوبة**

 - `TOOL_SPEC` القاموس
 - `run_tool(args)` الوظيفة
 - بشكل اختياري، ملف i18n JSON

4. **أعد تشغيل الوكيل** (أو قم بتشغيل أداة `system_reload`)

### القالب الكامل

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

راجع [القسم 5](#5-internationalization-i18n) للحصول على تفاصيل i18n.

---

## 3. إنشاء أداة Rust + Python

يعد تطبيق Rust مثاليًا للمهام ذات الأداء الحيوي (معالجة البيانات الثقيلة، والتشفير، ومعالجة الملفات، وما إلى ذلك).
uag يمكن تحميل ملفات `.pyd` المعدة مسبقًا مباشرةً، لذلك **لا يحتاج المستخدمون النهائيون إلى `pip install`**.

### بنية الأداة

تتكون أداة Rust مما يلي الملفات:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

للتوزيع، ضع ملفات `_tool.py` + `_tool.json` + `.pyd` في
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### الخطوات

#### الخطوة 1: إنشاء مشروع Rust

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

#### الخطوة 2: تنفيذ Rust (src/lib.rs)

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

**النقاط الرئيسية:**
- كشف الوظائف باستخدام `#[pyfunction(name = "run_<name>")]`
- نوع الإرجاع هو `PyResult<String>`
- يجب أن يتطابق اسم الدالة `#[pymodule]` مع اسم الصندوق (`my_rust_tools`)

#### الخطوة 3: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: إعادة تسمية `target/release/my_rust_tools.dll` إلى `my_rust_tools.pyd`
Linux: إعادة تسمية `target/release/libmy_rust_tools.so` إلى `my_rust_tools.so`
macOS: أعد تسمية `target/release/libmy_rust_tools.dylib` إلى `my_rust_tools.so`

أو باستخدام maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### الخطوة 4: إنشاء غلاف Python

إنشاء `my_rust_tool.py` في `UAGENT_EXTERNAL_TOOLS_DIRS` الدليل:

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

**``load_rust_pyd()`` ترتيب الدقة:**

1. ابحث عن `<module_name>.pyd` (أو `.so`) في نفس الدليل مثل المجمّع `.py`
2. الرجوع إلى الوحدة النمطية المثبتة بالنقطة

#### الخطوة 5: التوزيع

هناك حاجة إلى هذه الملفات الثلاثة فقط. لا يحتاج المستخدمون النهائيون **لا** إلى أي `تثبيت نقطة`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### ملاحظات

- **وقت الإنشاء فقط:** مطلوب سلسلة أدوات الصدأ و`maturin`
 ```bash
  pip install maturin
  ```
- The Rust يجب أن يتطابق اسم الصندوق (`اسم [lib] في `Cargo.toml`) مع الوسيطة الأولى لـ `load_rust_pyd()`
- اسم ملف المجمع وموقع `.pyd` مستقلان طالما أنهما في نفس الدليل

---

## 4. TOOL_SPEC Reference

### أساسي البنية

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

### الخصائص

| المجال | اكتب | الوصف |
|-------|-------------|
| `النوع` | شارع | دائمًا `"وظيفة"` |
| `x_build` | شارع | `"rust"` لتطبيق Rust (حذف في Python) |
| `نوع_الأداة` | شارع | اسم النوع (اختياري). تمكين التحكم على أساس النوع |
| `مستوى_الأداة` | كثافة العمليات | 0=ممكّن، 1=شرطي (افتراضي)، -1=معطل |
| `اسم الوظيفة` | شارع | **مطلوب**. اسم الأداة (أحرف صغيرة + أرقام + شرطة سفلية) |
| ` وصف الوظيفة ` | شارع | **مطلوب**. الوصف |
| `function.x_search_terms` | قائمة [شارع] | الكلمات الرئيسية للبحث المدرك لـ i18n (ملتفة بـ `_(...)`) |
| `function.x_search_terms_en` | قائمة [شارع] | تم إصلاح كلمات البحث الأساسية باللغة الإنجليزية |
| `function.parameters` | إملاء | تعريف المعلمة (تنسيق استدعاء دالة OpenAI) |

---

## 5. التدويل (i18n)

### آلية الترجمة

استدعاء `make_tool_translator(__file__)` يؤدي إلى تحميل الترجمات من ملف `.json`
بنفس الاسم الأساسي في نفس الملف الدليل.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### استخدام مفاتيح الترجمة

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### تنسيق ملف JSON

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

انظر الموجود ملفات `_tool.json` لرموز اللغات المدعومة.

---

## 6. الاختبار والتصحيح

### التحقق من بناء الجملة

```bash
python -m py_compile my_tool.py
```

### أداة التحقق Loading

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### سجلات الأخطاء

تتم طباعة الأخطاء أثناء تحميل الأداة إلى stderr. إذا لم يتم تحميل أداتك،
تحقق من سجلات بدء تشغيل uag.

---

## 7. أمثلة مرجعية

### أمثلة على أدوات Python

- `date_calc_tool.py` (في `src/uagent/tools/`) — حساب التاريخ. انسخ خارجيًا وخصص.
- `calculator_tool.py` (in `src/uagent/tools/`) — الحاسبة.

### أمثلة على أدوات الصدأ

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (في `src/uagent/tools_rust/`) — إنشاء UUID
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (في `src/uagent/tools_rust/`) — تحويل ثابت

انسخ الملفين `_tool.py` و`.pyd` إلى `UAGENT_EXTERNAL_TOOLS_DIRS` لاستخدامها كأدوات خارجية.

### إعداد أدلة الأدوات الخارجية

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

يمكن فصل الدلائل المتعددة بواسطة `:` (Linux/macOS) أو `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (مفرد) مدعوم أيضًا للتوافق مع الإصدارات السابقة.