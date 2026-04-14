# uag (uagent)

uag 是一个在本地环境中运行的通用工具执行代理。它可以通过命令行界面 (CLI) 与用户交互，并根据指示执行文件操作、网络搜索、Python 脚本运行等多种任务。

## 主要功能

- **本地文件操作**：读取、写入、编辑和搜索文件。
- **信息检索**：使用 DuckDuckGo 进行网络搜索，提取网页内容。
- **代码执行**：安全地运行 Python 脚本和 PowerShell 命令。
- **多媒体处理**：生成图像、读取 PDF/PPTX 文件、截屏。
- **多语言支持**：支持包括中文、日文和英文在内的多种语言。
- **MCP (Model Context Protocol) 支持**：可以连接到外部 MCP 服务器以扩展其功能。

## 安装方法

您可以使用 pip 从 PyPI 安装：

```bash
pip install uag
```

首次运行时，会自动启动设置向导。

## 快速入门

安装后，只需输入以下命令即可启动：

```bash
uag
```

启动后，您可以向代理提出如下请求：
- "读取当前目录下的 README 并总结其内容。"
- "在 Web 上搜索最新的 AI 新闻并制作摘要。"
- "将 images 文件夹中的所有 PNG 文件压缩为 ZIP。"

## 配置（环境变量）

uag 的行为可以通过环境变量进行配置。详细信息请参阅：
- [ENVIRONMENT.md (English)](ENVIRONMENT.md)

## 文档

- [README.md (English)](README.md)
- [README.ja.md (Japanese)](README.ja.md)

## 许可证

基于 Apache License 2.0 许可证发布。
