<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — あなたの環境、あなたの自由。
</p>

<p align="center">
  ファイル操作 / Web検索 / 画像生成・分析 / PDF・Excel抽出 / IoT制御 / MCP統合<br>
  20+ プロバイダ / 3つのUI / ツール並列実行 / エージェントスキルマーケットプレイス
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

---

## なぜuagなのか？

**ベンダーロックインからの解放。** ほとんどのAIアシスタントは特定のプロバイダやクラウドサービスに縛られます。uagは違います。

- **あなたのマシンでローカルに動作**。データはあなたの手元に残ります（API呼び出しは除く）。
- **プロバイダの自由**: OpenAI、Claude、Gemini、DeepSeek、Ollama、Azure、Bedrock、Novita、HuggingFace…21のプロバイダを1つのインターフェースから利用可能。環境変数を変えるだけで切り替えられます。再インストールや移行は不要です。
- **170ツール**: ファイルI/O、Web検索、画像生成、Gmail、BLEデバイススキャン、MCPサーバ統合 — **111のツールは並行実行に対応**（スレッドプールで最大8つ同時実行、`UAGENT_PARALLEL_WORKERS`で変更可能）。LLMが複数のツール呼び出しを同時に要求すると、uagは自動的に並列化します。
- **3つのUI + A2A**: CLI、GUI、Web、そしてエージェント間プロトコル。同じエンジンをどのインターフェースでも使えます。
- **IoT対応**: SwitchBot、ECHONET Lite、Matter、UPnP — AIを通じて家電を制御。
- **エージェントスキル**: マーケットプレイスからコミュニティ製スキルをインストール。uagを無限に拡張できます。

uagは **あなたの思い通りに動くAIアシスタント**です。プロバイダに縛られず、インターフェースに縛られず、プラットフォームに縛られません。

## クイックスタート

```bash
pip install uag
uag
```

初回起動時にセットアップウィザードがプロバイダ設定を案内します。
環境変数の一覧は [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) を参照してください。

## 特徴

### 🧠 マルチプロバイダ構成

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)** / **SAKURA AI Engine**

すべてのプロバイダは同じツールセットとインターフェースを共有します。`UAGENT_PROVIDER` を切り替えるだけで変更でき、コード修正や個別インストールは不要です。

### ⚡ ツールの並列実行

LLMが複数のツールを同時に要求すると、uagは **自動的に並列実行** します。
111のツールが `x_parallel_safe` に指定されており、`ThreadPoolExecutor` で同時実行されます（デフォルト8スレッド、`UAGENT_PARALLEL_WORKERS` で変更可能）。

**例**: 「北欧の首都の天気を調べて」と質問 → LLMが `search_web` を5ヶ国分同時に要求 → 5つの検索が並行実行 → 結果が1つのバッチにまとまる。

読み取り専用のツール（ファイル検索、ハッシュ計算、ディレクトリ一覧、翻訳、DBクエリなど）は積極的に並列化されます。

### 🧩 プラグインシステム（Claude Code 互換）

uagentは **Claude Code 互換のプラグインシステム** を実装しています。プラグインはスキル、サブエージェント、MCPサーバ、フックなどを `.claude-plugin/plugin.json` マニフェストを持つ自己完結型ディレクトリにバンドルします。

**対応コンポーネント**: スキル、サブエージェント、MCPサーバ、フック（12のライフサイクルイベント）、スラッシュコマンド、出力スタイル、userConfig、依存関係、チャンネル、マーケットプレイス

**CLIコマンド**:
```
:plugin list                         # インストール済みプラグイン一覧
:plugin install <source> [--scope]   # インストール（dir/zip/git/http）
:plugin install <name>@<marketplace>  # マーケットプレイスからインストール
:plugin remove <name>                # アンインストール
:plugin enable/disable <name>        # 有効/無効の切り替え
:plugin marketplace add/remove/list  # マーケットプレイスの管理
:plugin init <name>                  # 新規プラグインのスキャフォールド
```

詳細は [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) を参照してください。

### 🔄 セッションの継続性

- **セッション中のプロバイダ切り替え**: `UAGENT_PROVIDER` を変更しても会話履歴は保持されます。
- **過去セッションの再読み込み**: `:load <番号>` で中断したところから再開。
- **ツール結果のキャッシュ**: 同じツール呼び出しが繰り返された場合、再実行を防ぎます。

### 🛠 170ツール

