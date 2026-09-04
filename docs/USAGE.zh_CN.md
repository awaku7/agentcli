# 使用方法（命令行选项）

本文档介绍了 uag 入口点可用的命令行选项。

______________________________________________________________________

## 入口点

| 命令 | Python 模块 | 接口 |
|---|---|---|
| `uag` | `python -m uagent` | CLI（标准输入循环） |
| `uagg` | `python -m uagent.gui` | GUI（tkinter）|
| `uagw` | `python -m uagent.web` | Web 服务器 (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP 服务器 |

______________________________________________________________________

## CLI 启动选项 (`uag`)

### `--workdir` / `-C <路径>`

工作目录。 若未设置，则回退到 `UAGENT_WORKDIR` 环境变量，若该变量未定义，则使用当前目录。
若目录不存在，则会自动创建。

### `--tool-genre-mask <int>`

工具类型位掩码。 若提供此参数，将跳过交互式类型选择提示。

| 位 | 类型 | 描述 |
|-----|-------|-------------|
| 1 | basic | 基本文件/聊天工具 |
| 2 | comm | 通信工具（Bluesky、Teams） |
| 4 | office | 办公套件工具（Excel、PDF、PPTX） |
| 8 | devel | 开发工具（git、lint、编译） |
| 16 | iot | IoT 设备工具（SwitchBot、ECHONET、Matter、UPnP） |
| 32 | exec | 命令执行工具 |
| 64 | external | 外部插件工具 |
| 128 | media | 图像/音频生成与分析 |
| 256 | 文件 | 文件管理工具 |
| 512 | 索引 | 源代码/索引导航工具 |
| 1024 | 开发 | 开发者和代码库工具 |
| 2048 | 网络 | 网络和浏览器工具 |
| 4096 | utility | 实用及支持工具 |
| 8191 | all | 所有工具 |

示例：

```
uag --tool-genre-mask 1 # 仅基础
uag --tool-genre-mask 9 # 基础 + 开发 (1 + 8)
uag --tool-genre-mask 8191    # 所有工具
```

### `--use-tool` / `--no-use-tool`

启用或禁用向 LLM 发送工具定义。 该选项将覆盖 `UAGENT_USE_TOOL` 环境变量。

- `--use-tool` 强制启用工具发送。
- `--no-use-tool` 强制禁用工具发送。

禁用时，LLM 将不会接收任何工具定义，也无法调用任何工具。

### `--computer-use` / `--no-computer-use`

启用或禁用“计算机使用”功能。 该选项将覆盖 `UAGENT_COMPUTER_USE` 环境变量。

### `--inject-message` / `-M <message>`

在启动时向 LLM 注入一条消息，并在完成后退出。 这默认启用 `--non-interactive` 选项。

### `--embedded`

适用于受限或对可重复性要求较高的部署场景的嵌入式模式。

- 禁用会话存储。
- 除非显式启用，否则隐藏工具管理工具（`tool_catalog`、`tool_load`、`unload_tool`）。
- 忽略 `--tool-genre-mask`；如需显式加载工具，请使用 `--enable-tool`。

### `--enable-tool <名称>`

在启动时显式加载一个工具。该选项可以重复使用，也支持以逗号分隔的名称列表。

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

指定的顺序将被保留，并反映在提交给 LLM 的工具顺序中。显式启用的工具将被固定，不会被自动卸载。

### `--plugin-dir <路径>`

从指定目录加载插件。 该选项可以重复使用。

______________________________________________________________________

## 仅限 CLI 的选项

### `--inject-message-auto <目标选项>`

从非交互式的注入目标启动自动驾驶模式。 该值使用的选项与 `:auto` 相同；当值中包含选项时，请将完整值用引号括起来。

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "对项目进行排序 --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "对项目进行排序 --infinite"
```

常规模式采用评审员判断路径。 将 `UAGENT_AUTO_SENTINEL=1` 设为 1 以启用单 LLM 哨兵模式。 在此模式下，目标 LLM 必须在每个响应结尾精确包含以下其中之一：

- `<AUTO_CONTINUE>` — 运行下一轮
- `<AUTO_COMPLETE>` — 成功完成

缺少或无效的标记会安全地停止自动驾驶。 这仍然会运行目标 `LLM`；只是避免了额外的审核器 `LLM` 调用。

### `--non-interactive`

非交互模式。不启动标准输入循环。 如果将文件路径作为位置参数提供，则处理该路径后程序立即退出。

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Web 服务器选项 (`uagw`)

### `--host <address>`

Web 服务器的绑定地址（默认：`127.0.0.1`，可通过 `UAGENT_WEB_HOST` 覆盖）。

默认情况下，Web 服务器仅监听本地主机（`127.0.0.1`）。若要使其对网络上的其他机器可见，请使用 `--host 0.0.0.0`。

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

使用上述相同的位掩码选择工具类型。 若指定此选项，将跳过交互式类型提示。

### `--use-tool` / `--no-use-tool`

启用或禁用向 LLM 发送工具定义。 覆盖 `UAGENT_USE_TOOL`。

### `--computer-use` / `--no-computer-use`

启用或禁用“计算机使用”功能。 该选项将覆盖 `UAGENT_COMPUTER_USE`。

### `--no-frontend`

仅运行 API，不使用 HTML 模板或静态前端文件。

### `--embedded`

禁用会话存储并隐藏工具管理工具（`tool_catalog`、`tool_load`、`unload_tool`）。

______________________________________________________________________

## A2A 服务器选项（`uaga`）

### `--host <address>`

A2A HTTP 服务器的绑定地址（默认：`0.0.0.0`，可通过 `UAGENT_A2A_HOST` 覆盖）。

### `--port <数字>`

A2A HTTP 服务器的端口号（默认：`8765`，可通过 `UAGENT_A2A_PORT` 覆盖）。

### `--reload`

启用代码更改时的热重载（默认：关闭，可通过 `UAGENT_A2A_RELOAD` 覆盖）。

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

使用上述描述的位掩码选择工具类型。 若指定此选项，将跳过交互式类型提示。

### `--use-tool` / `--no-use-tool`

启用或禁用向 LLM 发送工具定义。 覆盖 `UAGENT_USE_TOOL`。

### `--computer-use` / `--no-computer-use`

启用或禁用“计算机使用”功能。 该选项将覆盖 `UAGENT_COMPUTER_USE`。

### `--embedded`

禁用会话存储并隐藏工具管理工具（`tool_catalog`、`tool_load`、`unload_tool`）。

______________________________________________________________________

## 相关环境变量

| 变量 | 描述 |
|---|---|
| `UAGENT_PROVIDER` | LLM 提供商名称（启动时必填） |
| `UAGENT_*_API_KEY` | 所选提供商的 API 密钥 |
| `UAGENT_WORKDIR` | 默认工作目录 |
| `UAGENT_WEB_HOST` | Web 服务器绑定地址（默认：`127.0.0.1`） |
| `UAGENT_A2A_HOST` | A2A 服务器绑定地址（默认：`0.0.0.0`） |
| `UAGENT_A2A_PORT` | A2A 服务器端口（默认：`8765`） |
| `UAGENT_A2A_RELOAD` | 默认启用 A2A 热重载 |
| `UAGENT_USE_TOOL` | 设置为 `0`、`false`、`no` 或 `off` 时禁用工具 |
| `UAGENT_COMPUTER_USE` | 默认启用或禁用“计算机使用”功能 |
| `UAGENT_SESSION_STORE` | 启用或禁用会话存储； 嵌入式模式强制设置为 `0` |
| `UAGENT_PLUGIN_DIRS` | 附加的插件搜索目录 |
| `UAGENT_AUTO_SENTINEL` | 设置为 `1` 时，选择启用单LLM自动驾驶哨兵模式 |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | 连续调用新工具的最大次数（默认：`100`） |
| `UAGENT_MAX_TOOL_ROUNDS` | 每次用户操作中每个工具的 LLM 轮次上限 （默认：`200`）|
| `UAGENT_SHRINK_CNT` | 消息中的可选自动压缩阈值（`0`/未设置 = 禁用）|
| `UAGENT_SHRINK_KEEP_LAST` | 压缩后保留的消息数量（默认：`20`） |
| `UAGENT_LANG` | 界面语言（`ja`、`en` 等） |

有关环境变量的完整列表，请参见 [ENVIRONMENT.md](ENVIRONMENT.md)。

______________________________________________________________________

## 示例

### 使用 OpenAI 的最小启动配置

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### 仅使用基本工具的本地 Ollama 配置

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### 在所有接口上运行 Web 服务器

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

或

```
uagw --host 0.0.0.0
```

### A2A 在本地主机上运行服务器并使用自定义端口

```
uaga --host 127.0.0.1 --port 8080
```

### 禁用小型模型的工具

```
uag --no-use-tool --tool-genre-mask 1
```

### 非交互式文件处理

```
uag --non-interactive README.md
```
