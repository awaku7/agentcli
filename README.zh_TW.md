# uag (uagent)

uag 是一個在本地環境中運行的通用工具執行代理。它可以透過命令行界面 (CLI) 與用戶交互，並根據指示執行文件操作、網絡搜索、Python 腳本運行等多種任務。

## 主要功能

- **本地文件操作**：讀取、寫入、編輯和搜索文件。
- **信息檢索**：使用 DuckDuckGo 進行網絡搜索，提取網頁內容。
- **代碼執行**：安全地運行 Python 腳本和 PowerShell 命令。
- **多媒體處理**：生成圖像、讀取 PDF/PPTX 文件、截屏。
- **多語言支持**：支持包括中文、日文和英文在內的多種語言。
- **MCP (Model Context Protocol) 支持**：可以連接到外部 MCP 服務器以擴展其功能。

## 安裝方法

您可以使用 pip 從 PyPI 安裝：

```bash
pip install uag
```

首次運行時，會自動啟動設置向導。

## 快速入門

安裝後，只需輸入以下命令即可啟動：

```bash
uag
```

啟動後，您可以向代理提出如下請求：
- "讀取當前目錄下的 README 並總結其內容。"
- "在 Web 上搜索最新的 AI 新聞並製作摘要。"
- "將 images 文件夾中的所有 PNG 文件壓縮為 ZIP。"

## 配置（環境變量）

uag 的行為可以透過環境變量進行配置。詳細信息請參閱：
- [ENVIRONMENT.md (English)](ENVIRONMENT.md)

## 文檔

- [README.md (English)](README.md)
- [README.ja.md (Japanese)](README.ja.md)

## 許可證

基於 Apache License 2.0 許可證發布。
