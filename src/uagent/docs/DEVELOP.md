# DEVELOP (for developers)

This document is developer-facing notes for **uag** (a local tool-execution agent).

- Entry points:
  - CLI: `python -m uagent` (command: `uag`)
  - GUI: `python -m uagent.gui` (command: `uagg`)
  - Web: `python -m uagent.web` (command: `uagw`)

Notes:

- In this document, **uagent** refers to the Python package / codebase, while **uag** refers to the user-facing CLI project name.
- Startup behavior is shared across entry points unless noted otherwise.

______________________________________________________________________

## 0. Runtime requirements

- Python: 3.11+
- Git: required for development workflows and some tools
- OS: Windows / macOS / Linux

### 0.1 Startup options

All entry points (CLI/GUI/Web/A2A) accept the following common options unless noted otherwise.

| Option | Entry points | Description | Defined in |
|---|---|---|---|
| `--workdir` / `-C` | CLI, GUI, Web, A2A | Working directory. Priority: CLI arg > `UAGENT_WORKDIR` > current dir | `util_tools.py:parse_startup_args()` |
| `--non-interactive` | CLI | Non-interactive mode. No stdin loop; exit after processing startup file (if any). | `util_tools.py:parse_startup_args()` |
| `--tool-genre-mask <int>` | CLI, GUI, Web, A2A | Tool genre bitmask (1=basic,2=comm,4=office,8=devel,16=iot,32=exec,64=external,128=media,255=all). Skips interactive genre prompt when specified. | `util_tools.py:parse_startup_args()`, `a2a/server.py` |
| `--use-tool` / `--no-use-tool` | CLI, GUI, Web, A2A | Enable/disable tool sending to LLM. Overrides `UAGENT_USE_TOOL` env var. | `util_tools.py:parse_startup_args()`, `a2a/server.py` |
| `--host` | A2A only | Bind address (default: `0.0.0.0`, overridable by `UAGENT_A2A_HOST`). | `a2a/server.py` |
| `--port` | A2A only | Port number (default: `8765`, overridable by `UAGENT_A2A_PORT`). | `a2a/server.py` |
| `--reload` | A2A only | Enable hot reload (overridable by `UAGENT_A2A_RELOAD`). | `a2a/server.py`

______________________________________________________________________

## 1. Repository structure / key modules

Key modules:

- Core state + UI integration: `src/uagent/core.py`
- CLI UI loop: `src/uagent/cli.py`
  - Standard input loop, `:cd` / `:ls` / `:cp` / `:mv` / `:head` / `:tail`, and startup-time workdir initialization (mode A initializes the workdir inside `main()`).
  - `:head <path> [n]` prints the first n lines (default 20), and `:tail <path> [n]` prints the last n lines (default 20).
  - `:cp` / `:mv` are treated as safe file operations inside the workdir.
- LLM orchestration entrypoint: `src/uagent/uagent_llm.py`
  - Round/message/tool-call helpers are split into:
    - `src/uagent/llm_helpers.py`
    - `src/uagent/llm_message_helpers.py`
    - `src/uagent/llm_round_helpers.py`
    - `src/uagent/llm_flow_helpers.py`
  - Retry / backoff helpers live in `src/uagent/llm_errors.py`
- Provider wiring (OpenAI/Azure/Gemini/Claude/Vertex AI/Ollama/DeepSeek/Z.AI/Alibaba/Moonshot/MiMo/LM Studio/etc.): `src/uagent/providers/util_providers.py`
  - To add a new provider, modify: `util_providers.py` (detect_provider/get_model_name/make_client), `env_validate.py` (allowed list), `runtime_banner.py` (banner display), and `provider_caps.py` (Responses API support if applicable).
- Common helpers (commands, callbacks injection, messages building, etc.): `src/uagent/util_tools.py`
- Startup initialization: `src/uagent/runtime_init.py` (compatibility re-export)
  - `src/uagent/runtime_workdir.py`: `decide_workdir()` / `apply_workdir()`
  - `src/uagent/runtime_banner.py`: `build_startup_banner()`
  - `src/uagent/runtime_env.py`: `validate_or_exit_startup_env(context=...)`
  - `src/uagent/runtime_memory.py`: `append_long_memory_system_messages()`

Implementation notes:

