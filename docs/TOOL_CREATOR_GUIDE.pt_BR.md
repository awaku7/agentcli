# Tool Creator Guide

Este guia explica como adicionar suas próprias ferramentas ao uag **sem modificar o próprio uag**.
Se você deseja adicionar uma ferramenta diretamente à árvore de origem do uag, consulte
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Índice
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Estrutura básica da ferramenta](#1-estrutura-básica-da-ferramenta)
2. [Criando uma ferramenta Python](#2-creating-a-python-tool)
3. [Criando uma ferramenta Rust + Python](#3-creating-a-rust--python-tool)
4. [Referência TOOL_SPEC](#4-tool_spec-reference)
5. [Internacionalização (i18n)](#5-internacionalização-i18n)
6. [Teste e depuração](#6-teste-e-depuração)
7. [Exemplos de referência](#7-exemplos-de-referência)

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


## 1. Estrutura básica da ferramenta

Uma ferramenta consiste nos seguintes elementos:

| Elemento | Obrigatório | Descrição |
|---------|----------|-------------|
| `TOOL_SPEC` | Sim | Dicionário definindo nome, descrição e parâmetros da ferramenta |
| `run_tool(args)` | Sim | Função executada quando a ferramenta é chamada. Args é um ditado, return é uma string. |
| i18n JSON | Recomendado | Arquivo JSON de tradução (mesmo nome base, `<nome>_tool.json`) |

### Ferramenta Python mínima

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

## 2. Criando uma ferramenta Python

### Etapas

1. **Defina a variável de ambiente `UAGENT_EXTERNAL_TOOLS_DIRS`** (se ainda não estiver definida)

 Exemplo:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Vários diretórios podem ser separados por `:` (Linux/macOS) ou `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (singular) também é suportado para compatibilidade com versões anteriores.

2. **Crie um arquivo Python**

 O nome do arquivo é gratuito, mas a nomenclatura `<nome>_tool.py` é recomendada (por exemplo, `my_tool.py`).

3. **Implemente os elementos necessários**

 - dicionário `TOOL_SPEC`
 - função `run_tool(args)`
 - Opcionalmente, um arquivo JSON i18n

4. **Reinicie o agente** (ou execute a ferramenta `system_reload`)

### Modelo completo

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

Veja a [Seção 5](#5-internationalization-i18n) para detalhes do i18n.

---

## 3. Criando uma ferramenta Rust + Python

A implementação do Rust é ideal para tarefas críticas de desempenho (processamento pesado de dados, criptografia, processamento de arquivos, etc.).
uag pode carregar arquivos `.pyd` pré-construídos diretamente, então **os usuários finais não precisam de `pip install`**.

### Estrutura da ferramenta

Uma ferramenta Rust consiste no seguinte arquivos:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Para distribuição, coloque os arquivos `_tool.py` + `_tool.json` + `.pyd` em
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Etapas

#### Etapa 1: Criar o Rust projeto

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

#### Etapa 2: implementação de ferrugem (src/lib.rs)

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

**Pontos principais:**
- Expor funções com `#[pyfunction(name = "run_<name>")]`
- O tipo de retorno é `PyResult<String>`
- O nome da função `#[pymodule]` deve corresponder ao nome da caixa (`my_rust_tools`)

#### Etapa 3: Construir

```bash
cd my_rust_tool
cargo build --release
```

Windows: renomear `target/release/my_rust_tools.dll` para `my_rust_tools.pyd`
Linux: renomear `target/release/libmy_rust_tools.so` para `my_rust_tools.so`
macOS: renomeie `target/release/libmy_rust_tools.dylib` para `my_rust_tools.so`

Ou usando maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Etapa 4: Crie o wrapper Python

Crie `my_rust_tool.py` em seu diretório `UAGENT_EXTERNAL_TOOLS_DIRS`:

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

**``load_rust_pyd()`` ordem de resolução:**

1. Procure por `<module_name>.pyd` (ou `.so`) no mesmo diretório do wrapper `.py`
2. Volte para um módulo instalado pelo pip

#### Etapa 5: Distribuição

Apenas esses 3 arquivos são necessários. Os usuários finais **não** precisam de qualquer `pip install`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Notas

- **Somente tempo de compilação:** Rust toolchain e `maturin` são necessários
 ```bash
  pip install maturin
  ```
- O nome da caixa Rust (`[lib] name` em `Cargo.toml`) deve corresponder ao primeiro argumento de `load_rust_pyd()`
- O nome do arquivo wrapper e a localização do `.pyd` são independentes, desde que estejam no mesmo diretório

---

## 4. Referência TOOL_SPEC

### Básico Estrutura

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

### Propriedades

| Campo | Tipo | Descrição |
|-------|------|-------------|
| `tipo` | str | Sempre `"função"` |
| `x_build` | str | `"rust"` para implementação de Rust (omitir para Python) |
| `gênero_ferramenta` | str | Nome do gênero (opcional). Permite controle baseado em gênero |
| `nível_ferramenta` | int | 0=habilitado, 1=condicional (padrão), -1=desabilitado |
| `função.nome` | str | **Obrigatório**. Nome da ferramenta (minúsculas + dígitos + sublinhado) |
| `função.descrição` | str | **Obrigatório**. Descrição |
| `função.x_search_terms` | lista[str] | Palavras-chave de pesquisa compatíveis com i18n (envolver com `_(...)`) |
| `function.x_search_terms_en` | lista[str] | Palavras-chave de pesquisa em inglês corrigidas |
| `função.parâmetros` | dict | Definição de parâmetros (formato de chamada de função OpenAI) |

---

## 5. Internacionalização (i18n)

### Mecanismo de tradução

Chamar `make_tool_translator(__file__)` carrega traduções de um arquivo `.json`
com o mesmo nome base no mesmo diretório.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Usando chaves de tradução

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Formato de arquivo JSON

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

Ver existente Arquivos `_tool.json` para códigos de idioma suportados.

---

## 6. Teste e depuração

### Verificação de sintaxe

```bash
python -m py_compile my_tool.py
```

### Ferramenta de verificação Carregando

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Logs de erros

Erros durante o carregamento da ferramenta são impressos em stderr. Se sua ferramenta não estiver carregada,
verifique os logs de inicialização do uag.

---

## 7. Exemplos de referência

### Exemplos de ferramentas Python

- `date_calc_tool.py` (em `src/uagent/tools/`) — Cálculo de data. Copie externamente e personalize.
- `calculator_tool.py` (em `src/uagent/tools/`) — Calculadora.

### Exemplos de ferramentas Rust

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (em `src/uagent/tools_rust/`) — UUID geração
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (em `src/uagent/tools_rust/`) — Conversão de slug

Copie os arquivos `_tool.py` e `.pyd` em `UAGENT_EXTERNAL_TOOLS_DIRS` para usá-los como ferramentas externas.

### Configuração Diretórios de ferramentas externas para cima

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Vários diretórios podem ser separados por `:` (Linux/macOS) ou `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (singular) também é suportado para compatibilidade com versões anteriores.