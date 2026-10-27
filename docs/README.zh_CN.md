<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>通用 AI 网关</strong><br>
  一个本地代理。任意模型。任意工具。你的环境，你的规则。
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">讨论</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">翻译</a>
</p>

______________________________________________________________________

**为什么选择 uag？**

uag 是一个本地优先的 AI 代理，可将你偏好的模型连接到你实际使用的工具。
它为文件、浏览器、代码库、通信、云 API、IoT 设备、MCP 服务器和多代理工作流提供单一且可扩展的运行时。

- **提供商自由** — OpenAI、Anthropic、Gemini、Azure、Bedrock、Ollama、llama.cpp、Grok、DeepSeek 等。
- **本地优先执行** — 代理运行时和工具执行留在你的机器上；只有你选择的 API 调用会离开本机。
- **统一工具层** — 同一套工具可从 CLI、桌面 GUI、Web UI、VS Code 和 A2A 使用。
- **为并行而设计** — 独立的只读操作可以并发运行。
- **可扩展** — 无需更改核心即可添加工具、插件、Agent Skills、MCP 服务器和 Rust 支持的工具。
- **安全感知** — 破坏性操作、凭据、设备控制和网络写入支持明确确认及策略控制。

> **简而言之：** uag 是你的 AI 模型与真实环境之间的控制平面。

> **🧠 基于上下文的工具结果** — 在可能的情况下，大型工具结果不会被纳入当前模型上下文。 uag 将其存储为“工件”，并向模型传递一个带有稳定 Artifact 引用且范围受限的预览。当工具生成大量结果时，这可以大幅减少后续轮次所需的输入令牌数量。
> [详细的上下文压缩指南](CONTEXT_COMPRESSION.zh_CN.md)

## 快速开始

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

首次启动时会打开设置向导，帮助配置提供商，并将所选设置存储在本地环境中。

对于常用功能组：

```bash
python -m pip install "uag[core,providers,tools]"
```

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## 使用界面

| 界面 | 命令 | 适用场景 |
|---|---|---|
| **CLI** | `uag` | 快速、以键盘为主的工作 |
| **桌面 GUI** | `uagg` | 原生桌面体验 |
| **Web UI** | `uagw` | 基于浏览器的访问 |
| **A2A server** | `uaga` | 代理间通信 |
| **VS Code** | Extension | 在编辑器中解释、重构、修复和浏览工具 |

所有界面共享相同的提供商配置、工具注册表、安全规则和会话数据。

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## 你可以构建什么

提供商适配器覆盖托管和本地运行时，包括：

- 读取、创建、编辑、搜索、计算哈希、归档和检查文件
- 审查 Git 更改、扫描机密、运行测试、执行代码检查、编译并测量覆盖率
- 浏览大型 Python、TypeScript、JavaScript、Go、Rust、C/C++、Java、C#、COBOL、VBA 及其他代码库
- 使用 Playwright 自动化浏览器，包括多页面工作流和下载

- **MCP** — 连接外部工具服务器，包括支持 OAuth 的服务
- **A2A** — 与其他代理及兼容服务器协作
- **Cloud** — 访问 AWS、Google Cloud 和 Azure API，写入时需要确认
- **Communication** — Gmail、Bluesky、Discord、Microsoft Teams 和 pybitchat
- **IoT** — SwitchBot、ECHONET Lite、Matter、BACnet、Modbus TCP、OPC UA 和 UPnP
- **Media** — 图像生成/编辑、音频转录/语音、相机捕获和 QR 码
- **Documents** — PDF、PowerPoint、Word、Excel、CSV、JSON、YAML、SQL 和日志分析

- **SwitchBot** — 云端和 BLE 发现、状态、控制、批处理及订阅
- **ECHONET Lite** — 发现并控制日本家用电器，包括 INF 通知
- **Matter** — 端点、集群、属性、状态历史、订阅和控制
- **BACnet / Modbus TCP / OPC UA** — 工业和楼宇自动化的读取、写入、浏览和监控
- **UPnP** — 设备发现、WAN 状态和路由器端口映射管理

### uag 的定位

一侧是人员和界面，另一侧是模型、工具和现实世界系统，uag 位于两者之间。
它协调对话、选择能力、应用安全规则，并使工作流能够恢复。

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### 插件、Agent Skills 和 marketplaces

无需分叉核心代码，即可将 uag 变成专用代理：

