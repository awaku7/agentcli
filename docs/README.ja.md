<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — ユニバーサル AI ゲートウェイ</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — あなたの環境、あなたの自由。
</p>

<p align="center">
  ファイル操作 / Web 検索 / 画像生成および分析 / PDF および Excel 抽出 / IoT 制御 / MCP 統合<br>
  15 を超えるプロバイダー / 3 つの UI / 並列ツール実行 / エージェント スキル マーケットプレイス
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">これをあなたの言語で読んでください</a>
</p>

---

## なぜuagなのか?

**ベンダー ロックインから解放されます。** ほとんどの AI アシスタントは、ユーザーを特定のプロバイダーまたはクラウド サービスに結び付けます。ワグは違うよ。

- **お使いのマシン上でローカルに実行**。データは保管されます (API 呼び出しを除く)。
- **プロバイダーの自由**: OpenAI、Claude、Gemini、DeepSeek、Ollama、Azure、Bedrock...15 以上のプロバイダーに、単一のインターフェイスからすべてアクセス可能。環境変数を再構成することでそれらを切り替えます。再インストールや移行は必要ありません。
- **131 ツール**: ファイル I/O、Web 検索、画像生成、Gmail、BLE デバイス スキャン、MCP サーバー統合 - **76 は並列セーフです** (スレッド プール経由で最大 8 つが同時に実行、`UAGENT_PARALLEL_WORKERS` 経由で構成可能)。 LLM が複数のツール呼び出しを同時に起動すると、uag はそれらを自動的に並列化します。
- **4 UI + A2A**: CLI、GUI、Web、およびエージェント間プロトコル。同じエンジン、どのインターフェイスでも。
- **IoT ready**: SwitchBot, ECHONET Lite, Matter, UPnP — control your home devices through AI.
- **エージェント スキル**: コミュニティが構築したスキルをマーケットプレイスからインストールします。 uagを無限に拡張します。

uag は **あなたの条件に応じた AI アシスタント**です。 Not tied to a provider, not tied to an interface, not tied to a platform.

## クイックスタート

```bash
pip install uag
uag
```

最初の起動時に、セットアップ ウィザードの手順に従ってプロバイダーの構成が行われます。
See [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) for all environment variables.

## 特徴

### 🧠 マルチプロバイダー アーキテクチャ

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

すべてのプロバイダーは同じツールセットとインターフェイスを共有します。 `UAGENT_PROVIDER` の設定で切り替え — コード変更も個別インストールも不要です。

### ⚡ ツールの並列実行

LLM が複数のツールを同時に要求すると、uag は **自動的に並列化** します。
76 のツールが `x_parallel_safe` に指定されており、`ThreadPoolExecutor` 経由で同時実行されます（デフォルト8スレッド、`UAGENT_PARALLEL_WORKERS` で変更可能）。

**例**: 「北欧の首都の天気を調べて」と尋ねる → LLM が `search_web` × 5 か国を発火 → 5 つの検索すべてが並行して実行される → 結果が 1 つのバッチで収集される。

Read-only tools (file search, hash calculation, directory listing, translation, DB queries, etc.) are aggressively parallelized.

### 🔄 セッションの継続性

- **セッション中にプロバイダーを切り替える** `UAGENT_PROVIDER` — 会話履歴は保存されます。
- **過去のセッションをリロード** `:load <index>` — 中断したところから再開します。
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 ツール

