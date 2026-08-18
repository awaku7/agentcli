<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  24 providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Why uag?

**Break free from vendor lock-in.** Most AI assistants tie you to a specific provider or cloud service. uag is different.

- **Runs locally** on your machine. Your data stays with you (except API calls you make).
- **Provider freedom**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 providers, all accessible from a single interface. Swap between them by reconfiguring environment variables — no reinstall, no migration.
- **222 tools**: File I/O, web search, image generation, Gmail, BLE device scanning, MCP server integration — **130 are statically marked parallel-safe** (up to 8 execute concurrently via thread pool, configurable via `UAGENT_PARALLEL_WORKERS`). When the LLM fires multiple tool calls at once, uag automatically parallelizes them.
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
See [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) for all environment variables.

## Computer Use

Computer Use is opt-in and supports both a visible Playwright browser runtime
and a desktop runtime. When enabled, both runtimes are created and registered;
the BrowserRuntime is used by the existing handler API by default. Runtime resources are
closed together on normal exit, `Ctrl-C`, and process shutdown. Set
`UAGENT_COMPUTER_HEADLESS=1` for browser-based CI or smoke tests.
See [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md)
for the integration and safety details.

## Realtime Voice and AEC3

The realtime voice mode supports OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API, and Amazon Bedrock Nova Sonic with full-duplex microphone and speaker I/O. The required `pywebrtc-audio` AEC3 backend is installed automatically, and Bedrock's optional bidirectional-streaming SDK is installed automatically only when the Bedrock provider is selected:

```bash
python scheck.py realtime
```

The AEC3 pipeline receives the actual microphone signal (`near`) and the audio actually handed to the speaker (`far`) so the assistant can listen while speaking. Enable diagnostics only when investigating audio issues:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime supports a safety-limited Function Calling integration. The current realtime adapter exposes read-only `get_current_time` automatically. Destructive tools and device controls are not exposed without an explicit allowlist and confirmation flow. Grok realtime uses a separate adapter and does not use this OpenAI-specific function-call path.

## Features

### 🧠 Multi-Provider Architecture

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

All providers share the same toolset and interface. Switch by setting `UAGENT_PROVIDER` — no code changes, no separate installations.

#### Ollama and llama.cpp

Ollama and llama.cpp are separate providers. Ollama uses its own service and model management, while `llama.cpp` connects to a `llama-server` OpenAI-compatible endpoint:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

The llama.cpp provider uses the Chat Completions-compatible path. Keep `UAGENT_RESPONSES=0` unless a compatible proxy is configured.

### ⚡ Parallel Tool Execution

When the LLM requests multiple tools simultaneously, uag **automatically parallelizes** them.
130 tools are statically marked `x_parallel_safe` and execute concurrently via a `ThreadPoolExecutor` (8 threads by default; set `UAGENT_PARALLEL_WORKERS` to change).

**Example**: Ask "Check the weather in Nordic capitals" → LLM fires `search_web` × 5 countries → all 5 searches run in parallel → results collected in one batch.

The current count is based on tool modules that define a `TOOL_SPEC` (currently 222, including the 2 Rust-backed tools in `src/uagent/tools_rust/`). `http_request` uses method-sensitive safety: `GET`/`HEAD`/`OPTIONS` calls may run in parallel, while write methods remain serial.

Read-only tools (file search, hash calculation, directory listing, translation, DB queries, etc.) are aggressively parallelized.

### 🧩 Plugin System (Claude Code Compatible)

uagent implements a **Claude Code-compatible plugin system**. Plugins bundle skills, agents, MCP servers, hooks, and more into self-contained directories with a `.claude-plugin/plugin.json` manifest.

**Supported components**: Skills, Sub-agents, MCP servers, Hooks (12 lifecycle events), Slash commands, Output styles, userConfig, Dependencies, Channels, Marketplaces

**CLI commands**:

```
:plugin list                         # List installed plugins
:plugin install <source> [--scope]   # Install (dir/zip/git/http)
:plugin install <name>@<marketplace>  # Install from marketplace
:plugin remove <name>                # Uninstall
:plugin enable/disable <name>        # Toggle
:plugin marketplace add/remove/list  # Manage marketplaces
:plugin init <name>                  # Scaffold new plugin
```

See [DEVELOP_PLUGIN.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md) for full documentation.

### 🔄 Session Continuity

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 229 Tools

