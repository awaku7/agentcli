<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag——通用人工智能网关</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — 你的环境，你的自由。
</p>

<p align="center">
  文件操作 / 网络搜索 / 图像生成和分析 / PDF 和 Excel 提取 / IoT 控制 / MCP 集成<br>
  24 providers / 3 UI / 并行工具执行 / Agent Skills 市场
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## 为什么是uag？

\*\*摆脱供应商锁定。\*\*大多数人工智能助手会将您与特定的提供商或云服务联系起来。 uag 是不同的。

- **在您的计算机上本地运行**。您的数据保留在您身边（您进行的 API 调用除外）。
- **提供商自由**：OpenAI、Claude、Gemini、DeepSeek、Ollama、Azure、Bedrock、HuggingFace...超过 24 个提供商，均可通过单一界面访问。通过重新配置环境变量在它们之间进行交换——无需重新安装，无需迁移。
- **222 个工具**：文件 I/O、网络搜索、图像生成、Gmail、BLE 设备扫描、MCP 服务器集成 — **130 个工具是并行安全的**（最多 8 个通过线程池并发执行，可通过“UAGENT_PARALLEL_WORKERS”进行配置）。当 LLM 一次触发多个工具调用时，uag 会自动并行化它们。
- **3 UI + A2A**：CLI、GUI、Web 和代理到代理协议。相同的引擎，任何接口。
- **代理技能**：从市场安装社区构建的技能。无限延伸uag。

uag 是**您的人工智能助手，按照您的意愿**。不依赖于提供商、不依赖于接口、不依赖于平台。

## 快速入门

```bash
pip install uag
uag
```

首次启动时，设置向导将引导您完成提供程序配置。
有关所有环境变量，请参阅 [docs/ENVIRONMENT.md](ENVIRONMENT.md)。

＃＃ 特征

### 🧠 多提供商架构

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

所有提供商共享相同的工具集和界面。通过设置“UAGENT_PROVIDER”进行切换——无需更改代码，无需单独安装。

### ⚡ 并行工具执行

当 LLM 同时请求多个工具时，uag **自动并行化**它们。
130 个工具被标记为“x_parallel_safe”，并通过“ThreadPoolExecutor”并发执行（默认为 8 个线程；设置“UAGENT_PARALLEL_WORKERS”进行更改）。

**示例**：询问“检查北欧首都的天气” → LLM 触发 `search_web` × 5 个国家 → 所有 5 个搜索并行运行 → 一批收集结果。

只读工具（文件搜索、哈希计算、目录列表、翻译、数据库查询等）被积极并行化。

### 🧩 插件系统（兼容 Claude Code）

uagent 实现了**兼容 Claude Code 的插件系统**。插件将技能、代理、MCP 服务器、钩子等捆绑到带有 `.claude-plugin/plugin.json` 清单的独立目录中。

**支持的组件**：技能、子代理、MCP 服务器、钩子（12 个生命周期事件）、斜杠命令、输出样式、userConfig、依赖项、通道、市场

**CLI commands**:

```
:plugin list                         # 列出已安装的插件
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # 从市场安装
:plugin remove <name>                # 卸载
:plugin enable/disable <name>        # 切换
:plugin marketplace add/remove/list  # 管理市场
:plugin init <name>                  # 创建新插件的结构
```

详细文档请参阅 [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md)。

### 🔄 会话连续性

- **在会话中切换提供商**：`UAGENT_PROVIDER` — 对话历史记录会保留。
- **重新加载过去的会话**：`:load <index>` — 从上次中断的地方继续。

### 🛠 222 个工具