|カテゴリー |ツール |
|---|---|
| **ファイル操作** | read/write/create/delete/search/grep/hash/zip, parse_eml (.eml files) |
| **ウェブ** | fetch_url, search_web, screenshot, browser_playwright |
| **メディア** | generate_image, analyze_image, img2img, audio_speech, audio_transcribe |
| **ドキュメント** | PDF/PPTX/DOCX/RTF/ODT抽出、Excel構造化抽出 |
| **コミュニケーション** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook — see [COMMUNICATION.md](COMMUNICATION.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **開発ツール** | git_ops, python_compile, lint_format, run_tests, db_query, **13 source code navigators (idx family)** |
| **MCP** | Connect to external MCP servers, list tools, execute |
| **A2A** | Agent-to-agent communication (with other uag instances or A2A-compatible servers) |
| **システム** |環境変数、システム仕様、時刻、日付の計算 |
| **ソース ナビ** | **13 の idx ツール** (Python、PHP、TypeScript、Java、C#、Dart、C/C++、Rust、Go、Swift、Kotlin、COBOL 用) — ファイル全体を読み込まずに関数/クラスのインデックスまたは特定の定義を取得します。

### 🖥 3 つのインターフェイス + A2A + VS Code

|モード |コマンド |目的 |
|---|---|---|
| **CLI** | `uag` |端末ベースの高速操作 |
| **GUI** | `uagg` | tkinter 経由のデスクトップ UI |
| **ウェブ** | `uagw` |ブラウザベースのアクセス |
| **A2A サーバー** | `uaga` |マルチエージェント通信用の Agent2Agent プロトコル |
| **VS Code** | — | Extension (Chat Panel, Explain, Refactor, Fix Error, Tools Tree View) — see [VSCODE.md](VSCODE.md) |

### 🏠 IoT デバイス制御

- **SwitchBot**: クラウド一括制御 & BLE スキャン/制御
- **ECHONET Lite**: ローカルネットワーク上の家電製品 (エアコン、照明、給湯器など) を検出して制御します。
- **重要事項**: コントローラー/ブリッジ/デバイス トポロジの読み取り専用検査
- **UPnP**: デバイス検出と IGD ポート転送

[IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md) を参照してください。

### 🎯 エージェント スキル マーケットプレイス

`:skills mp_search` では、[SkillsMP](https://skillsmp.com) および [ClawHub](https://clawhub.ai) を参照してコミュニティ スキルを確認できます。
uag の機能をその場でインストールして拡張します。

### 🧩 バッチ状態マネージャー

uag は、長時間実行される複数ファイルのタスク全体の進行状況を追跡できます。 LLM が数十のファイルを処理するとき、`batch_state` は保留中、完了、失敗したファイルのリストをディスクに保存します。セッションが終了するかラウンドがタイムアウトになると、次の実行は停止したところから再開され、何も失われません。

### 🛡 人間参加型

`human_ask` を使用すると、破壊的な操作 (ファイルの削除、上書き、シェル コマンド) を実行する前に、LLM が一時停止して確認を求められます。あなたはコントロールを維持できます。

### 🛑 割り込み (c キー / Stop ボタン)

LLM 応答生成中にいつでも停止し、LLM に停止コマンドを注入できます。

| インターフェース | 割り込み方法 |
|---|---|
| **CLI** | LLM ストリーミング中に `c` キーを押すと、現在の応答が停止し、`"Stop"` がユーザーメッセージとして送信されます |
| **WEB UI** | 赤い **■ Stop** ボタンをクリック（LLM 処理中に自動表示） |
| **Desktop GUI** | 赤い **■** ボタンをクリック（LLM 処理中に自動表示） |

割り込みは「プロンプト注入」として機能します: 単に中断するだけでなく、`"Stop"` を LLM にユーザーメッセージとして送り返すことで、LLM が適切に応答を締めくくることができます。

自動パイロットモード（`:auto` コマンド）を終了するには `x` キーを押します。

### 🕵️ ブラウザ自動化と Web インスペクター

2 つの補完的な Playwright ベースのツール:

- **browser_playwright**: 実際のブラウザ セッションを自動化します。移動、クリック、フォームへの入力、データの抽出、複数ページのフローの処理を行います。ヘッドレスまたはヘッドなしで動作します。
- **playwright_inspector**: ブラウザーの遷移を記録し、各ステップで DOM スナップショットとスクリーンショットをキャプチャします。 Web インタラクションのデバッグや、時間の経過に伴うページの変更の監査に役立ちます。

### 🔄 動的ツールの読み込み

`tool_catalog` および `tool_load` を使用すると、実行時にツールを検出して有効にすることができます。
起動時にすべてをロードする必要はありません。必要なときに、必要なものだけをアクティブにします。

### 🌐 i18n / L10n

日本語 / 英語 / 简体中文 / 繁體中文 / 한국어 / スペイン語 / フランス語 / Русский / など。
`UAGENT_LANG` をスイッチに設定します。新しいロケールを追加するには、[ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) を参照してください。

この README の翻訳は [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md) で入手できます。

### 🔒 暗号化された環境変数

API キーとシークレットを `.env.sec` (暗号化された `.env` ファイル) に保存します。
`uag_envsec` で管理します。

## 構成と詳細

- **環境変数**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **セットアップ ウィザード**: `python -m uagent.setup_cli`
- **暗号化された環境**: `uag_envsec` — `.env` を `.env.sec` として暗号化します
- **レスポンス API**: `UAGENT_RESPONSES=1` をレスポンス API モードに設定します (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **開発者ドキュメント**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **LLM の小さなヒント**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## プロジェクトの理念

uag は **あなたのマシン上であなたの条件に合わせてあなたの AI になることを目指しています。**

- SaaS への依存関係なし - ローカルで実行
- プロバイダーのロックインなし - いつでも切り替え可能
- UI ロックインなし — CLI / GUI / Web / A2A
- 機能のロックインなし - ツールとスキルで拡張可能

ベンダー ロックインのない、無料の AI エージェント エクスペリエンス。