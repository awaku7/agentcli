# agentcli コードマップ概要

## 解析対象

- リポジトリ: `C:\KAIHATSU\agentcli`
- 生成元: `code_map`（JSON）
- 解析ファイル数: **768**
- ファイル間リレーション数: **2,416**
- 解析内容: シンボル定義、プロジェクト依存関係、ファイル間の import / require 関係

## 検出された言語

| 言語 | ファイル数 |
|---|---:|
| Python | 740 |
| JavaScript | 7 |
| TypeScript | 6 |
| Rust | 4 |
| C# | 3 |
| C++ | 1 |
| COBOL | 1 |
| Dart | 1 |
| Go | 1 |
| Java | 1 |
| Kotlin | 1 |
| PHP | 1 |
| Swift | 1 |

## プロジェクト情報

- プロジェクト参照ファイル: 6
- 宣言済み依存関係: 9
- 依存関係の衝突: 0
- 依存関係エッジ: 0
- 推移依存関係: 0

## 主要領域

- `src/uagent`: Python製のCLI / GUI / Web / A2Aエージェント本体
- `src/uagent/providers`: LLMプロバイダー実装と互換処理
- `src/uagent/tools`: ファイル、Web、クラウド、IoT、MCP、文書処理などのツール群
- `src/uagent/tools_rust`: Rust拡張ツール
- `frontend`: Webフロントエンド
- `vscode-extension`: VS Code拡張
- `mcps`: MCPサーバー
- `tests`: pytestテスト

## 生成ファイル

- 詳細なJSONコードマップ: `outputs/code_map/code_map_20260819_102200_965208.json`
- `include_symbols=true`
- `include_relations=true`
- `project_only=false`
