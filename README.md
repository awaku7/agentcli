<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>

<h1 align="center">UAG</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Your AI models. Your tools. Your environment.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#interfaces">Interfaces</a> ·
  <a href="#what-you-can-build">Capabilities</a> ·
  <a href="#documentation">Docs</a> ·
  <a href="docs/README.ja.md">日本語</a> ·
  <a href="docs/README.translations.md">Other languages</a>
</p>

---

**UAG is an open-source, local-first AI agent runtime** that connects the language model
you choose to the tools and systems you use. Work with code, files, browsers,
services, and devices from a consistent interface—without tying your workflows
to a single model provider.

| **Bring your model** | **Connect real tools** | **Stay in control** |
| :--- | :--- | :--- |
| Hosted and local models, including OpenAI, Claude, Gemini, Grok, Bedrock, and Ollama. | Files, code, web, MCP, Agent Skills, plugins, cloud services, and IoT. | Local execution, human confirmation, credential storage, and configurable policies. |

> UAG is the agent execution layer, **not** a model provider. External model
> requests and connected-service calls depend on your configuration; local-first
> does not mean entirely offline or isolated by default.

## Quick start

Requires **Python 3.11+**. Install from [PyPI](https://pypi.org/project/uag/)
and launch the interactive CLI:

~~~bash
python -m pip install --upgrade uag
uag
~~~

On first launch, the setup wizard helps you choose a provider and configure its
credentials. You can also configure providers through environment variables or
the credential store.

For a larger set of provider and tool dependencies up front:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Then try asking:

~~~text
> What changed in this Git repository? Summarize the risks.
> Find the latest documentation for this library and explain the migration steps.
> Inspect these files and produce a concise report.
> :help
~~~

**New to UAG?** See the [Windows installation walkthrough](docs/QUICKSTART.md)
(including Git and virtual-environment prerequisites) or the
[configuration reference](docs/ENVIRONMENT.md). Platform-specific integrations
are optional.

## Interfaces

Use the same agent runtime and tool registry from multiple entry points.

| Interface | Start with | Ideal for |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminal-first work and automation |
| **Desktop** | `uagg` | Native desktop conversations |
| **Web** | `uagw` | Browser-based conversations and rooms |
| **A2A** | `uaga` | Agent-to-agent integration |
| **VS Code** | [Extension guide](docs/VSCODE.md) | Working alongside code |

The GUI and Web UI require their relevant optional dependencies. See
[platform setup](docs/USAGE.md) and [environment configuration](docs/ENVIRONMENT.md).

## What you can build

| Capability | What UAG provides |
| :--- | :--- |
| **Model-agnostic workflows** | Switch among hosted and local providers using `UAGENT_PROVIDER` without rewriting tools. |
| **Code and file operations** | Repository navigation, Git inspection, linting, tests, file operations, and browser automation. |
| **Extensible tooling** | A catalog of 200+ tools, dynamic `tool_catalog` / `tool_load` discovery, custom Python and Rust-backed tools. |
| **Connected agents** | MCP servers, A2A, Claude Code-compatible plugins, Agent Skills, and sub-agents. |
| **Long-running work** | Auto-pilot, parallel independent read operations, scheduled tasks, restart recovery, and persisted sessions. |
| **Beyond the terminal** | Cloud and communication integrations, documents, media, realtime voice, and supported IoT protocols. |

### One runtime, many integrations

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**Provider examples:** OpenAI, Anthropic, Gemini, Vertex AI, Azure OpenAI,
Amazon Bedrock, Grok, DeepSeek, OpenRouter, Ollama, llama.cpp, and LM Studio.
For provider-specific settings, see [Environment variables](docs/ENVIRONMENT.md).

### Customize it with skills and plugins

Extend UAG without modifying the core. Install Agent Skills from SkillsMP or
ClawHub, connect MCP servers, or load Claude Code-compatible plugins with tools,
skills, agents, and hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Custom tools can expose `TOOL_SPEC` and `run_tool()`; Rust-backed tools are also
supported. Start with the [Tool Creator Guide](TOOL_CREATOR_GUIDE.md),
[Plugin Development Guide](src/uagent/docs/DEVELOP_PLUGIN.md), and
[MCP OAuth / Proxy Guide](docs/MCP_OAUTH_PROXY_GUIDE.md).

## Built for real workflows

### Context and memory

Large tool results can be saved as **Artifacts** instead of crowding the active
model context. An agent can retrieve the relevant portion later using
`artifact_read`. Sessions are stored in SQLite by default, with history search
and explicit memory review workflows.

- [Context compression](docs/CONTEXT_COMPRESSION.md)
- [Memory](docs/MEMORY.md)
- [Session portability](docs/SESSION_PORTABILITY.md)

### Automation and collaboration

UAG supports parallel independent read operations, multi-agent coordination,
session recovery, and Auto-pilot for multi-round work. Use `:auto` to start
Auto-pilot; press **F12** to interrupt the current response and request that
Auto-pilot stop.

- [Auto-pilot](docs/README_AUTO.md)
- [Timers and scheduled tasks](docs/SET_TIMER.md)
- [Multi-agent runtime](docs/MULTI_AGENT_RUNTIME.md)

### Security and observability

Sensitive operations can require `human_ask` confirmation. Credentials can be
stored in the operating system's credential manager or an encrypted file
backend. The Web UI supports configured OIDC sign-in and access controls.
OpenTelemetry tracing and metrics are **opt-in**.

- [Enterprise policies](docs/ENTERPRISE_POLICY.md)
- [Web identity and rooms](docs/WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](docs/UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability guide](src/uagent/docs/DEVELOP_OBSERVABILITY.md)

These are configurable controls, not a blanket guarantee that arbitrary tool
execution is sandboxed. See the deployment and policy guides before exposing
UAG to untrusted users or networks.

### Languages, devices, and voice

UAG includes resources for **38 locales** (English plus 37 translations),
optional full-duplex voice integrations, and tools for systems such as SwitchBot,
Matter, ECHONET Lite, BACnet, Modbus TCP, and OPC UA.

- [Translations](docs/README.translations.md)
- [IoT use cases](docs/IOT_USECASE.md)
- [Communication tools](docs/COMMUNICATION.md)

## Documentation

| Start here | Go deeper |
| :--- | :--- |
| [Quickstart (Windows)](docs/QUICKSTART.md) | [Architecture](docs/ARCHITECTURE.md) |
| [CLI usage](docs/USAGE.md) | [Context management](docs/UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](docs/ENVIRONMENT.md) | [Enterprise policy](docs/ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](docs/MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](docs/COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](docs/VSCODE.md) | [Developer guide](src/uagent/docs/DEVELOP.md) |

Browse the [documentation directory](docs/) or read the
[Japanese README](docs/README.ja.md) and
[other translations](docs/README.translations.md).

## Development and contributing

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Before a **Python code** pull request, run the relevant tests and project checks:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Read [AGENTS.md](AGENTS.md) and the
[developer guide](src/uagent/docs/DEVELOP.md) for detailed contribution
guidelines. Issues, documentation improvements, tools, translations,
and focused pull requests are welcome.

## License

UAG is released under the [Apache License 2.0](LICENSE).
