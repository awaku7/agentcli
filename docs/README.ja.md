<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — ユニバーサル AI ゲートウェイ</h1>

<p align="center">
 <b>ユニバーサル <b>A</b>I <b>G</b>ateway — あなたの環境、あなたの自由。
</p>

<p align="center">
 ファイル操作 / Web 検索 / 画像生成および分析 / PDF および Excel 抽出 / IoT 制御 / MCP 統合<br>
 24 プロバイダー / 3 UI / 並列ツール実行 /エージェント スキル マーケットプレイス
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## なぜ uag なのか?

**ベンダー ロックインから解放されます。** ほとんどの AI アシスタントは、ユーザーを特定のプロバイダーまたはクラウド サービスに結び付けます。 uag は異なります。

- **お使いのマシン上でローカルに実行されます**。データは保持されます (API 件の通話を除く)。
- **プロバイダーの自由**: OpenAI、Claude、Gemini、DeepSeek、Ollama、Azure、Bedrock、Novita、HuggingFace... 24 のプロバイダー、すべて単一のインターフェイスからアクセス可能。環境変数を再構成することでそれらを切り替えます — 再インストールや移行は必要ありません。
- **222 ツール**: ファイル I/O、Web 検索、画像生成、Gmail、BLE デバイス スキャン、MCP サーバー統合 — **130 は静的に並列セーフとマークされています** (スレッド プール経由で最大 8 つが同時に実行され、「UAGENT_PARALLEL_WORKERS」で構成可能)。 LLM が複数のツール呼び出しを同時に起動すると、uag はそれらを自動的に並列化します。
- **3 UI + A2A**: CLI、GUI、Web、およびエージェント間プロトコル。同じエンジン、任意のインターフェイス。
- **IoT 対応**: SwitchBot、ECHONET Lite、Matter、UPnP — AI を通じてホーム デバイスを制御。
- **エージェント スキル**: コミュニティが構築したスキルをマーケットプレイスからインストールします。 uag を無限に拡張します。

uag は **あなたの条件に応じた AI アシスタント**です。プロバイダーにも、インターフェースにも、プラットフォームにも結びついていません。

## クイック スタート

```bash
pip install uag
uag
```

最初の起動時に、セットアップ ウィザードによってプロバイダーの構成が指示されます。
すべての環境については [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) を参照してください。変数。

## Computer Use

Computer Use はオプトインであり、表示される Playwright ブラウザ ランタイム
とデスクトップ ランタイムの両方をサポートします。有効にすると、両方のランタイムが作成および登録されます。

```bat
set UAGENT_COMPUTER_USE=1
```

代わりに `desktop` を使用して OS デスクトップ ランタイムを選択します。 Runtime リソースは、通常の終了、`Ctrl-C`、およびプロセスのシャットダウン時に一緒に閉じられます。ブラウザベースの CI またはスモーク テストの場合は、
「UAGENT_COMPUTER_HEADLESS=1」を設定します。
統合と安全性の詳細については、[docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md) を参照してください。

## リアルタイム音声と AEC3

リアルタイム音声モードは、OpenAI リアルタイム、Azure OpenAI GPT リアルタイム、xAI Grok 音声 API、Google Gemini マルチモーダル ライブ API、および全二重マイクとスピーカー I/O を備えた Amazon Bedrock Nova Sonic をサポートします。必話す。オーディオの問題を調査する場合にのみ診断を有効にします:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI リアルタイム関数呼び出し

OpenAI リアルタイムは、安全性が制限された関数呼び出し統合をサポートしています。現在のリアルタイム アダプタは、読み取り専用の `get_current_time` を自動的に公開します。破壊的なツールとデバイス制御は、明示的な許可リストと確認フローがなければ公開されません。 Grok リアルタイムは別のアダプターを使用し、この OpenAI 固有の関数呼び出しパスを使用しません。

## 機能

### 🧠 マルチプロバイダー アーキテクチャ

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakena AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

すべてのプロバイダーは同じツールセットとインターフェイスを共有しています。 `UAGENT_PROVIDER` を設定して切り替えます。コードの変更や個別のインストールは必要ありません。