| カテゴリ | ツール |
|---|---|
| **ファイル操作** | read/write/create/delete/search/grep/hash/zip、file_type、parse_eml（.emlファイル） |
| **Web** | fetch_url、search_web、screenshot、browser_playwright |
| **メディア** | generate_image、analyze_image、img2img、audio_speech、audio_transcribe |
| **ドキュメント** | PDF/PPTX/DOCX/RTF/ODT抽出、Excel構造化抽出 |
| **コミュニケーション** | gmail_send、gmail_read、bluesky、discord_channel、teams_webhook — [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) 参照 |
| **IoT** | SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **開発ツール** | git_ops、python_compile、lint_format、run_tests、db_query、**13のソースコードナビゲーター（idxファミリ）** |
| **MCP** | 外部MCPサーバへの接続、ツール一覧、実行 |
| **A2A** | エージェント間通信（他のuagインスタンスやA2A対応サーバと） |
| **システム** | 環境変数、システム情報、時刻、日付計算、uuid_gen、slugify |
| **ソースナビ** | **13のidxツール**（Python、PHP、TypeScript、Java、C#、Dart、C/C++、Rust、Go、Swift、Kotlin、COBOL）— ファイル全体を読まずに関数やクラスのインデックスを取得 |

### 🖥 4つのインターフェース + VS Code拡張

| モード | コマンド | 用途 |
|---|---|---|
| **CLI** | `uag` | ターミナルベースの高速操作 |
| **GUI** | `uagg` | tkinterによるデスクトップUI |
| **Web** | `uagw` | ブラウザベースのアクセス |
| **A2Aサーバ** | `uaga` | マルチエージェント通信用のAgent2Agentプロトコル |
| **VS Code** | — | [拡張機能](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) — チャットパネル、説明、リファクタリング、エラー修正、ツールツリービュー |

VS Code拡張機能の詳細（インストール、コマンド、キーバインド、設定）は [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) を参照してください。

### 🏠 IoTデバイス制御

- **BACnet**: BACnet/IP デバイス（HVAC、照明、電力メーター）の読み取り/書き込み。プッシュ通知のCOVサブスクリプション
- **Modbus TCP**: 保持/入力レジスタおよびコイルの読み取り/書き込み。ポーリングベースの変更監視
- **OPC UA**: アドレス空間の参照、変数の読み取り/書き込み、データ変更のサブスクライブ
- **SwitchBot**: クラウドのバッチ制御とBLEスキャン/制御。ポーリングベースのサブスクリプション
- **ECHONET Lite**: 家電製品（AC、照明、給湯器など）の検出、制御、INF通知のサブスクライブ
- **Matter**: 読み取り/書き込み制御 + 状態変化監視のための属性サブスクリプション
- **UPnP**: デバイスの検出とIGDポート転送

詳細は [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) を参照。

### 🎯 エージェントスキルマーケットプレイス

