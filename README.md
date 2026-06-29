<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Why uag?

**Break free from vendor lock-in.** Most AI assistants tie you to a specific provider or cloud service. uag is different.

- **Runs locally** on your machine. Your data stays with you (except API calls you make).
- **Provider freedom**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 15+ providers, all accessible from a single interface. Swap between them by reconfiguring environment variables — no reinstall, no migration.
- **131 tools**: File I/O, web search, image generation, Gmail, BLE device scanning, MCP server integration — **76 are parallel-safe** (up to 8 execute concurrently via thread pool, configurable via `UAGENT_PARALLEL_WORKERS`). When the LLM fires multiple tool calls at once, uag automatically parallelizes them.
- **3 UIs + A2A**: CLI, GUI, Web, and Agent-to-Agent protocol. Same engine, any interface.
- **IoT ready**: SwitchBot, ECHONET Lite, Matter, UPnP — control your home devices through AI.
- **Agent Skills**: Install community-built skills from the marketplace. Extend uag endlessly.

uag is **your AI assistant on your terms**. Not tied to a provider, not tied to an interface, not tied to a platform.

## Quick Start

```bash
pip install uag
uag
```

On first launch, the setup wizard walks you through provider configuration.
See [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) for all environment variables.

## Features

### 🧠 Multi-Provider Architecture

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

All providers share the same toolset and interface. Switch by setting `UAGENT_PROVIDER` — no code changes, no separate installations.

### ⚡ Parallel Tool Execution

When the LLM requests multiple tools simultaneously, uag **automatically parallelizes** them.
76 tools are marked `x_parallel_safe` and execute concurrently via a `ThreadPoolExecutor` (8 threads by default; set `UAGENT_PARALLEL_WORKERS` to change).

**Example**: Ask "Check the weather in Nordic capitals" → LLM fires `search_web` × 5 countries → all 5 searches run in parallel → results collected in one batch.

Read-only tools (file search, hash calculation, directory listing, translation, DB queries, etc.) are aggressively parallelized.

### 🔄 Session Continuity

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 Tools

| Category | Tools |
|---|---|
| **File Operations** | read/write/create/delete/search/grep/hash/zip, parse_eml (.eml files) |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | generate_image, analyze_image, img2img, audio_speech, audio_transcribe |
| **Documents** | PDF/PPTX/DOCX/RTF/ODT extraction, Excel structured extraction |
| **Communication** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook — see [COMMUNICATION.md](COMMUNICATION.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Dev Tools** | git_ops, python_compile, lint_format, run_tests, db_query, **13 source code navigators (idx family)** |
| **MCP** | Connect to external MCP servers, list tools, execute |
| **A2A** | Agent-to-agent communication (with other uag instances or A2A-compatible servers) |
| **System** | env vars, system specs, time, date calculation |
| **Source Nav** | **13 idx tools** for Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — get a function/class index or specific definition without reading the whole file |

### 🖥 4 Interfaces + VS Code Extension

| Mode | Command | Purpose |
|---|---|---|
| **CLI** | `uag` | Fast terminal-based operation |
| **GUI** | `uagg` | Desktop UI via tkinter |
| **Web** | `uagw` | Browser-based access |
| **A2A Server** | `uaga` | Agent2Agent protocol for multi-agent communication |
| **VS Code** | — | [Extension](VSCODE.md) with Chat Panel, Explain, Refactor, Fix Error, and Tools Tree View |

See [VSCODE.md](VSCODE.md) for details on the VS Code extension — installation, commands, keybindings, and configuration.

### 🏠 IoT Device Control

- **SwitchBot**: Cloud batch control & BLE scan/control
- **ECHONET Lite**: Discover and control home appliances (AC, lights, water heaters, etc.) on local network
- **Matter**: Read-only inspection of controller/bridge/device topology
- **UPnP**: Device discovery & IGD port forwarding

See [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` to browse [SkillsMP](https://skillsmp.com) and [ClawHub](https://clawhub.ai) for community skills.
Install and extend uag's capabilities on the fly.

### 🧩 Batch State Manager

uag can track progress across long-running multi-file tasks. When the LLM processes dozens of files, `batch_state` persists the list of pending, completed, and failed files to disk. If the session ends or a round times out, the next run resumes from where it stopped — nothing gets lost.

### 🛡 Human-in-the-Loop

`human_ask` lets the LLM pause and ask for your confirmation before performing destructive operations (file deletion, overwrites, shell commands). You stay in control.

### 🛑 Interrupt (c-key / Stop button)

Stop LLM response generation at any time and inject a stop command back to the LLM.

| Interface | How to interrupt |
|---|---|
| **CLI** | Press `c` key during LLM streaming — the current response stops, and `"Stop"` is sent as a user message so the LLM responds accordingly |
| **WEB UI** | Click the red **■ Stop** button (appears automatically during LLM processing) |
| **Desktop GUI** | Click the red **■** button (appears automatically during LLM processing) |

The interrupt works as "prompt injection": instead of just aborting, it feeds `"Stop"` back to the LLM as a user message, allowing it to gracefully conclude or acknowledge the interruption.

Press `x` key to exit auto-pilot mode (see `:auto` command).

### 🕵️ Browser Automation & Web Inspector

Two complementary Playwright-based tools:

- **browser_playwright**: Automate real browser sessions — navigate, click, fill forms, extract data, handle multi-page flows. Works headless or headed.
- **playwright_inspector**: Record browser transitions, capture DOM snapshots and screenshots at each step. Useful for debugging web interactions or auditing page changes over time.

### 🔄 Dynamic Tool Loading

`tool_catalog` and `tool_load` let you discover and enable tools at runtime.
No need to load everything at startup — activate only what you need, when you need it.

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / and more.
Set `UAGENT_LANG` to switch. See [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) to add a new locale.

Translations of this README are available in [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Encrypted Environment Variables

Store API keys and secrets in `.env.sec` — an encrypted `.env` file.
Manage with `uag_envsec`.

## Configuration & Details

- **Environment variables**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Setup wizard**: `python -m uagent.setup_cli`
- **Encrypted env**: `uag_envsec` — encrypt `.env` as `.env.sec`
- **Responses API**: Set `UAGENT_RESPONSES=1` for Responses API mode (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **Developer docs**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Small LLM tips**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Project Philosophy

uag aspires to be **your AI, on your machine, on your terms.**

- No SaaS dependency — runs locally
- No provider lock-in — switch anytime
- No UI lock-in — CLI / GUI / Web / A2A
- No feature lock-in — extend with tools and skills

A free AI agent experience, free from vendor lock-in.
