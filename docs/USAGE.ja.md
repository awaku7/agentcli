# 使用方法（コマンドラインオプション）

このドキュメントでは、uag エントリポイントで使用可能なコマンドラインオプションについて説明します。

______________________________________________________________________

## エントリポイント

| コマンド | Python モジュール | インターフェース |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin ループ) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Web サーバー (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP サーバー |

______________________________________________________________________

## CLI 起動オプション (`uag`)

### `--workdir` / `-C <パス>`

作業ディレクトリ。設定されていない場合は、環境変数 `UAGENT_WORKDIR` が優先され、それがない場合はカレントディレクトリが使用されます。
ディレクトリが存在しない場合は作成されます。

### `--tool-genre-mask <int>`

ツールのジャンルを表すビットマスク。指定すると、対話式のジャンル選択プロンプトがスキップされます。

| ビット | ジャンル | 説明 |
|-----|-------|-------------|
| 1 | basic | 必須のファイル／チャットツール |
| 2 | comm | コミュニケーションツール (Bluesky, Teams) |
| 4 | office | オフィススイートツール (Excel, PDF, PPTX) |
| 8 | devel | 開発ツール (git, lint, compile) |
| 16 | iot | IoTデバイス用ツール (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | コマンド実行ツール |
| 64 | external | 外部プラグインツール |
| 128 | media | 画像・音声の生成および分析 |
| 256 | file | ファイル管理ツール |
| 512 | index | ソース・インデックスナビゲーションツール |
| 1024 | dev | 開発者およびリポジトリツール |
| 2048 | web | Webおよびブラウザツール |
| 4096 | utility | ユーティリティおよびサポートツール |
| 8191 | all | すべてのツール |

例:

```
uag --tool-genre-mask 1 # 基本ツールのみ
uag --tool-genre-mask 9 # 基本ツール + 開発ツール (1 + 8)
uag --tool-genre-mask 8191    # すべてのツール
```

### `--use-tool` / `--no-use-tool`

LLM へのツール定義の送信を有効または無効にします。 `UAGENT_USE_TOOL` 環境変数を上書きします。

- `--use-tool` はツール送信を強制的に有効にします。
- `--no-use-tool` はツール送信を強制的に無効にします。

無効にしている場合、LLM はツール定義を受け取らず、いかなるツールも呼び出すことができません。

### `--computer-use` / `--no-computer-use`

Computer Use を有効または無効にします。 環境変数 `UAGENT_COMPUTER_USE` を上書きします。

### `--inject-message` / `-M <message>`

起動時に LLM にメッセージを挿入し、完了後に終了します。 これは `--non-interactive` を意味します。

### `--embedded`

制約のある、または再現性が重要なデプロイメント向けの組み込みモードです。

- セッションストアを無効にします。
- 明示的に有効にしない限り、ツール管理ツール (`tool_catalog`, `tool_load`, `unload_tool`) を非表示にします。
- `--tool-genre-mask` を無視します。ツールを明示的に読み込むには `--enable-tool` を使用してください。

### `--enable-tool <name>`

起動時にツールを明示的に読み込みます。このオプションは複数回指定でき、コンマ区切りの名前も指定可能です。

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

指定された順序は保持され、LLM に提示されるツールの順序に反映されます。明示的に有効化されたツールは、自動アンロードの対象外となります。

### `--plugin-dir <path>`

指定されたディレクトリからプラグインを読み込みます。このオプションは複数回指定可能です。

______________________________________________________________________

## CLI 専用のオプション

### `--inject-message-auto <goal-options>`

非対話型のインジェクションされたゴールからオートパイロットを開始します。値は `:auto` と同じオプションを使用します。オプションを含む場合は、値全体を引用符で囲んでください。

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "アイテムを並べ替える --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "項目を並べ替える --infinite"
```

通常モードでは、レビュアーの判断パスが使用されます。 `UAGENT_AUTO_SENTINEL=1` に設定すると、シングルLLM センチネルモードが有効になります。 このモードでは、ターゲットの `LLM` は各応答を、以下のいずれか1つで正確に終了させる必要があります：

- `<AUTO_CONTINUE>` — 次のラウンドを実行
- `<AUTO_COMPLETE>` — 正常に終了

マーカーが欠落しているか無効な場合、オートパイロットは安全に停止します。この場合でもターゲットの LLM は実行されますが、追加のレビュアー LLM 呼び出しのみが回避されます。

### `--non-interactive`

非対話モード。stdin ループを開始しません。 ファイルパスが位置引数として指定された場合、それが処理された後、プログラムは直ちに終了します。

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Web サーバーのオプション (`uagw`)

### `--host <address>`

Webサーバーのバインド先アドレス（デフォルト: `127.0.0.1`、`UAGENT_WEB_HOST`で上書き可能）。

デフォルトでは、Web サーバーはローカルホスト (`127.0.0.1`) でのみリスニングします。ネットワーク上の他のマシンからアクセスできるようにするには、`--host 0.0.0.0` を使用してください。

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

前述と同じビットマスクを使用して、ツールのジャンルを選択します。これを指定すると、対話形式のジャンルプロンプトがスキップされます。

### `--use-tool` / `--no-use-tool`

LLM へのツール定義の送信を有効または無効にします。 `UAGENT_USE_TOOL` を上書きします。

### `--computer-use` / `--no-computer-use`

Computer Use を有効または無効にします。 `UAGENT_COMPUTER_USE` を上書きします。

### `--no-frontend`

HTML テンプレートや静的なフロントエンドファイルを使用せずに、API のみを実行します。

### `--embedded`

セッションストアを無効にし、ツール管理ツールを非表示にします (`tool_catalog`, `tool_load`, `unload_tool`)。

______________________________________________________________________

## A2A サーバーオプション (`uaga`)

### `--host <address>`

A2A HTTP サーバーのバインド先アドレス（デフォルト: `0.0.0.0`、`UAGENT_A2A_HOST` で上書き可能）。

### `--port <number>`

A2A HTTP サーバーのポート番号（デフォルト: `8765`、`UAGENT_A2A_PORT` で上書き可能）。

### `--reload`

コード変更時のホットリロードを有効にする（デフォルト：オフ、`UAGENT_A2A_RELOAD`で上書き可能）。

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

前述のビットマスクを使用してツールのジャンルを選択します。 指定すると、対話型のジャンルプロンプトがスキップされます。

### `--use-tool` / `--no-use-tool`

LLM へのツール定義の送信を有効または無効にします。 `UAGENT_USE_TOOL` を上書きします。

### `--computer-use` / `--no-computer-use`

Computer Use を有効または無効にします。 `UAGENT_COMPUTER_USE` を上書きします。

### `--embedded`

セッションストアを無効にし、ツール管理ツール (`tool_catalog`, `tool_load`, `unload_tool`) を非表示にします。

______________________________________________________________________

## 関連する環境変数

| 変数 | 説明 |
|---|---|
| `UAGENT_PROVIDER` | LLM プロバイダー名（起動時に必須） |
| `UAGENT_*_API_KEY` | 選択したプロバイダーの API キー |
| `UAGENT_WORKDIR` | デフォルトの作業ディレクトリ |
| `UAGENT_WEB_HOST` | Web サーバーのバインドアドレス（デフォルト：`127.0.0.1`） |
| `UAGENT_A2A_HOST` | A2A サーバーのバインドアドレス（デフォルト：`0.0.0.0`） |
| `UAGENT_A2A_PORT` | A2A サーバーのポート (デフォルト: `8765`) |
| `UAGENT_A2A_RELOAD` | A2A ホットリロードをデフォルトで有効にする |
| `UAGENT_USE_TOOL` | `0`、`false`、`no`、または `off` に設定するとツールを無効化 |
| `UAGENT_COMPUTER_USE` | Computer Use をデフォルトで有効または無効にする |
| `UAGENT_SESSION_STORE` | セッションストアを有効または無効にする； 組み込みモードでは `0` が強制される |
| `UAGENT_PLUGIN_DIRS` | 追加のプラグイン検索ディレクトリ |
| `UAGENT_AUTO_SENTINEL` | `1`に設定すると、シングルLLMオートパイロット・センチネルモードを有効にする |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | 連続する新しいツール呼び出しの最大回数（デフォルト: `100`） |
| `UAGENT_MAX_TOOL_ROUNDS` | ユーザー操作あたりの最大 LLM/ツール実行回数（デフォルト: `200`） |
| `UAGENT_SHRINK_CNT` | メッセージ内のオプションの自動圧縮しきい値（`0`/未設定 = 無効） |
| `UAGENT_SHRINK_KEEP_LAST` | 縮小後に保持するメッセージ数（デフォルト: `20`） |
| `UAGENT_LANG` | インターフェースの言語（`ja`、`en` など） |

環境変数の完全な一覧については、[ENVIRONMENT.md](ENVIRONMENT.md)を参照してください。

______________________________________________________________________

## 例

### OpenAI を使用した最小限の起動

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### 基本ツールのみを使用したローカル環境

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### すべてのインターフェース上のWebサーバー

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

または

```
uagw --host 0.0.0.0
```

### ローカルホスト上のカスタムポートで動作する A2A サーバー

```
uaga --host 127.0.0.1 --port 8080
```

### 小規模なモデルでツールを無効にする

```
uag --no-use-tool --tool-genre-mask 1
```

### 非対話型のファイル処理

```
uag --non-interactive README.md
```
