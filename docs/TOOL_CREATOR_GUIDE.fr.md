# Guide du créateur d'outils

Ce guide explique comment ajouter vos propres outils à uag **sans modifier uag lui-même**.
Si vous souhaitez ajouter un outil directement à l'arborescence des sources d'uag, voir
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Table des matières

1. [Structure de l'outil de base](#1-basic-tool-structure)
2. [Création d'un outil Python](#2-creating-a-python-tool)
3. [Création d'un outil Rust + Python](#3-creating-a-rust--python-tool)
4. [Référence TOOL_SPEC](#4-tool_spec-reference)
5. [Internationalisation (i18n)](#5-internationalization-i18n)
6. [Test et débogage](#6-test-et-débogage)
7. [Exemples de référence](#7-reference-examples)

---

## 1. Structure de base de l'outil

Un outil se compose des éléments suivants :

| Élément | Obligatoire | Description |
|---------|----------|-------------|
| `TOOL_SPEC` | Oui | Dictionnaire définissant le nom, la description et les paramètres de l'outil |
| `run_tool(args)` | Oui | Fonction exécutée lors de l'appel de l'outil. Args est un dict, return est une chaîne. |
| i18n JSON | Recommandé | Fichier JSON de traduction (même nom de base, `<name>_tool.json`) |

### Outil Python minimal

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

## 2. Création d'un outil Python

### Étapes

1. **Définissez la variable d'environnement `UAGENT_EXTERNAL_TOOLS_DIRS`** (si elle n'est pas déjà définie)

 Exemple :
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Plusieurs répertoires peuvent être séparés par `:` (Linux/macOS) ou `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (singulier) est également pris en charge pour des raisons de compatibilité ascendante.

2. **Créez un fichier Python**

 Le nom du fichier est gratuit, mais le nom `<name>_tool.py` est recommandé (par exemple `my_tool.py`).

3. **Implémentez les éléments requis**

 - Dictionnaire `TOOL_SPEC`
 - Fonction `run_tool(args)`
 - En option, un fichier JSON i18n

4. **Redémarrez l'agent** (ou exécutez l'outil `system_reload`)

### Modèle complet

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

Voir la [Section 5](#5-internationalization-i18n) pour plus de détails sur i18n.

---

## 3. Création un outil Rust + Python

L'implémentation de Rust est idéale pour les tâches critiques en termes de performances (traitement de données volumineux, cryptographie, traitement de fichiers, etc.).
uag peut charger directement des fichiers `.pyd` prédéfinis, de sorte que **les utilisateurs finaux n'ont pas besoin de `pip install`**.

### Structure de l'outil

Un outil Rust se compose des éléments suivants fichiers :

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Pour la distribution, placez les fichiers `_tool.py` + `_tool.json` + `.pyd` dans
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Étapes

#### Étape 1 : Créez le Projet Rust

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

#### Étape 2 : Implémentation de Rust (src/lib.rs)

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

**Points clés :**
- Exposer les fonctions avec `#[pyfunction(name = "run_<name>")]`
- Le type de retour est `PyResult<String>`
- Le nom de la fonction `#[pymodule]` doit correspondre à la caisse name (`my_rust_tools`)

#### Étape 3 : Build

```bash
cd my_rust_tool
cargo build --release
```

Windows : renommez `target/release/my_rust_tools.dll` en `my_rust_tools.pyd`
Linux : renommez `target/release/libmy_rust_tools.so` en `my_rust_tools.so`
macOS : renommez `target/release/libmy_rust_tools.dylib` en `my_rust_tools.so`

Ou en utilisant maturin :
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Étape 4 : Créez le wrapper Python

Créez `my_rust_tool.py` dans votre répertoire `UAGENT_EXTERNAL_TOOLS_DIRS` :

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

**``load_rust_pyd()`` ordre de résolution :**

1. Recherchez `<module_name>.pyd` (ou `.so`) dans le même répertoire que le wrapper `.py`
2. Revenir à un module installé par pip

#### Étape 5 : Distribution

Seuls ces 3 fichiers sont nécessaires. Les utilisateurs finaux n'ont **pas** besoin d'installation pip.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Notes

- **Au moment de la construction uniquement :** La chaîne d'outils Rust et `maturin` sont requis
 ```bash
  pip install maturin
  ```
- Le nom de la caisse Rust (`[lib] name` dans `Cargo.toml`) doit correspondre au premier argument de `load_rust_pyd()`
- Le nom du fichier wrapper et l'emplacement `.pyd` sont indépendants tant qu'ils se trouvent dans le même répertoire

---

## 4. Référence TOOL_SPEC

### De base Structure

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

### Propriétés

| Champ | Tapez | Description |
|-------|------|-------------|
| `type` | str | Toujours `"fonction"` |
| `x_build` | str | `"rust"` pour l'implémentation de Rust (omettre pour Python) |
| `outil_genre` | str | Nom du genre (facultatif). Permet un contrôle basé sur le genre |
| `niveau_outil` | entier | 0=activé, 1=conditionnel (par défaut), -1=désactivé |
| `fonction.nom` | str | **Requis**. Nom de l'outil (minuscules + chiffres + trait de soulignement) |
| `fonction.description` | str | **Requis**. Description |
| `fonction.x_search_terms` | liste[str] | Mots-clés de recherche compatibles i18n (enrouler avec `_(...)`) |
| `function.x_search_terms_en` | liste[str] | Mots-clés de recherche en anglais fixes |
| `fonction.paramètres` | dict | Définition des paramètres (format d'appel de la fonction OpenAI) |

---

## 5. Internationalisation (i18n)

### Mécanisme de traduction

L'appel de `make_tool_translator(__file__)` charge les traductions à partir d'un fichier `.json`
avec le même nom de base dans le même répertoire.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Utilisation des clés de traduction

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Format de fichier JSON

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

Voir existant Fichiers `_tool.json` pour les codes de langue pris en charge.

---

## 6. Test et débogage

### Vérification de la syntaxe

```bash
python -m py_compile my_tool.py
```

### Outil de vérification Chargement

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Journaux d'erreurs

Les erreurs lors du chargement de l'outil sont imprimées sur stderr. Si votre outil n'est pas chargé,
vérifiez les journaux de démarrage d'uag.

---

## 7. Exemples de référence

### Exemples d'outils Python

- `date_calc_tool.py` (dans `src/uagent/tools/`) — Calcul de date. Copiez en externe et personnalisez.
- `calculator_tool.py` (dans `src/uagent/tools/`) — Calculatrice.

### Exemples d'outils Rust

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (dans `src/uagent/tools_rust/`) — UUID génération
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (dans `src/uagent/tools_rust/`) — Conversion Slug

Copiez les fichiers `_tool.py` et `.pyd` dans `UAGENT_EXTERNAL_TOOLS_DIRS` pour les utiliser comme outils externes.

### Paramètre Répertoires d'outils externes

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Plusieurs répertoires peuvent être séparés par `:` (Linux/macOS) ou `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (singulier) est également pris en charge pour une compatibilité ascendante.