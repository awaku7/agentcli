\<palign="center">
<img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">

</p>

通用人工智慧網關</h1>

\<palign="center">
<b>U</b>通用<b>A</b>I <b>G</b>網關 - 您的環境，您的自由。

</p>

\<palign="center">
檔案操作/網路搜尋/影像產生與分析/PDF與Excel擷取/物聯網控制/MCP整合<br>
24個供應商/3個UI/並行工具執行/代理技能市集

</p>

href="https://github.com/awaku7/agentcli">GitHub</a>
·
<a href="https://pypi.org/project/uag/">PyPI</a>
·
<a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">用您的語言閱讀此內容</a>

</p>

______________________________________________________________________

## 為什麼 uag？

\*\*擺脫供應商鎖定。 \*\* 大多數 AI 助理會將您與特定提供者或雲端服務連結起來。 uag 是不同的。

- **在您的電腦上本地運行**。您的資料保留在您身邊（您撥打的 API 電話除外）。
- **提供者自由**：OpenAI、Claude、Gemini、DeepSeek、Ollama、Azure、Bedrock、Novita、HuggingFace...24 個提供者，均可透過單一介面存取。透過重新配置環境變數在它們之間進行交換 - 無需重新安裝，無需遷移。
- **222 個工具**：檔案 I/O、網路搜尋、影像產生、Gmail、BLE 裝置掃描、MCP 伺服器整合 - **130 個靜態標記為平行安全性**（最多 8 個透過執行緒池並發執行，可透過「UAGENT_PARALLEL_WORKERS」進行設定）。當 LLM 一次觸發多個工具呼叫時，uag 會自動並行化它們。
- **3 UI + A2A**：CLI、GUI、Web 和代理到代理協定。相同的引擎，任何接口。
- **物聯網就緒**：SwitchBot、ECHONET Lite、Matter、UPnP — 透過 AI 控制您的家庭設備。
- **代理技能**：從市場安裝社群建構的技能。無限擴展 uag。

uag 是**您的 AI 助手，隨心所欲**。不依賴提供者、不依賴介面、不依賴平台。

## 快速入門

\`\`bash
pip install uag
uag

````

首次啟動時，設定精靈將引導您完成提供者設定。 
有關所有環境變量，請參閱 [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)。 

## 計算機使用

計算機使用是可選的，並且支援可見的Playwright 瀏覽器運行時
和桌面運行時。啟用後，將建立並註冊兩個執行時間；
所選運行時由 `UAGENT_COMPUTER_ENVIRONMENT` 控制：

```bat
set UAGENT_COMPUTER_USE=1
set UAGENT_COMPUTER_ENVIserMENT_COMPUTER_USE=1
set UAGENT_COMPUTER_ENVIserMENT_COMPUTER_USE=1
set UAGENT_COMPUTER_ENVIserMENT 作業運行時資源在正常退出、「Ctrl-C」和進程關閉時一起關閉。設定
`UAGENT_COMPUTER_HEADLESS=1`以進行基於瀏覽器的 CI 或冒煙測試。 
請參閱 [docs/COMPUTER_USE_IMPLMENTATION.md](docs/COMPUTER_USE_IMPLMENTATION.md)
以了解整合和安全性詳細資訊。 

## 即時語音和 AEC3

即時語音模式支援 OpenAI Realtime、Azure OpenAI GPT Realtime、xAI Grok Voice API、Google Gemini Multimodal Live API 和具有全雙工麥克風和具有 Irock Irock Nrock Nco 揚聲器和揚聲器/O 的 Amazon Bed Irock Nova。所需的 `pywebrtc-audio` AEC3 後端會自動安裝，並且僅當選擇 Bedrock 提供者時，才會自動安裝 Bedrock 的可選雙向流 SDK：