- 从目录、ZIP、Git 仓库、HTTP 源或 marketplace 安装 **兼容 Claude Code 的插件**
- 打包 skills、sub-agents、MCP 服务器、hooks、slash commands、输出样式、依赖项和 channels
- 从 [SkillsMP](https://skillsmp.com) 和 [ClawHub](https://clawhub.ai) 浏览社区能力
- 通过 `UAGENT_EXTERNAL_TOOLS_DIR` 在本地添加组织私有 skills 和工具

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

参见 [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md)。

- **200+ 个工具**，覆盖文件、Web、媒体、文档、代码、云、通信和 IoT
- **动态发现和加载** — 使用 `tool_catalog` 查找能力，并在需要时通过 `tool_load` 启用
- **代码智能** — `code_map`、特定语言的 `idx` 导航器、Git 审查、测试执行、代码检查、编译和覆盖率
- **兼容 Claude Code 的插件**，支持 skills、agents、MCP 服务器、hooks、commands 和 marketplaces
- **Agent Skills**，来自 SkillsMP 和 ClawHub
- **自定义 Python 工具**，使用 `TOOL_SPEC` 和 `run_tool()`
- **Rust 支持的工具**，用于轻量级原生扩展

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## 为真实工作流而构建

### 🧠 基于上下文的工具结果

在可能的情况下，大型工具结果不会被纳入当前模型上下文。 uag 将其存储为“工件”，并向模型传递一个带有稳定 Artifact 引用且范围受限的预览。当工具生成大量结果时，这可以大幅减少后续轮次所需的输入令牌数量。

使用 `:load <index>` 恢复之前的对话。工具结果可以缓存，也可以更换提供商而无需重新构建应用程序。

[Context compression](CONTEXT_COMPRESSION.zh_CN.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### 自动驾驶

使用 `:auto` 进行多轮工作，并可选用审查模型。使用 `--max-rounds N` 设置轮次上限。
按 **F12** 停止自动驾驶，或按 **F12** 停止当前响应。

在安全的情况下，独立的只读操作会并发运行。Web 搜索、文件检查、仓库分析及类似工作负载可以通过可配置的工作池（`UAGENT_PARALLEL_WORKERS`）并行完成。写入操作仍会串行执行，或需要确认。

会话连续性、工具结果缓存、批处理状态、重启恢复、DAG 调度和多代理编排，让复杂工作可以恢复，而不是只能一次性完成。

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 私密、多语言且具备策略意识

`human_ask` 会在敏感操作前暂停。文件删除、覆盖、Shell 命令、设备控制、凭据操作和网络写入都可以由确认及策略规则管理。

使用凭据存储，而不要在提示中放置长期有效的机密：

Web UI 包含使用 Authorization Code + PKCE 的 OIDC 登录、已验证的 ID 令牌、服务器端会话以及项目/房间访问控制。配置后，已验证的 Microsoft Entra ID 组声明可用于目录支持的访问策略。Windows Active Directory、OAuth 和 trusted-proxy 部署可通过明确的已验证身份适配器集成；Windows AD 需要特定部署的 Kerberos/Negotiate 验证器，且默认未启用。

uag 提供可选启用、与提供商无关的 OpenTelemetry 跟踪和指标，覆盖 Agent、LLM、工具、Context、Memory 和检索操作。可观察性默认关闭。

本地优先并不意味着默认完全离线，也不意味着所有工具执行均受到隔离。外部模型及关联服务的调用取决于具体配置。

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 多语言翻译

- `translate_text` 支持通过 `provider=auto`、`provider=deepl` 或 `provider=google` 调用 `Google Translate` 以及官方 DeepL Python 客户端。
- 工具定义支持 37 种语言环境以及英语（共计 38 种），同时保留了占位符和技术标识符。

可通过 OpenAI Realtime、Azure OpenAI、xAI Grok Voice、Gemini Live 和 Bedrock Nova Sonic 使用全双工语音，并支持可选的 AEC3 回声消除以及受安全限制的实时函数调用。

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## 文档

| 主题 | 文档 |
|---|---|
| 环境变量 | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| 架构和不变量 | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| 仓库工具 | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT 用例 | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| 通信工具 | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| 自动驾驶 | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code 扩展 | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| 开发者指南 | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| 工具流程 | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## 开发与贡献

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

运行 PR 前检查：

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

完整的开发工作流请参见 [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)。

欢迎提交错误报告、功能想法、文档改进、翻译、工具、skills 和拉取请求。
进行较大改动前，请先创建 issue 或 discussion。阅读 [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)，并在提交拉取请求前运行上述检查。

## 许可证

基于 [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE) 授权。
