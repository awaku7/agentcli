<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag ロゴ" width="720">
</p>

<h1 align="center">uag — ユニバーサル AI ゲートウェイ</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — あなたの環境、あなたの自由。
</p>

<p align="center">
  ファイル操作 / Web検索 / 画像生成および分析 / PDFおよびExcel抽出 / IoT制御 / MCP統合<br>
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
- **111 のツール**: ファイル I/O、Web 検索、画像生成、BLE デバイス スキャン、MCP サーバー統合 - そのうち **55 は並列実行**。 LLM が複数のツール呼び出しを同時に起動すると、uag はスレッド プールを介してそれらの呼び出しを自動的に実行します。
- **3 UI + A2A**: CLI、GUI、Web、およびエージェント間プロトコル。同じエンジン、どのインターフェイスでも。
- **IoT 対応**: SwitchBot、ECHONET Lite、Matter、UPnP — AI を通じてホームデバイスを制御します。
- **エージェント スキル**: コミュニティが構築したスキルをマーケットプレイスからインストールします。 uagを無限に拡張します。

uag は **あなたの条件に応じた AI アシスタント**です。プロバイダーにも、インターフェースにも、プラットフォームにも結びついていません。

## クイックスタート

```bash
pip install uag
uag
```

最初の起動時に、セットアップ ウィザードの手順に従ってプロバイダーの構成が行われます。
すべての環境変数については、[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) を参照してください。

## 特徴

### 🧠 マルチプロバイダー アーキテクチャ

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

すべてのプロバイダーは同じツールセットとインターフェイスを共有します。 `UAGENT_PROVIDER` を設定して切り替えます。コードの変更や個別のインストールは必要ありません。

### ⚡ ツールの並列実行

LLM が複数のツールを同時に要求すると、uag はそれらを **自動的に並列化**します。
55 のツールには「x_Parallel_safe」のマークが付けられ、4 スレッドの「ThreadPoolExecutor」を通じて同時に実行されます。

**例**: 「北欧の首都の天気を調べて」と尋ねる → LLM が `search_web` × 5 か国を起動 → 5 つの検索すべてが並行して実行 → 結果が 1 つのバッチに収集される。

読み取り専用ツール (ファイル検索、ハッシュ計算、ディレクトリ一覧表示、変換、DB クエリなど) は積極的に並列化されています。

### 🔄 セッションの継続性

- **「UAGENT_PROVIDER」を使用してセッション中にプロバイダーを切り替える** - 会話履歴は保存されます。
- **過去のセッションを再ロード**するには `:load <index>` を使用します。中断したところから再開します。
- **ツール結果のキャッシュ**により、同じツール呼び出しが繰り返される場合の冗長な再実行が回避されます。

### 🛠 111 ツール

