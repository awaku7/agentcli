# คู่มือผู้สร้างเครื่องมือ

คู่มือนี้จะอธิบายวิธีเพิ่มเครื่องมือของคุณเองลงใน uag **โดยไม่ต้องแก้ไข uag เอง**
หากคุณต้องการเพิ่มเครื่องมือลงในแผนผังแหล่งที่มา uag โดยตรง ดู
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## สารบัญ

1. [โครงสร้างเครื่องมือพื้นฐาน](#1-โครงสร้างเครื่องมือพื้นฐาน)
2. [การสร้างเครื่องมือ Python](#2-creating-a-python-tool)
3. [การสร้างเครื่องมือ Rust + Python](#3-creating-a-rust--python-tool)
4. [การอ้างอิง TOOL_SPEC](#4-tool_spec-reference)
5. [การทำให้เป็นสากล (i18n)](#5-การทำให้เป็นสากล-i18n)
6. [การทดสอบและการดีบัก](#6-การทดสอบและการดีบัก)
7. [ตัวอย่างอ้างอิง](#7-reference-examples)

---

## 1. โครงสร้างเครื่องมือพื้นฐาน

เครื่องมือประกอบด้วยองค์ประกอบต่อไปนี้:

| องค์ประกอบ | จำเป็น | |
|---------|---------|-------------|
| `TOOL_SPEC` | ใช่ | พจนานุกรมที่กำหนดชื่อเครื่องมือ คำอธิบาย และพารามิเตอร์ |
| `run_tool(args)` | ใช่ | ฟังก์ชั่นที่ดำเนินการเมื่อมีการเรียกใช้เครื่องมือ Args คือ dict ส่วน return คือสตริง |
| i18n JSON | แนะนำ | การแปลไฟล์ JSON (ชื่อฐานเดียวกัน `<name>_tool.json`) |

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

## 2. การสร้างเครื่องมือ Python

### ขั้นตอน

1. **ตั้งค่าตัวแปรสภาพแวดล้อม `UAGENT_EXTERNAL_TOOLS_DIRS`** (หากยังไม่ได้ตั้งค่า)

 ตัวอย่าง:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 หลายไดเรกทอรีสามารถแยกได้ด้วย `:` (Linux/macOS) หรือ `;` (Windows)
 `UAGENT_EXTERNAL_TOOLS_DIR` (เอกพจน์) ยังรองรับความเข้ากันได้แบบย้อนหลังอีกด้วย

2. **สร้างไฟล์ Python**

 ชื่อไฟล์นั้นฟรี แต่แนะนำให้ตั้งชื่อไฟล์ `<name>_tool.py` (เช่น `my_tool.py`)

3. **ติดตั้งองค์ประกอบที่จำเป็น**

 - พจนานุกรม `TOOL_SPEC`
 - ฟังก์ชัน `run_tool(args)`
 - หรืออาจเป็นไฟล์ JSON i18n

4. **รีสตาร์ทเอเจนต์** (หรือเรียกใช้เครื่องมือ `system_reload`)

### เทมเพลตแบบเต็ม

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

ดู [ส่วนที่ 5](#5-internationalization-i18n) สำหรับรายละเอียด i18n

---

## 3. การสร้างเครื่องมือ Rust + Python

การใช้งาน Rust นั้นเหมาะอย่างยิ่งสำหรับงานที่เน้นประสิทธิภาพ (การประมวลผลข้อมูลจำนวนมาก การเข้ารหัส การประมวลผลไฟล์ ฯลฯ)
uag สามารถโหลดไฟล์ `.pyd` ที่สร้างไว้ล่วงหน้าได้โดยตรง ดังนั้น **ผู้ใช้ปลายทางไม่จำเป็นต้อง `pip install`**.

### โครงสร้างเครื่องมือ

เครื่องมือ Rust ประกอบด้วยสิ่งต่อไปนี้ files:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

สำหรับการแจกจ่าย ให้วางไฟล์ `_tool.py` + `_tool.json` + `.pyd` ไว้ใน
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### ขั้นตอน

#### ขั้นตอนที่ 1: สร้าง โครงการ Rust

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

#### ขั้นตอนที่ 2: การใช้งานสนิม (src/lib.rs)

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

**ประเด็นสำคัญ:**
- แสดงฟังก์ชันด้วย `#[pyfunction(name = "run_<name>")]`
- ประเภทการส่งคืนคือ `PyResult<String>`
- ชื่อฟังก์ชัน `#[pymodule]` จะต้องตรงกับชื่อลัง (`my_rust_tools`)

#### ขั้นตอนที่ 3: สร้าง

```bash
cd my_rust_tool
cargo build --release
```

Windows: เปลี่ยนชื่อ `target/release/my_rust_tools.dll` เป็น `my_rust_tools.pyd`
Linux: เปลี่ยนชื่อ `target/release/libmy_rust_tools.so` เป็น `my_rust_tools.so`
macOS: เปลี่ยนชื่อ `target/release/libmy_rust_tools.dylib` เป็น `my_rust_tools.so`

หรือใช้ maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### ขั้นตอน 4: สร้าง Python wrapper

สร้าง `my_rust_tool.py` ในไดเรกทอรี `UAGENT_EXTERNAL_TOOLS_DIRS` ของคุณ:

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

**``load_rust_pyd()`` ลำดับการแก้ปัญหา:**

1. ค้นหา `<module_name>.pyd` (หรือ `.so`) ในไดเร็กทอรีเดียวกันกับ wrapper `.py`
2 ถอยกลับไปที่โมดูลที่ติดตั้ง pip

#### ขั้นตอนที่ 5: การแจกจ่าย

ต้องใช้ 3 ไฟล์เหล่านี้เท่านั้น ผู้ใช้ปลายทาง **ไม่** ต้องการ `pip install` ใดๆ

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### หมายเหตุ

- **เวลาสร้างเท่านั้น:** ต้องใช้ toolchain ที่เป็นสนิมและ `maturin`
 ```bash
  pip install maturin
  ```
- ชื่อลังสนิม (`[lib] name` ใน `Cargo.toml`) ต้องตรงกับอาร์กิวเมนต์แรกของ `load_rust_pyd()`
- ชื่อไฟล์ wrapper และตำแหน่ง `.pyd` มีความเป็นอิสระตราบใดที่อยู่ในไดเร็กทอรีเดียวกัน

---

## 4. การอ้างอิง TOOL_SPEC

### พื้นฐาน โครงสร้าง

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

### คุณสมบัติ

| สนาม | พิมพ์ | คำอธิบาย |
|-------|------|-------------|
| `พิมพ์` | STR | `"function"` |
| เสมอ `x_build` | STR | `"rust"` สำหรับการใช้งาน Rust (ละเว้นสำหรับ Python) |
| `ประเภทเครื่องมือ` | STR | ชื่อประเภท (ไม่บังคับ) เปิดใช้งานการควบคุมตามประเภท |
| `ระดับเครื่องมือ` | อินท์ | 0=เปิดใช้งาน, 1=มีเงื่อนไข (ค่าเริ่มต้น), -1=ปิดใช้งาน |
| `function.name` | STR | **ที่จำเป็น**. ชื่อเครื่องมือ (ตัวพิมพ์เล็ก + หลัก + ขีดล่าง) |
| `function.description` | STR | **ที่จำเป็น**. คำอธิบาย |
| `function.x_search_terms` | รายการ[str] | คำค้นหาที่ทราบโดย i18n (ปิดท้ายด้วย `_(...)`) |
| `function.x_search_terms_en` | รายการ[str] | แก้ไขคำค้นหาภาษาอังกฤษ |
| `function.parameters` | คำสั่ง | คำจำกัดความของพารามิเตอร์ (รูปแบบการเรียกฟังก์ชัน OpenAI) |

---

## 5. การทำให้เป็นสากล (i18n)

### กลไกการแปล

การเรียก `make_tool_translator(__file__)` จะโหลดการแปลจากไฟล์ `.json`
ที่มีชื่อฐานเดียวกันในชื่อเดียวกัน directory.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### การใช้คีย์การแปล

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### รูปแบบไฟล์ JSON

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

ดูที่มีอยู่ ไฟล์ `_tool.json` สำหรับรหัสภาษาที่รองรับ

---

## 6. การทดสอบและการดีบัก

### ตรวจสอบไวยากรณ์

```bash
python -m py_compile my_tool.py
```

### เครื่องมือตรวจสอบ กำลังโหลด

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### บันทึกข้อผิดพลาด

ข้อผิดพลาดระหว่างการโหลดเครื่องมือจะถูกพิมพ์ไปที่ stderr หากเครื่องมือของคุณไม่ได้โหลด
ตรวจสอบบันทึกการเริ่มต้น uag

---

## 7. ตัวอย่างอ้างอิง

### Python Tool Examples

- `date_calc_tool.py` (ใน `src/uagent/tools/`) — การคำนวณวันที่ คัดลอกภายนอกและปรับแต่ง
- `calculator_tool.py` (ใน `src/uagent/tools/`) — เครื่องคิดเลข

### ตัวอย่างเครื่องมือสนิม

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (ใน `src/uagent/tools_rust/`) — UUID รุ่น
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (ใน `src/uagent/tools_rust/`) — การแปลง Slug

คัดลอกไฟล์ `_tool.py` และ `.pyd` ลงใน `UAGENT_EXTERNAL_TOOLS_DIRS` เพื่อใช้เป็นเครื่องมือภายนอก

### การตั้งค่าไดเรกทอรีเครื่องมือภายนอก

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

หลายไดเรกทอรีสามารถแยกออกได้ด้วย `:` (Linux/macOS) หรือ `;` (Windows)
`UAGENT_EXTERNAL_TOOLS_DIR` (เอกพจน์) ยังได้รับการสนับสนุนสำหรับความเข้ากันได้แบบย้อนหลัง