#### Ollama と llama.cpp

Ollama と llama.cpp は別のプロバイダーです。 Ollama は独自のサービスとモデル管理を使用しますが、`llama.cpp` は `llama-server` OpenAI 互換エンドポイントに接続します:

```bash
#オラマ
UAGENT_PROVIDER=オラマ
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

llama.cpp プロバイダーはチャット補完互換を使用します。パス。互換性のあるプロキシが設定されていない限り、`UAGENT_RESPONSES=0` を維持してください。

### ⚡ ツールの並列実行

LLM が複数のツールを同時に要求すると、uag はそれらを **自動的に並列化**します。
130 のツールは静的に `x_Parallel_safe` とマークされ、`ThreadPoolExecutor` 経由で同時に実行されます (8 スレッドによる)デフォルト; UAGENT_PARALLEL_WORKERS を変更に設定します)。

**例**: 「北欧の首都の天気を確認してください」と尋ねる → LLM が `search_web` × 5 か国を起動 → 5 つの検索がすべて並行して実行される → 結果が 1 つのバッチで収集される。

現在の数は、`TOOL_SPEC` を定義するツール モジュールに基づいています (現在 222、Rust-backed の 2 つを含む)ツールは `src/uagent/tools_rust/` にあります)。 `http_request` はメソッド依存の安全性を使用します。`GET`/`HEAD`/`OPTIONS` 呼び出しは並列実行できますが、書き込みメソッドはシリアルのままです。

読み取り専用ツール (ファイル検索、ハッシュ計算、ディレクトリ一覧、変換、DB クエリなど) は積極的に並列化されます。

### 🧩 プラグイン システム (Claude コード互換)

uagent は、 **Claude コード互換のプラグイン システム**。プラグインは、スキル、エージェント、MCP サーバー、フックなどを「.claude-plugin/plugin.json」マニフェストを使用して自己完結型ディレクトリにバンドルします。

**サポートされるコンポーネント**: スキル、サブエージェント、MCP サーバー、フック (12 のライフサイクル イベント)、スラッシュ コマンド、出力スタイル、userConfig、依存関係、チャネル、マーケットプレイス

**CLI コマンド**:

```
:plugin list # インストールされているプラグインをリストする
:plugin install <source> [--scope] # インストール (dir/zip/git/http)
:plugin install <name>@<marketplace> # マーケットプレイスからインストール
:plugin delete <name> # アンインストール
:plugin enable/disable <name> # Toggle
:plugin Marketplace add/remove/list # Marketplaces の管理
:plugin init <name> # 新しいプラグインの足場
```

完全なドキュメントについては、[DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) を参照してください。

### 🔄 セッション継続性

- **`UAGENT_PROVIDER` を使用してセッション中にプロバイダーを切り替えます** - 会話履歴は保存されます。
- **`:load <index>` を使用して過去のセッションをリロード** – 中断したところから再開します。
- **ツール結果のキャッシュ** により、同じツール呼び出しが繰り返された場合の冗長な再実行が回避されます。

### 🛠 229 ツール

|カテゴリー |ツール |
|---|---|
| **ファイル操作** |読み取り/書き込み/作成/削除/検索/grep/ハッシュ/zip、file_type、parse_eml (.eml ファイル)、`path_alias` |
| **Web** | fetch_url、search_web、スクリーンショット、browser_playwright、`url_alias`、`public_transit_route` ([ガイド](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **メディア** |画像生成、画像分析、img2img、audio_speech、audio_transcribe |
| **ドキュメント** | PDF/PPTX/DOCX/RTF/ODT 抽出、Excel 構造化抽出 |
| **予測** | 9 つのモデル (AutoARIMA、Prophet、LightGBM、CatBoost、TimesFM など) による時系列予測、自動モデル選択、プロット生成、i18n |
| **コミュニケーション** | gmail_send、gmail_read、bluesky、discord_channel、teams_webhook、**pybitchat** (BLE メッシュ) — [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) および[BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE)、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **クラウド API** | `aws_api`、`gcp_api`、`azure_api` — 汎用 AWS、Google クラウド、および Azure API オペレーション。書き込み操作には明示的な確認が必要です |
| **開発ツール** | workspace_status、git_ops、git_review、security_scan、coverage_report、python_compile、lint_format、run_tests、db_query、**29 ソース コード ナビゲーター (idx ファミリ)** |
| **MCP** |外部 MCP サーバーに接続し、ツールをリストし、実行します — [OAuth / プロキシ ガイド](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** |エージェント間の通信 (他の uag インスタンスまたは A2A 互換サーバーと) |
| **システム** |環境変数、システム仕様、時刻、日付計算、[数量](docs/QUANTITIES.md)、[geodesic\_ distance](docs/GEODESIC_DISTANCE.md)、uuid_gen、slugify |
| **ソース ナビ** | **29 idx ツール** (Python、PHP、TypeScript、Java、C#、Dart、C/C++、Rust、Go、Swift、Kotlin、COBOL、VBA、LotusScript、Makefile 用) — ファイル全体を読み込まずに関数/クラスのインデックスまたは特定の定義を取得 |

#### リポジトリのレビューとカバレッジ

- `workspace_status`: アクティブなワークスペースの Git をレポートしますファイルを変更せずに、ブランチ、変更、アップストリーム同期状態、Python ランタイム、一般的なプロジェクト マーカーを確認します。
- `git_review`: シークレット値を公開せずに、Git の変更、危険なファイル、テスト候補、およびシークレットの検出結果を要約します。
- `security_scan`: リポジトリ ファイルをスキャンして、可能性のあるシークレットと危険な設定ファイルを探します。
- `coverage_report`: Python のカバレッジを実行して正規化します。 TypeScript/JavaScript、Rust、Go、Java/Kotlin、.NET、C/C++、Ruby、PHP、Swift、Dart/Flutter。
- 不足しているカバレッジの依存関係は、実行が要求されたときに自動的にインストールできます。 `dry_run` はパッケージをインストールしません。

パラメータ、出力、および安全性の詳細については、[リポジトリ分析ツール](docs/REPOSITORY_TOOLS.md) を参照してください。

ツール引数で繰り返されるファイル パスと URL の短縮については、[パスと URL のエイリアス](docs/PATH_URL_ALIASES.md) を参照してください。

### 🖥 4 インターフェイス + VSコード拡張子

|モード |コマンド |目的 |
|---|---|---|
| **CLI** | `uag` |端末ベースの高速操作 |
| **GUI** | `うあぐ` | tkinter 経由のデスクトップ UI |
| **Web** | `うぐう` |ブラウザベースのアクセス |
| **A2A サーバー** |うが |マルチエージェント通信用の Agent2Agent プロトコル |
| **VS コード** | — | [拡張機能](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) チャット パネル、説明、リファクタリング、エラー修正、ツール ツリー ビュー付き |

VS Code 拡張機能の詳細については、[VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) を参照してください — インストール、コマンド、

### 🏠 IoT デバイス制御

- **BACnet**: BACnet/IP デバイス (HVAC、照明、電力メーター) の読み取り/書き込み。プッシュ通知の COV サブスクリプション
- **Modbus TCP**: 保持/入力レジスタおよびコイルの読み取り/書き込み。ポーリングベースの変更監視
- **OPC UA**: アドレス空間の参照、変数の読み取り/書き込み、データ変更のサブスクライブ
- **SwitchBot**: クラウドのバッチ制御と BLE スキャン/制御。ポーリングベースのサブスクリプション
- **ECHONET Lite**: 家電製品 (AC、照明、給湯器など) からの INF 通知を検出、制御、サブスクライブ
- **Matter**: 状態変化監視のための読み取り/書き込み制御 + 属性サブスクリプション
- **UPnP**: デバイスの検出と IGD ポート転送

参照[IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` でコミュニティの [SkillsMP](https://skillsmp.com) および [ClawHub](https://clawhub.ai) を参照します。スキル。
uag の機能をその場でインストールして拡張します。

### 🤖 自動操縦 (`:auto`)

uag は **複数の LLM ラウンドにわたって自律的に目標を追求できます**。反復的な改善が必要な複雑な複数ステップのタスクに最適です。

- **仕組み**: 各ラウンドにはメイン クエリ (ステップ A) があり、その後に「完了か続行か?」を決定するレビューアの判断 (ステップ B) が続きます。
- **同じプロバイダー、同じ API**: レビューアの判断は、応答 API のサポートを含む、メイン クエリと同じコード パスを使用します。
- **別個のジャッジLLM** (オプション): レビュー担当者に別のプロバイダー/モデルを使用するように `UAGENT_AP_PROVIDER` を設定します (例: 審査に安価なモデルを使用します)。
- **いつでも終了**: **F11** キーを押すと自動パイロットを停止できます。**F12** は現在の LLM 応答だけを停止します。または、目標が達成されたかどうかをレビュー担当者に判断させます。
- **構成可能**: `--max-rounds N` で予算を制御します。

完全なドキュメントについては、[README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) を参照してください。

### 🧩 バッチ状態Manager

uag は、長時間実行される複数ファイルのタスク全体の進行状況を追跡できます。 LLM が数十のファイルを処理するとき、「batch_state」は保留中、完了、失敗したファイルのリストをディスクに保存します。セッションが終了するかラウンドがタイムアウトになると、次の実行は停止したところから再開され、何も失われません。

### 🛡 Human-in-the-Loop

`human_ask` を使用すると、LLM が一時停止し、破壊的な操作 (ファイルの削除、上書き、シェル コマンド) を実行する前に確認を求めることができます。制御を維持します。

### 🛑 割り込み (C キー / 停止ボタン)

いつでも LLM 応答の生成を停止し、LLM に停止コマンドを挿入します。

|インターフェース |中断方法 |
|---|---|
| **CLI** | LLM ストリーミング中に F12を押すと、現在の応答が停止し、`"Stop"` がユーザー メッセージとして送信されるため、LLM はそれに応じて応答します |
| **ウェブ UI** |赤い **■ 停止** ボタンをクリックします (LLM の処理中に自動的に表示されます) |
| **デスクトップ GUI** |赤い **■** ボタンをクリックします (LLM の処理中に自動的に表示されます) |

割り込みは「プロンプト挿入」として機能します。単に中止するのではなく、「Stop」をユーザー メッセージとして LLM に送り返し、割り込みを正常に終了または確認できるようにします。

**F11** キーを押して自動パイロットモードを終了します。**F12** は現在の LLM 応答を停止します（詳細は [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) を参照）。

### 🕵️ ブラウザー自動化と Web インスペクター

2 つの補完的な Playwright ベースのツール:

- **browser_playwright**: 実際のブラウザー セッションを自動化します。移動、クリック、フォームへの入力、データの抽出、複数ページのフローの処理。ヘッドレスまたはヘッド付きで動作します。
- **playwright_inspector**: ブラウザーの遷移を記録し、各ステップで DOM スナップショットとスクリーンショットをキャプチャします。 Web インタラクションのデバッグや、時間の経過に伴うページ変更の監査に役立ちます。

### 🔄 動的ツールの読み込み

`tool_catalog` と `tool_load` を使用すると、実行時にツールを検出して有効にすることができます。
起動時にすべてをロードする必要はありません。必要なときに、必要なものだけをアクティブにします。

### 🦀 Rust Nativeツール

`uuid_gen` と `slugify` はパフォーマンスのために Rust (PyO3 経由) に実装されています。
これらは事前に構築された `.pyd` から直接ロードされます — **`pip install` は必要ありません**。

外部開発者は Rust ベースのツールを出荷することもできます:
ラッパー `.py` の隣に `.pyd` を配置し、使用します`uagent.tools.rust_helper` から `load_rust_pyd()` を取得すると、ユーザーは追加の依存関係なしでツールを入手できます。
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md) を参照してください。

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / など。
`UAGENT_LANG` を設定して切り替えます。新しいロケールを追加するには、[ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) を参照してください。

