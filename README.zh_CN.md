<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (本地 AI 智能体)

uag 是一款能够在您的本地 PC 上执行 **命令**、操作 **文件** 并读取 **各种数据格式**（PDF/PPTX/Excel 等）的交互式智能体。它提供三种界面：CLI、GUI 和 Web。


GitHub: https://github.com/awaku7/agentcli

## 安装

您可以通过 pip 安装 `uag`：

```bash
pip install uag
```

安装后，首次运行 `uag` 将自动启动 **交互式设置向导** 以配置您的环境变量。有关配置和加密的详细信息，请参阅 **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**。

## 主要功能

- **实用工具集**：配备用于文件操作、网络搜索、数据提取（PDF/PPTX/Excel）、图像生成和分析的工具，均可在本地环境中执行。
- **多供应商支持**：支持 OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA。
- **灵活的界面**：
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (模型上下文协议)**：支持连接到外部 MCP 工具服务器。
- **会话持续性**：即使切换供应商或模型，也能保持对话上下文。
- **Web 检查器**：使用 `playwright_inspector` 自动保存浏览器跳转、DOM 和截图。
- **内置文档**：使用 `uag docs` 命令即时访问详细的内部文档。

## 使用方法

### 启动与退出
从终端运行 `uag` 即可开始。输入 `:exit` 退出。

### A2A (智能体间通信) 服务器
您可以启动一个独立于现有界面的 A2A 兼容 HTTP 服务器。
```bash
uaga
# 或 python -m uagent.a2a.server
```

### 实用技巧 (持续与控制)
- `:tools`：显示已加载工具的列表。
- `:logs [n]`：显示会话日志（`n` 用于指定条目数）。
- `:load <index>`：加载过去的会话以恢复对话。
- `:skills`：选择并加载智能体技能（额外的角色或指令）。
- `:shrink [n]`：整理历史记录，仅保留最后 `n` 条消息以节省 Token。

## 配置与详情

### 环境变量与设置
有关详细设置（API 密钥、显示语言 `UAGENT_LANG`、历史压缩设置等），请参阅 **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**。
- **设置**：通过 `python -m uagent.setup_cli` 进行交互式配置。
- **加密**：使用 `uag_envsec` 工具安全地加密您的 `.env` 文件。
- **更新**：使用 `uag_envsec add --file .env.sec --key NAME --value VALUE`，可在已有的加密文件中添加或更新变量。

### 开发者与国际化
- **开发者文档**：[`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **添加语言区域**：[`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **其他语言的 README**：[English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt.md)
