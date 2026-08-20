\<palign="center">
<img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">

</p>

\<h1align="center">uag — 通用人工智能网关</h1>

\<palign="center">
<b>U</b>通用<b>A</b>I <b>G</b>网关 - 您的环境，您的自由。

</p>

\<palign="center">
文件操作/网络搜索/图像生成和分析/PDF和Excel提取/物联网控制/MCP集成<br>
24个提供商/3个UI/并行工具执行/代理技能市场

</p>

\<palign="center">
<a href="https://github.com/awaku7/agentcli">GitHub</a>
·
<a href="https://pypi.org/project/uag/">PyPI</a>
·
<a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>

</p>

______________________________________________________________________

## 为什么 uag？

**摆脱供应商锁定。** 大多数 AI 助手会将您与特定提供商或云服务联系起来。 uag 是不同的。

- **在您的计算机上本地运行**。您的数据保留在您身边（您拨打的 API 电话除外）。
- **提供者自由**：OpenAI、Claude、Gemini、DeepSeek、Ollama、Azure、Bedrock、Novita、HuggingFace...24 个提供者，均可通过单一界面访问。通过重新配置环境变量在它们之间进行交换 - 无需重新安装，无需迁移。
- **222 个工具**：文件 I/O、网络搜索、图像生成、Gmail、BLE 设备扫描、MCP 服务器集成 - **130 个静态标记为并行安全**（最多 8 个通过线程池并发执行，可通过“UAGENT_PARALLEL_WORKERS”进行配置）。当 LLM 一次触发多个工具调用时，uag 会自动并行化它们。
- **3 UI + A2A**：CLI、GUI、Web 和代理到代理协议。相同的引擎，任何接口。
- **物联网就绪**：SwitchBot、ECHONET Lite、Matter、UPnP — 通过 AI 控制您的家庭设备。
- **代理技能**：从市场安装社区构建的技能。无限扩展 uag。

uag 是**您的 AI 助手，随心所欲**。不依赖于提供商、不依赖于接口、不依赖于平台。

## 快速入门

```bash
pip install uag
uag
```

基础安装会将提供商和工具集成设为可选依赖。当选定的提供商或工具需要某个缺失的软件包时，系统会自动安装。若要预先安装主要功能，请运行:

```bash
pip install "uag[core,providers,tools,development,platform,web]"
```

若要为仓库安装完整的开发和测试环境，请运行:

```bash
pip install -r requirements.txt
```

首次启动时，设置向导会引导您完成提供商配置。
有关所有环境变量，请参阅 [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)。

## 计算机使用

计算机使用是可选的，并且支持可见的Playwright 浏览器运行时
和桌面运行时。启用后，将创建并注册两个运行时；

```bat
set UAGENT_COMPUTER_USE=1
```

使用 `desktop` 来选择操作系统桌面运行时。运行时资源在正常退出、“Ctrl-C”和进程关闭时一起关闭。设置
`UAGENT_COMPUTER_HEADLESS=1`以进行基于浏览器的 CI 或冒烟测试。
请参阅 [docs/COMPUTER_USE_IMPLMENTATION.md](docs/COMPUTER_USE_IMPLMENTATION.md)
了解集成和安全详细信息。

## 实时语音和 AEC3

实时语音模式支持 OpenAI Realtime、Azure OpenAI GPT Realtime、xAI Grok Voice API、Google Gemini Multimodal Live API 和具有全双工麦克风和扬声器 I/O 的 Amazon Bedrock Nova Sonic。所需的 `pywebrtc-audio` AEC3 后端会自动安装，并且仅当选择 Bedrock 提供程序时，才会自动安装 Bedrock 的可选双向流 SDK：

```bash
python scheck.py realtime
```

AEC3 管道接收实际的麦克风信号（`near`）和实际传递到扬声器的音频（`far`），以便助手可以在说话时收听。仅在调查音频问题时启用诊断：

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI 实时函数调用

OpenAI Realtime 支持安全限制的函数调用集成。当前实时适配器自动公开只读“get_current_time”。如果没有明确的许可名单和确认流程，破坏性工具和设备控制就不会暴露。 Grok 实时使用单独的适配器，并且不使用此 OpenAI 特定的函数调用路径。

## 功能

### 🧠 多提供商架构

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / 阿里云 (Qwen) / KIMI (Moonshot) AI)/Xiaomi MiMo/LM Studio/MiniMax/Sakana AI (Fugu)/SAKURA AI Engine/Together AI/Vercel AI Gateway
所有提供商共享相同的工具集和界面。通过设置 `UAGENT_PROVIDER` 进行切换 — 无需更改代码，无需单独安装。

#### Ollama 和 llama.cpp

