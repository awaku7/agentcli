# Hướng dẫn tạo công cụ

Hướng dẫn này giải thích cách thêm các công cụ của riêng bạn vào uag **mà không sửa đổi chính uag**.
Nếu bạn muốn thêm một công cụ trực tiếp vào cây nguồn uag, xem
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Mục lục
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Cấu trúc công cụ cơ bản](#1-cấu-trúc-công-cụ-cơ-bản)
2. [Tạo công cụ Python](#2-creating-a-python-tool)
3. [Tạo công cụ Rust + Python](#3-creating-a-rust--python-tool)
4. [Tham khảo TOOL_SPEC](#4-tool_spec-reference)
5. [Quốc tế hóa (i18n)](#5-internationalization-i18n)
6. [Kiểm tra và gỡ lỗi](#6-kiểm-tra-và-gỡ-lỗi)
7. [Ví dụ tham khảo](#7-reference-examples)

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


## 1. Cấu trúc công cụ cơ bản

Một công cụ bao gồm các phần tử sau:

| Yếu tố | Bắt buộc | Mô tả |
|---------|----------|-------------|
| `TOOL_SPEC` | Có | Từ điển xác định tên, mô tả và tham số của công cụ |
| `run_tool(args)` | Có | Chức năng được thực thi khi công cụ được gọi. Args là một lệnh, return là một chuỗi. |
| i18n JSON | Được đề xuất | Tệp JSON dịch (cùng tên cơ sở, `<name>_tool.json`) |

### Công cụ Python tối thiểu

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

## 2. Tạo công cụ Python

### Các bước

1. **Đặt biến môi trường `UAGENT_EXTERNAL_TOOLS_DIRS`** (nếu chưa được đặt)

 Ví dụ:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Nhiều thư mục có thể được phân tách bằng `:` (Linux/macOS) hoặc `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (số ít) cũng được hỗ trợ để tương thích ngược.

2. **Tạo tệp Python**

 Tên tệp là miễn phí nhưng nên đặt tên `<name>_tool.py` (ví dụ: `my_tool.py`).

3. **Triển khai các phần tử bắt buộc**

 - `TOOL_SPEC` từ điển
 - `run_tool(args)` function
 - Tệp JSON i18n

4, tùy chọn. **Khởi động lại tác nhân** (hoặc chạy công cụ `system_reload`)

### Mẫu đầy đủ

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

Xem [Phần 5](#5-internationalization-i18n) để biết chi tiết về i18n.

---

## 3. Tạo a Rust + Python Tool

Triển khai Rust là lý tưởng cho các tác vụ quan trọng về hiệu suất (xử lý dữ liệu nặng, mật mã, xử lý tệp, v.v.).
uag có thể tải trực tiếp các tệp `.pyd` dựng sẵn, vì vậy **người dùng cuối không cần `pip install`**.

### Cấu trúc công cụ

Công cụ Rust bao gồm những công cụ sau files:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Để phân phối, hãy đặt các tệp `_tool.py` + `_tool.json` + `.pyd` trong
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Bước

#### Bước 1: Tạo dự án Rust

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

#### Bước 2: Triển khai Rust (src/lib.rs)

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

**Các điểm chính:**
- Hiển thị các hàm với `#[pyfunction(name = "run_<name>")]`
- Kiểu trả về là `PyResult<String>`
- Tên hàm `#[pymodule]` phải khớp với tên thùng (`my_rust_tools`)

#### Bước 3: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: đổi tên `target/release/my_rust_tools.dll` thành `my_rust_tools.pyd`
Linux: đổi tên `target/release/libmy_rust_tools.so` thành `my_rust_tools.so`
macOS: đổi tên `target/release/libmy_rust_tools.dylib` thành `my_rust_tools.so`

Hoặc sử dụng maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Bước 4: Tạo trình bao bọc Python

Tạo `my_rust_tool.py` trong thư mục `UAGENT_EXTERNAL_TOOLS_DIRS` của bạn:

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

**``load_rust_pyd()`` thứ tự độ phân giải:**

1. Tìm `<module_name>.pyd` (hoặc `.so`) trong cùng thư mục với trình bao bọc `.py`
2. Quay trở lại mô-đun được cài đặt bằng pip

#### Bước 5: Phân phối

Chỉ cần 3 tệp này. Người dùng cuối **không** cần bất kỳ `cài đặt pip` nào.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Ghi chú

- **Chỉ trong thời gian xây dựng:** Cần có chuỗi công cụ Rust và `maturin`
 ```bash
  pip install maturin
  ```
- Tên thùng Rust (`[lib] name` trong `Cargo.toml`) phải khớp với đối số đầu tiên của `load_rust_pyd()`
- Tên tệp trình bao bọc và vị trí `.pyd` độc lập miễn là chúng nằm trong cùng một thư mục

---

## 4. TOOL_SPEC Reference

### Basic Cấu trúc

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

### Thuộc tính

| Lĩnh vực | Loại | Mô tả |
|-------|------|-------------|
| `loại` | str | Luôn luôn `"chức năng"` |
| `x_build` | str | `"rust"` để triển khai Rust (bỏ qua cho Python) |
| `thể_công_cụ` | str | Tên thể loại (tùy chọn). Cho phép kiểm soát dựa trên thể loại |
| `cấp_công_cụ` | int | 0=đã bật, 1=có điều kiện (mặc định), -1=đã tắt |
| `function.name` | str | **Yêu cầu**. Tên công cụ (chữ thường + chữ số + dấu gạch dưới) |
| `function.description` | str | **Yêu cầu**. Mô tả |
| `function.x_search_terms` | danh sách[str] | Từ khóa tìm kiếm nhận biết i18n (được gói bằng `_(...)`) |
| `function.x_search_terms_en` | danh sách[str] | Đã sửa lỗi từ khóa tìm kiếm tiếng Anh |
| `function.parameters` | chính tả | Định nghĩa tham số (định dạng gọi hàm OpenAI) |

---

## 5. Quốc tế hóa (i18n)

### Cơ chế dịch thuật

Gọi `make_tool_translator(__file__)` tải các bản dịch từ tệp `.json`
có cùng tên cơ sở trong cùng một 

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Sử dụng phím dịch

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Định dạng tệp JSON

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

Xem hiện có Các tệp `_tool.json` cho mã ngôn ngữ được hỗ trợ.

---

## 6. Kiểm tra và gỡ lỗi

### Kiểm tra cú pháp

```bash
python -m py_compile my_tool.py
```

### Công cụ xác minh Đang tải

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Nhật ký lỗi

Lỗi trong quá trình tải công cụ được in ra thiết bị lỗi chuẩn. Nếu công cụ của bạn không được tải,
hãy kiểm tra nhật ký khởi động uag.

---

## 7. Ví dụ tham khảo

### Ví dụ về công cụ Python

- `date_calc_tool.py` (trong `src/uagent/tools/`) — Tính toán ngày. Sao chép bên ngoài và tùy chỉnh.
- `calculator_tool.py` (trong `src/uagent/tools/`) — Máy tính.

### Ví dụ về công cụ Rust

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (trong `src/uagent/tools_rust/`) — UUID thế hệ
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (trong `src/uagent/tools_rust/`) — Chuyển đổi sên

Sao chép tệp `_tool.py` và `.pyd` vào `UAGENT_EXTERNAL_TOOLS_DIRS` để sử dụng chúng làm bên ngoài tools.

### Thiết lập thư mục công cụ bên ngoài

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Nhiều thư mục có thể được phân tách bằng `:` (Linux/macOS) hoặc `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (số ít) cũng được hỗ trợ để tương thích ngược.