この README の翻訳は、次の場所で入手できます。 [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒暗号化された環境変数

API キーとシークレットを `.env.sec` (暗号化された `.env` ファイル) に保存します。
次の方法で管理します。 「uag_envsec」。

## 設定と詳細

- **環境変数**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **セットアップ ウィザード**: `python -m uagent.setup_cli`
- **暗号化された環境**: `uag_envsec` — `.env` を `.env.sec` として暗号化します
- **レスポンス API**: レスポンス API モード (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI) に `UAGENT_RESPONSES=1` を設定します。 Sakana AI (Fugu) が自動的に有効になります。
- **開発者ドキュメント**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **ツール フロー**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) - ツールが LLM に送信される方法 (ジャンル マスク、tool_catalog、GPT-5.4+ ネイティブ ツール検索)
- **LLM の小さなヒント**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## プロジェクトの理念

uag は、**あなたの AI を、あなたのマシン上で、あなたの条件で実現することを目指しています。**

- SaaS への依存なし — ローカルで実行
- プロバイダーのロックインなし — いつでも切り替え可能
- UI のロックインなし — CLI / GUI / Web / A2A
- 機能のロックインなし — ツールやツールで拡張スキル

ベンダー ロックインから解放された、無料の AI エージェント エクスペリエンス。