|カテゴリー |ツール |
|---|---|
| **ファイル操作** |読み取り/書き込み/作成/削除/検索/grep/ハッシュ/zip |
| **ウェブ** | fetch_url、search_web、スクリーンショット、browser_playwright |
| **メディア** |画像生成、画像分析、img2img、音声音声、音声転写 |
| **ドキュメント** | PDF/PPTX/DOCX/RTF/ODT抽出、Excel構造化抽出 |
| **IoT** | SwitchBot（クラウド+BLE）、ECHONET Lite、Matter、UPnP |
| **開発ツール** | git_ops、python_compile、lint_format、run_tests、db_query、**11 個のソースコードナビゲーター (idx ファミリー)** |
| **MCP** |外部 MCP サーバーに接続し、ツールをリストし、| を実行します。
| **A2A** |エージェント間の通信 (他の uag インスタンスまたは A2A 互換サーバーと) |
| **システム** |環境変数、システム仕様、時刻、日付の計算 |
| **ソースナビ** | 11 の idx ツール (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — ファイル全体を読まずに関数/クラスの一覧を取得 |
| **ソースナビ** | **11 の idx ツール** (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — ファイル全体を読まずに関数/クラスの一覧や特定の定義を取得 |

### 🖥 3 つのインターフェイス + A2A

|モード |コマンド |目的 |
|---|---|---|
| **CLI** | `uag` |端末ベースの高速操作 |
| **GUI** | `uagg` | tkinter 経由のデスクトップ UI |
| **ウェブ** | `uagw` |ブラウザベースのアクセス |
| **A2A サーバー** | `uaga` |マルチエージェント通信用の Agent2Agent プロトコル |

### 🏠 IoT デバイス制御

- **SwitchBot**: クラウド一括制御 & BLE スキャン/制御
- **ECHONET Lite**: ローカルネットワーク上の家電製品 (エアコン、照明、給湯器など) を検出して制御します。
- **重要事項**: コントローラー/ブリッジ/デバイス トポロジの読み取り専用検査
- **UPnP**: デバイス検出と IGD ポート転送

[IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md) を参照してください。

### 🎯 エージェント スキル マーケットプレイス

`:skills mp_search` を使用して、[SkillsMP](https://skillsmp.com) および [ClawHub](https://clawhub.ai) のコミュニティ スキルを参照します。
uag の機能をその場でインストールして拡張します。

### 🧩 バッチ状態マネージャー

uag は、長時間実行される複数ファイルのタスク全体の進行状況を追跡できます。 LLM が数十のファイルを処理する場合、「batch_state」は保留中、完了、失敗したファイルのリストをディスクに保存します。セッションが終了するかラウンドがタイムアウトになると、次の実行は停止したところから再開され、何も失われません。

### 🛡 人間参加型

`human_ask` を使用すると、破壊的な操作 (ファイルの削除、上書き、シェル コマンド) を実行する前に、LLM が一時停止して確認を求められます。あなたはコントロールを維持できます。

### 🕵️ ブラウザ自動化と Web インスペクター

2 つの補完的な Playwright ベースのツール:

- **browser_playwright**: 実際のブラウザ セッションを自動化します。移動、クリック、フォームへの入力、データの抽出、複数ページのフローの処理を行います。ヘッドレスまたはヘッドなしで動作します。
- **playwright_inspector**: ブラウザーの遷移を記録し、各ステップで DOM スナップショットとスクリーンショットをキャプチャします。 Web インタラクションのデバッグや、時間の経過に伴うページの変更の監査に役立ちます。

### 🔄 動的ツールの読み込み

「tool_catalog」と「tool_load」を使用すると、実行時にツールを検出して有効にすることができます。
起動時にすべてをロードする必要はありません。必要なときに、必要なものだけをアクティブにします。

### 🌐 i18n / L10n

日本語 / 英語 / 简体中文 / 繁體中文 / 한국어 / スペイン語 / フランス語 / Русский / など。
`UAGENT_LANG`を切り替えに設定します。新しいロケールを追加するには、[ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) を参照してください。

この README の翻訳は [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md) で入手できます。

### 🔒 暗号化された環境変数

API キーとシークレットを `.env.sec` (暗号化された `.env` ファイル) に保存します。
`uag_envsec`で管理します。

## 構成と詳細

- **環境変数**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **セットアップ ウィザード**: `python -m uagent.setup_cli`
- **暗号化された環境**: `uag_envsec` — `.env` を `.env.sec` として暗号化します
- **レスポンス API**: レスポンス API モードに「UAGENT_RESPONSES=1」を設定します (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **開発者ドキュメント**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **LLM の小さなヒント**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## プロジェクトの理念

uag は **あなたのマシン上であなたの条件に合わせてあなたの AI になることを目指しています。**

- SaaS への依存関係なし - ローカルで実行
- プロバイダーのロックインなし - いつでも切り替え可能
- UI ロックインなし — CLI / GUI / Web / A2A
- 機能のロックインなし - ツールとスキルで拡張可能

ベンダー ロックインのない、無料の AI エージェント エクスペリエンス。
