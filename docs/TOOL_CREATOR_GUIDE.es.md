# Guía del creador de herramientas

Esta guía explica cómo agregar sus propias herramientas a uag **sin modificar el propio uag**.
Si desea agregar una herramienta directamente al árbol de fuentes de uag, consulte
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Tabla de contenido
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Estructura de herramienta básica](#1-estructura-de-herramienta-básica)
2. [Creando una herramienta Python](#2-creando-una-herramienta-python)
3. [Creando una herramienta Rust + Python](#3-creando-una-herramienta-rust--python)
4. [Referencia TOOL_SPEC](#4-tool_spec-reference)
5. [Internacionalización (i18n)](#5-internacionalización-i18n)
6. [Prueba y depuración](#6-prueba-y-depuración)
7. [Ejemplos de referencia](#7-ejemplos-de-referencia)

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


## 1. Estructura básica de la herramienta

Una herramienta consta de los siguientes elementos:

| Elemento | Requerido | Descripción |
|---------|----------|-------------|
| `HERRAMIENTA_SPEC` | Sí | Diccionario que define el nombre, la descripción y los parámetros de la herramienta |
| `run_tool(argumentos)` | Sí | Función ejecutada cuando se llama a la herramienta. Args es un dict, return es una cadena. |
| i18nJSON | Recomendado | Traducción de archivo JSON (mismo nombre base, `<nombre>_tool.json`) |

### Herramienta mínima de Python

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

## 2. Creación de una herramienta Python

### Pasos

1. **Establezca la variable de entorno `UAGENT_EXTERNAL_TOOLS_DIRS`** (si aún no está configurada)

 Ejemplo:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Se pueden separar varios directorios por `:` (Linux/macOS) o `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (singular) también se admite por compatibilidad con versiones anteriores.

2. **Crear un archivo Python**

 El nombre del archivo es gratuito, pero se recomienda el nombre `<nombre>_tool.py` (por ejemplo, `my_tool.py`).

3. **Implemente los elementos requeridos**

 - Diccionario `TOOL_SPEC`
 - Función `run_tool(args)`
 - Opcionalmente, un archivo JSON i18n

4. **Reinicie el agente** (o ejecute la herramienta `system_reload`)

### Plantilla completa

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

Consulte la [Sección 5](#5-internationalization-i18n) para obtener detalles sobre i18n.

---

## 3. Creación de una herramienta Rust + Python

La implementación de Rust es ideal para tareas críticas para el rendimiento (procesamiento de datos pesados, criptografía, procesamiento de archivos, etc.).
uag puede cargar archivos `.pyd` prediseñados directamente, por lo que **los usuarios finales no necesitan `pip install`**.

### Estructura de herramientas

Una herramienta Rust consta de lo siguiente archivos:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Para distribución, coloque los archivos `_tool.py` + `_tool.json` + `.pyd` en
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Pasos

#### Paso 1: Crear el Rust proyecto

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

#### Paso 2: Implementación de Rust (src/lib.rs)

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

**Puntos clave:**
- Exponer funciones con `#[pyfunction(name = "run_<name>")]`
- El tipo de retorno es `PyResult<String>`
- El nombre de la función `#[pymodule]` debe coincidir con el nombre de la caja (`my_rust_tools`)

#### Paso 3: Compilación

```bash
cd my_rust_tool
cargo build --release
```

Windows: cambie el nombre de `target/release/my_rust_tools.dll` a `my_rust_tools.pyd`
Linux: cambie el nombre `target/release/libmy_rust_tools.so` a `my_rust_tools.so`
macOS: cambie el nombre de `target/release/libmy_rust_tools.dylib` a `my_rust_tools.so`

O usando maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Paso 4: Cree el contenedor de Python

Cree `my_rust_tool.py` en su directorio `UAGENT_EXTERNAL_TOOLS_DIRS`:

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

**``load_rust_pyd()`` orden de resolución:**

1. Busque `<nombre_módulo>.pyd` (o `.so`) en el mismo directorio que el contenedor `.py`
2. Recurrir a un módulo instalado por pip

#### Paso 5: Distribución

Solo se necesitan estos 3 archivos. Los usuarios finales **no** necesitan ninguna "instalación de pip".

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Notas

- **Solo tiempo de compilación:** Se requieren la cadena de herramientas Rust y `maturin`
  ```bash
  pip install maturin
  ```
- El nombre de la caja de Rust (`[lib] nombre` en `Cargo.toml`) debe coincidir con el primer argumento de `load_rust_pyd()`
- El nombre del archivo contenedor y la ubicación de `.pyd` son independientes siempre y cuando estén en el mismo directorio

---

## 4. Referencia TOOL_SPEC

### Básico Estructura

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

### Propiedades

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `tipo` | cadena | Siempre `"función"` |
| `x_build` | cadena | `"rust"` para la implementación de Rust (omitir para Python) |
| `género_herramienta` | cadena | Nombre del género (opcional). Habilita el control basado en género |
| `nivel_herramienta` | entero | 0=habilitado, 1=condicional (predeterminado), -1=deshabilitado |
| `función.nombre` | cadena | **Requerido**. Nombre de la herramienta (minúsculas + dígitos + guión bajo) |
| `función.descripción` | cadena | **Requerido**. Descripción |
| `función.x_search_terms` | lista[cadena] | Palabras clave de búsqueda compatibles con i18n (ajustar con `_(...)`) |
| `function.x_search_terms_en` | lista[cadena] | Se corrigieron las palabras clave de búsqueda en inglés |
| `función.parámetros` | dictar | Definición de parámetros (formato de llamada a función OpenAI) |

---

## 5. Internacionalización (i18n)

### Mecanismo de traducción

Llamar a `make_tool_translator(__file__)` carga traducciones desde un archivo `.json`
con el mismo nombre base en el mismo directorio.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Uso de claves de traducción

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Formato de archivo JSON

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

Ver existente Archivos `_tool.json` para códigos de idioma admitidos.

---

## 6. Pruebas y depuración

### Verificación de sintaxis

```bash
python -m py_compile my_tool.py
```

### Verificar herramienta Cargando

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Registros de errores

Los errores durante la carga de herramientas se imprimen en stderr. Si su herramienta no está cargada,
verifique los registros de inicio de uag.

---

## 7. Ejemplos de referencia

### Ejemplos de herramientas Python

- `date_calc_tool.py` (en `src/uagent/tools/`) — Cálculo de fecha. Copiar externamente y personalizar.
- `calculator_tool.py` (en `src/uagent/tools/`) — Calculadora.

### Ejemplos de herramientas Rust

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (en `src/uagent/tools_rust/`) — Generación de UUID
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (en `src/uagent/tools_rust/`) — Conversión de slug

Copie los archivos `_tool.py` y `.pyd` en `UAGENT_EXTERNAL_TOOLS_DIRS` para usarlos como herramientas externas.

### Configuración de herramienta externa Directorios

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Se pueden separar varios directorios mediante `:` (Linux/macOS) o `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (singular) también es compatible para compatibilidad con versiones anteriores.