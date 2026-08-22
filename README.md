<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  One local agent. Any model. Any tool. Your environment, your rules.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

## Why uag?

uag is a local-first AI agent that connects the model you prefer to the tools you actually use.
It gives you a single, extensible runtime for files, browsers, codebases, communication, cloud APIs,
IoT devices, MCP servers, and multi-agent workflows.

- **Provider freedom** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek, and more.
- **Local-first execution** — your agent runtime and tool execution stay on your machine; only the API calls you choose leave it.
- **One tool layer** — the same tools work from the CLI, desktop GUI, web UI, VS Code, and A2A.
- **Parallel by design** — independent read-only operations can run concurrently.
- **Extensible** — add tools, plugins, Agent Skills, MCP servers, and Rust-backed tools without changing the core.
- **Safety-aware** — destructive actions, credentials, device controls, and network writes support explicit confirmation and policy controls.

> **In short:** uag is the control plane between your AI models and your real environment.

## Flagship capabilities

### 🧠 One agent, every model

Use hosted or local models through one consistent tool interface. Switch providers with
`UAGENT_PROVIDER`—no code changes, migration, or separate workflow.

### 🖥 Computer Use and browser automation

Opt-in Computer Use combines a Playwright browser runtime with desktop interaction. Automate
navigation, forms, multi-page flows, downloads, screenshots, and DOM extraction. The Browser
Inspector records transitions and page state for debugging and auditing.

See [Computer Use](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md).

### ⚡ Parallel tool execution

Independent read-only operations run concurrently when safe. Web searches, file inspection,
repository analysis, and similar workloads can complete in parallel with a configurable worker
pool (`UAGENT_PARALLEL_WORKERS`). Write operations remain serialized or require confirmation.

### 🧩 Built to extend

- **200+ tools** for files, web, media, documents, code, cloud, communication, and IoT
- **Dynamic loading** with `tool_catalog` and `tool_load`
- **Claude Code-compatible plugins** with skills, agents, MCP servers, hooks, commands, and marketplaces
- **Agent Skills** from SkillsMP and ClawHub
- **Custom Python tools** with `TOOL_SPEC` and `run_tool()`
- **Rust-backed tools** for lightweight native extensions

### 🔄 Reliable long-running work

Session continuity, tool-result caching, batch state, restart recovery, DAG scheduling, and
multi-agent orchestration make complex work resumable instead of one-shot.

### 🎙 Realtime voice

Full-duplex voice is available through OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live,
and Bedrock Nova Sonic, with optional AEC3 echo cancellation and safety-limited realtime function calling.

### 🌍 Private, multilingual, and policy-aware

Use uag in Japanese, English, Chinese, Korean, Spanish, French, Russian, and more. Credentials can
be stored in the native OS keychain or encrypted file backend. Enterprise policies can govern tools,
providers, networks, credentials, plugins, skills, and MCP servers.

