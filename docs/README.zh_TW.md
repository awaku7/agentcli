<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>你的 AI 模型。你的工具。你的環境。</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">其他語言</a></p>

---

**UAG 是開放原始碼、以本機執行為優先的 AI 代理執行環境。** 它能將你選擇的語言模型與實際使用的工具及系統連接，透過一致的介面處理程式碼、檔案、瀏覽器、服務與裝置，而不必將工作流程綁定單一模型供應商。

| **自行選擇模型** | **連接實際工具** | **保有掌控權** |
| :--- | :--- | :--- |
| OpenAI、Claude、Gemini、Grok、Bedrock、Ollama 等雲端及本機模型 | 檔案、程式碼、Web、MCP、Agent Skills、外掛、雲端服務及 IoT | 本機執行、人工確認、認證資料儲存與可設定的政策 |

> UAG 是**代理執行層，而非模型供應商**。是否呼叫外部模型或已連接的服務取決於你的設定。「本機優先」不表示預設完全離線，也不保證所有工具都在隔離環境中執行。

## 快速開始
<!-- README-SYNC:quick-start -->

需要 **Python 3.11 或更新版本**。從 [PyPI](https://pypi.org/project/uag/) 安裝 UAG，接著啟動互動式命令列：

~~~bash
python -m pip install --upgrade uag
uag
~~~

首次啟動時，設定精靈會協助選擇模型供應商及設定認證資料。你也可以使用環境變數或認證資料儲存區。若要預先安裝更多模型及工具相依套件，請執行：

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

接著可以試試以下要求：

~~~text
> 這個 Git 儲存庫有哪些變更？請摘要風險。
> 搜尋此程式庫的最新文件，並說明遷移步驟。
> 檢查這些檔案並產生精簡報告。
> :help
~~~

初次使用可閱讀 Windows 安裝指南（包含 Git 與虛擬環境的準備）以及環境設定參考： [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## 使用介面
<!-- README-SYNC:interfaces -->

多種操作介面共用同一個代理執行環境及工具登錄表。

| 介面 | 啟動方式 | 適用用途 |
| :--- | :--- | :--- |
| **CLI** | `uag` | 終端機工作與自動化 |
| **桌面** | `uagg` | 原生桌面對話 |
| **Web** | `uagw` | 瀏覽器中的對話及房間 |
| **A2A** | `uaga` | 代理之間的整合 |
| **VS Code** | [擴充功能指南](VSCODE.md) | 與程式碼編輯並行工作 |

桌面與 Web 介面需要額外的相依套件，快速入門的 `uag[core,providers,tools]` 安裝並未包含這些套件：

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Web 伺服器也可能在啟動時嘗試安裝 FastAPI 和 Uvicorn。預先安裝即可避免依賴執行時自動安裝。詳細資訊請參閱： [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## UAG 可以完成什麼
<!-- README-SYNC:capabilities -->

| 能力 | UAG 提供的功能 |
| :--- | :--- |
| **與模型無關的工作流程** | 透過 `UAGENT_PROVIDER` 切換雲端或本機模型供應商，不必重新撰寫工具 |
| **程式碼與檔案操作** | 儲存庫導覽、Git 檢查、程式碼分析、測試、檔案操作與瀏覽器自動化 |
| **可擴充的工具** | 200 多種工具；以 `tool_catalog` 和 `tool_load` 動態探索與載入；支援 Python 與 Rust 自訂工具 |
| **互連代理** | MCP 伺服器、A2A、相容 Claude Code 的外掛、Agent Skills 及子代理 |
| **長時間任務** | 自動駕駛模式、獨立唯讀操作並行執行、排程工作、重新啟動後復原及持久化工作階段 |
| **不僅限於終端機** | 雲端、通訊、文件、媒體、即時語音與支援的 IoT 通訊協定 |

### 一個執行環境連結多種系統
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**支援的模型供應商範例**列於下方；個別設定請參閱環境設定說明。

### 使用技能與外掛擴充
<!-- README-SYNC:extensions -->

不修改核心程式碼也能擴充 UAG。可從 SkillsMP 或 ClawHub 安裝 Agent Skills、連接 MCP 伺服器，或載入包含工具、技能、代理與 hooks 的 Claude Code 相容外掛。

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

自訂工具可提供 `TOOL_SPEC` 與 `run_tool()`；也支援以 Rust 為基礎的工具。請參閱下列開發指南： [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## 支援實際工作流程
<!-- README-SYNC:workflows -->

### 情境與記憶
<!-- README-SYNC:context-memory -->

大量工具結果可儲存為**成品資料（Artifacts）**，不必占用模型的活動情境。稍後可使用 `artifact_read` 只取回所需部分。工作階段預設儲存於 SQLite，並支援歷史搜尋與明確的記憶檢視流程。

- [Context compression](CONTEXT_COMPRESSION.zh_TW.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### 自動化與協作
<!-- README-SYNC:automation -->

UAG 支援獨立唯讀操作並行執行、多代理協調、工作階段復原及多回合任務的自動駕駛模式。使用 `:auto` 啟動；按 **F12** 可中斷目前的回答並要求停止自動駕駛。

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 安全性與可觀測性
<!-- README-SYNC:security -->

敏感操作可以要求透過 `human_ask` 進行人工確認。認證資料可存於作業系統的認證管理員或加密檔案。經設定後，Web 介面支援 OIDC 登入及存取控制。OpenTelemetry 追蹤和指標屬於**選擇性啟用**功能。

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

這些控制措施皆可設定，**並不保證任意工具執行都受沙箱隔離**。向不受信任的使用者或網路公開 UAG 前，請先閱讀部署與政策指南。

### 語言、裝置與語音
<!-- README-SYNC:languages -->

UAG 提供 **38 個地區語言版本**（英文及 37 種翻譯）、可選用的全雙工語音整合，以及 SwitchBot、Matter、ECHONET Lite、BACnet、Modbus TCP、OPC UA 等系統的工具。

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## 文件
<!-- README-SYNC:documentation -->

可從以下文件開始閱讀，再深入各項主題：

| 開始閱讀 | 深入了解 |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

也歡迎瀏覽完整文件目錄及其他語言版本： [Documentation](./) · [Other languages](README.translations.md).

## 開發與貢獻
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

提交涉及 **Python 程式碼**變更的拉取請求之前，請執行相關測試及專案檢查：

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

貢獻規範與開發指南如下。歡迎問題回報、文件改善、工具、翻譯及聚焦的拉取請求： [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## 授權條款
<!-- README-SYNC:license -->

UAG 依下列授權條款發行： [Apache License 2.0](../LICENSE).
