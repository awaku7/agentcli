<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>

<h1 align="center">UAG</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  あなたのAIモデル。あなたのツール。あなたの環境。
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>

<p align="center">
  <a href="#クイックスタート">クイックスタート</a> ·
  <a href="#インターフェース">インターフェース</a> ·
  <a href="#uagでできること">主な機能</a> ·
  <a href="#ドキュメント">資料</a> ·
  <a href="../README.md">English</a> ·
  <a href="README.translations.md">その他の言語</a>
</p>

---

**UAGは、オープンソースのローカルファーストなAIエージェント実行基盤です。**
好みの言語モデルを、普段使うツールやシステムと接続します。コード、ファイル、
ブラウザー、サービス、デバイスを共通のインターフェースで扱えます。
特定のモデル提供事業者にワークフローを縛られません。

| **好きなモデルを選択** | **現実のツールと接続** | **制御権を維持** |
| :--- | :--- | :--- |
| OpenAI、Claude、Gemini、Grok、Bedrock、Ollamaなどのクラウド・ローカルモデル | ファイル、コード、Web、MCP、Agent Skills、プラグイン、クラウド、IoT | ローカル実行、人間による確認、認証情報の保存、設定可能なポリシー |

> UAGは**モデル提供サービスではなく、エージェントの実行基盤**です。
> 外部モデルへのリクエストや接続先サービスの呼び出しは設定によって発生します。
> 「ローカルファースト」は、完全なオフライン動作や隔離を保証するものではありません。

## クイックスタート
<!-- README-SYNC:quick-start -->

