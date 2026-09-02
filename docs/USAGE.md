# USAGE (Command-line options)

This document describes the command-line options available for uag entry points.

______________________________________________________________________

## Entry points

| Command | Python module | Interface |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin loop) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Web server (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP server |

______________________________________________________________________

## Common options (all entry points)

### `--workdir` / `-C <path>`

Working directory. If not set, falls back to `UAGENT_WORKDIR` env var, then the current directory.
The directory is created if it does not exist.

### `--tool-genre-mask <int>`

Tool genre bitmask. When provided, the interactive genre selection prompt is skipped.

| Bit | Genre | Description |
|-----|-------|-------------|
| 1 | basic | Essential file/chat tools |
| 2 | comm | Communication tools (Bluesky, Teams) |
| 4 | office| Office suite tools (Excel, PDF, PPTX) |
| 8 | devel | Development tools (git, lint, compile) |
| 16 | iot | IoT device tools (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Command execution tools |
| 64 | external | External plugin tools |
| 128 | media | Image/audio generation and analysis |
| 255 | all | All tools |

Examples:

```
uag --tool-genre-mask 1       # basic only
uag --tool-genre-mask 9       # basic + devel (1 + 8)
uag --tool-genre-mask 255     # all tools
```

### `--use-tool` / `--no-use-tool`

Enable or disable sending tool definitions to the LLM. Overrides the `UAGENT_USE_TOOL` environment variable.

- `--use-tool` forces tool sending on.
- `--no-use-tool` forces tool sending off.

When disabled, the LLM receives no tool definitions and cannot call any tool.

### `--embedded`

Embedded mode for constrained or reproducibility-sensitive deployments.

- Disables the session store.
- Hides tool-management tools (`tool_catalog`, `tool_load`, `unload_tool`) unless explicitly enabled.
- Ignores `--tool-genre-mask`; use `--enable-tool` for explicit tool loading.

### `--enable-tool <name>`

Explicitly load a tool at startup. The option can be repeated, and comma-separated names are also accepted.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

The specified order is preserved and is reflected in the tool order presented to the LLM. Explicitly enabled tools are pinned against automatic unloading.

______________________________________________________________________

## CLI-only options

### `--inject-message-auto <goal-options>`

Start auto-pilot from a non-interactive injected goal. The value uses the same options as `:auto`; quote the complete value when it contains options.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --infinite"
```

The normal mode uses the reviewer judgment path. Set `UAGENT_AUTO_SENTINEL=1` to opt into single-LLM sentinel mode. In that mode, the target LLM must end each response with exactly one of:

- `<AUTO_CONTINUE>` — run another round
- `<AUTO_COMPLETE>` — finish successfully

Missing or invalid markers stop auto-pilot safely. This still runs the target LLM; it only avoids the additional reviewer LLM call.

### `--non-interactive`

Non-interactive mode. Does not start the stdin loop. If a file path is given as a positional argument, it is processed and the program exits immediately.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Web-only options (`uagw`)

### `--host <address>`

Bind address for the Web server (default: `127.0.0.1`, overridable by `UAGENT_WEB_HOST`).

By default, the Web server listens on localhost only (`127.0.0.1`). To make it accessible from other machines on the network, use `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

______________________________________________________________________

## A2A-only options

### `--host <address>`

Bind address for the A2A HTTP server (default: `0.0.0.0`, overridable by `UAGENT_A2A_HOST`).

### `--port <number>`

Port number for the A2A HTTP server (default: `8765`, overridable by `UAGENT_A2A_PORT`).

### `--reload`

Enable hot reload on code changes (default: off, overridable by `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

______________________________________________________________________

## Related environment variables

| Variable | Description |
|---|---|
| `UAGENT_PROVIDER` | LLM provider name (required at startup) |
| `UAGENT_*_API_KEY` | API key for the selected provider |
| `UAGENT_WORKDIR` | Default working directory |
| `UAGENT_WEB_HOST` | Web server bind address (default: `127.0.0.1`) |
| `UAGENT_USE_TOOL` | Disable tools when set to `0`, `false`, `no`, or `off` |
| `UAGENT_AUTO_SENTINEL` | Opt into single-LLM auto-pilot sentinel mode when set to `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Maximum consecutive fresh tool calls (default: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Maximum LLM/tool rounds per user operation (default: `200`) |
| `UAGENT_SHRINK_CNT` | Auto-shrink threshold in messages (default: `100`, `0` = off) |
| `UAGENT_SHRINK_KEEP_LAST` | Messages to retain after shrink (default: `20`) |
| `UAGENT_LANG` | Interface language (`ja`, `en`, etc.) |

For the full list of environment variables, see [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Examples

### Minimal start with OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Local Ollama with basic tools only

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Web server on all interfaces

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

or

```
uagw --host 0.0.0.0
```

### A2A server on localhost with custom port

```
uaga --host 127.0.0.1 --port 8080
```

### Disable tools for a small model

```
uag --no-use-tool --tool-genre-mask 1
```

### Non-interactive file processing

```
uag --non-interactive README.md
```
