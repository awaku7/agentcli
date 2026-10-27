<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  1つのローカルエージェント。あらゆるモデル。あらゆるツール。あなたの環境、あなたのルール。
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

**uagを選ぶ理由**

uagは、好みのモデルを実際のツールにつなぐ、ローカルファーストのAIエージェントです。
ファイル、ブラウザー、コードベース、コミュニケーション、クラウドAPI、IoTデバイス、MCPサーバー、
マルチエージェントワークフローを扱う、単一の拡張可能なランタイムを提供します。

- **プロバイダーの自由** — OpenAI、Anthropic、Gemini、Azure、Bedrock、Ollama、llama.cpp、vLLM、Grok、DeepSeekなど。
- **ローカルファースト実行** — エージェントのランタイムとツールは手元のマシン上で動作し、選択したAPI呼び出しだけが外部へ送られます。
- **統一されたツールレイヤー** — CLI、デスクトップGUI、Web UI、VS Code、A2Aのどこからでも同じツールを利用できます。
- **並列実行を前提とした設計** — 独立した読み取り専用操作を同時に実行できます。
- **拡張可能** — コアを変更せずに、ツール、プラグイン、Agent Skills、MCPサーバー、Rust実装のツールを追加できます。
- **安全性を重視** — 破壊的操作、認証情報、デバイス制御、ネットワークへの書き込みは、明示的な確認とポリシー制御に対応します。

> **要するに:** uagは、AIモデルと現実の環境の間に位置するコントロールプレーンです。

> **🧠 コンテキストに応じたツールの結果** — 大規模なツール結果は、現在のモデルに渡すコンテキストから可能な限り除外します。uagは結果をアーティファクトとして保存し、代わりに安定したArtifact参照を含む必要な範囲だけのプレビューをモデルに渡します。これにより、ツールが大量の結果を生成しても、後続ターンに必要な入力トークン数を大幅に削減できます。
> [詳細なコンテキスト圧縮ガイド](CONTEXT_COMPRESSION.ja.md) を参照してください。

## クイックスタート

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

初回起動時にセットアップウィザードが開きます。プロバイダーの設定を支援し、選択した設定をローカル環境に保存します。

一般的な機能グループを利用するには:

```bash
python -m pip install "uag[core,providers,tools]"
```

> プラットフォーム連携はオプションです。オペレーティングシステムに必要なものだけをインストールしてください。

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## インターフェース

| インターフェース | コマンド | 最適な用途 |
|---|---|---|
| **CLI** | `uag` | 速く、キーボード中心の作業 |
| **Desktop GUI** | `uagg` | ネイティブなデスクトップ体験 |
| **Web UI** | `uagw` | ブラウザーからのアクセス |
| **A2A server** | `uaga` | エージェント間通信 |
| **VS Code** | Extension | エディター内での説明、リファクタリング、修正、ツールの閲覧 |

すべてのインターフェースで、同じプロバイダー設定、ツールレジストリ、安全ルール、セッションデータを共有します。

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## できること

プロバイダーアダプターは、次のようなホスト型・ローカルの各種ランタイムに対応しています。

- ファイルの読み取り、作成、編集、検索、ハッシュ計算、アーカイブ、検査
- Gitの変更確認、シークレットのスキャン、テスト実行、Lint、コンパイル、カバレッジ計測
- 大規模なPython、TypeScript、JavaScript、Go、Rust、C/C++、Java、C#、COBOL、VBAなどのコードベースをナビゲート
- 複数ページのワークフローやダウンロードを含む、Playwrightによるブラウザー自動化

- **MCP** — OAuth対応サービスを含む外部ツールサーバーに接続
- **A2A** — 他のエージェントや互換サーバーと連携
- **Cloud** — 書き込み時の確認を伴うAWS、Google Cloud、Azure APIアクセス
- **Communication** — Gmail、Bluesky、Discord、Microsoft Teams、pybitchat
- **IoT** — SwitchBot、ECHONET Lite、Matter、BACnet、Modbus TCP、OPC UA、UPnP
- **Media** — 画像の生成・編集、音声の文字起こし・音声合成、カメラ撮影、QRコード
- **Documents** — PDF、PowerPoint、Word、Excel、CSV、JSON、YAML、SQL、ログ分析

- **SwitchBot** — クラウドとBLEによる検出、状態取得、制御、バッチ処理、サブスクリプション
- **ECHONET Lite** — INF通知を含む、日本の家電の検出と制御
- **Matter** — エンドポイント、クラスター、属性、状態履歴、サブスクリプション、制御
- **BACnet / Modbus TCP / OPC UA** — 産業およびビルオートメーションの読み取り、書き込み、ブラウジング、監視
- **UPnP** — デバイス検出、WAN状態、ルーターのポートマッピング管理

### uagの位置づけ

uagは、一方では人やインターフェースと、もう一方ではモデル、ツール、現実世界のシステムとの間に位置します。
会話を調整し、機能を選択し、安全ルールを適用し、ワークフローを再開可能な状態に保ちます。

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### プラグイン、Agent Skills、マーケットプレイス

コアをフォークせずに、uagを専門エージェントに変えられます:

