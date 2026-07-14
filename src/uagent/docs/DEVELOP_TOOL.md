# DEVELOP_TOOL (How to create a tool)

This document explains how to add a new **Tool plugin** to uag.

Tools are Python modules under `src/uagent/tools/` (or external tools under `UAGENT_EXTERNAL_TOOLS_DIR`). Note: External tools must be in a flat directory (no subdirectories).

______________________________________________________________________

## 1. What a tool is

A tool is a Python module that exports:

- `TOOL_SPEC: dict`
  - OpenAI/Azure "function tool" schema compatible metadata.
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

### 3.1 Tool Level (`tool_level`)

You can specify `tool_level` in `TOOL_SPEC` to control tool loading:
- `tool_level == -1`: Disabled (will not be registered/loaded as an LLM tool, but dynamic commands are allowed).
- `tool_level == 0` (or missing): Enabled.
- `tool_level == 1`: Conditional loading (currently treated as disabled by default, but can be enabled dynamically).

For example, platform-specific tools like `cmd_exec` or `pwsh_exec` use:
```python
"tool_level": 0 if os.name == "nt" else -1,
```
You can also define `LOAD_DISABLED_REASON` at the module level to explain why the tool is disabled:
```python
LOAD_DISABLED_REASON = "This tool is available on Windows only."
```

### 3.2 Tool Genre (`tool_genre`)

You can categorize tools by specifying `tool_genre` at the top-level of `TOOL_SPEC`. The supported genres are:
- `"basic"`: Basic tools (env, time, prompts, skills, memory, tools control)
- `"comm"`: Communication tools (e.g., Teams, Discord)
- `"office"`: Office tools (e.g., Excel, Word, Document extraction)
- `"devel"`: Development tools (e.g., lint, py_compile, run_tests)
- `"iot"`: IoT tools (e.g., Bluetooth/BLE, ECHONET, Matter, SwitchBot)
- `"exec"`: Execution tools (e.g., cmd, python, pwsh, bash)
- `"external"`: External tools (e.g., A2A, MCP, fetch, search web)
- `"media"`: Media tools (e.g., image gen/edit/analyze, audio, QR code)
- `"file"`: File tools (e.g., create, delete, read, write, search, zip)

Example:
```python
TOOL_SPEC: Dict[str, Any] = {
    "tool_level": 1, # Loaded conditionally via genre control
    "tool_genre": "office",
    "type": "function",
    "function": { ... }
}
```
During interactive CLI startup, users are prompted to select which tool genres to enable. The selected genres are then activated dynamically.

### 3.3 External data flag (prompt injection defense)

If your tool fetches content from external/third-party sources (web pages, user messages, emails, etc.),
mark it in `TOOL_SPEC` so that the result is automatically wrapped with isolation markers:

```python
TOOL_SPEC: Dict[str, Any] = {
    "external_data": True,  # <-- add this flag
    "type": "function",
    "function": { ... }
}
```

Tools with this flag have their output wrapped in `---BEGIN_UAGENT_EXTERNAL_CONTENT---` /
`---END_UAGENT_EXTERNAL_CONTENT---` markers. The system prompt instructs the LLM not to
follow any instructions found within these markers, providing defense against prompt injection.

See `fetch_url_tool.py`, `bluesky_tool.py`, or `gmail_read_tool.py` for examples.

### 3.4 Suppressing tool trace

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
- Agent Skills-related tools should keep `SKILL.md` parsing, validation, and path checks inside the tool, and return structured JSON for list/load/validate helpers.

### 4.1 Persisted batch state tools

When a tool needs to resume multi-file work across runs, follow the batch-state pattern used by `batch_state_tool.py`:

- Default state dir: `~/.uag/batches/`
- Override with `UAGENT_BATCHES_DIR`
- Validate `batch_id`
- Keep `load` capable of resuming the saved task state
- Use structured JSON for `init`, `load`, `update`, `append_log`, `finalize`, `list`, and `delete`

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

## 8. Rust (native) tools

Tools implemented in Rust (via PyO3) are treated as ordinary tool plugins.
The only difference is how the native `.pyd` is loaded.

### 8.1 Standard pattern (recommended for external tools)

Place a pre-built `.pyd` file next to the wrapper `.py` file, then use the
shared helper from ``uagent.tools.rust_helper``:

```python
from __future__ import annotations

import os
from typing import Any

from uagent.tools.i18n_helper import make_tool_translator
from uagent.tools.rust_helper import load_rust_pyd

_ = make_tool_translator(__file__)

_rust_mod = load_rust_pyd("my_rust_tools")
run_tool = _rust_mod.run_my_operation

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_build": "rust",
    "tool_genre": "utility",
    "tool_level": 0,
    "function": {
        "name": "my_operation",
        "description": _("tool.description", default="..."),
        "parameters": {
            "type": "object",
            "properties": { ... },
            "additionalProperties": False,
        },
    },
}
```

``load_rust_pyd`` resolves the ``.pyd`` in this order:

1. Look for ``<module_name>.pyd`` next to the wrapper file (auto-detected).
2. Fall back to a pip-installed module (``import <module_name>``).

### 8.2 Custom .pyd path (internal build output)

For tools built from source (e.g. inside the project's ``tools_rust/``
directory), pass ``pyd_path`` explicitly:

```python
_rust_mod = load_rust_pyd(
    "uag_tools_rust",
    pyd_path=os.path.join(os.path.dirname(__file__), "target", "release", "uag_tools_rust.pyd"),
)
```

### 8.3 Rust project structure (PyO3 + maturin)

A minimal Rust tool project:

```
my_rust_tool/
├── Cargo.toml
├── pyproject.toml         # [build-system] requires = ["maturin>=1.0"]
├── src/
│   └── lib.rs             # #[pymodule] with pyfunctions
└── my_rust_tool.pyd       # pre-built binary (ship this)
```

- The Rust module name (``#[pymodule]``) must match the ``module_name``
  passed to ``load_rust_pyd()``.
- Build locally with ``maturin build --release`` or ``cargo build --release``
  then copy the resulting ``.dll`` / ``.so`` / ``.dylib`` as ``.pyd``
  (Windows) next to the wrapper file.
- **maturin (and Rust toolchain) are build-time dependencies only.**
  End-users do **not** need to install maturin, Rust, or any extra pip
  packages. The ``.pyd`` + ``.py`` pair is fully self-contained.

______________________________________________________________________

## 9. Common pitfalls

- Missing `TOOL_SPEC` or `run_tool` → tool is not registered.
- Invalid JSON schema under `parameters` → LLM tool call args may break.
- Printing sensitive data → use masking and `human_ask(is_password=True)` when necessary.

______________________________________________________________________

## 10. Technical requirements for tool plugins

When implementing or updating a tool, keep the following runtime requirements in mind:

- Export both `TOOL_SPEC` and `run_tool`.
- Keep JSON schema definitions strict and valid (`additionalProperties: False` is preferred).
- Keep placeholders such as `{path}`, `%(err)s`, and multiline prompt structure unchanged.
- If the tool uses localized strings, keep the companion `<tool>_tool.json` file in sync with the Python code.
- Do not print secrets or raw user input.
- For destructive or external actions, confirm with `human_ask` before proceeding.
- After adding or changing a tool module, verify it loads and run `python -m py_compile` if the file is standalone.

______________________________________________________________________
