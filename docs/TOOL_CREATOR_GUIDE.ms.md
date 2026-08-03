# Panduan Pencipta Alat

Panduan ringkas ini menunjukkan cara mencipta alat Python luaran untuk uag.

## Alat Python

Cipta fail `my_tool.py`:

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

Letakkan fail dalam direktori alat luaran dan tetapkan:

```bat
set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
```

Untuk Linux/macOS:

```bash
export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
```

## i18n

Gunakan `make_tool_translator(__file__)` dan kekalkan semua pengecam kod tanpa perubahan. Simpan terjemahan dalam fail `my_tool.json` yang sepadan.

## Medan penting

Nama medan berikut mesti dikekalkan tepat:

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

Lihat [panduan lengkap dalam bahasa Inggeris](../TOOL_CREATOR_GUIDE.md) untuk Rust/PyO3, plugin, format i18n dan semua butiran.
