```
██╗   ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗ ██████╗██╗     ██╗
██║   ██║██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██║     ██║
██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     ██║     ██║
██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██║     ██║
╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ╚██████╗███████╗██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝╚══════╝╚═╝
```

# uag (Local AI Agent)

uag is an interactive agent that executes **commands**, manipulates **files**, and reads **various data formats** (PDF/PPTX/Excel, etc.) on your local PC. It provides three interfaces: CLI, GUI, and Web.

## Installation

You can install `uag` via pip:

```bash
pip install uag
```

After installation, running `uag` for the first time will automatically launch an **interactive setup wizard** to configure your environment variables. For detailed information on configuration and encryption, see **[ENVIRONMENT.md](ENVIRONMENT.md)**.

## Key Features

- **Practical Toolset**: Equipped with tools for file manipulation, web search, data extraction (PDF/PPTX/Excel), image generation, and analysis, all executable in your local environment.
- **Multi-Provider Support**: Supports OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Claude / Grok / NVIDIA.
- **Flexible Interfaces**: 
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: Support for connecting to external MCP tool servers.
- **Session Continuity**: Maintain conversation context even when switching providers or models.
- **Web Inspector**: Automatically save browser transitions, DOM, and screenshots using `playwright_inspector`.
- **Built-in Docs**: Instantly access detailed internal documentation using the `uag docs` command.

## Usage

### Start and Exit
Run `uag` from your terminal to start. Type `:exit` to quit.

### A2A (Agent2Agent) Server
You can launch an A2A-compatible HTTP server separate from the existing interfaces.
```bash
uaga
# or python -m uagent.a2a.server
```

### Handy Tips (Continuity and Control)
- `:tools`: Display a list of loaded tools.
- `:logs [n]`: Show session logs (`n` to specify the number of entries).
- `:load <index>`: Load a past session to resume the conversation.
- `:skills`: Select and load Agent Skills (additional roles or instructions).
- `:shrink [n]`: Organize history to keep only the last `n` messages to save tokens.

## Configuration and Details

### Environment Variables and Setup
For detailed settings (API keys, display language `UAGENT_LANG`, history shrink settings, etc.), see **[ENVIRONMENT.md](ENVIRONMENT.md)**.
- **Setup**: Configure interactively via `python -m uagent.setup_cli`.
- **Encryption**: Securely encrypt your `.env` file using the `uag_envsec` tool.

### Developers and Internationalization
- **Developer Docs**: `src/uagent/docs/DEVELOP.md`
- **Adding Locales**: `src/uagent/docs/ADD_LOCALE.md`
- **README in other languages**: [日本語](README.ja.md) / [Deutsch](README.de.md) / [Français](README.fr.md) / [한국어](README.ko.md) / [简体中文](README.zh_CN.md) / [繁體中文](README.zh_TW.md)
