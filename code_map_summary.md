# agentcli コードマップ概要

## 解析対象

- リポジトリ: `C:\KAIHATSU\agentcli`
- 解析ファイル数: **662**
- 解析内容: シンボル定義、プロジェクト依存関係、ファイル間の import 関係

## プロジェクト構成

| 領域 | 構成 |
|---|---|
| Backend | Python (`src/uagent`) |
| Rust 拡張 | Cargo (`src/uagent/tools_rust`) |
| Frontend | Svelte / Vite (`frontend`) |
| VS Code 拡張 | TypeScript (`vscode-extension`) |
| MCP サーバー | Python (`mcps`) |
| テスト | pytest 系 (`tests`) |

## 検出されたマニフェスト

- `pyproject.toml`
- `src/uagent/tools_rust/Cargo.toml`
- `frontend/package.json`
- `vscode-extension/package.json`

## 主要モジュール

### コア・実行基盤

- `src/uagent/cli.py`: CLI エントリーポイント、入力処理、履歴管理
- `src/uagent/core.py`: 状態管理、ログ、プロンプト、コンテキスト圧縮
- `src/uagent/uagent_llm.py`: LLM ラウンド実行、ツール呼び出しループ
- `src/uagent/util_tools.py`: コマンド処理とツール連携
- `src/uagent/web.py`: Web UI、WebSocket、セッション管理

### LLM プロバイダー

`src/uagent/providers` に以下のプロバイダー実装があります。

- OpenAI / Azure
- Gemini
- Claude
- Grok / xAI
- DeepSeek
- Ollama
- OpenRouter
- Bedrock
- ZAI
- Together
- Novita
- Vercel
- PFN

Responses API、ストリーミング、推論レベル、画像・音声入力などの互換処理も含まれます。

### ツール基盤

`src/uagent/tools` に多数のツールを実装しています。

- ファイル操作、検索、差分、パッチ
- Python 実行、各種コード解析
- PDF、PowerPoint、Excel、Word 文書処理
- Web 検索、HTTP、ブラウザー操作
- AWS、Azure、GCP API
- BACnet、Modbus、OPC UA、ECHONET Lite、Matter
- MQTT、UPnP、SwitchBot、BLE
- 画像生成・解析、音声入出力
- スケジューラー、メモリ、プラグイン、スキル
- MCP クライアント、OAuth、ステートレス HTTP
- A2A クライアント・サーバー

### MCP

- `src/uagent/tools/mcp`: MCP プロトコル、HTTP/stdio、OAuth、PKCE、トークン管理
- `mcps/ucp_mcp_server_main.py`: UCP 対応 MCP サーバー
- MCP の legacy / stateless HTTP モードに対応

### A2A

- `src/uagent/a2a/client.py`: A2A クライアント
- `src/uagent/a2a/server.py`: A2A サーバー
- `src/uagent/a2a/task_store.py`: タスク管理
- Bearer 認証、ストリーミング、タスクの取得・キャンセルに対応

### フロントエンド・VS Code 拡張

- Svelte 5 / Vite による Web フロントエンド
- WebSocket ベースのチャット、設定、セッション、ツール操作
- VS Code 拡張からチャット、コード説明、リファクタリング、診断修正を実行

### プラグイン・スキル

- プラグインの検出、インストール、検証、有効化・無効化
- スキル、エージェント、フック、MCP サーバー、コマンドの統合
- マーケットプレイスおよび依存関係解決に対応

### Rust 拡張

`src/uagent/tools_rust` に PyO3 ベースの Rust 拡張があります。

- UUID 生成
- slugify

## 依存関係

### Cargo

- `pyo3` 0.29
- `uuid` 1.x

### npm

- Svelte 5
- Vite 6
- `@sveltejs/vite-plugin-svelte`
- TypeScript 5
- VS Code 型定義・パッケージングツール

依存関係の競合は検出されませんでした。

## テスト

`tests` 以下には、次の領域を含む広範なテストがあります。

- ツール入出力と安全性
- LLM プロバイダー互換性
- MCP / OAuth
- プラグインとスキル
- コード解析ツール
- ネットワーク・PCAP 解析
- IoT プロトコル
- WebSocket / Web UI
- 国際化・翻訳
- メモリ・セッション・スケジューラー

## 依存関係グラフの特徴

解析では、CLI と `core.py` を中心に、LLM 実行層、プロバイダー層、ツール登録層、WebSocket 層、プラグイン層へ広がる import 関係が確認されました。

特に中心性が高いモジュールは次のとおりです。

- `src/uagent/core.py`
- `src/uagent/uagent_llm.py`
- `src/uagent/tools/__init__.py`
- `src/uagent/util_tools.py`
- `src/uagent/plugin_shared.py`
- `src/uagent/providers/responses_common.py`

## 注意点

- 生成済みの `src/uagent/static/assets/index.js` は圧縮・バンドル済みのため、シンボル抽出結果が大量かつ難読化された名前になります。
- 全体マップは大規模なため、詳細調査では `src/uagent/core.py`、`uagent_llm.py`、`tools/__init__.py` などに絞るのが適しています。
