<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag 徽标" width="720">
</p>

<h1 align="center">uag — 通用人工智能网关</h1>

<p align="center">
  <b>U</b>universal <b>A</b>I <b>G</b>ateway — 您的环境，您的自由。
</p>

<p align="center">
  文件操作/网络搜索/图像生成和分析/PDF和Excel提取/物联网控制/MCP集成<br>
  超过 15 个提供商/3 个 UI/并行工具执行/代理技能市场
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">用您的语言阅读本文</a>
</p>

---

## 为什么是uag？

**摆脱供应商锁定。**大多数人工智能助手会将您与特定的提供商或云服务联系起来。 uag 是不同的。

- **在您的计算机上本地运行**。您的数据保留在您身边（您进行的 API 调用除外）。
- **提供商自由**：OpenAI、Claude、Gemini、DeepSeek、Ollama、Azure、Bedrock...超过 15 个提供商，均可通过单一界面访问。通过重新配置环境变量在它们之间进行交换——无需重新安装，无需迁移。
- **111 种工具**：文件 I/O、网络搜索、图像生成、BLE 设备扫描、MCP 服务器集成 — 并且 **其中 55 种工具并行运行**。当 LLM 一次触发多个工具调用时，uag 会通过线程池自动执行它们。
- **3 UI + A2A**：CLI、GUI、Web 和代理到代理协议。相同的引擎，任何接口。
- **物联网就绪**：SwitchBot、ECHONET Lite、Matter、UPnP — 通过人工智能控制您的家庭设备。
- **代理技能**：从市场安装社区构建的技能。无限延伸uag。

uag 是**您的人工智能助手，按照您的意愿**。不依赖于提供商、不依赖于接口、不依赖于平台。

## 快速入门

```bash
pip install uag
uag
````

首次启动时，设置向导将引导您完成提供程序配置。
有关所有环境变量，请参阅 [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)。

## 特点

### 🧠 多提供商架构

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / 阿里云 (Qwen) / KIMI (Moonshot AI) / 小米 MiMo / LM Studio / MiniMax

所有提供商共享相同的工具集和界面。通过设置“UAGENT_PROVIDER”进行切换——无需更改代码，无需单独安装。

### ⚡ 并行工具执行

当 LLM 同时请求多个工具时，uag **自动并行化**它们。
55 个工具被标记为“x_parallel_safe”，并通过 4 线程“ThreadPoolExecutor”并发执行。

**示例**：询问“检查北欧首都的天气” → LLM 触发 `search_web` × 5 个国家 → 所有 5 个搜索并行运行 → 一批收集结果。

只读工具（文件搜索、哈希计算、目录列表、翻译、数据库查询等）被积极并行化。

### 🔄 会话连续性

- **使用“UAGENT_PROVIDER”在会话中切换提供商** — 保留对话历史记录。
- **使用 `:load <index>` 重新加载过去的会话** — 从上次中断的地方继续。
- **工具结果缓存**避免重复调用同一工具时冗余的重新执行。

### 🛠 111 个工具

|类别 |工具|
|---|---|
| **文件操作** |读/写/创建/删除/搜索/grep/散列/zip |
| **网络** | fetch_url、search_web、屏幕截图、browser_playwright |
| **媒体** |生成图像、分析图像、img2img、音频语音、音频转录 |
| **文件** | PDF/PPTX/DOCX/RTF/ODT提取、Excel结构化提取 |
| **物联网** | SwitchBot（云 + BLE）、ECHONET Lite、Matter、UPnP |
| **开发工具** | git_ops、python_compile、lint_format、run_tests、db_query |
| **MCP** |连接到外部 MCP 服务器、列出工具、执行 |
| **A2A** |代理间通信（与其他 uag 实例或 A2A 兼容服务器）|
| **系统** |环境变量、系统规格、时间、日期计算 |

### 🖥 3 个接口 + A2A

|模式|命令|目的|
|---|---|---|
| **命令行** | `uag` |快捷的终端操作 |
| **图形用户界面** | `uagg` |通过 tkinter 的桌面 UI |
| **网络** | `uagw` |基于浏览器的访问 |
| **A2A 服务器** | `uaga` |用于多代理通信的Agent2Agent协议|

### 🏠 物联网设备控制

- **SwitchBot**：云批量控制和BLE扫描/控制
- **ECHONET Lite**：发现并控制本地网络上的家用电器（空调、灯、热水器等）
- **事项**：控制器/网桥/设备拓扑的只读检查
- **UPnP**：设备发现和 IGD 端口转发

请参阅 [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 代理技能市场

`:skills mp_search` 浏览 [SkillsMP](https://skillsmp.com) 和 [ClawHub](https://clawhub.ai) 以获取社区技能。
即时安装和扩展 uag 的功能。

### 🧩 批量状态管理器

uag 可以跟踪长时间运行的多文件任务的进度。当 LLM 处理数十个文件时，“batch_state”会将待处理、已完成和失败的文件列表保留到磁盘。如果会话结束或一轮超时，下一次运行将从停止处继续 - 不会丢失任何内容。

### 🛡 人机交互

`human_ask` 允许 LLM 在执行破坏性操作（文件删除、覆盖、shell 命令）之前暂停并要求您确认。您保持掌控。

### 🕵️ 浏览器自动化和 Web 检查器

两个基于 Playwright 的互补工具：

- **browser_playwright**：自动化真实的浏览器会话 - 导航、单击、填写表单、提取数据、处理多页面流。无头或有头均可工作。
- **playwright_inspector**：记录浏览器转换，捕获每一步的 DOM 快照和屏幕截图。对于调试 Web 交互或审核页面随时间的变化很有用。

### 🔄 动态工具加载

`tool_catalog` 和 `tool_load` 可让您在运行时发现并启用工具。
无需在启动时加载所有内容 - 仅在需要时激活您需要的内容。

### 🌐 国际化 / 本土化

日本语 / English / 简体中文 / 繁体中文 / 한국어 / Español / Français / Русский / 等。
设置`UAGENT_LANG`进行切换。请参阅 [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) 添加新的区域设置。

本自述文件的翻译可在 [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md) 中找到。

### 🔒 加密环境变量

将 API 密钥和机密存储在“.env.sec”中——一个加密的“.env”文件。
使用“uag_envsec”进行管理。

## 配置和详细信息

- **环境变量**：[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **设置向导**：`python -m uagent.setup_cli`
- **加密的 env**: `uag_envsec` — 将 `.env` 加密为 `.env.sec`
- **响应 API**：为响应 API 模式设置“UAGENT_RESPONSES=1”（OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio）
- **开发人员文档**：[DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **LLM小技巧**：[SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## 项目理念

uag 渴望成为 **您的人工智能，在您的机器上，按照您的条件。**

- 无 SaaS 依赖性 — 在本地运行
- 没有供应商锁定——随时切换
- 无 UI 锁定 — CLI / GUI / Web / A2A
- 无功能锁定——通过工具和技能进行扩展

免费的人工智能代理体验，不受供应商锁定。