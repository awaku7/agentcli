# 工具创建者指南

本指南介绍了如何将您自己的工具添加到 uag **而不修改 uag 本身**。
如果您想将工具直接添加到 uag 源代码树中，请参阅
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md)。

---

## 目录
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1。 [基本工具结构](#1-基本工具结构)
2. [创建 Python 工具](#2-创建-python-工具)
3. [创建 Rust + Python 工具](#3-creating-a-rust--python-tool)
4. [工具规格参考](#4-工具规格参考)
5。 [国际化 (i18n)](#5-国际化-i18n)
6。 [测试和调试](#6-测试和调试)
7. [参考示例](#7-参考-示例)

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


## 1. 基本工具结构

工具由以下元素组成：

|元素|必填 |描述 |
|---------|----------|-------------|
| `工具规格` |是的 |定义工具名称、描述和参数的字典 |
| `run_tool(args)` |是的 |调用该工具时执行的函数。 Args 是一个字典，return 是一个字符串。 |
| i18n JSON |推荐|翻译 JSON 文件（相同的基本名称，`<name>_tool.json`） |

### 最小 Python 工具

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

## 2. 创建 Python 工具

### 步骤

1. **设置 `UAGENT_EXTERNAL_TOOLS_DIRS` 环境变量**（如果尚未设置）

 示例：
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 多个目录可以用 `:` (Linux/macOS) 或 `;` (Windows) 分隔。
 `UAGENT_EXTERNAL_TOOLS_DIR` （单数）也支持向后兼容。

2。 **创建 Python 文件**

 文件名随意，但建议使用 `<name>_tool.py` 命名（例如 `my_tool.py`）。

3. **实现所需的元素**

 - `TOOL_SPEC` 字典
 - `run_tool(args)` 函数
 - 可选的 i18n JSON 文件

4。 **重新启动代理**（或运行 `system_reload` 工具）

### 完整模板

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

有关 i18n 详细信息，请参阅[第 5 节](#5-internationalization-i18n)。

---

## 3. 创建 Rust + Python 工具

Rust 实现非常适合性能关键型任务（繁重的数据处理、加密、文件处理等）。
uag 可以直接加载预构建的 `.pyd` 文件，因此 **最终用户不需要 `pip install`**。

### 工具结构

Rust 工具由以下部分组成文件:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

要进行分发，请将 `_tool.py` + `_tool.json` + `.pyd` 文件放在 
`UAGENT_EXTERNAL_TOOLS_DIRS` 中。

### 步骤

#### 第 1 步：创建 Rust project

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

#### 步骤 2：Rust 实现(src/lib.rs)

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

**要点：**
- 使用 `#[pyfunction(name = "run_<name>")]` 公开函数
- 返回类型为 `PyResult<String>`
- `#[pymodule]` 函数名称必须与 crate 名称匹配(`my_rust_tools`)

#### 步骤 3：构建

```bash
cd my_rust_tool
cargo build --release
```

Windows：将 `target/release/my_rust_tools.dll` 重命名为 `my_rust_tools.pyd`
Linux：重命名`target/release/libmy_rust_tools.so` 为 `my_rust_tools.so`
macOS：将 `target/release/libmy_rust_tools.dylib` 重命名为 `my_rust_tools.so`

或使用 maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### 步骤 4：创建Python 包装器

在 `UAGENT_EXTERNAL_TOOLS_DIRS` 目录中创建 `my_rust_tool.py`：

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

**``load_rust_pyd()`` 解析顺序：**

1。在与包装器`.py`相同的目录中查找`<module_name>.pyd`（或`.so`）
2。回退到 pip 安装的模块

#### 步骤 5：分发

仅需要这 3 个文件。最终用户**不需要**任何`pip install`。

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

###注释

- **仅构建时：**需要Rust工具链和`maturin`
 ```bash
  pip install maturin
  ```
- Rust箱子名称(`Cargo.toml` 中的`[lib] name`) 必须与 `load_rust_pyd()` 的第一个参数匹配
- 包装文件名和 `.pyd` 位置是独立的，只要它们在同一目录中即可

---

## 4. TOOL_SPEC 参考

### 基本结构

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

### 属性

|领域 |类型 |描述 |
|--------|------|-------------|
| `类型` | STR |始终"功能"|
| `x_build` | STR | `"rust"` 用于 Rust 实现（对于 Python 则省略） |
| `工具类型` | STR |流派名称（可选）。启用基于类型的控制 |
| `工具级别` |整数 | 0=启用，1=有条件（默认），-1=禁用|
| `函数名称` | STR | **必需的**。工具名称（小写+数字+下划线）|
| `功能.描述` | STR | **必需的**。描述 |
| `function.x_search_terms` |列表[str] |国际化搜索关键字（用 `_(...)` 括起来）|
| `function.x_search_terms_en` |列表[str] |修复了英文搜索关键字 |
| `函数.参数` |字典 |参数定义（OpenAI 函数调用格式）|

---

## 5. 国际化（i18n）

### 翻译机制

调用`make_tool_translator(__file__)`从`.json`文件加载翻译
相同的基名目录。

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### 使用翻译键

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON 文件格式

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

查看现有支持的语言代码的 `_tool.json` 文件。

---

## 6. 测试和调试

### 语法检查

```bash
python -m py_compile my_tool.py
```

### 验证工具正在加载

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### 错误日志

工具加载期间的错误将打印到 stderr。如果您的工具未加载，
检查 uag 启动日志。

---

## 7. 参考示例

### Python 工具示例

- `date_calc_tool.py`（在 `src/uagent/tools/` 中）— 日期计算。外部复制并自定义。
- `calculator_tool.py` （在 `src/uagent/tools/` 中） — 计算器。

### Rust 工具示例

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` （在 `src/uagent/tools_rust/` 中） — UUID生成
- `rust_slugify_tool.py` + `uag_tools_rust.pyd`（在`src/uagent/tools_rust/`中）- Slug 转换

将`_tool.py`和`.pyd`文件复制到`UAGENT_EXTERNAL_TOOLS_DIRS`中以将它们用作外部工具。

###设置外部工具目录

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

多个目录可以用 `:` (Linux/macOS) 或 `;` (Windows) 分隔。
`UAGENT_EXTERNAL_TOOLS_DIR`（单数）也支持向后兼容。