```bash
python scheck.py realtime
``

管道接收實際的麥克風訊號（`near`）和實際傳遞到揚聲器的音訊（`far`），以便助手可以在說話時收聽。僅在調查音訊問題時啟用診斷：

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
````

### OpenAI 實時函數

\`\`

### OpenAI 即時函數

目前即時適配器會自動公開只讀“get_current_time”。如果沒有明確的許可名單和確認流程，破壞性工具和設備控制就不會暴露。 Grok 即時使用單獨的適配器，且不使用此 OpenAI 特定的函數呼叫路徑。

## 功能

### 🧠 多供應商架構

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVID /L/A / /Sy HuggingFace / 阿里雲 (Qwen) / KIMI (Moonshot) AI)/Xiaomi MiMo/LM Studio/MiniMax/Sakana AI (Fugu)/SAKURA AI Engine/Together AI/Vercel AI Gateway
所有提供者共享相同的工具集和介面。透過設定 `UAGENT_PROVIDER` 進行切換 — 無需更改程式碼，無需單獨安裝。

#### Ollama 和 llama.cpp

Ollama 和 llama.cpp 是單獨的提供者。 Ollama 使用自己的服務和模型管理，而 `llama.cpp` 連接到 `llama-server` OpenAI 相容端點：

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
的AGENT_LLAMA提供者使用聊天完成相容的路徑。除非配置了相容的代理，否則保持“UAGENT_RESPONSES=0”。 
### ⚡並行工具執行
當 LLM 同時請求多個工具時，uag **自動並行化**它們。 
130 個工具靜態標記為“x_parallel_safe”，並透過“ThreadPoolExecutor”並發執行（預設為 8 個執行緒；設定`UAGENT_PARALLEL_WORKERS` 變更）。 
**範例**：詢問「檢查北歐首都的天氣」→ LLM 觸發 `search_web` × 5 個國家 → 所有 5 個搜尋並行運行 → 一批收集結果。 
目前計數是基於定義「TOOL_SPEC」的工具模組（目前為 222 個，包括 2 個 Rust 支援的工具） `src/uagent/tools_rust/`)。 `http_request` 使用方法敏感的安全性：`GET`/`HEAD`/`OPTIONS` 呼叫可以並行運行，而寫入方法保持串列。 
唯讀工具（檔案搜尋、哈希計算、目錄列表、翻譯、資料庫查詢等）被積極並行化。 
### 🧩插件系統（Claude 程式碼相容）
uagent 實作了 **Claude 程式碼相容的插件系統**。插件透過 `.claude-plugin/plugin.json` 清單將技能、代理、MCP 伺服器、掛鉤等捆綁到獨立目錄中。 
**支持的组件**：技能、子代理、MCP 服务器、挂钩（12 个生命周期事件）、斜线命令、输出样式、用户配置、依赖项、通道、市场
**CLI命令**:
```

:plugin list # 列出已安装的插件
:plugin install <source> [--scope] #安裝(dir/zip/git/http)
:plugin install <name>@<marketplace> # 從市場安裝
:plugin remove <name> # 卸載
:插件啟用/停用<name> # 切換
:plugin market add/remove/list # 管理市場外掛程式啟用
[DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) 以取得完整文件。

### 🔄 會話連續性

- **使用 `UAGENT_PROVIDER` 在會話中切換提供者** — 保留對話歷史記錄。
- \*\*使用 `:load 重新載入過去的會話** <index>` — 從上次停下的地方繼續。
- **工具結果快取**可避免重複呼叫相同工具時重複執行。

### 🛠 229 工具