### ✨ 独自のツールの作成

uag 用の新しいツールの作成は簡単です。
`TOOL_SPEC` と `run_tool()` を含む単一の `.py` ファイルを作成し、それを `UAGENT_EXTERNAL_TOOLS_DIR` に配置すると、
すぐに使用できます。 Rust 開発者の場合は、ユーザー向けに追加の依存関係が一切ない、事前にビルドされた `.pyd` を出荷します。

ステップバイステップ ガイドについては、[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
を参照してください。

## 貢献

貢献は大歓迎です!バグ レポート、機能の提案、ドキュメントの改善、翻訳、プル リクエストはすべて歓迎です。

- **問題**: バグまたは機能リクエストについては、GitHub の問題をオープンしてください。
- **プル リクエスト**: リポジトリをフォークし、変更を加え、PR を送信します。開発セットアップとガイドラインについては、[DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) を参照してください。
- **翻訳**: README の翻訳とロケールの追加は歓迎されます。 [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) を参照してください。
- **ツールとスキル**: 新しいツール プラグインとエージェント スキルはマーケットプレイス経由で提供できます。

### 開発チェック (PR 前)

最初にテスト専用の依存関係をインストールします。これらはランタイム
依存関係リストから除外されます:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

プッシュする前に GitHub アクションで使用されるのと同じチェックを実行します:

```bash
python -m ruff check srcテスト
python -m black --check src テスト
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

ローカル反復を高速化するには、影響を受けるテストのみを実行します:

```bash
pytest -q testing/<affected_area>
```

追加関連する場合はチェックします:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

ロケール (`.po`) 編集後: `python scripts/compile_locales.py` および `python scripts/po_qc_summary.py`。

Runtimeポリシー (詳細は [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): ヘルパーは `sys.exit` の代わりに raise を行います。ツール ホストはツール `SystemExit`/`Exception` をエラー文字列に変換するため、単一のツールがプロセスを強制終了することはできません。スタートアップのフェールファスト終了は引き続き意図的です。

## アーキテクチャと運用上の不変条件

A2A ライフサイクル、I18N コンテキスト、オプションの依存関係のインストール、ツールの安全性、プロバイダーの機能、OAuth 信頼境界、構造化イベント、および受け入れ検証をカバーする永続的なコントラクトについては、[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) を参照してください。

## エンタープライズ ポリシー エンジン

ツール、プロバイダー、資格情報、MCP サーバー、ネットワーク、スキル、プラグインの組織レベルのポリシーがサポートされています。 `UAGENT_POLICY_FILE` を JSON/YAML ポリシー ファイルに設定します。構成例、役割、確認、許可リストについては、[docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) を参照してください。

### Runtime のリカバリとオーケストレーション

[RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / を参照してください。 [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) : 永続的リカバリ、依存関係を意識した実行、マルチエージェント オーケストレーション、およびリモート A2A の使用。

を参照してください。共有ランタイム リーダー リース調整用の [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md)
