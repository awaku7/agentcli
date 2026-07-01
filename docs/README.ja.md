<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — あなたの環境、あなたの自由。
</p>

<p align="center">
  ファイル操作 / Web検索 / 画像生成・分析 / PDF・Excel抽出 / IoT制御 / MCP統合<br>
  15以上のプロバイダ / 3つのUI / ツール並列実行 / エージェントスキルマーケットプレイス
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
- **プロバイダの自由**: OpenAI、Claude、Gemini、DeepSeek、Ollama、Azure、Bedrock、HuggingFace…15以上のプロバイダを1つのインターフェースから利用可能。環境変数を変えるだけで切り替えられます。再インストールや移行は不要です。
- **131のツール**: ファイルI/O、Web検索、画像生成、Gmail、BLEデバイススキャン、MCPサーバ統合 — **76のツールは並列実行に対応**（スレッドプールで最大8つ同時実行、`UAGENT_PARALLEL_WORKERS` で変更可能）。LLMが複数のツール呼び出しを同時に要求すると、uagは自動的に並列化します。
- **3つのUI + A2A**: CLI、GUI、Web、そしてエージェント間プロトコル。同じエンジンをどのインターフェースでも使えます。
- **IoT対応**: SwitchBot、ECHONET Lite、Matter、UPnP — AIで家電を制御。
- **エージェントスキル**: マーケットプレイスからコミュニティ製スキルをインストール。uagを無限に拡張できます。

uagは **あなたの思い通りに動くAIアシスタント**です。プロバイダに縛られず、インターフェースに縛られず、プラットフォームに縛られません。

## クイックスタート

```bash
pip install uag
uag
```

初回起動時にセットアップウィザードがプロバイダ設定を案内します。
環境変数の一覧は [ENVIRONMENT.md](../ENVIRONMENT.md) を参照してください。

## 特徴

### 🧠 マルチプロバイダ構成

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

すべてのプロバイダは同じツールセットとインターフェースを共有します。`UAGENT_PROVIDER` を切り替えるだけで変更でき、コード修正や個別インストールは不要です。

### ⚡ ツールの並列実行

LLMが複数のツールを同時に要求すると、uagは **自動的に並列実行** します。
76のツールが `x_parallel_safe` に指定されており、`ThreadPoolExecutor` で同時実行されます（デフォルト8スレッド、`UAGENT_PARALLEL_WORKERS` で変更可能）。

**例**: 「北欧の首都の天気を調べて」と質問 → LLMが `search_web` を5ヶ国分同時に要求 → 5つの検索が並行実行 → 結果が1つのバッチにまとまる。

読み取り専用のツール（ファイル検索、ハッシュ計算、ディレクトリ一覧、翻訳、DBクエリなど）は積極的に並列化されます。

### 🔄 セッションの継続性

- **セッション中のプロバイダ切り替え**: `UAGENT_PROVIDER` を変更しても会話履歴は保持されます。
- **過去セッションの再読み込み**: `:load <番号>` で中断したところから再開。
- **ツール結果のキャッシュ**: 同じツール呼び出しが繰り返された場合、再実行を防ぎます。

### 🛠 131ツール

| カテゴリ | ツール |
|---|---|
| **ファイル操作** | read/write/create/delete/search/grep/hash/zip、parse_eml（.emlファイル） |
| **Web** | fetch_url、search_web、screenshot、browser_playwright |
| **メディア** | generate_image、analyze_image、img2img、audio_speech、audio_transcribe |
| **ドキュメント** | PDF/PPTX/DOCX/RTF/ODT抽出、Excel構造化抽出 |
| **コミュニケーション** | gmail_send、gmail_read、bluesky、discord_channel、teams_webhook — [COMMUNICATION.md](COMMUNICATION.md) 参照 |
| **IoT** | SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP |
| **開発ツール** | git_ops、python_compile、lint_format、run_tests、db_query、**13のソースコードナビゲーター（idxファミリ）** |
| **MCP** | 外部MCPサーバへの接続、ツール一覧、実行 |
| **A2A** | エージェント間通信（他のuagインスタンスやA2A対応サーバと） |
| **システム** | 環境変数、システム情報、時刻、日付計算 |
| **ソースナビ** | **13のidxツール**（Python、PHP、TypeScript、Java、C#、Dart、C/C++、Rust、Go、Swift、Kotlin、COBOL）— ファイル全体を読まずに関数やクラスのインデックスを取得 |

### 🖥 4つのインターフェース + VS Code拡張

