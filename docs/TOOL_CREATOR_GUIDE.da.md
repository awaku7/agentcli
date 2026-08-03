# Vejledning til værktøjsudviklere

Denne korte vejledning viser, hvordan du opretter et eksternt Python-værktøj til uag.

## Python-værktøj

Opret en fil som `my_tool.py`:

```python
from typing import Any

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "my_tool",
        "description": "Describe what the tool does.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    return "result"
```

Placér filen i en ekstern værktøjsmappe og konfigurer:

```bat
set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
```

På Linux/macOS:

```bash
export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
```

## i18n

Brug `make_tool_translator(__file__)` og behold alle kodeidentifikatorer uændrede. Oversættelser placeres i den tilsvarende `my_tool.json`-fil.

## Vigtige felter

Behold disse feltnavne nøjagtigt:

```text
TOOL_SPEC
run_tool
function.name
function.description
function.parameters
function.x_search_terms
function.x_search_terms_en
x_parallel_safe
UAGENT_EXTERNAL_TOOLS_DIRS
```

Se [den komplette engelske vejledning](../TOOL_CREATOR_GUIDE.md) for Rust/PyO3, plugins, i18n-format og alle detaljer.