See [Environment variables](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md),
[Enterprise Policy](https://github.com/awaku7/agentcli/blob/main/docs/ENTERPRISE_POLICY.md), and
[Tool Creator Guide](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

## Quick start

### Install

```bash
python -m pip install --upgrade uag
uag
```

The first launch opens the setup wizard. It helps configure a provider and stores the selected settings
in your local environment.

For the common feature groups:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Platform integrations are optional. Install only what your operating system needs; see
> [Platform setup](#platform-setup).

### Choose a provider

Set a provider and its API key before launching, or configure them in the setup wizard.

```bash
# OpenAI
export UAGENT_PROVIDER=openai
export OPENAI_API_KEY="your-api-key"

# Anthropic
export UAGENT_PROVIDER=anthropic
export ANTHROPIC_API_KEY="your-api-key"

# Local Ollama
export UAGENT_PROVIDER=ollama
export UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
export UAGENT_OLLAMA_DEPNAME=llama3.1
```

Windows PowerShell uses `$env:NAME = "value"` instead of `export NAME=value`.
See [Environment variables](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) for the complete provider matrix.

### Try it

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

## Interfaces

| Interface | Command | Best for |
|---|---|---|
| **CLI** | `uag` | Fast, keyboard-first work |
| **Desktop GUI** | `uagg` | A native desktop experience |
| **Web UI** | `uagw` | Browser-based access |
| **A2A server** | `uaga` | Agent-to-agent communication |
| **VS Code** | Extension | Explain, refactor, fix, and browse tools in the editor |

All interfaces share the same provider configuration, tool registry, safety rules, and session data.

## What it can do

### Work with your environment

- Read, create, edit, search, hash, archive, and inspect files
- Review Git changes, scan for secrets, run tests, lint, compile, and measure coverage
- Navigate large Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA, and other codebases
- Automate browsers with Playwright, including multi-page workflows and downloads

### Use any model

Provider adapters cover hosted and local runtimes, including:

**OpenAI · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

Switch providers with `UAGENT_PROVIDER`; your tools and interface do not change.

### Connect services and devices

- **MCP** — connect external tool servers, including OAuth-enabled services
- **A2A** — coordinate with other agents and compatible servers
- **Cloud** — AWS, Google Cloud, and Azure API access with confirmation for writes
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams, and pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA, and UPnP
- **Media** — image generation/editing, audio transcription/speech, camera capture, and QR codes
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL, and log analysis

The runtime currently includes a large catalog of tools. Discover the exact tools available in your installation with:

```text
:tools
```

## Platform setup

The core package is cross-platform. Platform-specific dependencies should be installed selectively.

### Windows

```powershell
python -m pip install PySide6 winrt-Windows.Devices.Geolocation
```

### macOS

```bash
python -m pip install PySide6 pyobjc-framework-CoreLocation
```

### Linux

```bash
python -m pip install PySide6 ewmh dbus-next
```

Some integrations have additional system requirements, such as browser binaries, Bluetooth permissions,
cloud credentials, or an MQTT/OPC UA server. The relevant tool reports what is missing when it runs.

## Sessions, automation, and safety

### Session continuity

Resume previous conversations with `:load <index>`. Tool results can be cached, and providers can be changed
without rebuilding the application.

### Auto-pilot

Use `:auto` for multi-round work with an optional reviewer model. Set a round limit with `--max-rounds N`.
Press **F11** to stop auto-pilot or **F12** to stop the current response.

See [Auto-pilot](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md).

### Human confirmation

`human_ask` pauses before sensitive actions. File deletion, overwrites, shell commands, device controls,
credential operations, and network writes can be governed by confirmation and policy rules.

Organization-wide controls are available through the [Enterprise Policy Engine](https://github.com/awaku7/agentcli/blob/main/docs/ENTERPRISE_POLICY.md).

### Credentials

Use the credential store instead of placing long-lived secrets in prompts:

```text
:credential set provider/openai api_key
:credential get provider/openai
:credential list
```

The store can use Windows Credential Manager, macOS Keychain, Linux Secret Service, or the encrypted file
backend. See [Credential Store](https://github.com/awaku7/agentcli/blob/main/docs/ENTERPRISE_POLICY.md) for configuration details.

## Extensions

### Agent Skills and plugins

Install community skills from SkillsMP or ClawHub, or install Claude Code-compatible plugins containing
skills, agents, MCP servers, hooks, commands, and output styles.

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
```

See [Plugin development](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md) and [Agent Skills](https://github.com/awaku7/agentcli/tree/main/skills).

### Create a tool

A tool can be a single Python file with `TOOL_SPEC` and `run_tool()`. Put it in
`UAGENT_EXTERNAL_TOOLS_DIR` and reload the catalog. Rust developers can ship a pre-built native module
with a thin Python wrapper.

See [Tool Creator Guide](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### MCP servers

Connect to external MCP servers from the CLI or configuration file. OAuth and proxy guidance is available
in [MCP OAuth / Proxy Guide](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md).

## Realtime voice

Optional realtime voice integrations support OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice,
Google Gemini Live, and Amazon Bedrock Nova Sonic. Install the relevant audio dependencies and run:

```bash
python scheck.py realtime
```

AEC3 support is available for full-duplex microphone and speaker audio. Enable diagnostics only while
troubleshooting:

```bash
export UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

## Configuration and documentation

| Topic | Documentation |
|---|---|
| Environment variables | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architecture and invariants | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repository tools | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT use cases | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Communication tools | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Auto-pilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code extension | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Developer guide | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Tool flow | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

## Development

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,test]"
```

Run the pre-PR checks:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

For the full development workflow, see [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

## Project principles

- **Local-first** — the runtime belongs to you.
- **Provider-neutral** — models are replaceable infrastructure.
- **Composable** — tools, skills, plugins, and MCP servers are first-class extensions.
- **Safe by default** — sensitive operations remain visible and controllable.
- **Open to contribution** — code, tools, skills, translations, and documentation are welcome.

## Contributing

Bug reports, feature ideas, documentation improvements, translations, tools, skills, and pull requests are welcome.
Please open an issue or discussion before large changes. Read the [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
and run the checks above before submitting a pull request.

## License

Licensed under the [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