- `runtime_init.py` provides `load_dotenv_custom()` and `reload_dotenv_custom()` for loading `.env` and `.env.sec`.
- The load order is `.env` first, then `.env.sec` decrypted with `.uagent.key` if present.
- Startup still loads these files early, but CLI startup can re-run the loader after workdir selection so a newly created `.env.sec` can take effect without restarting.
- Treat this as startup-sensitive behavior: avoid relying on late mutations of cwd or secret files after import unless the reload path is used intentionally.
- If the `.env.sec` sync prompt appears and the user answers `n`/`N`, the startup `UAGENT_*` snapshot is restored for the session and `.env.sec` is left unchanged.

Documentation:

- Tool development: `src/uagent/docs/DEVELOP_TOOL.md`
- Host-side i18n: `src/uagent/docs/DEVELOP_I18N.md` (compile: `python scripts/compile_locales.py`, QC: `python scripts/po_qc_summary.py`)

______________________________________________________________________

## 2. High-level execution flow

1. Start one of the entry points (`uag` / `uagg` / `uagw`).
1. Startup initialization (`runtime_init.py`):
   - Decide workdir (`--workdir/-C`, `UAGENT_WORKDIR`, or current directory)
   - Create directory if needed and `chdir`
   - Build and print startup banner
   - Load `.env` and `.env.sec` from the current working directory if `python-dotenv` is available
1. Tool plugins are loaded from `src/uagent/tools/` (and optionally from an external directory).
1. Provider client is created based on environment variables (`util_providers.make_client`).
1. UI loop (CLI/GUI/Web) receives user input and enqueues events.
1. LLM rounds run via `uagent_llm.run_llm_rounds()`:
   - If the assistant returns tool calls, tools are executed and results are appended.
   - Retry/backoff behavior for rate limits is implemented in `llm_errors.py`.

______________________________________________________________________

## 3. Tools system (how it works)

### 3.1 Tool discovery and registration

Tools are plugin modules under `src/uagent/tools/`.

- A module is registered as a tool when it provides:
  - `TOOL_SPEC: dict` (OpenAI function schema compatible)
  - `run_tool(args: dict) -> str` (runner)

Tool loading happens in `src/uagent/tools/__init__.py` and is triggered at import time.

- Internal tools: discovered by `pkgutil.iter_modules([tools_dir])`
- External tools (optional): loaded from `UAGENT_EXTERNAL_TOOLS_DIR` (each `*.py` file)

### 3.2 Callbacks injection (host → tools)

Tools can require host features (Busy status updates, human_ask synchronization, env access).

`util_tools.init_tools_callbacks(core)` injects callbacks into the tools runtime (`tools.init_callbacks`).

This is how tools share state with the CLI stdin loop (especially `human_ask`).

### 3.3 Tool specs passed to the LLM

`tools.get_tool_specs()` returns specs for LLM calls.

Important details:

- Extended fields such as `function.system_prompt` are removed before sending to the LLM.
- For compatibility, the function name may be mirrored to top-level `name`.

### 3.5 Tool trace output

By default, a one-line trace is printed to stdout before tool execution:

- Example: `[TOOL] 2025-... name=<tool> args=<masked-json>`
- Secret-like keys are masked.

A tool may suppress the trace using the extended flag:

- `TOOL_SPEC['function']['x_scheck']['emit_tool_trace'] = False`

`human_ask` uses this to avoid logging the raw user reply.

### 3.6 Tool levels and genres

- **Tool Level (`tool_level`)**: Specified in `TOOL_SPEC` to control tool loading. `-1` is disabled, `0` is enabled, and `1` is conditional loading (disabled by default).
- **Tool Genre (`tool_genre`)**: Categorizes tools into `"comm"` (communication), `"office"` (Office suite), or `"devel"` (development). This must be specified at the top-level of `TOOL_SPEC`.
- **Startup Selection**: During interactive CLI startup, users are prompted to select which tool genres to enable using a bitmask (1: comm, 2: office, 4: devel, 8: iot, 16: exec, 32: external, 64: media, 127: all).
- **`--tool-genre-mask` CLI argument**: All entry points (CLI/GUI/Web/A2A) accept `--tool-genre-mask <int>`. When specified, the bitmask is applied directly and the interactive genre prompt is skipped. This works in both interactive and non-interactive modes. When omitted, the behavior is unchanged (interactive prompt in TTY mode, no genre selection in non-interactive mode).