Ollama 和 llama.cpp 是单独的提供程序。 Ollama 使用自己的服务和模型管理，而 `llama.cpp` 连接到 `llama-server` OpenAI 兼容端点：

```bash
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

llama.cpp 提供程序使用聊天完成兼容的路径。除非配置了兼容的代理，否则保持“UAGENT_RESPONSES=0”。

### ⚡并行工具执行

当 LLM 同时请求多个工具时，uag **自动并行化**它们。
130 个工具静态标记为“x_parallel_safe”，并通过“ThreadPoolExecutor”并发执行（默认为 8 个线程；设置`UAGENT_PARALLEL_WORKERS` 更改）。
**示例**：询问“检查北欧首都的天气”→ LLM 触发 `search_web` × 5 个国家 → 所有 5 个搜索并行运行 → 一批收集结果。
当前计数基于定义“TOOL_SPEC”的工具模块（当前为 222 个，包括 2 个 Rust 支持的工具） `src/uagent/tools_rust/`)。 `http_request` 使用方法敏感的安全性：`GET`/`HEAD`/`OPTIONS` 调用可以并行运行，而写入方法保持串行。
只读工具（文件搜索、哈希计算、目录列表、翻译、数据库查询等）被积极并行化。

### 🧩插件系统（Claude 代码兼容）

uagent 实现了 **Claude 代码兼容的插件系统**。插件通过 `.claude-plugin/plugin.json` 清单将技能、代理、MCP 服务器、挂钩等捆绑到独立目录中。
**支持的组件**：技能、子代理、MCP 服务器、挂钩（12 个生命周期事件）、斜线命令、输出样式、用户配置、依赖项、通道、市场
**CLI命令**:

```
:plugin list # 列出已安装的插件
:plugin install <source> [--scope] # 安装(dir/zip/git/http)
:plugin install <name>@<marketplace> # 从市场安装
:plugin remove <name> # 卸载
:插件启用/禁用<name> # 切换
:plugin market add/remove/list # 管理市场
:plugin init <name> # 支架新插件
```

请参阅 [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) 以获取完整文档。

### 🔄 会话连续性

- **使用 `UAGENT_PROVIDER` 在会话中切换提供者** — 保留对话历史记录。
- \*\*使用 `:load 重新加载过去的会话** <index>` — 从上次停下的地方继续。
- **工具结果缓存**可避免重复调用同一工具时重复执行。

### 🛠 229 个工具

|类别 |工具|
|---|---|
| **文件操作** |读/写/创建/删除/搜索/grep/hash/zip、file_type、parse_eml（.eml 文件）、`path_alias` |
| **网络** | fetch_url、search_web、屏幕截图、browser_playwright、`url_alias`、`public_transit_route` ([指南](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **媒体** |生成图像、分析图像、img2img、audio_speech、audio_transcribe |
| **文件** | PDF/PPTX/DOCX/RTF/ODT提取、Excel结构化提取|
| **预测** |使用 9 种模型进行时间序列预测（AutoARIMA、Prophet、LightGBM、CatBoost、TimesFM 等）、自动模型选择、绘图生成、i18n |
| **通讯** | gmail_send、gmail_read、bluesky、discord_channel、teams_webhook、**pybitchat** (BLE Mesh) — 请参阅 [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) 和 [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **物联网** | SwitchBot（云 + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **云 API** | `aws_api`、`gcp_api`、`azure_api` — 通用 AWS、Google 云和 Azure API 操作；写操作需要显式确认 |
| **开发工具** | workspace_status、git_ops、git_review、security_scan、coverage_report、python_compile、lint_format、run_tests、db_query、**29 个源代码导航器（idx 系列）** |
| **MCP** |连接到外部 MCP 服务器，列出工具，执行 — [OAuth / 代理指南](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** |代理到代理通信（与其他 uag 实例或 A2A 兼容服务器）|
| **系统** |环境变量、系统规格、时间、日期计算、[数量](docs/QUANTITIES.md)、[geodesic_distance](docs/GEODESIC_DISTANCE.md)、uuid_gen、slugify |
| **来源导航** | **29 个 idx 工具**，适用于 Python、PHP、TypeScript、Java、C#、Dart、C/C++、Rust、Go、Swift、Kotlin、COBOL、VBA、LotusScript、Makefile — 无需读取整个文件即可获取函数/类索引或特定定义 |

#### 存储库审查和覆盖范围

- `workspace_status`：报告活动工作区的 Git 分支、更改、上游同步状态、Python 运行时和常见项目标记，而无需修改文件。
- `git_review`：总结 Git 更改、有风险的文件、测试候选项和秘密发现，而不暴露秘密值。
- `security_scan`：扫描存储库文件以查找可能的秘密和有风险的配置文件。
- `coverage_report`：运行和标准化 Python、TypeScript/JavaScript、Rust、Go、Java/Kotlin、.NET、C/C++、Ruby、PHP、Swift 和Dart/Flutter.
- 请求执行时可以自动安装缺少的覆盖依赖项； `dry_run` 永远不会安装软件包。
  请参阅[存储库分析工具](docs/REPOSITORY_TOOLS.md) 了解参数、输出和安全详细信息。
  请参阅[路径和 URL 别名](docs/PATH_URL_ALIASES.md) 以缩短工具参数中的重复文件路径和 URL。

### 🖥 4 个接口 + VS Code 扩展

|模式|命令|目的|
|---|---|---|
| **命令行** | `uag` |快捷的终端操作|
| **图形用户界面** | `uagg` |通过 tkinter 的桌面 UI |
| **网络** | `uagw` |基于浏览器的访问|
| **A2A 服务器** | `uaga` |用于多代理通信的 Agent2Agent 协议 |
| **VS 代码** | — | [扩展](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) 带有聊天面板、解释、重构、修复错误和工具树视图 |
有关 VS Code 扩展的详细信息，请参阅 [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) — 安装、命令、键绑定和配置。

### 🏠 IoT设备控制

- **BACnet**：读/写 BACnet/IP 设备（HVAC、照明、功率计）。用于推送通知的 COV 订阅
- **Modbus TCP**：读/写保持/输入寄存器和线圈。基于轮询的更改监控
- **OPC UA**：浏览地址空间、读/写变量、订阅数据更改
- **SwitchBot**：云批量控制和 BLE 扫描/控制。基于轮询的订阅
- **ECHONET Lite**：发现、控制和订阅来自家用电器（空调、灯、热水器等）的INF通知
- **Matter**：用于状态变化监控的读/写控制+属性订阅
- **UPnP**：设备发现和IGD端口转发
  参见[IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯代理技能市场

`:skills mp_search`浏览[SkillsMP](https://skillsmp.com)和[ClawHub](https://clawhub.ai)以获取社区技能。
安装和扩展uag 的动态功能。

### 🤖 自动驾驶 (`:auto`)

uag 可以**在多个 LLM 轮中自主追求目标**。非常适合需要迭代细化的复杂、多步骤任务。

- **工作原理**：每轮都有一个主查询（步骤 A），然后是审阅者判断（步骤 B），决定“完成还是继续？”
- **相同的提供商，相同的 API**：审阅者判断使用与主查询相同的代码路径 - 包括响应 API 支持。
- **单独的判断 LLM** （可选）：设置要使用的`UAGENT_AP_PROVIDER`为评审者提供不同的提供商/模型（例如，使用更便宜的模型进行评审）。
- **随时退出**：按 **F11** 键停止自动驾驶。**F12** 只会停止当前的 LLM 响应。或者让审阅者决定何时达到目标。
- **可配置**：`--max-rounds N` 来控制预算。
  请参阅 [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) 以获取完整文档。

### 🧩 批处理状态管理器

uag 可以跟踪长时间运行的多文件任务的进度。当 LLM 处理数十个文件时，“batch_state”会将待处理、已完成和失败的文件列表保留到磁盘。如果会话结束或一轮超时，下一次运行将从停止处恢复 — 不会丢失任何内容。

### 🛡人机循环

` human_ask` 让 LLM 暂停并在执行破坏性操作（文件删除、覆盖、shell 命令）之前请求您确认。您保持控制。

### 🛑 中断（c 键/停止按钮）

随时停止 LLM 响应生成，并将停止命令注入回 LLM。
|接口|如何打断|
|---|---|
| **命令行** |在 LLM 流式传输期间按“c”键 — 当前响应停止，并且“停止”作为用户消息发送，以便 LLM 做出相应响应|
| **网页用户界面** |单击红色 **■ 停止** 按钮（在 LLM 处理期间自动出现）|
| **桌面图形用户界面** |单击红色 \*\*\*\*\*\*\*\* 按钮（在 LLM 处理过程中自动出现）|
中断作为“提示注入”工作：它不仅仅是中止，而是将“停止”作为用户消息反馈给 LLM，使其能够优雅地结束或确认中断。
按 **F11** 键退出自动驾驶模式。**F12** 只会停止当前的 LLM 响应（请参阅 [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)）。

### 🕵️ 浏览器自动化和 Web 检查器

两个互补的基于 Playwright 的工具：

- **browser_playwright**：自动化真实的浏览器会话 - 导航、单击、填写表单、提取数据、处理多页面流。无头或有头均可工作。
- **playwright_inspector**：记录浏览器转换，捕获每一步的 DOM 快照和屏幕截图。对于调试 Web 交互或审核页面随时间的变化非常有用。

### 🔄 动态工具加载

`tool_catalog` 和 `tool_load` 可让您在运行时发现并启用工具。
无需在启动时加载所有内容 - 仅在需要时激活您需要的内容。

### 🦀 Rust 原生工具

`uuid_gen` 和 `slugify` 在 Rust 中实现（通过 PyO3）性能。
它们直接从预构建的 `.pyd` 加载 — **不需要 `pip install`**。
外部开发人员还可以提供基于 Rust 的工具：在包装器 `.py` 旁边放置一个 `.pyd`，使用 `uagent.tools.rust_helper` 中的 `load_rust_pyd()`，并且
用户无需任何额外依赖即可获取该工具。请参阅
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)。

### 🌐 i18n / L10n

日本语 / English / 简体中文 / 繁体中文 / 한국어 / Español / Français / Русский / 等。
设置`UAGENT_LANG`进行切换。请参阅 [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) 添加新的语言环境。
此自述文件的翻译可在[docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)。

### 🔒加密的环境变量

将 API 密钥和机密存储在 `.env.sec` 中 - 一个加密的 `.env` 文件。
使用 `uag_envsec` 进行管理。

## 配置和详细信息

- **环境变量**：[docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **设置向导**：`python -m uagent.setup_cli`
- **加密的env**：`uag_envsec` — 将`.env`加密为`.env.sec`
- **响应 API**：为响应 API 模式设置 `UAGENT_RESPONSES=1` (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI)。自动启用 Sakana AI (Fugu)。
- **开发者文档**：[DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **工具流程**： [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — 如何将工具发送到 LLM（流派掩码、tool_catalog、GPT-5.4+ 本机 tool_search）
- **LLM 小技巧**： [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## 项目理念

uag 渴望成为 **您的 AI，在您的机器上，按照您的意愿。**

- 无 SaaS 依赖性 — 本地运行
- 无提供商锁定 — 随时切换
- 无 UI 锁定 — CLI / GUI / Web / A2A
- 无功能锁定 — 通过工具和技能进行扩展

免费的 AI 代理体验，来自供应商锁定。

### ✨ 创建您自己的工具

为 uag 编写新工具非常简单 - 使用
`TOOL_SPEC` 和 `run_tool()` 创建一个 `.py` 文件，将其放置在 `UAGENT_EXTERNAL_TOOLS_DIR` 中，
它可以立即可用。对于 Rust 开发人员，为用户提供预构建的“.pyd”，
对用户零额外依赖。

请参阅 [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
了解分步指南。

## 贡献

欢迎贡献！错误报告、功能建议、文档改进、翻译和拉取请求 - 全部赞赏。

- **问题**：针对错误或功能请求打开 GitHub 问题。
- **拉取请求**：分叉存储库，进行更改并提交 PR。请参阅 [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) 了解开发设置和指南。
- **翻译**：欢迎自述文件翻译和语言环境添加。请参阅 [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)。
- **工具和技能**：可以通过市场贡献新的工具插件和代理技能。

### 开发检查（PR 之前）

首先安装仅测试依赖项。它们不包含在运行时
依赖列表中：

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

在推送之前运行 GitHub 使用的相同检查操作：

```bash
python -m ruff check src测试
python -m black --check src测试
python脚本/tool_json_i18n_batch.py状态
python -m pytest -q .
```

为了更快的本地迭代，仅运行受影响的测试：

```bash
pytest -q测试/ <affected_area>
```

相关时的其他检查：

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

语言环境 (`.po`) 编辑后：`python script/compile_locales.py` 和 `python script/po_qc_summary.py`。

运行时策略（详细信息请参阅[DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1)：帮助程序引发而不是 `sys.exit`；工具主机将工具 `SystemExit`/`Exception` 转换为错误字符串，因此单个工具无法终止进程。启动快速失败退出仍然是故意的。

## 架构和操作不变量

请参阅 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 了解涵盖 A2A 生命周期、I18N 上下文、可选依赖项安装、工具安全、提供程序功能、OAuth 信任边界、结构化事件和验收验证的持久合约。

## 企业策略引擎

支持工具、提供商、凭证、MCP 服务器、网络、技能和插件的组织级策略。将“UAGENT_POLICY_FILE”设置为 JSON/YAML 策略文件；请参阅 [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) 了解配置示例、角色、确认和白名单。

### 运行时恢复和编排

请参阅 [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) 用于持久恢复、依赖项感知执行、多代理编排和远程 A2A 使用。

请参阅 [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) 了解共享运行时领导者租约协调。

## Installation and optional dependencies

The base installation keeps provider and tool integrations optional. Missing
packages are installed automatically when a selected provider or tool needs
one. To install the main feature groups in advance:

```bash
pip install "uag[core,providers,tools,development,platform,web]"
```

For a repository checkout with the full development and test environment:

```bash
pip install -r requirements.txt
```