|類別 |工具|
|---|---|
| **檔案操作** |讀取/寫入/建立/刪除/搜尋/grep/hash/zip、file_type、parse_eml（.eml 檔案）、`path_alias`\*\*
| fetch_url、search_web、螢幕截圖、browser_playwright、`url_alias`、`public_transit_route` ([指南](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **媒體** |產生映像、分析映像、img2img、audio_speech、audio_transcribe| **媒體** | PDF/PPTX/DOCX/RTF/ODT提取、Excel結構化提取|
| **預測** |使用 9 種模型進行時間序列預測（AutoARIMA、Prophet、LightGBM、CatBoost、TimesFM 等）、自動模型選擇、繪圖生成、i18n |
| **通訊** | gmail_send、gmail_read、bluesky、discord_channel、teams_webhook、**pybitchat** (BLE Mesh) — 請參閱 [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) 和[BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **物聯網** | SwitchBot（雲 + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |Kapi_apioo.雲端與 Azure API 操作；寫入操作需要明確確認 |
| **開發工具** | workspace_status、git_ops、git_review、security_scan、coverage_report、python_compile、lint_format、run_tests、db_query、reports、python_compile、lint_format、run_tests、db_query、who-29 個原始碼長MCP 伺服器，列出工具，執行 — [OAuth / 代理指南](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** |代理到代理通訊（與其他 uag 實例或 A2A 相容伺服器）|
| \*\* |環境變數、系統規格、時間、日期計算、[數量](docs/QUANTITIES.md)、[geodesic_distance](docs/GEODESIC_DISTANCE.md)、uuid_gen、slugify |
| **來源導航** | **29 個 idx 工具**，適用於Python、PHP、TypeScript、Java、C#、Dart、C/C++、Rust、Go、Swift、Kotlin、COBOL、VBA、LotusScript、Makefile — 無需讀取整個檔案即可取得函數/類別索引或特定定義 |

#### 儲存庫審查和覆蓋範圍

- \`workspace_status: 7：更新報告運行時和常見項目標記，而無需修改文件。
- `git_review`：總結 Git 變更、有風險的文件、測試候選項和秘密發現，而不暴露秘密值。
- `security_scan`：掃描儲存庫檔案以尋找可能的秘密和有風險的設定檔。
- `coverage_report`：運行和標準化 Python、TypeScript/JavaScript、Rust、Go、Java/Kotlin、.NET、C/C++、Ruby、PHP、Swift 和Dart/Flutter.
- 請求執行時可以安裝缺少的覆蓋依賴項； `dry_run` 永遠不會安裝軟體包。
  請參閱[儲存庫分析工具](docs/REPOSITORY_TOOLS.md) 以了解參數、輸出和安全性詳細資訊。
  請參閱[路徑和 URL 別名](docs/PATH_URL_ALIASES.md) 以縮短工具參數中的重複檔案路徑和 URL。

### 🖥 4 個介面 + VS Code 擴充

|模式|指令|目的|
|---|---|---|
| **指令列** | `uag` |指令|目的|
|---|---|---|
| **指令行** | `uag` | 快速的終端操作|
|基於瀏覽器的存取|
| **A2A 伺服器** | `瓦加` |用於多代理通訊的 Agent2Agent 協定 |
| **VS 程式碼** | — | [擴充](https://github.com/awaku7/agentcli/blob/main/docs/VVDE.md) 附面板、DE.md7/agentcli/blob/main/docs/V DE.md) 附面板、參考、重構錯誤、應用程式資訊、重構 18 月 18 月 48132 月2212 月22 月的新程式設計資訊 | [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) — 安裝、指令、鍵綁定與設定。

### 🏠 IoT裝置控制

- **BACnet**：讀取/寫入 BACnet/IP 裝置（HVAC、照明、功率計）。用於推播通知的 COV 訂閱
- **Modbus TCP**：讀取/寫入保持/輸入暫存器和線圈。基於輪詢的變更監控
- **OPC UA**：瀏覽位址空間、讀取/寫入變數、訂閱資料變更
- **SwitchBot**：雲端批量控制和 BLE 掃描/控制。基於輪詢的訂閱
- **ECHONET Lite**：發現、控制和訂閱來自家用電器（空調、燈、熱水器等）的INF通知
- **Matter**：用於狀態變化監控的讀取/寫入控制+屬性訂閱
- **UPnP**：設備發現與IGD連接埠轉送
  請參閱[IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯代理技能市場

`:skills mp_search`瀏覽[SkillsMP](https://skillsmp.com)和[ClawHub](https://clawhub.ai)以獲取社區技能。
安裝並擴充uag 的動態功能。

### 🤖 自動駕駛 (`:auto`)

uag 可以**在多個 LLM 輪中自主追求目標**。非常適合需要迭代細化的複雜、多步驟任務。

- **工作原理**：每輪都有一個主查詢（步驟 A），然後是審閱者判斷（步驟 B），決定“完成還是繼續？”
- **相同​​的提供商，相同的 API**：審閱者判斷使用與主查詢相同的代碼路徑 - 包括響應 API 支援。
- **單獨的判斷 LLM** （可選）：設定要使用的`UAGENT_AP_PROVIDER`為評審者提供不同的提供者/模型（例如，使用較便宜的模型進行評審）。
- **隨時退出**：按「x」鍵立即停止，即使是在回應中。或讓審閱者決定何時達到目標。
- **可設定**：`--max-rounds N` 來控制預算。
  請參閱 [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) 以取得完整文件。

### 🧩 批次狀態管理器

uag 可以追蹤長時間運行的多檔案任務的進度。當 LLM 處理數十個檔案時，「batch_state」會將待處理、已完成和失敗的檔案清單保留到磁碟。如果會話結束或一輪逾時，下一次運行將從停止處恢復 — 不會丟失任何內容。

### 🛡人機循環

` human_ask` 讓 LLM 暫停並在執行破壞性操作（檔案刪除、覆蓋、shell 命令）之前請求您確認。您保持控制。

### 🛑 中斷（c 鍵/停止按鈕）

隨時停止 LLM 回應生成，並將停止命令注入回 LLM。
|介面|如何打斷|
|---|---|
| **命令列** |在 LLM 串流傳輸期間按「c」鍵 — 當前回應停止，且「停止」作為使用者訊息傳送，以便 LLM 做出對應回應|
| \*\* 使用者介面\*\* | 紅色圖形機\*\* |21 \*22\*\*21 \*221. \*\*\*\*\*\*\*\* 按鈕（在 LLM 處理過程中自動出現）|
中斷作為「提示注入」工作：它不僅僅是中止，而是將「停止」作為用戶訊息反饋給 LLM，使其能夠優雅地結束或確認中斷。
按「x」鍵退出自動駕駛模式（請參閱[README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md))。

### 🕵️ 瀏覽器自動化和 Web 檢查器

兩個互補的基於 Playwright 的工具：

- **browser_playwright**：自動化真實的瀏覽器會話 - 導航、點擊、填寫表單、提取資料、處理多重串流。無頭或有頭均可工作。
- **playwright_inspector**：記錄瀏覽器轉換，捕捉每一步的 DOM 快照和螢幕截圖。對於調試 Web 互動或審核頁面隨時間的變化非常有用。

### 🔄 動態工具載入

`tool_catalog` 和 `tool_load` 可讓您在執行時發現並啟用工具。
無需在啟動時加載所有內容 - 僅在需要時啟動您需要的內容。

### 🦀 Rust 原生工具

`uuid_gen` 和 `slugify` 在 Rust 中實現（透過 PyO3）效能。
它們直接從預先建置的 `.pyd` 載入 — **不需要 `pip install`**。
外部開發人員還可以提供基於 Rust 的工具：在包裝器 `.py` 旁邊放置一個 `.pyd`，使用 `uagent.tools.rust_helper` 中的 `load_rust_pyd()`，並且
用戶無需任何額外依賴即可獲取該工具。請參閱
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)。

### 🌐 i18n / L10n

日本語 / English / 簡體中文 / 繁體中文 / 한국어 / Español / Français / Русский / 等。
設定`UAGENT_LANG`進行切換。請參閱 [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) 新增新的語言環境。
此自述文件的翻譯可在[docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)。

### 🔒加密的環境變數

將 API 金鑰和機密儲存在 `.env.sec` 中 - 一個加密的 `.env` 檔案。
使用 `uag_envsec` 來管理。

## 設定與詳細資訊

- **環境變數**：[docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **設定精靈**：``` python -m uagent.setup_`` 將 ```.env`加密為`.env.sec\`
- **回應 API**：為回應 API 模式設定 `UAGENT_RESPONSES=1` (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI)。自動啟用 Sakana AI (Fugu)。
- **開發者文件**：[DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **工具流程**： [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — 如何將工具傳送至 LLM（類型遮罩、tool_catalog、GPT-5.4+ 本機 tool_search）
  -小技巧\*\*PH_5 小技巧： [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## 專案理念

uag 渴望成為 \*\*您的 AI，在您的機器上，按照您的意願。 \*\*

- 無 SaaS 依賴性 — 本地運行
- 無提供者鎖定 — 隨時切換
- 無 UI 鎖定 — CLI / GUI / Web / A2A
- 無功能鎖定 — 透過工具和技能進行擴展

免費的 AI 代理體驗，來自供應商鎖定。

### ✨ 創建您自己的工具

為 uag 編寫新工具非常簡單 - 使用
`TOOL_SPEC` 和 `run_tool()` 創建一個 `.py` 文件，將其放置在 \`UAGENT_EXTERNAL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIRL_TOOLS_DIR）》。對於 Rust 開發人員，為使用者提供預先建置的“.pyd”，
對使用者零額外依賴。

請參閱 [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
了解逐步指南。

## 貢獻

歡迎貢獻！錯誤報告、功能建議、文件改進、翻譯和拉取請求 - 全部讚賞。

- **問題**：針對錯誤或功能請求開啟 GitHub 問題。
- **拉取請求**：分叉儲存庫，進行更改並提交 PR。請參閱 [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) 以了解開發設定和指南。
- **翻譯**：歡迎自述文件翻譯和語言環境新增。請參閱 [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)。
- **工具和技能**：可以透過市場貢獻新的工具插件和代理技能。

### 開發檢查（PR 之前）

首先安裝僅測試依賴項。它們不包含在運行時
依賴列表中：

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

在推送之前運行 PHPH_install black ruff

```

在推送src測試
python -m black --check src測試
python腳本/tool_json_i18n_batch.py狀態
python -m pytest -q .
```

為了更快的本地迭代，只執行受影響的測試：只執行受影響
\<affected_area>

````

相關時的其他檢查：

```bash
python -m py_compile src/uagent/
mypy src/uagent
````

⏅

script/po_qc_summary.py\`。

運行時策略（詳細資訊請參閱[DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1)：幫助程式引發而不是 `sys.exit`；工具主機將字串工具無法終止。啟動快速失敗退出仍然是故意的。

## 架構和操作不變量

請參閱 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 了解涵蓋 A2A 生命週期、I18N 上下文、可選依賴項安裝、工具安全、提供程序功能、OAuth 信任邊界、結構化事件和驗收驗證的持久合約。

## 企業策略引擎

支援工具、提供者、憑證、MCP 伺服器、網路、技能和外掛程式的組織級策略。將「UAGENT_POLICY_FILE」設定為 JSON/YAML 策略檔案；請參閱 [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) 以了解設定範例、角色、確認和白名單。

### 運行時恢復與編排

請參閱 [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.) / \[MULNUL_RUNm/M用於持久恢復、依賴項感知執行、多代理編排和遠端 A2A 使用。

請參閱 [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) 以了解共享運行時領導者租約協調。