**Python 3.11以上**が必要です。[PyPI](https://pypi.org/project/uag/)からインストールしてCLIを起動します。

~~~bash
python -m pip install --upgrade uag
uag
~~~

初回起動時にはセットアップウィザードでモデルプロバイダーと認証情報を設定できます。
環境変数や認証情報ストアを使った設定にも対応します。

プロバイダーやツールの依存パッケージをまとめて導入するには、次を実行します。

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

例えば、次のように指示できます。

~~~text
> このGitリポジトリの変更点とリスクをまとめて。
> このライブラリの最新のドキュメントを探し、移行手順を説明して。
> このファイル群を調べて、簡潔なレポートを作成して。
> :help
~~~

初めて使う方は[Windows向け導入ガイド](QUICKSTART.md)（Gitや仮想環境の準備を含む）や
[環境設定リファレンス](ENVIRONMENT.md)を参照してください。
OS固有の連携はオプションです。

## インターフェース
<!-- README-SYNC:interfaces -->

同じエージェントランタイムとツールレジストリを、複数の入口から利用できます。

| インターフェース | 起動方法 | 用途 |
| :--- | :--- | :--- |
| **CLI** | `uag` | ターミナルでの操作や自動化 |
| **デスクトップ** | `uagg` | ネイティブのデスクトップ対話 |
| **Web** | `uagw` | ブラウザー経由の会話やルーム管理 |
| **A2A** | `uaga` | エージェント間の連携 |
| **VS Code** | [拡張機能ガイド](VSCODE.md) | コード編集と並行した作業 |

デスクトップとWebには、クイックスタートの
`uag[core,providers,tools]` に含まれない追加の依存パッケージが必要です。

~~~bash
# デスクトップGUI（PySide6とプラットフォーム連携）
python -m pip install "uag[platform]"

# Web UI（認証関連、FastAPI、Uvicorn）
python -m pip install "uag[web]" fastapi uvicorn
~~~

Webサーバーは起動時にFastAPIやUvicornのインストールを試みることもありますが、
先に導入しておけば実行時の自動インストールに依存しません。
詳しくは[インターフェース設定](USAGE.md)と[環境設定](ENVIRONMENT.md)を参照してください。

## UAGでできること
<!-- README-SYNC:capabilities -->

| 機能 | UAGが提供するもの |
| :--- | :--- |
| **モデル非依存のワークフロー** | `UAGENT_PROVIDER` でクラウド・ローカルのプロバイダーを切り替え。ツールの書き換えは不要 |
| **コードとファイル操作** | リポジトリの移動、Git調査、Lint、テスト、ファイル操作、ブラウザー自動化 |
| **拡張可能なツール** | 200以上のツール、`tool_catalog` / `tool_load` による動的検出、Python・Rustによるカスタムツール |
| **連携するエージェント** | MCP、A2A、Claude Code互換プラグイン、Agent Skills、サブエージェント |
| **長時間の処理** | オートパイロット、独立した読み取り操作の並列実行、スケジュール、再起動後の復旧、永続セッション |
| **ターミナル以外にも展開** | クラウド、コミュニケーション、ドキュメント、メディア、リアルタイム音声、対応するIoTプロトコル |

### 1つのランタイムで多彩な連携
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**対応プロバイダーの例:** OpenAI、Anthropic、Gemini、Vertex AI、Azure OpenAI、
Amazon Bedrock、Grok、DeepSeek、OpenRouter、Ollama、llama.cpp、LM Studio。
個別の設定は[環境変数](ENVIRONMENT.md)を参照してください。

### Agent Skillsとプラグインでカスタマイズ
<!-- README-SYNC:extensions -->

コアを変更せずにUAGを拡張できます。SkillsMPやClawHubからAgent Skillsを導入したり、
MCPサーバーに接続したり、ツール・スキル・エージェント・フックを含む
Claude Code互換プラグインを読み込んだりできます。

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

カスタムツールは `TOOL_SPEC` と `run_tool()` を使って実装でき、Rustベースのツールにも対応します。
[ツール作成ガイド](../TOOL_CREATOR_GUIDE.md)、
[プラグイン開発ガイド](../src/uagent/docs/DEVELOP_PLUGIN.md)、
[MCP OAuth / プロキシガイド](MCP_OAUTH_PROXY_GUIDE.md)から始めてください。

## 実際のワークフローに対応
<!-- README-SYNC:workflows -->

### コンテキストとメモリー
<!-- README-SYNC:context-memory -->

大規模なツール結果をすべてモデルのアクティブなコンテキストに詰め込む代わりに、
**アーティファクト**として保存できます。必要な部分は後から
`artifact_read` で取り出せます。
セッションの保存にはデフォルトでSQLiteを使用し、履歴検索や明示的なメモリー確認にも対応します。

- [コンテキスト圧縮](CONTEXT_COMPRESSION.ja.md)
- [メモリー](MEMORY.ja.md)
- [セッションの移行](SESSION_PORTABILITY.md)

### 自動化と協調作業
<!-- README-SYNC:automation -->

独立した読み取り操作の並列実行、マルチエージェント連携、
セッション復旧、複数ラウンドのオートパイロットを利用できます。
`:auto` でオートパイロットを開始します。
現在の応答を中断してオートパイロットの停止を要求するには **F12** を押します。

- [オートパイロット](README_AUTO.ja.md)
- [タイマーとスケジュール](SET_TIMER.ja.md)
- [マルチエージェントランタイム](MULTI_AGENT_RUNTIME.md)

### セキュリティと可観測性
<!-- README-SYNC:security -->

機密性の高い操作には `human_ask` による確認を要求できます。
認証情報はOSの認証情報マネージャーまたは暗号化ファイルに保存できます。
Web UIは設定されたOIDCサインインとアクセス制御に対応します。
OpenTelemetryのトレースとメトリクスは**オプトイン**です。

- [エンタープライズポリシー](ENTERPRISE_POLICY.md)
- [MXCサンドボックスのプラットフォーム情報](SANDBOX_MXC.md)
- [リモートWeb / A2AのMXCデフォルト設定](REMOTE_MXC_DEFAULT.md)
- [WebのID管理とルーム](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry設計](UAG_OPENTELEMETRY_DESIGN.md)
- [開発者向け可観測性ガイド](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

これらは**設定可能な制御機能**であり、任意のツール実行が必ずサンドボックスに隔離されるという保証ではありません。
信頼できないユーザーやネットワークに公開する前に、デプロイとポリシーのガイドを確認してください。

### 言語・デバイス・音声
<!-- README-SYNC:languages -->

UAGには**38言語分のロケール**（英語と37言語の翻訳）があります。
オプションで全二重音声連携を利用でき、SwitchBot、Matter、
ECHONET Lite、BACnet、Modbus TCP、OPC UAなどのIoTシステム向けツールも備えています。

- [READMEの各国語版](README.translations.md)
- [IoTユースケース](IOT_USECASE.md)
- [コミュニケーションツール](COMMUNICATION.md)

## ドキュメント
<!-- README-SYNC:documentation -->

| 最初に読む資料 | 詳細資料 |
| :--- | :--- |
| [クイックスタート（Windows）](QUICKSTART.md) | [アーキテクチャ](ARCHITECTURE.md) |
| [CLIの使い方](USAGE.md) | [コンテキスト管理](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [環境変数とプロバイダー](ENVIRONMENT.md) | [エンタープライズポリシー](ENTERPRISE_POLICY.md) |
| [Agent Skills・プラグイン](../src/uagent/docs/DEVELOP_PLUGIN.md) | [ツールの流れ](../src/uagent/docs/TOOL_FLOW.md) |
| [MCPとOAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code拡張機能](VSCODE.md) | [開発者ガイド](../src/uagent/docs/DEVELOP.md) |

[ドキュメントディレクトリ](./)、[英語README](../README.md)、
[その他の翻訳README](README.translations.md)も参照してください。

## 開発と貢献
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

**Pythonコードを変更するPR**では、関連テストとプロジェクトチェックを実行してください。

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

詳しい手順は[AGENTS.md](../AGENTS.md)と[開発者ガイド](../src/uagent/docs/DEVELOP.md)を参照してください。
Issue、ドキュメント改善、ツール、翻訳、焦点を絞ったPRを歓迎します。

## ライセンス
<!-- README-SYNC:license -->

UAGは[Apache License 2.0](../LICENSE)で提供されています。
