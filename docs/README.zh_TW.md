<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag——通用人工智慧網關</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — 你的環境，你的自由。
</p>

<p align="center">
  檔案操作 / 網路搜尋 / 影像產生與分析 / PDF 和 Excel 擷取 / IoT 控制 / MCP 集成<br>
  24 providers / 3 UI / 平行工具執行 / Agent Skills 市場
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## 為什麼是uag？

\*\*擺脫供應商鎖定。 \*\*大多數人工智慧助理會將您與特定的供應商或雲端服務連結起來。 uag 是不同的。

- **在您的電腦上本機運作**。您的資料保留在您身邊（您進行的 API 呼叫除外）。
- **提供者自由**：OpenAI、Claude、Gemini、DeepSeek、Ollama、Azure、Bedrock、HuggingFace...超過 24 個提供者，均可透過單一介面存取。透過重新配置環境變數在它們之間進行交換—無需重新安裝，無需遷移。
- **229 個工具**：檔案 I/O、網路搜尋、影像產生、Gmail、BLE 裝置掃描、MCP 伺服器整合 — **130 個工具是並行安全的**（最多 8 個透過執行緒池並發執行，可透過「UAGENT_PARALLEL_WORKERS」進行設定）。當 LLM 一次觸發多個工具呼叫時，uag 會自動並行化它們。
- **3 UI + A2A**：CLI、GUI、Web 和代理到代理協定。相同的引擎，任何接口。
- **代理技能**：從市場安裝社群建立的技能。無限延伸uag。

uag 是**您的人工智慧助手，按照您的意願**。不依賴提供者、不依賴介面、不依賴平台。

## 快速入門

```bash
pip install uag
uag
```

首次啟動時，設定精靈將引導您完成提供者設定。
有關所有環境變量，請參閱 [docs/ENVIRONMENT.md](ENVIRONMENT.md)。

＃＃ 特徵

### 🧠 多提供者架構

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

所有提供者共享相同的工具集和介面。透過設定“UAGENT_PROVIDER”進行切換－無需更改程式碼，無需單獨安裝。

### ⚡ 平行工具執行

當 LLM 同時要求多個工具時，uag **會自動並行化**它們。
130 個工具被標記為“x_parallel_safe”，並透過“ThreadPoolExecutor”並發執行（預設為 8 個執行緒；設定“UAGENT_PARALLEL_WORKERS”進行更改）。

**範例**：詢問「檢查北歐首都的天氣」 → LLM 觸發 `search_web` × 5 個國家 → 所有 5 個搜尋並行運行 → 一批收集結果。

只讀工具（檔案搜尋、哈希計算、目錄列表、翻譯、資料庫查詢等）被積極並行化。

### 🧩 插件系統（Claude Code 相容）

uagent 實作了 Claude Code 相容的插件系統。插件會將技能、代理、MCP 伺服器、掛鉤等內容，與 `.claude-plugin/plugin.json` 清單一起封裝在獨立目錄中。

**支援的元件：技能、子代理程式、MCP 伺服器、掛鉤（12 個生命週期事件）、斜線命令、輸出樣式、userConfig、相依項、通道、市場**

**CLI commands**:

```
:plugin list                         # 列出已安裝的插件
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # 從市場安裝
:plugin remove <name>                # 解除安裝
:plugin enable/disable <name>        # 切換
:plugin marketplace add/remove/list  # 管理市場
:plugin init <name>                  # 建立新插件的基本架構
```

有關詳細資訊，請參閱完整文件。 [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md)

### 🔄 會話連續性

- **在工作階段中途切換提供者**（使用 `UAGENT_PROVIDER`）— 會話記錄會保留。
- **重新載入過去的工作階段**（使用 `:load <index>`）— 從上次中斷處繼續。

### 🛠 229 工具

