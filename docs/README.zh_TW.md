<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag 標誌" width="720">
</p>

<h1 align="center">uag — 通用人工智慧閘道</h1>

<p align="center">
  <b>U</b>universal <b>A</b>I <b>G</b>ateway — 您的環境，您的自由。
</p>

<p align="center">
  文件操作/網路搜尋/影像產生和分析/PDF和Excel提取/物聯網控制/MCP整合<br>
  超過 15 個提供者/3 個 UI/平行工具執行/代理技能市場
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">用您的語言閱讀本文</a>
</p>

---

## 為什麼是uag？

**擺脫供應商鎖定。 **大多數人工智慧助理會將您與特定的供應商或雲端服務連結起來。 uag 是不同的。

- **在您的電腦上本機運作**。您的資料保留在您身邊（您進行的 API 呼叫除外）。
- **提供者自由**：OpenAI、Claude、Gemini、DeepSeek、Ollama、Azure、Bedrock...超過 15 個供應商，皆可透過單一介面存取。透過重新配置環境變數在它們之間進行交換—無需重新安裝，無需遷移。
- **112 種工具**：檔案 I/O、網路搜尋、影像產生、BLE 裝置掃描、MCP 伺服器整合 — 並且 **其中 66 種工具並行運作**。當 LLM 一次觸發多個工具呼叫時，uag 會透過執行緒池自動執行它們。
- **4 UI + A2A**：CLI、GUI、Web 和代理到代理協定。相同的引擎，任何接口。
- **物聯網就緒**：SwitchBot、ECHONET Lite、Matter、UPnP — 透過人工智慧控制您的家庭設備。
- **代理技能**：從市場安裝社群建立的技能。無限延伸uag。

uag 是**您的人工智慧助手，按照您的意願**。不依賴提供者、不依賴介面、不依賴平台。

## 快速入門

```bash
pip install uag
uag
````

首次啟動時，設定精靈將引導您完成提供者設定。
有關所有環境變量，請參閱 [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)。

## 特點

### 🧠 多提供者架構

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / HuggingFace / 阿里雲 (Qwen) / KIMI (Moonshot AI) / 小米 MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)** / LM Studio / MiniMax MiMo

所有提供者共享相同的工具集和介面。透過設定“UAGENT_PROVIDER”進行切換－無需更改程式碼，無需單獨安裝。

### ⚡ 平行工具執行

當 LLM 同時要求多個工具時，uag **會自動並行化**它們。
55 個工具被標記為“x_parallel_safe”，並透過 4 個線程“ThreadPoolExecutor”並發執行。

**範例**：詢問「檢查北歐首都的天氣」 → LLM 觸發 `search_web` × 5 個國家 → 所有 5 個搜尋並行運行 → 一批收集結果。

只讀工具（檔案搜尋、哈希計算、目錄列表、翻譯、資料庫查詢等）被積極並行化。

### 🔄 會話連續性

- **使用「UAGENT_PROVIDER」在會話中切換提供者** — 保留對話歷史記錄。
- **使用 `:load <index>` 重新載入過去的會話** — 從上次中斷的地方繼續。
- **工具結果快取**避免重複呼叫相同工具時冗餘的重新執行。

### 🛠 112 工具

|類別 |工具|
|---|---|
| **檔案操作** |讀取/寫入/建立/刪除/搜尋/grep/雜湊/zip |
| **網頁** | fetch_url、search_web、螢幕截圖、browser_playwright |
| **媒體** |產生影像、分析影像、img2img、音訊語音、音訊轉錄 |
| **檔案** | PDF/PPTX/DOCX/RTF/ODT擷取、Excel結構化擷取 |
| **物聯網** | SwitchBot（雲端 + BLE）、ECHONET Lite、Matter、UPnP |
| **開發工具** | git_ops、python_compile、lint_format、run_tests、db_query、**11 個原始碼導航器 (idx 系列)** |
| **MCP** |連接到外部 MCP 伺服器、列出工具、執行 |
| **A2A** |代理間通訊（與其他 uag 實例或 A2A 相容伺服器）|
| **系統** |環境變數、系統規格、時間、日期計算 |

### 🖥 3 個介面 + A2A + VS Code

|模式|命令|目的|
|---|---|---|
| **命令列** | `uag` |快速的終端機操作 |
| **圖形使用者介面** | `uagg` |透過 tkinter 的桌面 UI |
| **網頁** | `uagw` |基於瀏覽器的存取 |
| **A2A 伺服器** | `uaga` |用於多代理通訊的Agent2Agent協定|
| **VS Code** | — | Extension (Chat Panel, Explain, Refactor, Fix Error, Tools Tree View) — see [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) |

### 🏠 物聯網設備控制

- **SwitchBot**：雲端批量控制和BLE掃描/控制
- **ECHONET Lite**：發現並控製本地網路上的家用電器（空調、燈、熱水器等）
- **事項**：控制器/橋接器/設備拓樸的唯讀檢查
- **UPnP**：設備發現和 IGD 連接埠轉發

請參閱 [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 代理技能市場

`:skills mp_search` 瀏覽 [SkillsMP](https://skillsmp.com) 和 [ClawHub](https://clawhub.ai) 以獲取社區技能。
即時安裝並擴充 uag 的功能。

### 🤖 Auto-Pilot (`:auto`)

uag can **autonomously pursue a goal across multiple LLM rounds**. Perfect for complex, multi-step tasks that need iterative refinement.

- **How it works**: Each round has a main query (Step A) followed by a reviewer judgment (Step B) that decides "COMPLETE or CONTINUE?"
- **Same provider, same API**: The reviewer judgment uses the identical code path as the main query — including Responses API support.
- **Exit anytime**: Press `x` key to stop immediately, even mid-response. Or let the reviewer decide when the goal is met.
- **Configurable**: `--max-rounds N` to control the budget.

See [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) for full documentation.

### 🧩 批次狀態管理器

uag 可以追蹤長時間運行的多檔案任務的進度。當 LLM 處理數十個檔案時，「batch_state」會將待處理、已完成和失敗的檔案清單保留到磁碟。如果會話結束或一輪逾時，下一次運行將從停止處繼續 - 不會丟失任何內容。

### 🛡 人機交互

`human_ask` 允許 LLM 在執行破壞性操作（檔案刪除、覆蓋、shell 命令）之前暫停並要求您確認。您保持掌控。

### 🛑 Interrupt (c-key / Stop button)

Stop LLM response generation at any time and inject a stop command back to the LLM.

| Interface | How to interrupt |
|---|---|
| **CLI** | Press `c` key during LLM streaming -- the current response stops, and `"Stop"` is sent as a user message so the LLM responds accordingly |
| **WEB UI** | Click the red **■ Stop** button (appears automatically during LLM processing) |
| **Desktop GUI** | Click the red **■** button (appears automatically during LLM processing) |

The interrupt works as "prompt injection": instead of just aborting, it feeds `"Stop"` back to the LLM as a user message, allowing it to gracefully conclude or acknowledge the interruption.

Press `x` key to exit auto-pilot mode (see `:auto` command).

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
- **回應 API**：為回應 API 模式設定「UAGENT_RESPONSES=1」（OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI）
- **開發人員文件**：[DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **LLM小技巧**：[SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## 專案理念

uag 渴望成為 **您的人工智慧，在您的機器上，按照您的條件。 **

- 無 SaaS 依賴性 — 在本地運行
- 沒有供應商鎖定－隨時切換
- 無 UI 鎖定 — CLI / GUI / Web / A2A
- 無功能鎖定－透過工具和技能進行擴展

免費的人工智慧代理體驗，不受供應商鎖定。