### 3.6.1 Tool-less mode (UAGENT_USE_TOOL / :tools on/off)

- **Environment variable**: `UAGENT_USE_TOOL=0` (or `false`/`no`/`off`) disables tool sending to the LLM at startup. All providers (OpenAI/Azure, Gemini/VertexAI, Claude, DeepSeek/Z.AI) are supported.
- **CLI argument**: `--use-tool` / `--no-use-tool` (all entry points: CLI/GUI/Web/A2A). Overrides `UAGENT_USE_TOOL` env var when specified. When neither is given, the env var (or default ON) is used.
- **Runtime toggle (CLI)**: `:tools on` enables tool sending; `:tools off` disables it. The change takes effect from the next LLM round.
- **Runtime toggle (Web)**: `GET /api/tools-enabled` returns the current state; `POST /api/tools-enabled` with `{"enabled": true/false}` toggles it (rejected while busy).
- **Implementation**: The runtime flag is `core.tools_enabled` (boolean, default `True`). It is initialized from `UAGENT_USE_TOOL` at startup in all entry points and read by `uagent_llm.run_llm_rounds()` each round via `getattr(_core_module, "tools_enabled", True)`.

### 3.7 Agent Skills lifecycle

- `:skills` injects the selected skill as a dedicated `[SKILL] ...` system message.
- Skill messages are persisted to the session log and restored on reload.
- `:skills status` shows active skill messages; `:skills clear` removes them.
- Keep skill instructions separate from the base `SYSTEM_PROMPT`.

### 3.8 Batch state helper

- `src/uagent/tools/batch_state_tool.py` provides persisted state for multi-file tasks.
- Default storage: `~/.uag/batches/`
- Override with `UAGENT_BATCHES_DIR`
- `load` can resume an existing batch and restore `task_description`, `instructions`, `target_files`, `done_files`, `pending_files`, and related progress fields.
- Supported actions: `init`, `load`, `update`, `append_log`, `finalize`, `list`, `delete`

______________________________________________________________________

## 4. Workdir / banner / long-term memory

### 4.1 Workdir selection

Workdir is decided in this priority order:

1. CLI option: `--workdir` / `-C`
1. Environment variable: `UAGENT_WORKDIR`
1. Fallback: current directory

CLI/Web/GUI perform workdir initialization inside `main()` (not at module import time).

### 4.2 Startup banner

The startup banner (workdir/provider/base_url/api_version/Responses mode, etc.) is generated by:

- `runtime_init.build_startup_banner()`

### 4.3 Long-term memory and shared memory

Long-term memory and shared memory can be inserted as system messages at startup.

Insertion order is:

1. base system prompt
1. long-term memory messages
1. shared memory messages
1. skill messages (if active)

Keep memory content concise and stable; it should augment, not replace, the base prompt.

______________________________________________________________________

## 5. MCP server tooling notes

MCP-related tools include:

- `mcp_servers_tool.py`
- `mcp_tools_list_tool.py`
- `handle_mcp_v2_tool.py`
- `mcp_servers_shared.py`

Recommended development flow:

1. Confirm the server definition in `mcp_servers.json`.
1. List available tools with `mcp_tools_list`.
1. Add or update the server entry with `mcp_servers`.
1. Validate the configuration.
1. Test the target tool via `handle_mcp_v2`.

If something fails, first check whether the server entry is reachable and whether the listed tools match the expected transport.
Validate again after each config change.

Recent smoke tests cover template creation and the basic add/list/validate/set_default/remove flow.

`mcp_servers_validate_tool.py` is hardened so it can still return raw output when callback-based truncation is unavailable.

______________________________________________________________________

## 6. Development checks

Common checks during development:

- Python syntax: `python -m py_compile src/uagent/**/*.py` (or use the repository's validation tools)
- Locale compile: `python scripts/compile_locales.py`
- Locale QC: `python scripts/po_qc_summary.py`
- Targeted tests: `pytest -q <path>` or the relevant `run_tests` flow
- If startup/tool/MCP behavior changed, run the affected path end-to-end
- Run the relevant test suite for the touched area

If a change affects startup, tools, or MCP behavior, verify the corresponding flow end-to-end.