- **云 API**: `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation.

|类别 |工具|
|---|---|
| **文件操作** |读/写/创建/删除/搜索/grep/hash/zip，parse_eml（.eml 文件）|
| **网络** | fetch_url、search_web、屏幕截图、browser_playwright |
| **媒体** |生成图像、分析图像、img2img、音频语音、音频转录 |
| **文件** | PDF/PPTX/DOCX/RTF/ODT提取、Excel结构化提取|
| **预测** | 使用9种模型（AutoARIMA、Prophet、LightGBM、CatBoost、TimesFM等）进行时间序列预测，自动模型选择，生成图表，i18n |
| **通讯** | gmail_send、gmail_read、bluesky、discord_channel、teams_webhook , **pybitchat** (BLE Mesh) — 请参阅 [COMMUNICATION.md](COMMUNICATION.md) 和 [BITCHAT.md](BITCHAT.md)|
| **物联网** | SwitchBot（云 + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **开发工具** | git_ops、python_compile、lint_format、run_tests、db_query、**29 个源代码导航器（idx 系列）** |
| **MCP** |连接到外部 MCP 服务器、列出工具、执行 — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** |代理间通信（与其他 uag 实例或 A2A 兼容服务器）|
| **系统** | 环境变量、系统规格、时间、日期计算, uuid_gen, slugify, quantities ||
| **来源导航** | **29 个 idx 工具**，适用于 Python、PHP、TypeScript、Java、C#、Dart、C/C++、Rust、Go、Swift、Kotlin、COBOL, VBA, LotusScript, Makefile — 无需读取整个文件即可获取函数/类索引或特定定义 |

#### 存储库审查和覆盖
- `git_review`：总结 Git 更改、有风险的文件、测试候选项和秘密结果，而不暴露秘密值。
- `security_scan`：扫描存储库文件以查找可能的秘密和有风险的配置文件。
- `coverage_report`：运行并规范化 Python、TypeScript/JavaScript、Rust、Go、Java/Kotlin、.NET、C/C++、Ruby、PHP、 Swift 和 Dart/Flutter。
- 请求执行时可以自动安装缺少的覆盖依赖项； `dry_run` 从不安装软件包。

有关参数、输出和安全详细信息，请参阅[存储库分析工具](REPOSITORY_TOOLS.md)。

### 🖥 4 个接口 + VS 代码扩展

|模式|命令 |目的|
|---|---|---|
| **命令行** | `uag` |快捷的终端操作 |
| **图形用户界面** | `uagg` |通过 tkinter 的桌面 UI |
| **网络** | `uagw` |基于浏览器的访问 |
| **A2A 服务器** | `瓦加` |用于多代理通信的Agent2Agent协议|
| **VS 代码** | — | [扩展](VSCODE.md) 带有聊天面板、解释、重构、修复错误和工具树视图 |

有关 VS Code 扩展的详细信息 - 安装、命令、键绑定和配置，请参阅 [VSCODE.md](VSCODE.md)。

### 🏠 物联网设备控制

- **事项**：控制器/网桥/设备拓扑的只读检查

请参阅 [IOT_USECASE.md](IOT_USECASE.md)

### 🏠 IoT 设备控制

- **BACnet**：读/写 BACnet/IP 设备（HVAC、照明、电表）。用于推送通知的 COV 订阅
- **Modbus TCP**：读/写保持/输入寄存器和线圈。 Polling-based change monitoring
- **OPC UA**: 浏览地址空间、读写变量并订阅数据变化
- **SwitchBot**: Cloud batch control & BLE scan/control. Polling-based subscription
- **ECHONET Lite**: 发现、控制家用电器（空调、灯具、热水器等），并订阅其 INF 通知
- **Matter**: 读写控制 + 属性订阅，用于监控状态变化
- **UPnP**: Device discovery & IGD port forwarding

参阅 [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 代理技能市场

`:skills mp_search` 浏览 [SkillsMP](https://skillsmp.com) 和 [ClawHub](https://clawhub.ai) 以获取社区技能。
即时安装和扩展 uag 的功能。

### 🤖 自动驾驶 (`:auto`)

uag 可以**在多轮法学硕士课程中自主追求一个目标**。非常适合需要迭代细化的复杂、多步骤任务。

- **工作原理**：每一轮都有一个主要查询（步骤 A），然后是审阅者判断（步骤 B），决定“完成还是继续？”
- **相同​​的提供程序，相同的 API**：审阅者判断使用相同的代码路径作为主要查询 - 包括响应 API 支持。
- **单独评判LLM**（可选）：设置“UAGENT_AP_PROVIDER”为审阅者使用不同的提供者/模型（例如，使用更便宜的模型进行评判）。
- **随时退出**：按“x”键立即停止，即使是在响应中。或者让评审者决定何时达到目标。
- **可配置**：`--max-rounds N` 来控制预算。

有关完整文档，请参阅 [README_AUTO.md](README_AUTO.md)。

### 🧩 批量状态管理器

uag 可以跟踪长时间运行的多文件任务的进度。当 LLM 处理数十个文件时，“batch_state”会将待处理、已完成和失败的文件列表保留到磁盘。如果会话结束或一轮超时，下一次运行将从停止处继续 - 不会丢失任何内容。

### 🛡 人机交互

` human_ask` 允许 LLM 在执行破坏性操作（文件删除、覆盖、shell 命令）之前暂停并要求您确认。您保持掌控。

### 🛑 中断（c 键/停止按钮）

随时停止 LLM 响应生成，并将停止命令注入回 LLM。

|接口|如何打断|
|---|---|
| **命令行** |在 LLM 流式传输期间按“c”键 — 当前响应停止，并且“停止”作为用户消息发送，以便 LLM 做出相应响应 |
| **网页用户界面** |单击红色 **■ 停止** 按钮（LLM 处理期间自动出现）|
| **桌面图形用户界面** |单击红色 \*\*\*\*\*\*\*\* 按钮（LLM 处理期间自动出现）|

中断充当“提示注入”：它不仅仅是中止，而是将“停止”作为用户消息反馈给 LLM，使其能够优雅地结束或确认中断。

按“x”键退出自动驾驶模式（请参阅 [README_AUTO.md](README_AUTO.md)）。

### 🕵️ 浏览器自动化和 Web 检查器

两个基于 Playwright 的互补工具：

- **browser_playwright**：自动化真实的浏览器会话 - 导航、单击、填写表单、提取数据、处理多页面流。无头或有头均可工作。
- **playwright_inspector**：记录浏览器转换，捕获每一步的 DOM 快照和屏幕截图。对于调试 Web 交互或审核页面随时间的变化很有用。

### 🔄 动态工具加载

`tool_catalog` 和 `tool_load` 可让您在运行时发现并启用工具。
无需在启动时加载所有内容 - 仅在需要时激活您需要的内容。

### 🦀 Rust Native Tools

为了提高性能，`uuid_gen` 和 `slugify` 使用 Rust（通过 PyO3）实现。

### 🌐 国际化 / 本土化

日本语 / English / 简体中文 / 繁体中文 / 한국어 / Español / Français / Русский / 等。
设置`UAGENT_LANG`进行切换。请参阅 [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md) 添加新的区域设置。

本自述文件的翻译可在 [docs/README.translations.md](README.translations.md) 中找到。

### 🔒 加密环境变量

将 API 密钥和机密存储在“.env.sec”中——一个加密的“.env”文件。
使用“uag_envsec”进行管理。

## 配置和详细信息

- **环境变量**：[docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **设置向导**：`python -m uagent.setup_cli`
- **加密的 env**: `uag_envsec` — 将 `.env` 加密为 `.env.sec`
- **响应 API**：为响应 API 模式设置“UAGENT_RESPONSES=1”（OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI）。自动启用 Sakana AI (Fugu)。
- **开发人员文档**：[DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **LLM小技巧**：[SLM_TIPS.md](SLM_TIPS.md)

## 项目理念

uag 渴望成为 **您的人工智能，在您的机器上，按照您的条件。**

- 无 SaaS 依赖性 — 在本地运行
- 没有供应商锁定——随时切换
- 无 UI 锁定 — CLI / GUI / Web / A2A
- 无功能锁定——通过工具和技能进行扩展

免费的人工智能代理体验，不受供应商锁定。

### ✨ 创建您自己的工具

[zh_CN.md](TOOL_CREATOR_GUIDE.zh_CN.md)
分步指南请参阅此处。

## 贡献

欢迎贡献！我们感谢错误报告、功能建议、文档改进、翻译和拉取请求。

- **Issues**: 针对错误或功能请求打开 GitHub 问题。
- **拉取请求**：Fork 仓库，完成修改并提交 PR。有关开发环境设置和指南，请参阅 [DEVELOP.md](../src/uagent/docs/DEVELOP.md)。

Realtime 语音和 AEC3

## Realtime语音模式支持全双工麦克风和扬声器输入/输出。如果缺少 AEC3 后端，uag 会自动安装 pywebrtc-audio。

**实时提供程序**：OpenAI Realtime、Azure OpenAI GPT Realtime、Google Gemini Live、xAI Grok Voice 和 Amazon Bedrock Nova Sonic。仅当选择 Bedrock 时，才会自动安装 Bedrock 双向流 SDK。

```bat
python scheck.py realtime
```

AEC3 使用实际的麦克风信号（近）和实际发送到扬声器的音频（远）。仅在调查音频问题时启用诊断。

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime 支持安全限制的 Function Calling 集成。当前适配器自动公开只读 get_current_time 函数。破坏性工具和设备控制需要明确的许可名单和确认流程。 Grok 实时使用单独的适配器，并且不使用此 OpenAI 特定的 Function Calling 路径。