| Category | Tools |
|---|---|
| **File Operations** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml files), `path_alias` |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `url_alias`, `public_transit_route` ([guide](https://github.com/awaku7/agentcli/blob/main/docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | generate_image, analyze_image, img2img, audio_speech, audio_transcribe |
| **Documents** | PDF/PPTX/DOCX/RTF/ODT extraction, Excel structured extraction |
| **Forecast** | Time series forecasting with 9 models (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), auto model selection, plot generation, i18n |
| **Communication** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — see [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) and [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Cloud APIs** | `aws_api`, `gcp_api`, `azure_api` — generic AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation |
| **Dev Tools** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 source code navigators (idx family)** |
| **MCP** | Connect to external MCP servers, list tools, execute — [OAuth / Proxy guide](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Agent-to-agent communication (with other uag instances or A2A-compatible servers) |
| **System** | env vars, system specs, time, date calculation, [quantities](https://github.com/awaku7/agentcli/blob/main/docs/QUANTITIES.md), [geodesic_distance](https://github.com/awaku7/agentcli/blob/main/docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Source Nav** | **29 idx tools** for Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — get a function/class index or specific definition without reading the whole file |

#### Repository review and coverage

- `workspace_status`: report the active workspace's Git branch, changes, upstream sync state, Python runtime, and common project markers without modifying files.
- `git_review`: summarize Git changes, risky files, test candidates, and secret findings without exposing secret values.
- `security_scan`: scan repository files for likely secrets and risky configuration files.
- `coverage_report`: run and normalize coverage for Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift, and Dart/Flutter.
- Missing coverage dependencies can be installed automatically when execution is requested; `dry_run` never installs packages.

See [Repository Analysis Tools](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) for parameters, output, and safety details.

See [Path and URL aliases](https://github.com/awaku7/agentcli/blob/main/docs/PATH_URL_ALIASES.md) for shortening repeated file paths and URLs in tool arguments.

### 🖥 4 Interfaces + VS Code Extension

| Mode | Command | Purpose |
|---|---|---|
| **CLI** | `uag` | Fast terminal-based operation |
| **GUI** | `uagg` | Desktop UI via tkinter |
| **Web** | `uagw` | Browser-based access |
| **A2A Server** | `uaga` | Agent2Agent protocol for multi-agent communication |
| **VS Code** | — | [Extension](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) with Chat Panel, Explain, Refactor, Fix Error, and Tools Tree View |

See [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) for details on the VS Code extension — installation, commands, keybindings, and configuration.

### 🏠 IoT Device Control

- **BACnet**: Read/write BACnet/IP devices (HVAC, lighting, power meters). COV subscription for push notifications
- **Modbus TCP**: Read/write holding/input registers and coils. Polling-based change monitoring
- **OPC UA**: Browse address space, read/write variables, subscribe to data changes
- **SwitchBot**: Cloud batch control & BLE scan/control. Polling-based subscription
- **ECHONET Lite**: Discover, control, and subscribe to INF notifications from home appliances (AC, lights, water heaters, etc.)
- **Matter**: Read/write control + attribute subscription for state change monitoring
- **UPnP**: Device discovery & IGD port forwarding

See [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` to browse [SkillsMP](https://skillsmp.com) and [ClawHub](https://clawhub.ai) for community skills.
Install and extend uag's capabilities on the fly.

### 🤖 Auto-Pilot (`:auto`)

uag can **autonomously pursue a goal across multiple LLM rounds**. Perfect for complex, multi-step tasks that need iterative refinement.

- **How it works**: Each round has a main query (Step A) followed by a reviewer judgment (Step B) that decides "COMPLETE or CONTINUE?"
- **Same provider, same API**: The reviewer judgment uses the identical code path as the main query — including Responses API support.
- **Separate judge LLM** (optional): Set `UAGENT_AP_PROVIDER` to use a different provider/model for the reviewer (e.g. use a cheaper model for judging).
- **Exit anytime**: Press **F11** to stop auto-pilot; **F12** stops the current LLM response. Or let the reviewer decide when the goal is met.
- **Configurable**: `--max-rounds N` to control the budget.

See [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) for full documentation.

### 🧩 Batch State Manager

uag can track progress across long-running multi-file tasks. When the LLM processes dozens of files, `batch_state` persists the list of pending, completed, and failed files to disk. If the session ends or a round times out, the next run resumes from where it stopped — nothing gets lost.

### 🛡 Human-in-the-Loop

`human_ask` lets the LLM pause and ask for your confirmation before performing destructive operations (file deletion, overwrites, shell commands). You stay in control.

### 🛑 Interrupt (F12 / Stop button)

Stop LLM response generation at any time and inject a stop command back to the LLM.

| Interface | How to interrupt |
|---|---|
| **CLI** | Press F12 during LLM streaming — the current response stops, and `"Stop"` is sent as a user message so the LLM responds accordingly |
| **WEB UI** | Click the red **■ Stop** button (appears automatically during LLM processing) |
| **Desktop GUI** | Click the red **■** button (appears automatically during LLM processing) |

The interrupt works as "prompt injection": instead of just aborting, it feeds `"Stop"` back to the LLM as a user message, allowing it to gracefully conclude or acknowledge the interruption.

Press **F11** to stop auto-pilot; **F12** stops the current LLM response (see [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Browser Automation & Web Inspector

Two complementary Playwright-based tools:

- **browser_playwright**: Automate real browser sessions — navigate, click, fill forms, extract data, handle multi-page flows. Works headless or headed.
- **playwright_inspector**: Record browser transitions, capture DOM snapshots and screenshots at each step. Useful for debugging web interactions or auditing page changes over time.

### 🔄 Dynamic Tool Loading

`tool_catalog` and `tool_load` let you discover and enable tools at runtime.
No need to load everything at startup — activate only what you need, when you need it.

### 🦀 Rust Native Tools

`uuid_gen` and `slugify` are implemented in Rust (via PyO3) for performance.
They load directly from a pre-built `.pyd` — **no `pip install` required**.

External developers can also ship Rust-based tools: place a `.pyd` next to the
wrapper `.py`, use `load_rust_pyd()` from `uagent.tools.rust_helper`, and
users get the tool without any extra dependencies. See
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / and more.
Set `UAGENT_LANG` to switch. See [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) to add a new locale.

Translations of this README are available in [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Encrypted Environment Variables

Store API keys and secrets in `.env.sec` — an encrypted `.env` file.
Manage with `uag_envsec`.

## Configuration & Details

- **Environment variables**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Setup wizard**: `python -m uagent.setup_cli`
- **Encrypted env**: `uag_envsec` — encrypt `.env` as `.env.sec`
- **Responses API**: Set `UAGENT_RESPONSES=1` for Responses API mode (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Auto-enabled for Sakana AI (Fugu).
- **Developer docs**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — how tools are sent to LLMs (genre mask, tool_catalog, GPT-5.4+ native tool_search)
- **Small LLM tips**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Project Philosophy

uag aspires to be **your AI, on your machine, on your terms.**

- No SaaS dependency — runs locally
- No provider lock-in — switch anytime
- No UI lock-in — CLI / GUI / Web / A2A
- No feature lock-in — extend with tools and skills

A free AI agent experience, free from vendor lock-in.

### ✨ Create Your Own Tools

Writing a new tool for uag is straightforward — create a single `.py` file with
`TOOL_SPEC` and `run_tool()`, place it in `UAGENT_EXTERNAL_TOOLS_DIR`, and
it's immediately available. For Rust developers, ship a pre-built `.pyd` with
zero extra dependencies for users.

See [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
for the step-by-step guide.

## Contributing

Contributions are welcome! Bug reports, feature suggestions, documentation improvements, translations, and pull requests — all appreciated.

- **Issues**: Open a GitHub issue for bugs or feature requests.
- **Pull requests**: Fork the repo, make your changes, and submit a PR. See [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) for development setup and guidelines.
- **Translations**: README translations and locale additions are welcome. See [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: New tool plugins and Agent Skills can be contributed via the marketplace.

### Development checks (before PR)

Install the test-only dependencies first. They are kept out of the runtime
dependency list:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

Run the same checks used by GitHub Actions before pushing:

```bash
python -m ruff check src tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

For a faster local iteration, run only the affected tests:

```bash
pytest -q tests/<affected_area>
```

Additional checks when relevant:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

After locale (`.po`) edits: `python scripts/compile_locales.py` and `python scripts/po_qc_summary.py`.

Runtime policy (details in [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): helpers raise instead of `sys.exit`; the tool host turns tool `SystemExit`/`Exception` into error strings so a single tool cannot kill the process. Startup fail-fast exits remain intentional.

## Architecture and operational invariants

See [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) for the durable contracts covering A2A lifecycle, I18N contexts, optional dependency installation, tool safety, provider capabilities, OAuth trust boundaries, structured events, and acceptance verification.

## Enterprise Policy Engine

Organization-level policies for tools, providers, credentials, MCP servers, networks, skills, and plugins are supported. Set `UAGENT_POLICY_FILE` to a JSON/YAML policy file; see [docs/ENTERPRISE_POLICY.md](https://github.com/awaku7/agentcli/blob/main/docs/ENTERPRISE_POLICY.md) for configuration examples, roles, confirmation, and allowlists.

## Credential Store

Provider API keys, OAuth tokens, MCP credentials, and A2A credentials can use the shared `CredentialStore`. The default backend is `auto`: when the optional `python-keyring` package is available, uag uses the native OS secret store (Windows Credential Manager, macOS Keychain, or Linux Secret Service); otherwise it falls back to the encrypted file store and then environment variables during resolution.

```text
:credential set provider/openai api_key
:credential get provider/openai
:credential remove provider/openai
:credential list
```

`set` masks the secret input, `get` never prints the secret, and `remove` requires confirmation. Set `UAGENT_CREDENTIAL_STORE_BACKEND=os` to require the OS keyring or `file` to force the encrypted file backend. See [docs/IMPROVEMENT_PRIORITY.md](https://github.com/awaku7/agentcli/blob/main/docs/IMPROVEMENT_PRIORITY.md) and [docs/ENTERPRISE_POLICY.md](https://github.com/awaku7/agentcli/blob/main/docs/ENTERPRISE_POLICY.md) for the storage and policy details.

### Runtime recovery and orchestration

See [RESTART_RECOVERY.md](https://github.com/awaku7/agentcli/blob/main/docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](https://github.com/awaku7/agentcli/blob/main/docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](https://github.com/awaku7/agentcli/blob/main/docs/MULTI_AGENT_RUNTIME.md) for durable recovery, dependency-aware execution, multi-agent orchestration, and remote A2A usage.

See [DISTRIBUTED_COORDINATION.md](https://github.com/awaku7/agentcli/blob/main/docs/DISTRIBUTED_COORDINATION.md) for shared-runtime leader lease coordination.
