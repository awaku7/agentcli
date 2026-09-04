# 使用方法（命令列選項）

本文說明 uag 入口點可用的命令列選項。

______________________________________________________________________

## 入口點

| 指令 | Python 模組 | 介面 |
|---|---|---|
| `uag` | `python -m uagent` | CLI（標準輸入循環） |
| `uagg` | `python -m uagent.gui` | 圖形介面 (tkinter) |
| `uagw` | `python -m uagent.web` | 網頁伺服器 (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP 伺服器 |

______________________________________________________________________

## CLI 啟動選項 (`uag`)

### `--workdir` / `-C <路徑>`

工作目錄。 若未設定，將回退至 `UAGENT_WORKDIR` 環境變數，若該變數未設定則使用當前目錄。
若目錄不存在，則會自動建立。

### `--tool-genre-mask <整數>`

工具類型位元遮罩。 若提供此參數，將跳過互動式類型選取提示。

| 位元 | 類型 | 說明 |
|-----|-------|-------------|
| 1 | basic | 基本檔案／聊天工具 |
| 2 | comm | 通訊工具（Bluesky、Teams） |
| 4 | office | 辦公室套件工具（Excel、PDF、PPTX） |
| 8 | devel | 開發工具 (git、lint、編譯) |
| 16 | iot | IoT 裝置工具 (SwitchBot、ECHONET、Matter、UPnP) |
| 32 | exec | 命令執行工具 |
| 64 | external | 外部外掛工具 |
| 128 | media | 影像／音訊生成與分析 |
| 256 | file | 檔案管理工具 |
| 512 | index | 原始碼／索引導覽工具 |
| 1024 | dev | 開發者與儲存庫工具 |
| 2048 | web | 網頁與瀏覽器工具 |
| 4096 | utility | 實用程式與支援工具 |
| 8191 | all | 所有工具 |

範例：

```
uag --tool-genre-mask 1 # 僅基本類別
uag --tool-genre-mask 9 # 基本類別 + 開發類別 (1 + 8)
uag --tool-genre-mask 8191    # 所有工具
```

### `--use-tool` / `--no-use-tool`

啟用或停用將工具定義傳送至 LLM。 此設定會覆寫 `UAGENT_USE_TOOL` 環境變數。

- `--use-tool` 強制啟用工具傳送。
- `--no-use-tool` 強制停用工具傳送。

當此功能停用時，LLM 將不會收到任何工具定義，且無法呼叫任何工具。

### `--computer-use` / `--no-computer-use`

啟用或停用「電腦使用」功能。 此設定會覆寫 `UAGENT_COMPUTER_USE` 環境變數。

### `--inject-message` / `-M <message>`

在啟動時將訊息注入 LLM，並於完成後退出。 這表示會自動啟用 `--non-interactive` 選項。

### `--embedded`

適用於受限環境或重視可重現性的部署之嵌入式模式。

- 停用工作階段儲存區。
- 除非明確啟用，否則會隱藏工具管理工具（`tool_catalog`、`tool_load`、`unload_tool`）。
- 忽略 `--tool-genre-mask`；若需明確載入工具，請使用 `--enable-tool`。

### `--enable-tool <名稱>`

在啟動時明確載入工具。此選項可重複使用，亦接受以逗號分隔的名稱。

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

所指定的順序將被保留，並反映在提供給 LLM 的工具順序中。明確定義啟用的工具將被固定，以防止自動卸載。

### `--plugin-dir <路徑>`

從指定目錄載入外掛程式。 此選項可重複使用。

______________________________________________________________________

## 僅限 CLI 的選項

### `--inject-message-auto <目標選項>`

從非互動式的注入目標啟動自動駕駛。 該值使用的選項與 `:auto` 相同；若值中包含選項，請將完整值以引號括起。

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "排序項目 --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "排序項目 --infinite"
```

常規模式採用審閱者判斷路徑。 請將 `UAGENT_AUTO_SENTINEL=1` 設為 1 以啟用單一 LLM 哨兵模式。 在此模式下，目標 LLM 必須在每個回應結尾處精確包含以下其中一項：

- `<AUTO_CONTINUE>` — 執行另一輪
- `<AUTO_COMPLETE>` — 成功完成

若缺少或標記無效，自動駕駛將安全停止。 此設定仍會執行目標 LLM；僅會避免額外的審查者 LLM 呼叫。

### `--non-interactive`

非互動模式。不會啟動標準輸入迴圈。 若將檔案路徑作為位置參數傳入，系統會處理該路徑並立即終止程式。

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Web 伺服器選項 (`uagw`)

### `--host <address>`

Web 伺服器的綁定位址（預設：`127.0.0.1`，可透過 `UAGENT_WEB_HOST` 覆寫）。

預設情況下，Web 伺服器僅監聽 localhost（`127.0.0.1`）。若要讓網路上的其他機器能夠存取，請使用 `--host 0.0.0.0`。

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <整數>`

使用上述所述的相同位元遮罩來選取工具類型。 若指定此參數，將跳過互動式類型提示。

### `--use-tool` / `--no-use-tool`

啟用或停用將工具定義傳送至 LLM。 此設定會覆寫 `UAGENT_USE_TOOL`。

### `--computer-use` / `--no-computer-use`

啟用或停用「電腦使用」功能。 此設定會覆寫 `UAGENT_COMPUTER_USE`。

### `--no-frontend`

僅執行 API，不使用 HTML 範本或靜態前端檔案。

### `--embedded`

停用會話儲存區並隱藏工具管理工具（`tool_catalog`、`tool_load`、`unload_tool`）。

______________________________________________________________________

## A2A 伺服器選項 (`uaga`)

### `--host <address>`

A2A HTTP 伺服器的綁定位址（預設：`0.0.0.0`，可透過 `UAGENT_A2A_HOST` 覆寫）。

### `--port <數字>`

A2A HTTP 伺服器的連接埠號碼（預設：`8765`，可透過 `UAGENT_A2A_PORT` 覆寫）。

### `--reload`

啟用程式碼變更時的熱重新載入（預設：關閉，可透過 `UAGENT_A2A_RELOAD` 覆寫）。

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <整數>`

使用上述所述的位元遮罩來選取工具類型。 若指定此參數，將跳過互動式類型提示。

### `--use-tool` / `--no-use-tool`

啟用或停用將工具定義傳送至 LLM。 此設定會覆寫 `UAGENT_USE_TOOL`。

### `--computer-use` / `--no-computer-use`

啟用或停用「電腦使用」功能。 此設定會覆寫 `UAGENT_COMPUTER_USE`。

### `--embedded`

停用工作階段儲存區，並隱藏工具管理工具（`tool_catalog`、`tool_load`、`unload_tool`）。

______________________________________________________________________

## 相關環境變數

| 變數 | 說明 |
|---|---|
| `UAGENT_PROVIDER` | LLM 供應商名稱（啟動時必填） |
| `UAGENT_*_API_KEY` | 所選供應商的 API 金鑰 |
| `UAGENT_WORKDIR` | 預設工作目錄 |
| `UAGENT_WEB_HOST` | Web 伺服器綁定位址（預設：`127.0.0.1`） |
| `UAGENT_A2A_HOST` | A2A 伺服器綁定位址（預設：`0.0.0.0`） |
| `UAGENT_A2A_PORT` | A2A 伺服器埠號（預設：`8765`） |
| `UAGENT_A2A_RELOAD` | 預設啟用 A2A 熱載入 |
| `UAGENT_USE_TOOL` | 設定為 `0`、`false`、`no` 或 `off` 時停用工具 |
| `UAGENT_COMPUTER_USE` | 預設啟用或停用「電腦使用」功能 |
| `UAGENT_SESSION_STORE` | 啟用或停用工作階段儲存； 嵌入式模式強制設定為 `0` |
| `UAGENT_PLUGIN_DIRS` | 額外的外掛程式搜尋目錄 |
| `UAGENT_AUTO_SENTINEL` | 設定為 `1` 時，選擇啟用單一 LLM 自動駕駛哨兵模式 |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | 最大連續新工具呼叫次數（預設：`100`） |
| `UAGENT_MAX_TOOL_ROUNDS` | 每次使用者操作中，每個工具的 LLM 輪次上限（預設：`200`） |
| `UAGENT_SHRINK_CNT` | 訊息中的可選自動壓縮閾值（`0`/未設定 = 停用） |
| `UAGENT_SHRINK_KEEP_LAST` | 壓縮後保留的訊息數（預設值：`20`） |
| `UAGENT_LANG` | 介面語言（`ja`、`en` 等） |

完整的環境變數清單請參閱 [ENVIRONMENT.md](ENVIRONMENT.md)。

______________________________________________________________________

## 範例

### 使用 OpenAI 的最簡啟動方式

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### 僅含基本工具的本地 Ollama

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### 所有介面皆啟用 Web 伺服器

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

或

```
uagw --host 0.0.0.0
```

### 在本地主機上以自訂埠號運行 A2A 伺服器

```
uaga --host 127.0.0.1 --port 8080
```

### 針對小型模型停用工具

```
uag --no-use-tool --tool-genre-mask 1
```

### 非互動式檔案處理

```
uag --non-interactive README.md
```