`:skills mp_search` で [SkillsMP](https://skillsmp.com) や [ClawHub](https://clawhub.ai) を検索し、コミュニティスキルをその場でインストールしてuagの機能を拡張できます。

### 🤖 オートパイロット（`:auto`）

uagは複数のLLMラウンドにわたって **自律的に目標を達成** できます。複雑なマルチステップタスクに適しています。

- **動作**: 各ラウンドはメインクエリ（Step A）とレビューアによる判定（Step B）で構成。Step Bが「COMPLETE」か「CONTINUE」を判断します。
- **同じプロバイダ、同じコードパス**: レビューア判定もメインクエリと同じコードパス（Responses API対応含む）を使用。
- **判定用LLMの分離（オプション）**: `UAGENT_AP_PROVIDER` を設定すると、レビューアに別のプロバイダ/モデルを使えます（例：判定には安価なモデルを使う）。
- **いつでも停止**: 応答中でも `x` キーで即座に中断可能。レビューアの自動判定も利用できます。
- **設定可能**: `--max-rounds N` で最大ラウンド数を指定。

詳細は [README_AUTO.ja.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.ja.md) を参照。

### 🧩 バッチ状態管理

uagは長時間かかる複数ファイルのタスクについて、処理状況を追跡できます。LLMが数十のファイルを処理するとき、`batch_state` は未処理・完了・失敗のファイル一覧をディスクに保存します。セッションが切れたりラウンドがタイムアウトしても、次回実行時に続きから再開できます。

### 🛡 人間参加型

`human_ask` を使うと、破壊的な操作（ファイル削除、上書き、シェルコマンドの実行）の前にLLMが一時停止して確認を求めます。あなたが常に制御権を持ちます。

### 🛑 割り込み（cキー / 停止ボタン）

LLMの応答生成中にいつでも停止し、LLMに停止コマンドを送れます。

| インターフェース | 割り込み方法 |
|---|---|
| **CLI** | LLMストリーミング中に `c` キーを押すと応答が停止し、`"Stop"` がユーザーメッセージとして送信されます |
| **Web UI** | 赤い **■ Stop** ボタンをクリック（LLM処理中に自動表示） |
| **デスクトップGUI** | 赤い **■** ボタンをクリック（LLM処理中に自動表示） |

この割り込みは「プロンプト注入」として機能します。単に中断するだけでなく、`"Stop"` をLLMに送り返すことで、LLMが適切に応答を締めくくれるようになります。

オートパイロットモード（`:auto`）を終了するには `x` キーを押します（[README_AUTO.ja.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.ja.md) 参照）。

### 🕵️ ブラウザ自動化とWebインスペクタ

2つの補完的なPlaywrightベースのツール:

- **browser_playwright**: 実際のブラウザセッションを自動化。移動、クリック、フォーム入力、データ抽出、複数ページの操作に対応。ヘッドレスでもヘッドありでも動作します。
- **playwright_inspector**: ブラウザの遷移を記録し、各ステップでDOMスナップショットとスクリーンショットを取得。Web操作のデバッグやページ変更の追跡に便利です。

### 🔄 動的ツール読み込み

`tool_catalog` と `tool_load` を使うと、実行時にツールを発見・有効化できます。起動時にすべてを読み込む必要はなく、必要なときに必要なものだけを有効にできます。

### 🦀 Rustネイティブツール

`uuid_gen` と `slugify` は Rust（PyO3）で実装されており、高速に動作します。
ビルド済みの `.pyd` から直接読み込まれるため、**`pip install` は不要**です。

外部の開発者も Rust ベースのツールを配布できます。`.pyd` をラッパー `.py` と同じ
ディレクトリに配置し、``uagent.tools.rust_helper`` の ``load_rust_pyd()`` を使用する
だけで、ユーザーは追加の依存関係なしでツールを利用できます。詳細は
[TOOL_CREATOR_GUIDE.ja.md](TOOL_CREATOR_GUIDE.ja.md) を参照してください。


### 🦀 Rust Native Tools

`uuid_gen` and `slugify` are implemented in Rust (via PyO3) for performance.
They load directly from a pre-built `.pyd` — **no `pip install` required**.

External developers can also ship Rust-based tools: place a `.pyd` next to the
wrapper `.py`, use ``load_rust_pyd()`` from ``uagent.tools.rust_helper``, and
users get the tool without any extra dependencies. See
[TOOL_CREATOR_GUIDE.ja.md](TOOL_CREATOR_GUIDE.ja.md).

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / など。
`UAGENT_LANG` で切り替えられます。新しいロケールの追加方法は [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) を参照。

このREADMEの翻訳版は [docs/README.translations.md](README.translations.md) で参照できます。

### 🔒 暗号化された環境変数

APIキーやシークレットは `.env.sec`（暗号化された `.env` ファイル）に保存できます。管理には `uag_envsec` を使います。

## 構成と詳細

- **環境変数**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **セットアップウィザード**: `python -m uagent.setup_cli`
- **暗号化環境**: `uag_envsec` — `.env` を `.env.sec` として暗号化
- **Responses API**: `UAGENT_RESPONSES=1` でResponses APIモードに（OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI）。Sakana AI（Fugu）では自動的に有効になります。
- **開発者向けドキュメント**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **ツールフロー**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — ツール送信方式の詳細（genre mask, tool_catalog, GPT-5.4+ native tool_search）
- **軽量LLM向けヒント**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## プロジェクトの理念

uagは **あなたのマシンで、あなたの思い通りに動く、あなたのAI** を目指しています。

- SaaSに依存しない — ローカルで動作
- プロバイダのロックインなし — いつでも切り替え可能
- UIのロックインなし — CLI / GUI / Web / A2A
- 機能のロックインなし — ツールとスキルで拡張可能

ベンダーロックインのない、自由なAIエージェント体験。

### ✨ Create Your Own Tools

Writing a new tool for uag is straightforward — create a single `.py` file with
`TOOL_SPEC` and `run_tool()`, place it in ``UAGENT_EXTERNAL_TOOLS_DIR``, and
it's immediately available. For Rust developers, ship a pre-built `.pyd` with
zero extra dependencies for users.

See [TOOL_CREATOR_GUIDE.ja.md](TOOL_CREATOR_GUIDE.ja.md)
for the step-by-step guide.

## Contributing

Contributions are welcome! Bug reports, feature suggestions, documentation improvements, translations, and pull requests — all appreciated.

- **Issues**: Open a GitHub issue for bugs or feature requests.
- **Pull requests**: Fork the repo, make your changes, and submit a PR. See [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) for development setup and guidelines.
- **Translations**: README translations and locale additions are welcome. See [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: New tool plugins and Agent Skills can be contributed via the marketplace.

### 開発時チェック（PR 前）

```bash
python -m py_compile src/uagent/
ruff format src/ && ruff check src/
mypy src/uagent
pytest -q tests/<affected_area>
```

ロケール（`.po`）編集後: `python scripts/compile_locales.py` と `python scripts/po_qc_summary.py`。

ランタイム方針（詳細は [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1）: ヘルパーは `sys.exit` ではなく例外を送出。ツールホストはツール側の `SystemExit`/`Exception` をエラー文字列に変換し、単一ツールがプロセスを落とさない。起動時 fail-fast の exit は意図的に残す。
