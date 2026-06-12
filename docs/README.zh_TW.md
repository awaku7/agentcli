<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (本地 AI 智能體)

uag 是一款能在您的本地 PC 上執行 **命令**、操作 **檔案** 並讀取 **各種數據格式**（PDF/PPTX/Excel 等）的互動式智能體。它提供三種介面：CLI、GUI 和 Web。

uag 的設計旨在**讓您擺脫廠商綁定的應用程式**：使用符合您工作流程的介面，切換供應商，並始終掌控您的環境。

GitHub: https://github.com/awaku7/agentcli

## 安裝

您可以透過 pip 安裝 `uag`：

```bash
pip install uag
```

安裝後，首次執行 `uag` 將自動啟動 **互動式設定精靈** 以配置您的環境變數。有關配置和加密的詳細資訊，請參閱 **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**。

## 主要功能

- **實用工具集**：配備用於檔案操作、網路搜尋、數據提取（PDF/PPTX/Excel）、圖像生成和分析的工具，均可在本地環境中執行。
- **多供應商支援**：支援 OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA。
- **靈活的介面**：
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (模型上下文協定)**：支援連接到外部 MCP 工具伺服器。
- **會話持續性**：即使切換供應商或模型，也能保持對話上下文。
- **Web 檢查器**：使用 `playwright_inspector` 自動保存瀏覽器跳轉、DOM 和截圖。
- **內建文件**：使用 `uag docs` 命令即時訪問詳細的內部文件。

## 使用方法

### 啟動與退出

從終端機執行 `uag` 即可開始。輸入 `:exit` 退出。

### A2A (智能體間通信) 伺服器

您可以啟動一個獨立於現有介面的 A2A 相容 HTTP 伺服器。

```bash
uaga
# 或 python -m uagent.a2a.server
```

### Responses API 說明

如果設定 `UAGENT_RESPONSES=1`，支援的提供者將使用 Responses API：OpenAI / Azure / Bedrock / OpenRouter / Ollama。
Gemini / Claude / Vertex AI 使用各自的原生 API 路徑，不在 Responses API 的涵蓋範圍內。
對於其他提供者，uag 會回退到提供者專用路徑或 chat-completions 流程。

請參閱 [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)，了解 `UAGENT_A2A_*` 設定，例如驗證、主機、埠、重新載入、公開基礎 URL、並行數和引擎。

### 實用技巧 (持續與控制)

- `:tools`：顯示已載入工具的列表。
- `:logs [n]`：顯示會話日誌（`n` 用於指定條目數）。
- `:load <index>`：載入過去的會話以恢復對話。
- `:skills`：選擇並載入智能體技能（額外的角色或指令）。
- `:shrink [n]`：整理歷史記錄，僅保留最後 `n` 條訊息以節省 Token。

## 配置與詳情

### 環境變數與設定

有關詳細設定（API 金鑰、顯示語言 `UAGENT_LANG`、歷史壓縮設定等），請參閱 **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**。

- **設定**：透過 `python -m uagent.setup_cli` 進行互動式配置。
- **加密**：使用 `uag_envsec` 工具安全地加密您的 `.env` 檔案。
- **更新**：使用 `uag_envsec add --file .env.sec --key NAME --value VALUE`，可在現有的加密檔案中新增或更新變數。

### 開發者與國際化

- **開發者文件**：[`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **添加語言區域**：[`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **其他語言的 README**：[`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