- **雲端 API**: `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation.

|類別 |工具|
|---|---|
| **檔案操作** |讀/寫/建立/刪除/搜尋/grep/hash/zip，parse_eml（.eml 檔案）|
| **網頁** | fetch_url、search_web、螢幕截圖、browser_playwright |
| **媒體** |產生影像、分析影像、img2img、音訊語音、音訊轉錄 |
| **檔案** | PDF/PPTX/DOCX/RTF/ODT擷取、Excel結構化擷取|
| **預測** | 使用9種模型（AutoARIMA、Prophet、LightGBM、CatBoost、TimesFM等）進行時間序列預測，自動模型選擇，產生圖表，i18n |
| **通訊** | gmail_send、gmail_read、bluesky、discord_channel、teams_webhook , **pybitchat** (BLE Mesh) — 請參閱 [COMMUNICATION.md](COMMUNICATION.md) 及 [BITCHAT.md](BITCHAT.md)|
| **物聯網** | SwitchBot（雲端 + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **開發工具** | git_ops、python_compile、lint_format、run_tests、db_query、**29 個原始碼導航器（idx 系列）** |
| **MCP** |連接到外部 MCP 伺服器、列出工具、執行 — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** |代理間通訊（與其他 uag 實例或 A2A 相容伺服器）|
| **系統** | 環境變數、系統規格、時間、日期計算, uuid_gen, slugify, quantities ||
| **來源導航** | **29 個 idx 工具**，適用於 Python、PHP、TypeScript、Java、C#、Dart、C/C++、Rust、Go、Swift、Kotlin、COBOL, VBA, LotusScript, Makefile — 無需讀取整個檔案即可取得函數/類別索引或特定定義 |

#### 儲存庫審查和覆蓋
- `git_review`：總結 Git 更改、有風險的文件、測試候選項和秘密結果，而不暴露秘密值。 
- `security_scan`：扫描存储库文件以查找可能的秘密和有风险的配置文件。 
- `coverage_report`：執行並規範 Python、TypeScript/JavaScript、Rust、Go、Java/Kotlin、.NET、C/C++、Ruby、PHP、 Swift 和 Dart/Flutter。 
- 请求执行时可以自动安装缺少的覆盖依赖项； `dry_run` 从不安装软件包。 

有关参数、输出和安全详细信息，请参阅[存储库分析工具](REPOSITORY_TOOLS.md)。

### 🖥 4 個介面 + VS 代碼擴展

|模式|命令|目的|
|---|---|---|
| **命令列** | `uag` |快速的終端機操作 |
| **圖形使用者介面** | `uagg` |透過 tkinter 的桌面 UI |
| **網頁** | `uagw` |基於瀏覽器的存取 |
| **A2A 伺服器** | `瓦加` |用於多代理通訊的Agent2Agent協定|
| **VS 程式碼** | — | [擴充](VSCODE.md) 附有聊天面板、解釋、重構、修復錯誤和工具樹視圖 |

有關 VS Code 擴充功能的詳細資訊 - 安裝、命令、鍵綁定和配置，請參閱 [VSCODE.md](VSCODE.md)。

### 🏠 物聯網設備控制

- **事項**：控制器/橋接器/設備拓樸的唯讀檢查

請參閱 [IOT_USECASE.md](IOT_USECASE.md)

### 🏠 IoT 設備控制

- **BACnet**：讀取/寫入 BACnet/IP 設備（HVAC、照明、電錶）。用於推播通知的 COV 訂閱
- **Modbus TCP**：讀取/寫入保持/輸入暫存器和線圈。基于轮询的更改监控
- **OPC UA**：浏览地址空间、读/写变量、订阅数据更改
- **SwitchBot**：云批量控制和 BLE 扫描/控制。基于轮询的订阅
- **ECHONET Lite**：发现、控制和订阅来自家用电器（空调、灯、热水器等）的 INF 通知
- **Matter**：读/写控制 + 用于状态变化监控的属性订阅
- **UPnP**：设备发现和 IGD連接埠轉送

請參閱[IOT_USECASE.md](IOT_USECASE.md)

### 🎯 代理技能市場

`:skills mp_search` 瀏覽 [SkillsMP](https://skillsmp.com) 和 [ClawHub](https://clawhub.ai) 以獲取社區技能。
即時安裝並擴充 uag 的功能。

### 🤖 自動駕駛 (`:auto`)

uag 可以**在多輪法學碩士課程中自主追求一個目標**。非常適合需要迭代細化的複雜、多步驟任務。

- **工作原理**：每一輪都有一個主要查詢（步驟 A），然後是審閱者判斷（步驟 B），決定“完成還是繼續？”
- **相同的提供程序，相同的 API**：審查者判斷使用相同的程式碼路徑作為主要查詢 - 包括回應 API 支援。
- **單獨評判LLM**（可選）：設定「UAGENT_AP_PROVIDER」為審查者使用不同的提供者/模型（例如，使用較便宜的模型進行評判）。
- **隨時退出**：按下「x」鍵立即停止，即使是在回應中。或讓評審者決定何時達到目標。
- **可設定**：`--max-rounds N` 來控制預算。

完整文檔，請參閱 [README_AUTO.md](README_AUTO.md)。

### 🧩 批次狀態管理器

uag 可以追蹤長時間運行的多檔案任務的進度。當 LLM 處理數十個檔案時，「batch_state」會將待處理、已完成和失敗的檔案清單保留到磁碟。如果會話結束或一輪逾時，下一次運行將從停止處繼續 - 不會丟失任何內容。

### 🛡 人機交互

` human_ask` 允許 LLM 在執行破壞性操作（檔案刪除、覆蓋、shell 命令）之前暫停並要求您確認。您保持掌控。

### 🛑 中斷（c 鍵/停止按鈕）

隨時停止 LLM 回應生成，並將停止命令注入回 LLM。

|接口|如何中斷|
|---|---|
| **命令列** |在 LLM 串流期間按下「c」鍵 — 當前回應停止，並且「停止」作為使用者訊息發送，以便 LLM 做出相應回應 |
| **網頁使用者介面** |點選紅色 **■ 停止** 按鈕（LLM 處理期間自動出現）|
| **桌面圖形使用者介面** |點選紅色 \*\*\*\*\*\*\*\* 按鈕（LLM 處理期間自動出現）|

中斷充當「提示注入」：它不僅僅是中止，而是將「停止」作為使用者訊息回饋給 LLM，使其能夠優雅地結束或確認中斷。

按下「x」鍵退出自動駕駛模式（請參閱 [README_AUTO.md](README_AUTO.md)）。

### 🕵️ 瀏覽器自動化和 Web 檢查器

兩個基於 Playwright 的互補工具：

- **browser_playwright**：自動化真實的瀏覽器會話 - 導航、點擊、填寫表單、提取資料、處理多頁面流。無頭或有頭均可工作。
- **playwright_inspector**：記錄瀏覽器轉換，捕捉每一步的 DOM 快照和螢幕截圖。對於調試 Web 互動或審核頁面隨時間的變化很有用。

### 🔄 動態工具加載

`tool_catalog` 和 `tool_load` 可讓您在執行時發現並啟用工具。
無需在啟動時加載所有內容 - 僅在需要時啟動您需要的內容。

### 🦀 Rust Native Tools

為提升效能，`uuid_gen` 和 `slugify` 使用 Rust（透過 PyO3）實作。

### 🌐 國際化 / 本土化

日本文 / English / 簡體中文 / 繁體中文 / 한국어 / Español / Français / Русский / 等。
設定`UAGENT_LANG`進行切換。請參閱 [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md) 新增新的區域設定。

本自述文件的翻譯可在 [docs/README.translations.md](README.translations.md) 中找到。

### 🔒 加密環境變量

將 API 金鑰和機密儲存在「.env.sec」中—一個加密的「.env」檔案。
使用“uag_envsec”進行管理。

## 配置和詳細信息

- **環境變數**：[docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **設定精靈**：`python -m uagent.setup_cli`
- **加密的 env**: `uag_envsec` — 將 `.env` 加密為 `.env.sec`
- **回應 API**：為回應 API 模式設定「UAGENT_RESPONSES=1」（OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI）。自動啟用 Sakana AI (Fugu)。
- **開發人員文件**：[DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **LLM小技巧**：[SLM_TIPS.md](SLM_TIPS.md)

## 專案理念

uag 渴望成為 \*\*您的人工智慧，在您的機器上，按照您的條件。 \*\*

- 無 SaaS 依賴性 — 在本地運行
- 沒有供應商鎖定－隨時切換
- 無 UI 鎖定 — CLI / GUI / Web / A2A
- 無功能鎖定－透過工具和技能進行擴展

免費的人工智慧代理體驗，不受供應商鎖定。

### ✨ 建立您自己的工具

[zh_TW.md](TOOL_CREATOR_GUIDE.zh_TW.md)
如需逐步指南，請參閱此處。

## 貢獻

歡迎各種貢獻！錯誤報告、功能建議、文件改進、翻譯和提取請求，都非常值得肯定。

- **Issues**: 針對錯誤或功能請求開啟 GitHub 問題。
- **提取請求**：Fork 儲存庫、完成修改並提交 PR。如需開發環境設定與指南，請參閱 [DEVELOP.md](../src/uagent/docs/DEVELOP.md)。

Realtime 語音和 AEC3

## Realtime語音模式支援全雙工麥克風和揚聲器輸入/輸出。如果缺少 AEC3 後端，uag 會自動安裝 pywebrtc-audio。

**即時提供者**：OpenAI Realtime、Azure OpenAI GPT Realtime、Google Gemini Live、xAI Grok Voice 和 Amazon Bedrock Nova Sonic。只有在選擇 Bedrock 時，才會自動安裝 Bedrock 雙向流 SDK。

```bat
python scheck.py realtime
```

AEC3 使用實際的麥克風訊號（近）和實際發送到揚聲器的音訊（遠）。僅在調查音訊問題時啟用診斷。

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime 支援安全限制的 Function Calling 整合。目前適配器會自動公開只讀 get_current_time 函數。破壞性工具和設備控制需要明確的許可名單和確認流程。 Grok 即時使用單獨的轉接器，且不使用此 OpenAI 特定的 Function Calling 路徑。
