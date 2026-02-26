# DEVELOP_TOOL (How to create a tool)

This document explains how to add a new **Tool plugin** to uag.

Tools are Python modules under `src/uagent/tools/` (or external tools under `UAGENT_EXTERNAL_TOOLS_DIR`).

______________________________________________________________________

## 1. What a tool is

A tool is a Python module that exports:

- `TOOL_SPEC: dict`
  - OpenAI/Azure “function tool” schema compatible metadata.
- `run_tool(args: dict) -> str`
  - Executes the tool and returns a **string**.

The plugin loader is implemented in:

- `src/uagent/tools/__init__.py`

A module is registered only when both are present.

______________________________________________________________________

## 2. Where to place files

### 2.1 Internal tool

Create a new file:

- `src/uagent/tools/<your_tool>_tool.py`

Optional: add i18n resources:

- `src/uagent/tools/<your_tool>_tool.json` (translations; e.g. `{"ja": {...}}`)

### 2.2 External tool

Place a `*.py` file under the directory pointed by:

- `UAGENT_EXTERNAL_TOOLS_DIR`

The file must export `TOOL_SPEC` and `run_tool`.

______________________________________________________________________

## 3. TOOL_SPEC requirements

Typical minimal example (see `get_workdir_tool.py`):

```python
from typing import Any, Dict

TOOL_SPEC: Dict[str, Any] = {
  "type": "function",
  "function": {
    "name": "your_tool_name",
    "description": "...",
    "parameters": {
      "type": "object",
      "properties": {
        "foo": {"type": "string"}
      },
      "required": ["foo"],
      "additionalProperties": False
    }
  }
}
```

Notes:

- `type="function"` is mandatory for OpenAI/Azure.
- The canonical function name is `TOOL_SPEC["function"]["name"]`.
- Prefer `additionalProperties: False` to keep args strict.
- Extended fields are allowed for local behavior (e.g. `function.system_prompt`, `function.x_scheck`).
  - However, `function.system_prompt` is **removed** before sending to the LLM.

### 3.1 Suppressing tool trace

Tools print a one-line trace by default. To suppress:

```python
TOOL_SPEC["function"]["x_scheck"] = {"emit_tool_trace": False}
```

`human_ask` uses this to avoid logging the raw user reply.

______________________________________________________________________

## 4. Implementing run_tool

Signature:

```python
def run_tool(args: Dict[str, Any]) -> str:
    ...
```

Guidelines:

- Validate required args and fail fast with a clear message.
- Return JSON strings when structured results are needed.
- Do not print secrets.
- For dangerous operations (delete/overwrite/exec), ask confirmation via `human_ask`.

______________________________________________________________________

## 5. i18n for tools (JSON)

Many built-in tools use `make_tool_translator(__file__)` and store translations in a JSON file
with the same base name.

Example:

- `src/uagent/tools/get_workdir_tool.json`

```json
{
  "ja": {
    "tool.system_prompt": "..."
  }
}
```

______________________________________________________________________

## 6. How tools are loaded

- Internal tools are discovered by scanning `src/uagent/tools/`.
- Modules starting with `_` and `context` are skipped.
- If a module is already imported, it is reloaded.
- Tool specs and runners are stored in memory:
  - `TOOL_SPECS` (list of specs)
  - `_RUNNERS` (name -> runner)

The tool list shown at startup is printed to stderr.

______________________________________________________________________

## 7. Testing / validation

Recommended steps:

1. Run the CLI and verify your tool is listed:

```bash
python -m uagent
```

2. Trigger the tool by asking the agent to use it.

1. If the tool is a standalone script too, add a `__main__` block for quick checks:

```python
if __name__ == "__main__":
    print(run_tool({}))
```

______________________________________________________________________

## 8. Common pitfalls

- Missing `TOOL_SPEC` or `run_tool` → tool is not registered.
- Invalid JSON schema under `parameters` → LLM tool call args may break.
- Printing sensitive data → use masking and `human_ask(is_password=True)` when necessary.

______________________________________________________________________
