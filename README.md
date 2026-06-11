<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Local AI Agent)

uag is a local interactive agent that executes **commands**, manipulates **files**, and reads **data files** such as PDF, PPTX, and Excel. It provides three user interfaces: CLI, GUI, and Web.
uag is built to **keep you free from vendor-locked apps**: use the interface that fits your workflow, switch providers, and stay in control of your environment.
GitHub: https://github.com/awaku7/agentcli

## Installation

Install from PyPI with pip:

```bash
pip install uag
```

If you use a virtual environment, activate it first and then run the command above.

On first launch, `uag` checks your environment and starts the setup wizard automatically when required provider variables are missing. For configuration details, see [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## Key Features

- **Practical toolset**: File manipulation, web search, PDF/PPTX/Excel extraction, image generation, and image analysis.
- **Multi-provider support**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Three interfaces**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A server**: `uaga` / `python -m uagent.a2a.server`
- **MCP support**: Connect to external MCP tool servers.
- **Session continuity**: Keep context when switching models or providers.
- **Web Inspector**: Save browser transitions, DOM snapshots, and screenshots with `playwright_inspector`.
- **Built-in docs**: Read bundled docs with `uag docs`.

## Usage

### Start and exit

Run `uag` in your terminal to start. Type `:exit` to quit.

### A2A server

Launch an Agent2Agent-compatible HTTP server:

```bash
uaga
```

See [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) for `UAGENT_A2A_*` settings such as auth, host, port, reload, public base URL, concurrency, and engine.

### Handy tips

- `:tools`: show loaded tools
- `:logs [n]`: show recent session logs
- `:load <index>`: load a previous session
- `:skills`: select and load Agent Skills
- `:shrink [n]`: summarize history and keep the last `n` messages

## Configuration and details

### Environment variables and setup

For API keys, language settings (`UAGENT_LANG`), history shrink settings, and more, see [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

- **Setup wizard**: `python -m uagent.setup_cli`
- **Encrypted environment**: use `uag_envsec` to encrypt `.env` as `.env.sec`
- **Update encrypted values**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Responses API note

If you set `UAGENT_RESPONSES=1`, Responses API is used for supported providers: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI use their native API paths and are not covered by Responses API.
Image analysis via Responses is currently limited to OpenAI / Azure / Bedrock / OpenRouter.
For other providers, uag falls back to the provider-specific or chat-completions path.

### Developer docs and translations

- **Developer docs**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Add locales**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **Other README translations**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
