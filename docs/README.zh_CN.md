<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>你的 AI 模型。你的工具。你的环境。</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">其他语言</a></p>

---

**UAG 是开源的、本地优先的 AI 智能体运行时。** 它将你选择的语言模型与你实际使用的工具和系统连接起来，让代码、文件、浏览器、服务及设备都能通过一致的界面操作，而不必把工作流程绑定到某一家模型提供商。

| **自选模型** | **连接实际工具** | **保持掌控** |
| :--- | :--- | :--- |
| OpenAI、Claude、Gemini、Grok、Bedrock、Ollama 等托管及本地模型 | 文件、代码、Web、MCP、Agent Skills、插件、云服务与 IoT | 本地执行、人工确认、凭据存储及可配置的策略 |

> UAG 是**智能体执行层，而不是模型提供商**。是否向外部模型或关联服务发送请求取决于你的配置。“本地优先”并不表示默认完全离线，也不代表所有工具都运行在隔离环境中。

## 快速开始
<!-- README-SYNC:quick-start -->

需要 **Python 3.11 或更高版本**。从 [PyPI](https://pypi.org/project/uag/) 安装 UAG，然后启动交互式命令行：

~~~bash
python -m pip install --upgrade uag
uag
~~~

首次启动时，设置向导会引导你选择模型提供商并配置凭据。也可以通过环境变量或凭据存储进行设置。若希望预先安装更多模型及工具依赖，请运行：

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

接下来可以尝试以下请求：

~~~text
> 这个 Git 仓库有哪些变化？请总结风险。
> 查找这个库的最新文档，并解释迁移步骤。
> 检查这些文件并生成简明报告。
> :help
~~~

如果是第一次使用，请参阅 Windows 安装指南（包括 Git 和虚拟环境的准备步骤）及配置参考： [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## 使用界面
<!-- README-SYNC:interfaces -->

多个入口共用同一个智能体运行时和工具注册表。

| 界面 | 启动方式 | 适用场景 |
| :--- | :--- | :--- |
| **CLI** | `uag` | 终端工作和自动化 |
| **桌面** | `uagg` | 原生桌面会话 |
| **Web** | `uagw` | 浏览器中的对话和会话房间 |
| **A2A** | `uaga` | 智能体之间的集成 |
| **VS Code** | [扩展指南](VSCODE.md) | 在编码时使用智能体 |

桌面和 Web 界面需要额外的依赖项，快速入门的 `uag[core,providers,tools]` 安装并不包含它们：

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Web 服务也可能在启动时尝试自动安装 FastAPI 和 Uvicorn。事先安装可避免依赖运行时自动安装。详细说明见： [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## UAG 可以实现什么
<!-- README-SYNC:capabilities -->

| 能力 | UAG 提供的功能 |
| :--- | :--- |
| **模型无关的工作流程** | 通过 `UAGENT_PROVIDER` 切换云端或本地模型提供商，不必重写工具 |
| **代码与文件操作** | 仓库导航、Git 检查、代码检查、测试、文件操作和浏览器自动化 |
| **可扩展工具体系** | 200 多种工具；使用 `tool_catalog` / `tool_load` 动态发现和载入；支持自定义 Python、Rust 工具 |
| **智能体互联** | MCP 服务器、A2A、兼容 Claude Code 的插件、Agent Skills 和子智能体 |
| **长时间运行的任务** | 自动驾驶模式、独立只读操作并行执行、定时任务、重启恢复和持久会话 |
| **不止于终端** | 云服务、通信、文档、媒体、实时语音及受支持的 IoT 协议 |

### 一个运行时连接多种系统
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**支持的模型提供商示例**如下；各提供商的专用配置请参阅环境配置参考。

### 用技能与插件扩展
<!-- README-SYNC:extensions -->

无需修改核心代码即可扩展 UAG。你可以从 SkillsMP 或 ClawHub 安装 Agent Skills，连接 MCP 服务器，或载入包含工具、技能、智能体与 hooks 的 Claude Code 兼容插件。

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

自定义工具可以提供 `TOOL_SPEC` 和 `run_tool()`；也支持 Rust 实现的工具。请参阅以下开发指南： [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## 适用于真实工作流程
<!-- README-SYNC:workflows -->

### 上下文与记忆
<!-- README-SYNC:context-memory -->

大型工具结果可以保存为**工件（Artifacts）**，而不必占用模型的活动上下文。之后可使用 `artifact_read` 只读取相关部分。会话默认存储在 SQLite 中，并支持搜索历史记录及明确的记忆审查流程。

- [Context compression](CONTEXT_COMPRESSION.zh_CN.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### 自动化与协作
<!-- README-SYNC:automation -->

UAG 支持独立只读操作并行执行、多智能体协调、会话恢复和处理多轮工作的自动驾驶模式。通过 `:auto` 启动自动驾驶；按 **F12** 可中断当前回答并请求停止自动驾驶。

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 安全与可观测性
<!-- README-SYNC:security -->

敏感操作可要求用户通过 `human_ask` 确认。凭据可存储在操作系统的凭据管理器或加密文件中。配置后，Web 界面支持 OIDC 登录与访问控制。OpenTelemetry 跟踪和指标是**选择启用**的功能。

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

这些都是可配置的控制措施，**不能保证任意工具执行均受到沙箱隔离**。向不可信的用户或网络开放 UAG 前，请先阅读部署与安全策略指南。

### 语言、设备和语音
<!-- README-SYNC:languages -->

UAG 提供 **38 个语言地区版本**（英语和 37 种译文），可选择启用全双工实时语音，并提供 SwitchBot、Matter、ECHONET Lite、BACnet、Modbus TCP、OPC UA 等系统的工具。

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## 文档
<!-- README-SYNC:documentation -->

从以下文档开始，再深入了解各个主题：

| 入门资料 | 深入阅读 |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

也可以浏览完整文档目录及其他语言的说明： [Documentation](./) · [Other languages](README.translations.md).

## 开发与贡献
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

提交修改 **Python 代码**的拉取请求前，请运行相关测试与项目检查：

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

贡献规范和详细开发指南见下方。欢迎提交问题、文档改进、工具、翻译及聚焦的拉取请求： [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## 许可证
<!-- README-SYNC:license -->

UAG 按以下许可证发布： [Apache License 2.0](../LICENSE).
