<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag——通用人工智慧網關</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## 為什麼是uag？

**擺脫供應商鎖定。 **大多數人工智慧助理會將您與特定的供應商或雲端服務連結起來。 uag 是不同的。

- **在您的電腦上本機運作**。您的資料保留在您身邊（您進行的 API 呼叫除外）。
- **提供者自由**：OpenAI、Claude、Gemini、DeepSeek、Ollama、Azure、Bedrock、HuggingFace...超過 15 個提供者，均可透過單一介面存取。透過重新配置環境變數在它們之間進行交換—無需重新安裝，無需遷移。
- **131 個工具**：檔案 I/O、網路搜尋、影像產生、Gmail、BLE 裝置掃描、MCP 伺服器整合 — **76 個工具是並行安全的**（最多 8 個透過執行緒池並發執行，可透過「UAGENT_PARALLEL_WORKERS」進行設定）。當 LLM 一次觸發多個工具呼叫時，uag 會自動並行化它們。
- **3 UI + A2A**：CLI、GUI、Web 和代理到代理協定。相同的引擎，任何接口。
- **物聯網就緒**：SwitchBot、ECHONET Lite、Matter、UPnP — 透過人工智慧控制您的家庭設備。
- **代理技能**：從市場安裝社群建立的技能。無限延伸uag。

uag 是**您的人工智慧助手，按照您的意願**。不依賴提供者、不依賴介面、不依賴平台。

## 快速入門

```bash
pip install uag
uag
```

首次啟動時，設定精靈將引導您完成提供者設定。
有關所有環境變量，請參閱 [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)。

＃＃ 特徵

### 🧠 多提供者架構

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude/

所有提供者共享相同的工具集和介面。透過設定“UAGENT_PROVIDER”進行切換－無需更改程式碼，無需單獨安裝。

### ⚡ 平行工具執行

當 LLM 同時要求多個工具時，uag **會自動並行化**它們。
76 個工具被標記為“x_parallel_safe”，並透過“ThreadPoolExecutor”並發執行（預設為 8 個執行緒；設定“UAGENT_PARALLEL_WORKERS”進行更改）。

**範例**：詢問「檢查北歐首都的天氣」 → LLM 觸發 `search_web` × 5 個國家 → 所有 5 個搜尋並行運行 → 一批收集結果。

只讀工具（檔案搜尋、哈希計算、目錄列表、翻譯、資料庫查詢等）被積極並行化。

### 🔄 會話連續性

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 工具

|類別 |工具|
|---|---|
| **檔案操作** |讀/寫/建立/刪除/搜尋/grep/hash/zip，parse_eml（.eml 檔案）|
| **網頁** | fetch_url、search_web、螢幕截圖、browser_playwright |
| **媒體** |產生影像、分析影像、img2img、音訊語音、音訊轉錄 |
| **檔案** | PDF/PPTX/DOCX/RTF/ODT擷取、Excel結構化擷取|
| **通訊** | gmail_send、gmail_read、bluesky、discord_channel、teams_webhook — 請參閱 [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **物聯網** | SwitchBot（雲端 + BLE）、ECHONET Lite、Matter、UPnP |
| **開發工具** | git_ops、python_compile、lint_format、run_tests、db_query、**13 個原始碼導航器（idx 系列）** |
| **MCP** |連接到外部 MCP 伺服器、列出工具、執行 |
| **A2A** |代理間通訊（與其他 uag 實例或 A2A 相容伺服器）|
| **系統** |環境變數、系統規格、時間、日期計算 |
| **來源導航** | **13 個 idx 工具**，適用於 Python、PHP、TypeScript、Java、C#、Dart、C/C++、Rust、Go、Swift、Kotlin、COBOL — 無需讀取整個檔案即可取得函數/類別索引或特定定義 |

### 🖥 4 個介面 + VS 代碼擴展

|模式|命令|目的|
|---|---|---|
| **命令列** | `uag` |快速的終端機操作 |
| **圖形使用者介面** | `uagg` |透過 tkinter 的桌面 UI |
| **網頁** | `uagw` |基於瀏覽器的存取 |
| **A2A 伺服器** | `瓦加` |用於多代理通訊的Agent2Agent協定|
| **VS 程式碼** | — | [擴充](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) 附有聊天面板、解釋、重構、修復錯誤和工具樹視圖 |

有關 VS Code 擴充功能的詳細資訊 - 安裝、命令、鍵綁定和配置，請參閱 [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md)。

### 🏠 物聯網設備控制

- **SwitchBot**：雲端批量控制和BLE掃描/控制
- **ECHONET Lite**：發現並控製本地網路上的家用電器（空調、燈、熱水器等）
- **事項**：控制器/橋接器/設備拓樸的唯讀檢查
- **UPnP**：設備發現和 IGD 連接埠轉發

請參閱 [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

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

完整文檔，請參閱 [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)。

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
| **桌面圖形使用者介面** |點選紅色 ******** 按鈕（LLM 處理期間自動出現）|

中斷充當「提示注入」：它不僅僅是中止，而是將「停止」作為使用者訊息回饋給 LLM，使其能夠優雅地結束或確認中斷。

按下「x」鍵退出自動駕駛模式（請參閱 [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)）。

### 🕵️ 瀏覽器自動化和 Web 檢查器

兩個基於 Playwright 的互補工具：

- **browser_playwright**：自動化真實的瀏覽器會話 - 導航、點擊、填寫表單、提取資料、處理多頁面流。無頭或有頭均可工作。
- **playwright_inspector**：記錄瀏覽器轉換，捕捉每一步的 DOM 快照和螢幕截圖。對於調試 Web 互動或審核頁面隨時間的變化很有用。

### 🔄 動態工具加載

`tool_catalog` 和 `tool_load` 可讓您在執行時發現並啟用工具。
無需在啟動時加載所有內容 - 僅在需要時啟動您需要的內容。

### 🌐 國際化 / 本土化

日本文 / English / 簡體中文 / 繁體中文 / 한국어 / Español / Français / Русский / 等。
設定`UAGENT_LANG`進行切換。請參閱 [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) 新增新的區域設定。

本自述文件的翻譯可在 [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md) 中找到。

### 🔒 加密環境變量

將 API 金鑰和機密儲存在「.env.sec」中—一個加密的「.env」檔案。
使用“uag_envsec”進行管理。

## 配置和詳細信息

- **環境變數**：[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **設定精靈**：`python -m uagent.setup_cli`
- **加密的 env**: `uag_envsec` — 將 `.env` 加密為 `.env.sec`
- **回應 API**：為回應 API 模式設定「UAGENT_RESPONSES=1」（OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI）。自動啟用 Sakana AI (Fugu)。
- **開發人員文件**：[DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **LLM小技巧**：[SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## 專案理念

uag 渴望成為 **您的人工智慧，在您的機器上，按照您的條件。 **

- 無 SaaS 依賴性 — 在本地運行
- 沒有供應商鎖定－隨時切換
- 無 UI 鎖定 — CLI / GUI / Web / A2A
- 無功能鎖定－透過工具和技能進行擴展

免費的人工智慧代理體驗，不受供應商鎖定。
