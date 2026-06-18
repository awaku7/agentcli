<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag（本地 AI 智能体）

uag 是一款能够在本地 PC 上执行 **命令**、操作 **文件** 并读取 **多种数据格式**（PDF/PPTX/Excel 等）的交互式智能体。它提供三种界面：CLI、GUI 和 Web。

uag 的设计旨在**让您摆脱厂商绑定的应用**：使用适合您工作流的界面，切换提供商，并始终掌控您的环境。

GitHub: https://github.com/awaku7/agentcli

## 安装

您可以通过 pip 安装 `uag`：

```bash
pip install uag
```

安装后，首次运行 `uag` 将自动启动 **交互式设置向导** 来配置您的环境变量。有关配置和加密的详细信息，请参阅 **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**。

## 主要功能

- **实用工具集**：配备有用于文件操作、网络搜索、数据提取（PDF/PPTX/Excel）、图像生成与分析的工具，均可在本地环境中执行。
- **多提供商支持**：支持 OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI。
- **灵活的界面**：
  - **CLI**：`uag` / `python -m uagent`
  - **GUI**：`uagg` / `python -m uagent.gui`
  - **Web**：`uagw` / `python -m uagent.web`
- **MCP（模型上下文协议）**：支持连接到外部 MCP 工具服务器。
- **会话延续性**：即使切换提供商或模型，也能保持对话上下文。
- **Agent Skills 市场**: 使用 `:skills mp_search` 浏览和安装来自 [SkillsMP](https://skillsmp.com) 或 [ClawHub](https://clawhub.ai) 的社区 Agent Skills。
- **Web 检查器**：使用 `playwright_inspector` 自动保存浏览器跳转、DOM 和截图。
- **内置文档**：使用 `uag docs` 命令即时访问详细的内部文档。
- **IoT device support**: Control SwitchBot, ECHONET Lite, Matter, and UPnP devices. See [IOT_USECASE.md](IOT_USECASE.md).

## 使用方法

## IoT Device Support

Control smart home and IoT devices through multiple interfaces:

- **SwitchBot Cloud**: List, control, and batch-operate SwitchBot devices (TV, air conditioner, lights, etc.).
  - Infrared remote devices (on/off, brightness, temperature)
  - Air conditioner mode and fan speed control
  - Batch execution of multiple commands
- **SwitchBot BLE**: Scan and control nearby SwitchBot BLE devices.
- **ECHONET Lite**: Discover and control ECHONET Lite home appliances over the local network.
- **Matter**: Inspect Matter controller/bridge/device structure (read-only).
- **UPnP**: Discover UPnP devices and manage IGD port forwarding.

For detailed usage, see [IOT_USECASE.md](IOT_USECASE.md).

### 启动与退出

在终端中运行 `uag` 即可启动。输入 `:exit` 退出。

For all command-line options, see [USAGE.md](USAGE.md).

### A2A（智能体间通信）服务器

您可以启动一个独立于现有界面的 A2A 兼容 HTTP 服务器。

```bash
uaga
# 或 python -m uagent.a2a.server
```

### Responses API 说明

如果设置 `UAGENT_RESPONSES=1`，则受支持的提供商将使用 Responses API：OpenAI / Azure / Bedrock / OpenRouter / Ollama。
Gemini / Claude / Vertex AI 使用各自的原生 API 路径，不在 Responses API 的覆盖范围内。
对于其他提供商，uag 会回退到提供商专用路径或 chat-completions 流程。

请参阅 [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)，了解 `UAGENT_A2A_*` 设置，例如认证、主机、端口、重新加载、公开基础 URL、并发数和引擎。

### 实用命令（会话控制）

- `:tools`：显示已加载的工具列表。
- `:logs [n]`：显示会话日志（可用 `n` 指定条目数）。
- `:load <index>`：加载历史会话以恢复对话。
- `:skills`: 选择并加载 Agent Skills（使用 `:skills mp_search` 浏览 [SkillsMP](https://skillsmp.com) 或 [ClawHub](https://clawhub.ai) 市场）
- `:shrink [n]`：整理历史记录，仅保留最近 `n` 条消息以节省 Token。
- Small LLM tips: see [SLM_TIPS.md](SLM_TIPS.md).

## 配置与详情

### 环境变量与设置

有关详细设置（API 密钥、显示语言 `UAGENT_LANG`、历史压缩设置等），请参阅 **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**。

- **设置**：通过 `python -m uagent.setup_cli` 进行交互式设置。
- **加密**：使用 `uag_envsec` 工具安全地加密您的 `.env` 文件。
- **更新**：使用 `uag_envsec add --file .env.sec --key NAME --value VALUE` 可在已有的加密文件中添加或更新变量。

### 开发者与国际化

- **开发者文档**：[`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **添加语言区域**：[`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **其他语言的 README**：[`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)