| モード | コマンド | 用途 |
|---|---|---|
| **CLI** | `uag` | ターミナルベースの高速操作 |
| **GUI** | `uagg` | tkinterによるデスクトップUI |
| **Web** | `uagw` | ブラウザベースのアクセス |
| **A2Aサーバ** | `uaga` | マルチエージェント通信用のAgent2Agentプロトコル |
| **VS Code** | — | チャットパネル、説明、リファクタリング、エラー修正、ツールツリービュー — [VSCODE.md](../VSCODE.md) 参照 |

### 🏠 IoTデバイス制御

- **SwitchBot**: クラウド一括制御 & BLEスキャン/制御
- **ECHONET Lite**: ローカルネットワーク上の家電（エアコン、照明、給湯器など）を検出・制御
- **Matter**: コントローラ/ブリッジ/デバイスのトポロジを読み取り専用で検査
- **UPnP**: デバイス検出とIGDポート転送

詳しくは [IOT_USECASE.md](../IOT_USECASE.md) を参照。

### 🎯 エージェントスキルマーケットプレイス

`:skills mp_search` で [SkillsMP](https://skillsmp.com) や [ClawHub](https://clawhub.ai) を検索し、コミュニティスキルをその場でインストールしてuagの機能を拡張できます。

### 🤖 オートパイロット（`:auto`）

uagは複数のLLMラウンドにわたって **自律的に目標を達成** できます。複雑なマルチステップタスクに適しています。

- **動作**: 各ラウンドはメインクエリ（Step A）とレビューアによる判定（Step B）で構成。Step Bが「COMPLETE」か「CONTINUE」を判断します。
- **同じプロバイダ、同じコードパス**: レビューア判定もメインクエリと同じコードパス（Responses API対応含む）を使用。
- **判定用LLMの分離（オプション）**: `UAGENT_AP_PROVIDER` を設定すると、レビューアに別のプロバイダ/モデルを使えます（例：判定には安価なモデルを使う）。
- **いつでも停止**: 応答中でも `x` キーで即座に中断可能。レビューアの自動判定も利用できます。
- **設定可能**: `--max-rounds N` で最大ラウンド数を指定。

詳細は [README_AUTO.ja.md](README_AUTO.ja.md) を参照。

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

オートパイロットモード（`:auto`）を終了するには `x` キーを押します。

### 🕵️ ブラウザ自動化とWebインスペクタ

2つの補完的なPlaywrightベースのツール:

- **browser_playwright**: 実際のブラウザセッションを自動化。移動、クリック、フォーム入力、データ抽出、複数ページの操作に対応。ヘッドレスでもヘッドありでも動作します。
- **playwright_inspector**: ブラウザの遷移を記録し、各ステップでDOMスナップショットとスクリーンショットを取得。Web操作のデバッグやページ変更の追跡に便利です。

### 🔄 動的ツール読み込み

`tool_catalog` と `tool_load` を使うと、実行時にツールを発見・有効化できます。起動時にすべてを読み込む必要はなく、必要なときに必要なものだけを有効にできます。

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / など。
`UAGENT_LANG` で切り替えられます。新しいロケールの追加方法は [ADD_LOCALE.md](../src/uagent/docs/ADD_LOCALE.md) を参照。

Translations of this README are available in [docs/README.translations.md](README.translations.md).

### 🔒 暗号化された環境変数

APIキーやシークレットは `.env.sec`（暗号化された `.env` ファイル）に保存できます。管理には `uag_envsec` を使います。

## 構成と詳細

- **環境変数**: [ENVIRONMENT.md](../ENVIRONMENT.md)
- **セットアップウィザード**: `python -m uagent.setup_cli`
- **暗号化環境**: `uag_envsec` — `.env` を `.env.sec` として暗号化
- **Responses API**: `UAGENT_RESPONSES=1` でResponses APIモードに（OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI）。Sakana AI（Fugu）では自動的に有効になります。
- **開発者向けドキュメント**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **軽量LLM向けヒント**: [SLM_TIPS.md](../SLM_TIPS.md)

## プロジェクトの理念

uagは **あなたのマシンで、あなたの思い通りに動く、あなたのAI** を目指しています。

- SaaSに依存しない — ローカルで動作
- プロバイダのロックインなし — いつでも切り替え可能
- UIのロックインなし — CLI / GUI / Web / A2A
- 機能のロックインなし — ツールとスキルで拡張可能

ベンダーロックインのない、自由なAIエージェント体験。
