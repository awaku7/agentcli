# Посібник із створення інструментів

Цей посібник пояснює, як додати власні інструменти до uag **без зміни самого uag**.
Якщо ви хочете додати інструмент безпосередньо до дерева вихідних кодів uag, див.
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Зміст

1. [Структура базового інструменту] (#1-структура базового інструменту)
2. [Створення інструменту Python](#2-creating-a-python-tool)
3. [Створення інструменту Rust + Python](#3-creating-a-rust--python-tool)
4. [Довідка щодо TOOL_SPEC](#4-tool_spec-reference)
5. [Інтернаціоналізація (i18n)](#5-internationalization-i18n)
6. [Тестування та налагодження](#6-testing-and-debugging)
7. [Довідкові приклади](#7-reference-examples)

---

## 1. Базова структура інструменту

Інструмент складається з таких елементів:

| Елемент | Необхідно | Опис |
|---------|----------|-------------|
| `TOOL_SPEC` | Так | Словник із визначенням назви, опису та параметрів інструменту |
| `запуск_інструмента(аргументи)` | Так | Функція, яка виконується під час виклику інструменту. Аргументи — це dict, return — рядок. |
| i18n JSON | Рекомендовано | Переклад файлу JSON (те саме базове ім'я, `<name>_tool.json`) |

### Мінімальний інструмент Python
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

## 2. Створення інструмента Python

### Кроки

1. **Установіть змінну середовища `UAGENT_EXTERNAL_TOOLS_DIRS`** (якщо ще не встановлено)

 Приклад:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Кілька каталогів можна розділити символом `:` (Linux/macOS) або `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (в однині) також є підтримується для зворотної сумісності.

2. **Створіть файл Python**

 Ім'я файлу є безкоштовним, але рекомендовано використовувати назву `<name>_tool.py` (наприклад, `my_tool.py`).

3. **Реалізація необхідних елементів**

 - Словник `TOOL_SPEC`
 - Функція `run_tool(args)`
 - За бажанням файл i18n JSON

4. **Перезапустіть агент** (або запустіть інструмент `system_reload`)

### Повний шаблон
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

Див. [Розділ 5](#5-internationalization-i18n) для деталей i18n.

---

## 3. Створення Rust + Python Інструмент

Інструментація Rust ідеально підходить для критичних для продуктивності завдань (важка обробка даних, криптографія, обробка файлів тощо).
uag може безпосередньо завантажувати попередньо зібрані файли `.pyd`, тому **кінцевим користувачам не потрібно `pip install`**.

### Структура інструменту

Інструмент Rust складається з наступного: файли:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Для поширення розмістіть файли `_tool.py` + `_tool.json` + `.pyd` у 
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Кроки

#### Крок 1: Створіть Rust project

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

#### Крок 2: Реалізація Rust (src/lib.rs)

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

**Ключові моменти:**
- Відкрити функції за допомогою `#[pyfunction(name = "run_<name>")]`
- Тип повернення: `PyResult<String>`
- Назва функції `#[pymodule]` має збігатися з назвою ящика (`my_rust_tools`)

#### Крок 3: Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: перейменуйте `target/release/my_rust_tools.dll` на `my_rust_tools.pyd`
Linux: перейменуйте `target/release/libmy_rust_tools.so` на `my_rust_tools.so`
macOS: перейменуйте `target/release/libmy_rust_tools.dylib` до `my_rust_tools.so`

Або за допомогою maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Крок 4. Створіть оболонку Python

Створіть `my_rust_tool.py` у своєму Каталог `UAGENT_EXTERNAL_TOOLS_DIRS`:

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

**``load_rust_pyd()`` порядок вирішення:**

1. Шукайте `<назва_модуля>.pyd` (або `.so`) у тому самому каталозі, що й оболонка `.py`
2. Поверніться до модуля, встановленого за допомогою pip

#### Крок 5: Розповсюдження

Потрібні лише ці 3 файли. Кінцевим користувачам **не** потрібна `інсталяція pip`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Примітки

- **Лише час збірки:** необхідні Rust toolchain і `maturin`
 ```bash
  pip install maturin
  ```
- Ім'я ящика Rust (`[lib] ім'я` в `Cargo.toml`) має збігатися з першим аргументом `load_rust_pyd()`
- Назва файлу-оболонки та розташування `.pyd` є незалежними, доки вони знаходяться в одному каталозі

---

## 4. TOOL_SPEC Reference

### Базовий Структура

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

### Властивості

| Поле | Тип | Опис |
|-------|------|-------------|
| `тип` | вул | Завжди `"функція"` |
| `x_build` | вул | `"rust"` для реалізації Rust (опущено для Python) |
| `жанр_інструмента` | вул | Назва жанру (необов'язково). Вмикає керування на основі жанру |
| `рівень_інструмента` | int | 0=увімкнено, 1=умовно (за замовчуванням), -1=вимкнено |
| `назва.функції` | вул | **Обов'язково**. Назва інструменту (малі літери + цифри + підкреслення) |
| `функція.опис` | вул | **Обов'язково**. Опис |
| `function.x_search_terms` | список [str] | Ключові слова пошуку з підтримкою i18n (обгорнути `_(...)`) |
| `function.x_search_terms_en` | список [str] | Виправлено ключові слова пошуку англійською |
| `функція.параметри` | дикт | Визначення параметра (формат виклику функції OpenAI) |

---

## 5. Інтернаціоналізація (i18n)

### Механізм перекладу

Виклик `make_tool_translator(__file__)` завантажує переклади з файлу `.json`
з тією самою базовою назвою в тому самому каталог.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Використання ключів перекладу

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Формат файлу JSON

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

Див. наявні файли `_tool.json` для інформації про підтримувану мову коди.

---

## 6. Тестування та налагодження

### Перевірка синтаксису

```bash
python -m py_compile my_tool.py
```

### Перевірка завантаження інструменту

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Журнали помилок

Помилки під час роботи інструменту завантаження друкуються в stderr. Якщо ваш інструмент не завантажується,
перевірте журнали запуску uag.

---

## 7. Довідкові приклади

### Приклади інструментів Python

- `date_calc_tool.py` (у `src/uagent/tools/`) — Обчислення дати. Скопіюйте назовні та налаштуйте.
- `calculator_tool.py` (у `src/uagent/tools/`) — Калькулятор.

### Приклади Rust Tool

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (у `src/uagent/tools_rust/`) — Генерація UUID
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (у `src/uagent/tools_rust/`) — Перетворення слизня

Скопіюйте файли `_tool.py` і `.pyd` у `UAGENT_EXTERNAL_TOOLS_DIRS`, щоб використовувати їх як зовнішні інструменти.

### Налаштування каталогів зовнішніх інструментів

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Кілька каталогів можна розділити символом `:` (Linux/macOS) або `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (однина) також підтримується для зворотної сумісності.

---

*Цей переклад було згенеровано автоматично. Щоб отримати найбільш точний і актуальний вміст, зверніться до англійської версії.*