# AGENTS.md

uag is a local tool-execution agent written in Python. It runs shell commands,
edits files, and interacts with LLMs through multiple providers (OpenAI, Claude,
Gemini, DeepSeek, Ollama, OpenRouter, etc.).

## Project structure

- `src/uagent/` — main Python package
  - `cli.py` — CLI entry point (`python -m uagent`, command: `uag`)
  - `gui.py` — GUI entry point (`python -m uagent.gui`, command: `uagg`)
  - `web.py` — Web entry point (`python -m uagent.web`, command: `uagw`)
  - `core.py` — core state and UI integration
  - `uagent_llm.py` — LLM orchestration entrypoint
  - `llm_helpers.py`, `llm_message_helpers.py`, `llm_round_helpers.py`, `llm_flow_helpers.py` — round/message/tool-call helpers
  - `llm_errors.py` — retry/backoff
  - `util_tools.py` — common helpers, commands (`:auto`, `:cd`, `:ls`, etc.)
  - `util_providers.py` — provider wiring (detect, model name, client creation)
  - `tools/` — tool plugin modules (one file per tool)
  - `providers/` — LLM provider implementations
  - `runtime/` — startup initialization, workdir, banner, env, memory
  - `a2a/` — A2A server implementation
  - `docs/` — developer documentation (DEVELOP.md, DEVELOP_TOOL.md, DEVELOP_I18N.md, etc.)
- `scripts/` — utility scripts (compile_locales.py, po_qc_summary.py)
- `pyproject.toml` — project metadata and dependencies
- `README.md`, `README.ja.md`, `README_AUTO.md` — user-facing documentation

## Entry points

| Command | Description |
|---|---|
| `python -m uagent` (or `uag`) | Interactive CLI |
| `python -m uagent.gui` (or `uagg`) | GUI mode |
| `python -m uagent.web` (or `uagw`) | Web UI |
| `python -m uagent.a2a.server` | A2A server (default port 8765) |

## Startup flow

1. Decide workdir (`--workdir` / `-C` > `UAGENT_WORKDIR` > current dir)
2. Load `.env` and `.env.sec` (decrypted with `.uagent.key`)
3. Build and print startup banner
4. Load tool plugins from `src/uagent/tools/`
5. Create provider client from environment variables
6. Enter UI loop (CLI/GUI/Web) and receive user input
7. LLM rounds via `uagent_llm.run_llm_rounds()`

## Dev environment tips

- Python 3.11+ required. Check with `python --version`.
- Node.js v24.18.0 required for locale tooling.
- Install deps: `pip install -e ".[dev]"` (or read `pyproject.toml` for dependencies).
- Work in the project root (`C:\KAIHATSU\agentcli` on the primary dev machine).
- Use VSCode for editing. The workspace is at the project root.
- Environment variables prefixed with `UAGENT_` configure behavior.
- Sensitive config goes into `.env.sec` (encrypted with `.uagent.key`).
- Run `python -m uagent` to start the CLI and test changes interactively.

## Commands to run before committing

- **Python syntax**: `python -m py_compile src/uagent/` (catches import/syntax errors).
- **Format/lint**: `ruff format src/` and `ruff check src/` (or `black src/` as fallback).
- **Locale compile**: `python scripts/compile_locales.py` (after editing .po files).
- **Locale QC**: `python scripts/po_qc_summary.py` (check translation quality).
- **Targeted tests**: `pytest -q tests/<affected_area>`.
- After changing tools, startup, or MCP behavior, run the affected path end-to-end.

## Coding conventions

- New tools go in `src/uagent/tools/<name>_tool.py` with `TOOL_SPEC` dict and a `run_tool()` function.
- CLI subcommands are registered via `CMD_SPEC` dicts (command + subcommand + handler).
- i18n: use `_("msgid", default="English text")` via `make_tool_translator(__file__)`.
- Keep `DEVELOP.md` in sync with implementation changes.
- Backup files (`.org`, `.org1`, `.org2`) must not be edited directly.
- Prefer CLI arguments over environment variables for configuration.
- All entry points (CLI/GUI/Web/A2A) should share consistent behavior.
- File creation: output full file contents, not diffs or partial summaries.
- Dangerous operations require user confirmation before execution.

## Tool system

- Tools are plugin modules under `src/uagent/tools/`.
- Each tool exports `TOOL_SPEC` (OpenAI function schema compatible) and `run_tool(args) -> str`.
- Tool genres: `basic`, `comm`, `office`, `devel`, `iot`, `exec`, `external`, `media`, `file`, `index`.
- Startup selects genres via bitmask (`--tool-genre-mask <int>`).
- Tool-less mode: `--no-use-tool` or `UAGENT_USE_TOOL=0` or `:tools off`.
- Skills: installed via `:skills install` or APM (`:skills apm use`).
- MCP servers: defined in `mcp_servers.json`, managed via `mcp_servers` / `mcp_tools_list` / `handle_mcp_v2` tools.

## i18n (internationalization)

### Two approaches

**1. Host side** (`core.py`, `cli.py`, `gui.py`, `web.py`, `runtime/`, `providers/`, etc.)

- Uses gettext. Import with `from .i18n import _`.
- Config file: `babel.cfg` (project root).

```python
print(_("Loaded long-term memory."))
print(_("Failed: %(err)s") % {"err": e})
print("[WARN] " + _("Failed to read: %(path)s") % {"path": p})
```

Use `%(name)s` placeholders instead of f-strings.

**Workflow:**

```bash
# 1. Extract POT from source code
pybabel extract -F babel.cfg -o src/uagent/locales/uagent.pot .

# 2. Rebuild English PO from POT
python scripts/po_rebuild_en.py

# 3. Update non-English PO (e.g. Japanese)
python scripts/po_rebuild_non_en.py src/uagent/locales/ja/LC_MESSAGES/uag.po

# 4. Compile .mo
python scripts/compile_locales.py

# 5. QC check
python scripts/po_qc_summary.py
```

- `.po` files are at `src/uagent/locales/<lang>/LC_MESSAGES/uag.po`.
- Keep `%(name)s` placeholders unchanged in translations.
- When adding a new host-side package, add its entry to `babel.cfg`.

**2. Tool side** (`tools/*_tool.py`)

- Uses `make_tool_translator(__file__)` + JSON key approach. Different mechanism; not covered in this AGENTS.md.

## PR instructions

- Run all checks above before submitting.
- If adding a new LLM provider, update: `util_providers.py`, `env_validate.py`, `runtime_banner.py`, and `provider_caps.py`.
- If adding a CLI option, ensure it works across all entry points (CLI/GUI/Web/A2A).
- Update `DEVELOP.md` and any relevant docs under `src/uagent/docs/`.
- For i18n changes, run `python scripts/compile_locales.py` and `python scripts/po_qc_summary.py`.
- Test the affected flow end-to-end.
