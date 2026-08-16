# Tool Creator Guide

Ang gabay na ito ay nagpapaliwanag kung paano idagdag ang sarili mong mga tool sa uag **nang hindi binabago ang uag mismo**.
Kung gusto mong magdagdag ng tool nang direkta sa uag source tree, tingnan ang
[DEVELOP_TOOL.md](src/uagent/docs/DEVELOP_TOOL.md##________________).
\_\_\_\_\_\_\_\_\_\_\_\_\_\_ ng Content. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Basic Tool Structure](#1-basic-tool-structure)
1. [Paggawa ng Python Tool](#2-creating-a-python-tool)
1. [Paggawa ng Rust + Python Tool](#3-creating-a-rust--python-tool)
1. [TOOL_SPEC Reference](#4-tool_spec-reference)
1. [Internationalization (i18n)](#5-internationalization-i18n)
1. [Pagsubok at Pag-debug](#6-pagsubok-at-pag-debug)
1. [Mga Halimbawa ng Sanggunian](#7-reference-examples)

______________________________________________________________________

## 0. Quick Start: Scaffold Command

Ang pinakamadaling paraan upang gumawa ng bagong tool ay ang paggamit ng **`:tool create`** command
mula sa CLI prompt. Awtomatikong bumubuo ito ng mga boilerplate file.

### Usage

```
:tool create <name> --lang python|rust [--description '...'] [--output-dir <dir>]
```

| Pangangatwiran | Kinakailangan | Paglalarawan |
|----------|----------|-------------|
| `<pangalan>` | Oo | Pangalan ng tool (hal., `my_search`, `file_processor`) |
| `--lang` | Hindi | `python` (default) o `kalawang` |
| `--paglalarawan` | Hindi | Maikling paglalarawan ng tool |
| `--output-dir` | Hindi | Direktoryo ng output (default: unang landas sa `UAGENT_EXTERNAL_TOOLS_DIRS`, o kasalukuyang direktoryo) |

### Mga Halimbawa

```teksto
# Python tool
:tool create my_search --lang python --description "Custom search tool"
# Rust tool
:tool-description-langkayang data processor"
```

### What Gets Generated

**Python (`--lang python`)**:

- `<name>_tool.py` — Tool pagpapatupad na may `TOOL_SPEC` at `run_tool()`
- `<name>_tool.json` — i18n translation template
  Ilagay ang mga ito sa iyong `UAGENT_EXTERNAL_TOOLS_DIRS`
  at i-restart ang ahente (o patakbuhin ang `system_reload`).
  **Rust (`--lang rust`)**:
- `<name>/` — Cargo project directory na may `Cargo.toml`, `pyproject.toml`, at `. `<name>\_tool.py`— Python wrapper na naglo-load ng pinagsama-samang`.pyd\`
  Pagkatapos ng scaffolding, buuin at i-install:

````bash
cd <name>
maturin build --release
pip install target/wheels/*.whl
`` na lugar `py. iyong
`UAGENT_EXTERNAL_TOOLS_DIRS` at i-restart ang ahente.
_______________________________________________________________________
## 1. Pangunahing Istraktura ng Tool
Ang tool ay binubuo ng mga sumusunod na elemento:
| Elemento | Kinakailangan | Paglalarawan |
|---------|----------|-------------|
| `TOOL_SPEC` | Oo | Diksyunaryo na tumutukoy sa pangalan, paglalarawan, at mga parameter ng tool |
| `run_tool(args)` | Oo | Isinasagawa ang pag-andar kapag tinawag ang tool. Ang Args ay isang dict, ang pagbabalik ay isang string. |
| i18n JSON | Inirerekomenda | Translation JSON file (parehong basename, `<name>_tool.json`) |
### Minimal Python Tool
```python
# my_tool.py
mula sa pag-type ng import Any
def run_tool(args: dict[str, Any]) -> str:
 name = args. {name}!"
TOOL_SPEC: dict[str, Any] = {
 "type": "function",
 "x_parallel_safe": True, # Safe to run concurrently when True
 "function": {
 "name": "my_tool",
 "description": "Saystypello": "Says:"parameter.",⎏: "object",
 "properties": {
 "name": {
 "type": "string",
 "description": "Name to greet",
 },
 },
 },
 },
}
````

______________________________________________________________________

### 2. Paggawa ng Python. **Itakda ang `UAGENT_EXTERNAL_TOOLS_DIRS` na environment variable** (kung hindi pa nakatakda)

Halimbawa:

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
```

Maaaring paghiwalayin ang maramihang mga direktoryo ng `:` (Linux/macOS) o `;` (Windows).
Ang `UAGENT_EXTERNAL_TOOLS_DIR` ay suportado din (isahan para sa⎏1 pabalik). **Gumawa ng Python file**
Ang pangalan ng file ay libre, ngunit inirerekomenda ang pagpapangalan ng `<name>_tool.py` (hal. `my_tool.py`).

1. **Ipatupad ang mga kinakailangang elemento**

- `TOOL_SPEC` dictionary
- `run_tool(args)` function
- Opsyonal, isang i18n JSON file

1. **I-restart ang ahente** (o patakbuhin ang tool na `system_reload`)

### Buong Template

```python
mula sa __future__ import annotation
mula sa pag-type ng import Any
mula sa uagent.tools.i18n_helper import make_tool_translator
_(make_default_tool_translator
_ = make_deffile_translator) dict[str, Any]) -> str:
 """Ipatupad ang tool."""
 input_text = args.get("input", "")
 result = f"Processed: {input_text}"
 return result
TOOL_SPEC: dict[str, Any] = {
:
 type": "function "my_tool",
 "description": _(
 "tool.description",
 default="Description of my_tool",
 ),
 "x_search_terms": _(
 "x_search_terms",
 default=["my_tool", "keyword1"],
 ),
 "x_search",:_terms" "parameters": {
 "type": "object",
 "properties": {
 "input": {
 "type": "string",
 "description": _("param.input", default="Input text"),
 },
 },
 },`}
 },
 },`}
 },
`Section 5](#5-internationalization-i18n) para sa mga detalye ng i18n.
________________________________________________________________________________
## 3. Ang paggawa ng Rust + Python Tool
Ang pagpapatupad ng kalawang ay mainam para sa mga gawaing kritikal sa pagganap (mabigat na pagpoproseso ng data, cryptography, pagpoproseso ng file, atbp.).
uag ay maaaring direktang mag-load ng mga pre-built` na file `. install`**.
### Tool Structure
Ang isang Rust tool ay binubuo ng mga sumusunod na file:
```

my_rust_tool/
├── Cargo.toml # Rust project definition
├── pyproject.toml # maturin build definition (build-time lang)
┎time └── lib.rs # Rust na pagpapatupad
└── my_rust_tool.pyd # Bumuo ng artifact (ipadala na may pamamahagi)

````
Para sa pamamahagi, ilagay ang `_tool.py` + `_tool.json` + `.pyd` na mga file sa
#DINAL_TO_EXTER.###UAGENT_EXTER. Mga Hakbang
#### Hakbang 1: Gumawa ng Rust project
**Cargo.toml**
```toml
[package]
name = "my_rust_tools"
version = "0.1.0"
edition = "2021"
[lib]
name = "my_rust_tools"-type = "my_rust_tools" ["cdylib"]
[dependencies]
pyo3 = { version = "0.29", features = ["extension-module", "abi3-py311"] }
````

**pyproject.toml**

```toml
[build-system]
requires = ["0.backend] = ["0.backend" "maturin"]
[proyekto]
name = "my_rust_tools"
bersyon = "0.1.0"
requires-python = ">=3.11"
```

#### Hakbang 2: Pagpapatupad ng kalawang (src/lib.rs)

```rust
use
 std::collections::HashMap;
#[pyfunction(name = "run_my_operation")]
pub fn run(args: HashMap<String, Py<PyAny>>) -> PyResult<String> {
 let py = unsafe { Python::⏏_input na String () = }tgs;
 .get("input")
 .and_then(|v: &Py<PyAny>| v.bind(py).extract::<String>().ok())
 .unwrap_or_default();
 let result = format!("Rust says: {}", inputf);
# Ok[py}
]⎎ my_rust_tools(m: &Bound<'_, PyModule>) -> PyResult<()> {
 m.add_function(wrap_pyfunction!(run, m)?)?;
 Ok(())
}
```

**Mga pangunahing punto:**

- "Py_name
  -"Ilantad ang mga function na may `") Ang uri ng pagbabalik ay `PyResult<String>\`
- Ang pangalan ng function na `#[pymodule]` ay dapat tumugma sa pangalan ng crate (`my_rust_tools`)

#### Hakbang 3: Build

````bash
cd my_rust_tool
cargo build --release
```rease 
`Windows_target: sa `my_rust_tools.pyd`
Linux: palitan ang pangalan ng `target/release/libmy_rust_tools.so` sa `my_rust_tools.so`
macOS: palitan ang pangalan ng `target/release/libmy_rust_tools.dylib` sa `my_rust_tools.so`
Or i-install ang matured` #in`:

 build-time lang
maturin build --release
# Extract .pyd/.so mula sa target/wheels/*.whl
````

#### Hakbang 4: Gumawa ng Python wrapper

Lumikha ng `my_rust_tool.py` sa iyong `UAGENT_EXTERNAL_TOOLS_DIRS` na direktoryo:

```python
mula sa __future__ import annotation
mula sa pag-type ng import Any
mula sa uagent.tools.i18n_helper import make_tool.roms 
. load_rust_pyd
_ = make_tool_translator(__file__)
# Ilagay ang .pyd sa parehong direktoryo — auto-detected
_rust_mod = load_rust_pyd("my_rust_tools")
run_tool = _rust_mod.run_my_operation
TOOL_trPEC: Any "type" "function",
 "x_build": "rust",
 "function": {
 "name": "my_operation",
 "description": _("tool.description", default="My Rust operation"),
 "x_search_terms": _("x_search_terms", default=["my_operation"]": 
 
 
 my_operation"],

"my_operation"],

 "my_operation" "parameters": {
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

**`load_rust_pyd()` resolution order:**

1. Hanapin ang `<module_name>.pyd` (o `.so`) sa parehong direktoryo ng wrapper na `.py`
1. Bumalik sa isang module na naka-install na pip

#### Hakbang 5: Pamamahagi

Tanging ang 3 file na ito ang kailangan. Ang mga end-user ay **hindi** nangangailangan ng anumang `pip install`.

````
my_rust_tool.py # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json # i18n na mga pagsasalin (opsyonal)
my_rust_tools.pyd # Pre-built native na binary
`##`** Build na native na binary
`##`** toolchain at `maturin` ay kinakailangan
 ```bash
 pip install maturin
````

- Ang Rust crate name (`[lib] name` sa `Cargo.toml`) ay dapat tumugma sa unang argumento ng `load_rust_pyd()`
- Ang wrapper file name at `.pyd` ay dapat na tugma sa lokasyon ng mga ito direktoryo

______________________________________________________________________

## 4. TOOL_SPEC Reference

### Basic Structure

```python
TOOL_SPEC: dict[str, Any] = {
 "type": "function", # Fixed
 "x_build": "rust", #" "Generality" para sa pagpapatupad ng Rustity
 (opsyonal)
 "tool_level": 0, # 0=enabled, 1=conditional, -1=disabled
 "function": {
 "name": "tool_name", # Tool name (snake_case)
 "description": "...", # Description
 "x_search_terms": [...], # Search keywords (i1_ware)
, # Search keywords (i1_ware) [...], # English search keywords (fixed)
 "parameters": {
 "type": "object",
 "properties": {
 "param1": {
 "type": "string",
 "description": "...",
 },
 "param2": "integer type": {
 "description",
 "enum": [1, 2, 3],
 },
 },
 "kinakailangan": ["param1"],
 },
 },
}
```

### Properties

| Patlang | Uri | Paglalarawan |
|-------|------|-------------|
| `uri` | str | Palaging `"function"` |
| `x_build` | str | `"rust"` para sa pagpapatupad ng Rust (omit para sa Python) |
| `tool_genre` | str | Pangalan ng genre (opsyonal). Pinapagana ang kontrol na batay sa genre |
| `level_tool` | int | 0=enabled, 1=conditional (default), -1=disabled |
| `x_parallel_safe` | bool | Kung ang mga independyenteng tawag ay maaaring tumakbo nang sabay |
| `function.name` | str | **Kinakailangan**. Pangalan ng tool (maliit na titik + digit + underscore) |
| `function.description` | str | **Kinakailangan**. Paglalarawan |
| `function.x_search_terms` | listahan[str] | i18n-aware na mga keyword sa paghahanap (balutin ng `_(...)`) |
| `function.x_search_terms_en` | listahan[str] | Nakapirming English na mga keyword sa paghahanap |
| `function.parameters` | dict | Depinisyon ng parameter (OpenAI function calling format) |

______________________________________________________________________

## 5. Internationalization (i18n)

### Translation Mechanism

Ang pagtawag sa `make_tool_translator(__file__)` ay naglo-load ng mga pagsasalin mula sa isang `.json` file
na may parehong basename sa parehong direktoryo.
`romthon ` uagent.tools.i18n_helper import make_tool_translator
\_ = make_tool_translator(__file__)

````
### Gamit ang Translation Keys
```python
description = _(
 "tool.description", # Key name
 default="#`llback English na text⎎", # Fa``⎎` Default na English na text
 JSON Format ng File
```json
{
 "en": {
 "tool.description": "Default na English na text",
 "param.input": "Input text"
 },
 "ja": {
 "tool.description": "日本語の誇",明掏"入力テキスト"
 }
}
````

Tingnan ang mga umiiral nang `_tool.json` file para sa mga sinusuportahang code ng wika.

______________________________________________________________________

## 6. Pagsubok at Pag-debug

### Pagsusuri ng Syntax

```thonbash
``compile
 my_tool.py
```

### I-verify ang Paglo-load ng Tool

```python
mula sa uagent.tools import _RUNNERS, reload_plugins
reload_plugins()
kung "my_tool" sa _RUNNERS:
 resulta = _RUNNERS:
 resulta = _RUNNERS""]
 print(result)
```

### Error Logs

Ang mga error habang naglo-load ng tool ay naka-print sa stderr. Kung hindi na-load ang iyong tool,
tingnan ang uag startup logs.

______________________________________________________________________

## 7. Mga Halimbawa ng Sanggunian

### Mga Halimbawa ng Python Tool

- `date_calc_tool.py` (sa `src/uagent/tools/`) — Pagkalkula ng petsa. Kopyahin sa labas at i-customize.
- `calculator_tool.py` (sa `src/uagent/tools/`) — Calculator.

### Mga Halimbawa ng Rust Tool

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (sa `src/_PH_2/`)tool `rust_slugify_tool.py` + `uag_tools_rust.pyd` (sa `src/uagent/tools_rust/`) — Slug conversion
  Kopyahin ang `_tool.py` at `.pyd` na mga file sa `UAGENT_EXTERNAL_TOOLS_DIRS` para magamit ang mga ito bilang external### Tools Up.
  Direktoryo

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools
# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path;to⎉ Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Maaaring paghiwalayin ang maramihang mga direktoryo ng `:` (Linux/macOS) o `;`TERNALGTO
\`(Windows). (isahan) ay sinusuportahan din para sa pabalik na pagkakatugma.