- ディレクトリ、ZIP、Gitリポジトリ、HTTPソース、マーケットプレイスから**Claude Code互換プラグイン**をインストール
- スキル、サブエージェント、MCPサーバー、フック、スラッシュコマンド、出力スタイル、依存関係、チャンネルをパッケージ化
- [SkillsMP](https://skillsmp.com)と[ClawHub](https://clawhub.ai)からコミュニティ機能を検索
- `UAGENT_EXTERNAL_TOOLS_DIR`を通じて、組織内のプライベートなスキルとツールをローカルに追加

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

[Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md)を参照してください。

- **200以上のツール** — ファイル、Web、メディア、ドキュメント、コード、クラウド、コミュニケーション、IoTに対応
- **動的な検出と読み込み** — `tool_catalog`で機能を探し、必要なときだけ`tool_load`で有効化
- **コードインテリジェンス** — `code_map`、言語別の`idx`ナビゲーター、Gitレビュー、テスト実行、Lint、コンパイル、カバレッジ
- **Claude Code互換プラグイン** — スキル、エージェント、MCPサーバー、フック、コマンド、マーケットプレイスに対応
- **Agent Skills** — SkillsMPとClawHubから利用可能
- **カスタムPythonツール** — `TOOL_SPEC`と`run_tool()`を使用
- **Rust実装のツール** — 軽量なネイティブ拡張向け

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## 実際のワークフローに対応

### 🧠 コンテキストに応じたツールの結果

大規模なツール結果は、現在のモデルに渡すコンテキストから可能な限り除外します。uagは結果をアーティファクトとして保存し、代わりに安定したArtifact参照を含む必要な範囲だけのプレビューをモデルに渡します。これにより、ツールが大量の結果を生成しても、後続ターンに必要な入力トークン数を大幅に削減できます。

`:load <index>`で以前の会話を再開できます。ツール結果はキャッシュでき、アプリケーションを再構築せずにプロバイダーを変更できます。

[Context compression](CONTEXT_COMPRESSION.ja.md) · [Memory](MEMORY.ja.md) · [Session portability](SESSION_PORTABILITY.md)

### オートパイロット

レビューモデルを使う複数ラウンドの作業には、`:auto`を使用します。`--max-rounds N`でラウンド上限を設定できます。
オートパイロットまたは現在の応答を停止するには、**F12**を押します。

独立した読み取り専用操作は、安全な場合に並行して実行されます。Web検索、ファイル検査、リポジトリ分析などの
処理を、設定可能なワーカープール（`UAGENT_PARALLEL_WORKERS`）で並列に実行できます。書き込み操作は
直列化するか、確認を求めます。

セッションの継続、ツール結果のキャッシュ、バッチ状態、再起動からの復旧、DAGスケジューリング、
マルチエージェントオーケストレーションにより、複雑な作業を一度きりではなく再開可能にします。

[Auto-pilot](README_AUTO.ja.md) · [Timers](SET_TIMER.ja.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 プライベート、多言語、ポリシー対応

`human_ask`は機密性の高い操作の前に処理を一時停止します。ファイルの削除、上書き、シェルコマンド、デバイス制御、
認証情報の操作、ネットワークへの書き込みは、確認およびポリシールールによって管理できます。

長期間有効なシークレットをプロンプトへ直接書く代わりに、認証情報ストアを使用してください。

Web UIは、Authorization Code + PKCEを使ったOIDCサインイン、検証済みIDトークン、サーバー側セッション、プロジェクト/ルームのアクセス制御に対応します。検証済みのMicrosoft Entra IDグループクレームは、設定に応じてディレクトリ連携のアクセスポリシーに利用できます。Windows Active Directory、OAuth、trusted-proxyは明示的な検証済みIDアダプターを介して連携できます。Windows ADにはデプロイ固有のKerberos/Negotiate検証器が必要で、既定では有効ではありません。

uag には、オプトイン、プロバイダー中立の OpenTelemetry トレースと、Agent、LLM、ツール、Context、Memory、および取得操作のメトリクスが含まれています。可観測性はデフォルトでは無効になっています。

ローカルファーストは、完全なオフライン動作やすべてのツール実行の隔離を意味しません。外部モデルや連携サービスへのアクセスは設定に依存します。

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 多言語翻訳

- `translate_text` は、`provider=auto`、`provider=deepl`、または `provider=google` を指定して、Google Translateまたは公式のDeepL Pythonクライアントを利用できます。
- ツール定義は英語を含む38言語で利用できます。プレースホルダーや技術的な識別子は保持されます。

全二重音声はOpenAI Realtime、Azure OpenAI、xAI Grok Voice、Gemini Live、Bedrock Nova Sonicで利用できます。
オプションでAEC3エコーキャンセルと、安全性を制限したリアルタイムの関数呼び出しにも対応します。

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## ドキュメント

| トピック | ドキュメント |
|---|---|
| 環境変数 | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| アーキテクチャと不変条件 | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| リポジトリツール | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoTユースケース | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| コミュニケーションツール | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| オートパイロット | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code拡張機能 | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| 開発者ガイド | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| ツールフロー | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## 開発と貢献

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

PRを出す前に、次のチェックを実行します。

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

開発ワークフローの全体については、[DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)を参照してください。

バグ報告、機能のアイデア、ドキュメントの改善、翻訳、ツール、スキル、プルリクエストを歓迎します。
大きな変更を加える前に、issueまたはdiscussionを開いてください。[開発者ガイド](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)を読み、
プルリクエストを送る前に上記のチェックを実行してください。

## ライセンス

[Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE)の下でライセンスされています。
