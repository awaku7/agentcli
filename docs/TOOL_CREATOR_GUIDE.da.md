# Værktøjsskabervejledning

Denne vejledning forklarer, hvordan du tilføjer dine egne værktøjer til uag **uden at ændre selve uag**.
Hvis du vil tilføje et værktøj direkte til uag-kildetræet, skal du se
\[DEVELOP_TOOL.md\](src/uagent/docs/DEVELOP_TOOL of⎯uagent/docs/DEVELOP_TOOL of⎯\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_md\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_A blive ændret). Indhold
0\. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. \[Grundlæggende værktøjsstruktur\](#1-grundlæggende værktøjsstruktur)
1. [Creating a Python Tool](#2-creating-a-python-tool)
1. [Creating a Rust + Python Tool](#3-creating-a-rust--python-tool)
1. [TOOL_SPEC Reference](#4-tool_spec-reference)
1. [Internationalisering (i18n)](#5-internationalisering-i18n)
1. [Test og debugging](#6-testing-and-debugging)
1. [Referenceeksempler](#7-referenceeksempler)

______________________________________________________________________

## 0. Hurtig start: Scaffold-kommando

Den nemmeste måde at oprette et nyt værktøj på er at bruge kommandoen **`:værktøj create`**
fra CLI-prompten. Det genererer boilerplate-filerne automatisk.

### Usage

```
:tool create <name> --lang python|rust [--description '...'] [--output-dir <dir>]
```

| Argument | Påkrævet | Beskrivelse |
|--------|--------|-------------------|
| `<navn>` | Ja | Værktøjsnavn (f.eks. `min_søgning`, `fil_processor`) |
| `--lang` | Nej | `python` (standard) eller `rust` |
| `--beskrivelse` | Nej | Kort beskrivelse af værktøjet |
| `--output-dir` | Nej | Outputmappe (standard: første sti i `UAGENT_EXTERNAL_TOOLS_DIRS`, eller aktuel mappe) |

### Eksempler

```tekst
# Python tool
:tool create my_search --lang python --description "Brugerdefineret søgeværktøj"
# "Rustool create heavy_processor" --tlang rust tool
script: processor"
```

### Hvad bliver genereret

**Python (`--lang python`)**:

- `<navn>_tool.py` — Værktøjsimplementering med `TOOL_SPEC` og `run_tool()`
- `<navn>_tool.json`
  i18n oversættelsesskabelon er klar til brug. Placer dem i din `UAGENT_EXTERNAL_TOOLS_DIRS`
  og genstart agenten (eller kør `system_reload`).
  **Rust (`--lang rust`)**:
- `<navn>/` — Cargo-projektmappe med `Cargo.toml`, `pyproject.toml` og `r.`src/\_lib. Python-indpakning, der indlæser den kompilerede `.pyd`
  Byg og installer efter stillads:

```bash
cd <name>
maturin build --release
pip install target/wheels/*.whl
```

Placer derefter `<name> og det indbyggede værktøj.py. din `UAGENT_EXTERNAL_TOOLS_DIRS\` og genstart agenten.

______________________________________________________________________

## 1. Grundlæggende værktøjsstruktur

Et værktøj består af følgende elementer:
| Element | Påkrævet | Beskrivelse |
|--------|--------|-------------------|
| `TOOL_SPEC` | Ja | Ordbog, der definerer værktøjets navn, beskrivelse og parametre |
| `run_tool(args)` | Ja | Funktion udført, når værktøjet kaldes. Args er en diktat, retur er en streng. |
| i18n JSON | Anbefalet | Oversættelse JSON fil (samme basenavn, `<navn>_tool.json`) |

### Minimal Python Tool

```python
# my_tool.py
fra indtastning import Any
def run_tool(args: dict[str, Enhver]) -> str:
(name = args.), f"(name = args.") {name}!"
TOOL_SPEC: dict[str, Enhver] = {
 "type": "function",
 "x_parallel_safe": Sandt, # Sikkert at køre samtidigt, når True
 "function": {
 "name": "mit_værktøj",
 "description" {⎏parameter": "Siger: "helloparameter": "sier:" "object",
 "properties": {
 "name": {
 "type": "string",
 "description": "Navn at hilse",
 },
 },
 },
 },
}
```

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Python#
##. Trin

1. **Indstil miljøvariablen `UAGENT_EXTERNAL_TOOLS_DIRS`** (hvis den ikke allerede er indstillet)
   Eksempel:

```bash
# Linux/macOS
eksport UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
# Windows set (cmd)
UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
```

Flere mapper kan adskilles med `:` (Linux/macOS) eller `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (singular) understøttes også. **Opret en Python-fil**
Filnavnet er gratis, men `<navn>_tool.py`-navngivning anbefales (f.eks. `my_tool.py`).

1. **Implementer de nødvendige elementer**

- `TOOL_SPEC` ordbog
- `run_tool(args)` funktion
- Eventuelt en i18n JSON fil

1. **Genstart agenten** (eller kør værktøjet `system_reload`)

### Fuld skabelon

```python
fra __future__ importer annotationer
fra indtastning importer enhver
fra uagent.tools.i18n_helper import make_tool_translator
___l make_tool_tool_tool_tool_tool_translator
___l make run_tool(args: dict[str, Enhver]) -> str:
 """Udfør værktøjet."""
 input_text = args.get("input", "")
 result = f"Behandlet: {input_text}"
 returner resultat
TOOL_SPEC: dict[str, "Alle]": "navn":":":" "my_tool",
 "description": _(
 "tool.description",
 default="Beskrivelse af mit_værktøj",
 ),
 "x_search_terms": _(
 "x_search_terms",
 default=["mit_værktøj", "søgeord1"],
 _en_søg",
 _en"_search,
 _en"_search: "keyword1"],
 "parameters": {
 "type": "object",
 "properties": {
 "input": {
 "type": "string",
 "description": _("param.input", default="Input tekst"),
 },
 },
 },
 },
 },
}
```

Se [Afsnit 5](#5-internationalization-i18n) for i18n-detaljer.

______________________________________________________________________

## 3. Oprettelse af et Rust + Python-værktøj

Rust-implementering er ideel til ydeevnekritiske opgaver (tung databehandling, PH\_\_ilt-filbehandling, PH\_\_ilt, etc.
). `.pyd`-filer direkte, så **slutbrugere behøver ikke `pip-installation`**.

### Værktøjsstruktur

Et Rust-værktøj består af følgende filer:

```
my_rust_tool/
├── Cargo.toml # Rustprojektdefinition
├─tom.-l . only)
├── src/
│ └── lib.rs # Rustimplementering
└── my_rust_tool.pyd # Byg artefakt (sendes med distribution)
```

Til distribution, placer `j_`_tool.py.` `_`_tool.py.` in
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Trin

#### Trin 1: Opret Rust-projektet

**Cargo.toml**

```toml
[pakke]
name = "my_rust_tools"
version = "0.1.0" "2021"
[lib]
name = "my_rust_tools"
crate-type = ["cdylib"]
[afhængigheder]
pyo3 = { version = "0.29", features = ["udvidelsesmodul", "abi3-py311"] }
```

**pyproject.toml**

```toml
[build-system]
requires = ["maturin>=1.0"]
build-backend = "maturin"]
[projekt]
name = "my_rust_tools"
requires = "0.honres ">=3.11"
```

#### Trin 2: Rustimplementering (src/lib.rs)

```rust
use pyo3::prelude::*;
use std::collections::HashMap;
#[pyfunction(name = "run_my_apgs_operation" fn)] Py<PyAny>>) -> PyResult<String> {
 lad py = usikker { Python::assume_attached() };
 lad input: String = args
 .get("input")
 .and_then(|v: &Py<PyAny>| v.bind:(py).
extract:(py). .unwrap_or_default();
 lad resultat = format!("Rust siger: {}", input);
 Ok(result)
}
#[pymodule]
fn my_rust_tools(m: &Bound<'_, PyModule>) -> PyResult<()> {
funktion(wrap;py?) Ok(())
}
```

**Nøglepunkter:**

- Eksponer funktioner med `#[pyfunction(name = "run_<name>")]`
- Returtypen er `PyResult<String>`
- `#[pymodule]` funktionsnavnet skal matche kassenavnet (`my__rust_tools:#` Build

```bash
cd my_rust_tool
cargo build --release
```

Windows: omdøb `target/release/my_rust_tools.dll` til `my_rust_tools.pyd`
Linux: omdøb `target/release/soolmy_rust `my_rust_tools.so`macOS: omdøb`target/release/libmy_rust_tools.dylib`til`my_rust_tools.so\`
Eller brug maturin:

```bash
pip install maturin # build-time only
maturin build --release from.pyd/so Extract from.pyd/ target/wheels/*.whl
```

#### Trin 4: Opret Python-indpakningen

Opret `my_rust_tool.py` i din `UAGENT_EXTERNAL_TOOLS_DIRS`-mappe:

```python
fra __future__ import annotations
fra indtastning import Enhver
fra uagent.tools.i18n_helper import make_tool_from-translator.PH_2.tools.__helper load_rust_pyd? "function",
 "x_build": "rust",
 "function": {
 "name": "my_operation",
 "description": _("tool.description", default="My Rust operation"),
 "x_search_terms": _("x_search_terms", default=["min_operation"]_),
search: ["min_operation"],
 "parameters": {
 "type": "objekt",
 "egenskaber": {
 "input": {
 "type": "streng",
 "description": _("param.input", default="Input tekst"),
 },
 },, },
}
```

**`load_rust_pyd()` opløsningsrækkefølge:**

1. Se efter `<modulnavn>.pyd` (eller `.so`) i samme mappe som indpakningen `.py`
1. Gå tilbage til et pip-installeret modul

#### Trin 5: Distribution

Kun disse 3 filer er nødvendige. Slutbrugere har **ikke** brug for nogen `pip-installation`.

````
my_rust_tool.py # Python-indpakning (TOOL_SPEC + run_tool)
my_rust_tool.json # i18n-oversættelser (valgfrit)
my_rust_tools.pyd # binative⎎`Note
native`#` **Kun byggetid:** Rust værktøjskæde og `maturin` er påkrævet
 ```bash
 pip install maturin
````

- Rust-kassenavnet (`[lib] navn` i `Cargo.toml`) skal matche det første argument for `load_rust_pyd()`
- Indpakningsfilnavnet er uafhængigt og det samme lange som filnavnet, og de er uafhængige. bibliotek

______________________________________________________________________

## 4. TOOL_SPEC Reference

### Grundlæggende struktur

```python
TOOL_SPEC: dict[str, Enhver] = {
 "type": "function", # Fixed
 "x_build": "rust", # Kun til "Rustool_gentility", # Kun til "Rustool-gentility", (valgfrit)
 "værktøjsniveau": 0, # 0=aktiveret, 1=betinget, -1=deaktiveret
 "funktion": {
 "navn": "værktøjsnavn", # Værktøjsnavn (snake_case)
 "beskrivelse": "...", # Beskrivelse
 "__i #8_0"-søgeord (...) "x_search_terms_en": [...], # Engelske søgeord (fast)
 "parameters": {
 "type": "object",
 "properties": {
 "param1": {
 "type": "string",
 "description": "...",
 "
 },
 "integer",
 " "description": "...",
 "enum": [1, 2, 3],
 },
 },
 "required": ["param1"],
 },
 },
}
```

### Egenskaber

| Felt | Skriv | Beskrivelse |
|-------|------|--------------------|
| `type` | str | Altid `"funktion"` |
| `x_build` | str | `"rust"` til Rust-implementering (udelad for Python) |
| `værktøjsgenre` | str | Genrenavn (valgfrit). Aktiverer genrebaseret kontrol |
| `værktøjsniveau` | int | 0=aktiveret, 1=betinget (standard), -1=deaktiveret |
| `x_parallel_safe` | bool | Om uafhængige opkald kan køre samtidigt |
| `funktion.navn` | str | **Påkrævet**. Værktøjsnavn (små bogstaver + cifre + understregning) |
| `funktion.beskrivelse` | str | **Påkrævet**. Beskrivelse |
| `funktion.x_search_terms` | liste[str] | i18n-bevidste søgeord (ombryd med `_(...)`) |
| `function.x_search_terms_da` | liste[str] | Rettede engelske søgeord |
| `funktion.parametre` | dikt | Parameterdefinition (OpenAI funktionsopkaldsformat) |

______________________________________________________________________

## 5. Internationalisering (i18n)

### Oversættelsesmekanisme

kalder `make_tool_translator(__file__)` indlæser oversættelser fra en `.json`-fil
med det samme basisnavn i samme mappe
\`thon. uagent.tools.i18n_helper import make_tool_translator
\_ = make_tool_translator(__file__)

````
### Brug af oversættelsesnøgler
```python
description = _(
 "tool.description", standardnavn, # Nøglenavn engelsk tekst=", # Default
 value
)
````

### JSON Filformat

```json
{
 "da": {
 "tool.description": "Standard engelsk tekst",
 "param.input": "Input tekst"
 },
 "ja": {.description "日本語の説明文",
 "param.input": "入力テキスト"
 }
}
```

Se eksisterende `_tool.json`-filer for understøttede sprogkoder og
\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Debugging

### Syntaks Check

```bash
python -m py_compile my_tool.py
```

### Bekræft værktøjet Indlæser

```python
fra uagent.tools importer _RUNNERS


reload_plugins-plugins_tools" (reload_plugins)myt" _RUNNERS:
 resultat = _RUNNERS["mit_værktøj"]({"input": "test")
 print(result)
```

### Fejllogs

Fejl under værktøjsindlæsning udskrives til stderr. Hvis dit værktøj ikke er indlæst,
tjek uag opstartslogfilerne.

______________________________________________________________________

## 7. Referenceeksempler

### Python Tool Eksempler

- `date_calc_tool.py` (i `src/uagent/tools/`) — Datoberegning Kopier eksternt og tilpas.
- `calculator_tool.py` (i `src/uagent/tools/`) — Calculator.

### Rustværktøjseksempler

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (i `⎎src/uagent/tools/`) `rust_slugify_tool.py` + `uag_tools_rust.pyd` (i `src/uagent/tools_rust/`) — Slug-konvertering
  Kopiér filerne `_tool.py` og `.pyd` ind i `UAGENT_EXTERNAL_TOOLS_DIRS` for at bruge dem som eksternt ##-værktøj. Directory

```bash
# Linux/macOS
eksport UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools
# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\sti\til\mine\værktøjer;C:\sti\til\andre\værktøjer
# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\sti\til\mine\værktøjer;C:\stimulighed\til\" mapper kan adskilles af `:` (Linux/macOS) eller `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (ental) understøttes også for bagudkompatibilitet.
```
