# Руководство для создателей инструментов

В этом руководстве объясняется, как добавить свои собственные инструменты в uag **без изменения самого uag**.
Если вы хотите добавить инструмент непосредственно в дерево исходного кода uag, см. 
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Содержание
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Базовая структура инструмента](#1-базовая-структура-инструмента)
2. [Создание инструмента Python](#2-создание-инструмента-python)
3. [Создание инструмента Rust + Python](#3-creating-a-rust--python-tool)
4. [Справочник по TOOL_SPEC](#4-tool_spec-reference)
5. [Интернационализация (i18n)](#5-интернационализация-i18n)
6. [Тестирование и отладка](#6-тестирование-и-отладка)
7. [Справочные примеры](#7-reference-examples)

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


## 1. Базовая структура инструмента

Инструмент состоит из следующих элементов:

| Элемент | Требуется | Описание |
|---------|----------|-------------|
| `TOOL_SPEC` | Да | Словарь, определяющий имя, описание и параметры инструмента |
| `run_tool(args)` | Да | Функция, выполняемая при вызове инструмента. Args — это dict, return — строка. |
| i18n JSON | Рекомендуется | JSON-файл перевода (то же базовое имя, `<name>_tool.json`) |

### Минимальный инструмент Python

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

## 2. Создание инструмента Python

### Шаги

1. **Установите переменную среды `UAGENT_EXTERNAL_TOOLS_DIRS`** (если она еще не установлена)

 Пример:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Несколько каталогов можно разделить `:` (Linux/macOS) или `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (единственное число) также поддерживается для обратной совместимости.

2. **Создайте файл Python**

 Имя файла произвольное, но рекомендуется использовать имя `<name>_tool.py` (например, `my_tool.py`).

3. **Реализуйте необходимые элементы**

 – словарь `TOOL_SPEC`
 – функцию `run_tool(args)`
 – опционально файл i18n JSON

4. **Перезапустите агент** (или запустите инструмент `system_reload`)

### Полный шаблон

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

См. [Раздел 5](#5-internationalization-i18n) для i18n подробности.

---

## 3. Создание инструмента Rust + Python

Реализация Rust идеально подходит для задач, критичных к производительности (интенсивная обработка данных, криптография, обработка файлов и т. д.).
uag может загружать предварительно созданные файлы `.pyd` напрямую, поэтому **конечным пользователям не нужен `pip install`**.

### Структура инструмента

Инструмент Rust состоит из следующих файлов:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Для распространения поместите файлы `_tool.py` + `_tool.json` + `.pyd` in
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Шаги

#### Шаг 1. Создайте Rust project

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

#### Шаг 2. Реализация Rust (src/lib.rs)

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

**Ключевые моменты:**
- Предоставляйте функции с помощью `#[pyfunction(name = "run_<name>")]`
- Тип возвращаемого значения: `PyResult<String>`
- Имя функции `#[pymodule]` должно совпадать с именем крейта (`my_rust_tools`)

#### Шаг 3. Сборка

```bash
cd my_rust_tool
cargo build --release
```

Windows: переименуйте `target/release/my_rust_tools.dll` в `my_rust_tools.pyd`
Linux: переименуйте `target/release/libmy_rust_tools.so` в `my_rust_tools.so`
macOS: переименуйте `target/release/libmy_rust_tools.dylib` в `my_rust_tools.so`

Или используйте maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Шаг 4. Создайте оболочку Python

Создайте `my_rust_tool.py` в вашем `UAGENT_EXTERNAL_TOOLS_DIRS` каталог:

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

**``load_rust_pyd()`` порядок разрешения:**

1. Найдите `<имя_модуля>.pyd` (или `.so`) в том же каталоге, что и оболочка `.py`
2. Вернитесь к модулю, установленному в pip

#### Шаг 5. Распространение

Требуются только эти 3 файла. Конечным пользователям **не** требуется никакая `pip install`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Примечания

- **Только во время сборки:** Требуются набор инструментов Rust и Maturin
 ```bash
  pip install maturin
  ```
- Имя крейта Rust (`[lib] name` в `Cargo.toml`) должно соответствовать первому аргументу `load_rust_pyd()`
- Имя файла оболочки и местоположение `.pyd` независимы, пока они находятся в одном и том же каталоге

---

## 4. Справочник по Tool_SPEC

### Basic Структура

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

### Свойства

| Поле | Тип | Описание |
|-------|------|-------------|
| `тип` | ул | Всегда `"функция"` |
| `x_build` | ул | `"rust"` для реализации Rust (опустить для Python) |
| `tool_genre` | ул | Название жанра (необязательно). Включает управление по жанрам |
| `tool_level` | интервал | 0=включено, 1=условно (по умолчанию), -1=выключено |
| `функция.имя` | ул | **Необходимый**. Имя инструмента (строчные буквы + цифры + подчеркивание) |
| `функция.описание` | ул | **Необходимый**. Описание |
| `function.x_search_terms` | список[строка] | Ключевые слова поиска с поддержкой i18n (оберните с помощью `_(...)`) |
| `function.x_search_terms_en` | список[строка] | Исправлены ключевые слова для поиска на английском языке |
| `функция.параметры` | диктовать | Определение параметра (формат вызова функции OpenAI) |

---

## 5. Интернационализация (i18n)

### Механизм перевода

Вызов `make_tool_translator(__file__)` загружает переводы из файла `.json`
с тем же базовым именем в том же самом каталог.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Использование ключей перевода

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Файл JSON Формат

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

Поддерживаемые коды языков см. в существующих файлах `_tool.json`.

---

## 6. Тестирование и отладка

### Синтаксис Проверьте

```bash
python -m py_compile my_tool.py
```

### Проверка загрузки инструмента

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Журналы ошибок

Ошибки во время загрузки инструмента выводятся в stderr. Если ваш инструмент не загружен,
проверьте журналы запуска uag.

---

## 7. Справочные примеры

### Примеры инструментов Python

- `date_calc_tool.py` (в `src/uagent/tools/`) — расчет даты. Скопируйте извне и настройте.
- `calculator_tool.py` (в `src/uagent/tools/`) — Калькулятор.

### Примеры инструментов Rust

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (в `src/uagent/tools_rust/`) — Генерация UUID
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (в `src/uagent/tools_rust/`) — преобразование URL-адресов

Скопируйте файлы `_tool.py` и `.pyd` в `UAGENT_EXTERNAL_TOOLS_DIRS`, чтобы использовать их как внешние инструменты.

### Настройка внешних каталогов инструментов

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Несколько каталогов можно разделить `:` (Linux/macOS) или `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (единственное число) также поддерживается для обратной совместимости.