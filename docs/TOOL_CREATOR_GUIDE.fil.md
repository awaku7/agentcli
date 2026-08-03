# Gabay sa Gumagawa ng Tool

Ipinapakita ng maikling gabay na ito kung paano gumawa ng external Python tool para sa uag.

## Python tool

Gumawa ng file na `my_tool.py`:

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

Ilagay ang file sa external tools directory at itakda:

```bat
set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
```

Para sa Linux/macOS:

```bash
export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
```

## i18n

Gamitin ang `make_tool_translator(__file__)` at huwag baguhin ang mga code identifier. Ilagay ang mga translation sa katumbas na `my_tool.json` file.

## Mahahalagang field

Panatilihing eksakto ang mga pangalan na ito:

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

Tingnan ang [kumpletong gabay sa English](../TOOL_CREATOR_GUIDE.md) para sa Rust/PyO3, plugins, i18n format, at iba pang detalye.
