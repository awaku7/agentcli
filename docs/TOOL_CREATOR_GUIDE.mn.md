# Хэрэгслийн Зохиогчийн гарын авлага

Энэ гарын авлага нь **uag-г өөрөө өөрчлөхгүйгээр** өөрийн хэрэглүүрийг uag-д хэрхэн нэмэхийг тайлбарладаг.
Хэрэв та uag эхийн мод руу шууд хэрэгсэл нэмэхийг хүсвэл, үзнэ үү
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Агуулга
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Үндсэн хэрэгслийн бүтэц](#1-үндсэн багаж-бүтэц)
2. [Python хэрэгсэл үүсгэх](#2-python-tool үүсгэх)
3. [Rust + Python хэрэгсэл үүсгэх](#3-зэв үүсгэх--python-tool)
4. [TOOL_SPEC лавлагаа](#4-хэрэгслийн_техникийн лавлагаа)
5. [Internationalization (i18n)](#5-Internationalization-i18n)
6. [Туршилт ба дибаг хийх](#6-туршилт, дибаг хийх)
7. [Лавлах жишээ](#7-лавлагаа-жишээнүүд)

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


## 1. Багажны үндсэн бүтэц

Хэрэгсэл нь дараах элементүүдээс бүрдэнэ:

| Элемент | Шаардлагатай | Тайлбар |
|---------|----------|-------------|
| `TOOL_SPEC` | Тийм | Хэрэгслийн нэр, тайлбар, параметрүүдийг тодорхойлсон толь бичиг |
| `run_tool(args)` | Тийм | Хэрэгслийг дуудах үед гүйцэтгэсэн функц. Args нь дикт, буцах нь тэмдэгт мөр юм. |
| i18n JSON | Зөвлөмж болгож байна | Орчуулгын JSON файл (ижил үндсэн нэр, `<name>_tool.json`) |

### Python-ийн хамгийн бага хэрэгсэл
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

## 2. Python хэрэгсэл үүсгэх

### Алхамууд

1. **`UAGENT_EXTERNAL_TOOLS_DIRS` орчны хувьсагчийг тохируулна уу** (хэрэв өмнө нь тохируулаагүй бол)

   Жишээ:
   ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

   Олон санг `:` (Linux/macOS) эсвэл `;` (Windows) -аар тусгаарлаж болно.
   `UAGENT_EXTERNAL_TOOLS_DIR` (ганц тоо) нь мөн хойшлогдсон нийцтэй байдлыг дэмждэг.

2. **Python файл үүсгэх**

   Файлын нэр үнэ төлбөргүй боловч `<name>_tool.py` гэж нэрлэхийг зөвлөж байна (жишээ нь `my_tool.py`).

3. **Шаардлагатай элементүүдийг хэрэгжүүлэх**

   - `TOOL_SPEC` толь бичиг
   - `run_tool(args)` функц
   - Сонголтоор i18n JSON файл

4. **Агентыг дахин эхлүүлнэ үү** (эсвэл `system_reload` хэрэгслийг ажиллуулна уу)

### Бүрэн загвар
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

i18n-ийн дэлгэрэнгүйг [5-р хэсэг](#5-internationalization-i18n) хэсгээс үзнэ үү.

---

## 3. Rust + Python хэрэгсэл үүсгэх

Rust хэрэгжүүлэлт нь гүйцэтгэлийн чухал ажлуудад (хүнд өгөгдөл боловсруулах, криптограф, файл боловсруулах гэх мэт) тохиромжтой.
uag нь урьдчилан бүтээгдсэн `.pyd` файлуудыг шууд ачаалах боломжтой тул **эцсийн хэрэглэгчид `pip суулгах` шаардлагагүй**.

### Хэрэгслийн бүтэц

Rust хэрэгсэл нь дараах файлуудаас бүрдэнэ:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Түгээхдээ `_tool.py` + `_tool.json` + `.pyd` файлуудыг 
`UAGENT_EXTERNAL_TOOLS_DIRS` дотор байрлуулна уу.

### Алхамууд

#### Алхам 1: Rust төсөл үүсгэх

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

#### Алхам 2: Rust хэрэгжилт (src/lib.rs)

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

**Гол санаанууд:**
- Функцуудыг `#[pyfunction(name = "run_<name>")]` ашиглан ил гаргах
- Буцах төрөл нь `PyResult<String>`
- `#[pymodule]` функцийн нэр нь crate-ийн нэртэй (`my_rust_tools`) таарч байх ёстой

#### Алхам 3: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: `target/release/my_rust_tools.dll`-ийн нэрийг `my_rust_tools.pyd` болгож өөрчлөх
Linux: `target/release/libmy_rust_tools.so`-ийн нэрийг `my_rust_tools.so`
macOS: `target/release/libmy_rust_tools.dylib`-ийн нэрийг `my_rust_tools.so`

Эсвэл maturin ашиглан:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Алхам 4: Python wrapper үүсгэх

`my_rust_tool.py`-г `UAGENT_EXTERNAL_TOOLS_DIRS` лавлах дотор үүсгэ:

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

**``load_rust_pyd()`` шийдвэрлэх дараалал:**

1. wrapper `.py`-тай ижил лавлахаас `<module_name>.pyd` (эсвэл `.so`)-г хайх
2. Pip суулгасан модуль руу буцах

#### Алхам 5: Түгээлт

Зөвхөн эдгээр 3 файл хэрэгтэй. Эцсийн хэрэглэгчид **pip суулгац хийх шаардлагагүй**.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Тэмдэглэл

- **Зөвхөн бүтээх хугацаа:** Rust хэрэгслийн гинж болон `maturin` шаардлагатай
  ```bash
  pip install maturin
  ```
- Rust crate нэр (`Cargo.toml` дахь `[lib] name`) нь `load_rust_pyd()`-ийн эхний аргументтай тохирч байх ёстой
- wrapper файлын нэр болон `.pyd` байршил нь нэг директорт байгаа л бол бие даасан байна

---

## 4. TOOL_SPEC лавлагаа

### Үндсэн бүтэц

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

| Талбар | Төрөл | Тодорхойлолт |
|-------|------|-------------|
| `type` | str | Үргэлж `"function"` |
| `x_build` | str | Rust хэрэгжүүлэхэд `"rust"` (Python-г орхигдуулсан) |
| `tool_genre` | str | Төрлийн нэр (заавал биш). Төрөлд суурилсан хяналтыг идэвхжүүлдэг |
| `tool_level` | int | 0=идэвхжүүлсэн, 1=нөхцөлт (өгөгдмөл), -1=идэвхгүй |
| `function.name` | str | **Шаардлагатай**. Хэрэгслийн нэр (жижиг үсэг + цифр + доогуур зураас) |
| `function.description` | str | **Шаардлагатай**. Тайлбар |
| `function.x_search_terms` | list[str] | i18n-д мэдлэгтэй хайлтын түлхүүр үгс (`_(...)`-ээр боох) |
| `function.x_search_terms_en` | list[str] | Англи хэлний тогтмол хайлтын түлхүүр үгс |
| `function.parameters` | dict | Параметрийн тодорхойлолт (OpenAI функц дуудах формат) |

---

## 5. Олон улсын хэлбэрт оруулах (i18n)

### Орчуулгын механизм

`make_tool_translator(__file__)`-г дуудах нь ижил нэртэй `.json` файлаас ижил лавлах руу орчуулгыг ачаална.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Орчуулгын түлхүүрүүдийг ашиглах

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON файлын формат

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

Дэмжигдсэн хэлний кодуудыг одоо байгаа `_tool.json` файлуудаас харна уу.

---

## 6. Туршилт ба дибаг хийх

### Синтакс шалгах

```bash
python -m py_compile my_tool.py
```

### Хэрэгсэл ачаалж байгааг баталгаажуулах

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Алдааны бүртгэл

Хэрэгслийг ачаалах үед гарсан алдааг stderr дээр хэвлэдэг. Хэрэв таны хэрэгсэл ачаалагдаагүй бол
uag эхлүүлэх бүртгэлийг шалгана уу.

---

## 7. Лавлах жишээнүүд

### Python хэрэгслийн жишээнүүд

- `date_calc_tool.py` (`src/uagent/tools/` дотор) — Огнооны тооцоо. Гаднаас хуулж, өөрчилнө үү.
- `calculator_tool.py` (`src/uagent/tools/` дотор) — Тооны машин.

### Rust хэрэгслийн жишээнүүд

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/` дотор) — UUID үүсгэх
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/` дотор) — Slug хөрвүүлэх

`_tool.py` болон `.pyd` файлуудыг `UAGENT_EXTERNAL_TOOLS_DIRS` руу хуулж гадаад хэрэгсэл болгон ашиглах.

### Гадаад хэрэгслийн лавлахуудыг тохируулах

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Олон лавлахыг `:` (Linux/macOS) эсвэл `;` (Windows) -аар тусгаарлаж болно.
`UAGENT_EXTERNAL_TOOLS_DIR` (ганц тоо) нь мөн хойшлогдсон нийцтэй байдлыг дэмждэг.

---

*Энэ орчуулгыг автоматаар үүсгэсэн. Хамгийн үнэн зөв, хамгийн сүүлийн үеийн контентыг англи хэл дээрх хувилбараас үзнэ үү.*