# QUICKSTART（uag / Windows）

このドキュメントは、PyPI から `uag` を **pip でインストールし、CLI（`uag`）で最小構成の動作確認を行う** ための手順です。

対象OS: Windows

______________________________________________________________________

## 1. 前提

- Python **3.11以上**（`pyproject.toml` の `requires-python = ">=3.11"`）
- （推奨）仮想環境（venv）を使用
- インストール後は `uag` コマンドで起動（見つからない場合は `python -m uagent` で起動可能）

______________________________________________________________________

## 2. Git をインストール（必須）

`uag` は起動時に Git のインストールをチェックします。事前に Git をインストールしてください。

### 2.1 Git for Windows

1. https://git-scm.com/download/ からインストーラを取得
1. インストール後、**新しいターミナル**を開いて確認

```bat
git --version
```

### 2.2 winget が使える場合

```bat
winget install --id Git.Git -e
```

______________________________________________________________________

## 3. 仮想環境の作成（推奨）

`uag` を使う作業フォルダで実行します。

```bat
python -m venv .venv
.\.venv\Scripts\activate
```

（PowerShell の場合、実行ポリシーの設定が必要になることがあります。その場合は次を実行してから、もう一度 `activate` してください。）

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

______________________________________________________________________

## 4. PyPI から `uag` を pip でインストール

必要に応じて、先に pip を更新します。

```bat
python -m pip install --upgrade pip
```

`uag` をインストールします。

```bat
python -m pip install uag
```

バージョンを固定したい場合:

```bat
python -m pip install "uag==0.4.6"
```

______________________________________________________________________

## 5. インストール確認

```bat
uag --help
where uag
python -c "import uagent; print(getattr(uagent, '__version__', 'ok'))"
```

`where uag` で見つからない場合は、次で起動できます。

```bat
python -m uagent --help
```

______________________________________________________________________

## 6. 起動と最小設定（CLI）

### 6.1 起動

```bat
uag
```

### 6.1.1（任意）A2A サーバー起動

A2A は別プロセスで動作し、既存の `uag` の挙動は変更しません。

```bat
set UAGENT_A2A_TOKEN=YOUR_TOKEN
uaga
```

`UAGENT_A2A_*` の詳細（認証、ホスト、ポート、再読み込み、公開 URL、同時実行数、実行モードなど）は [ENVIRONMENT.ja.md](ENVIRONMENT.ja.md) を参照してください。

`uag` が見つからない場合:

```bat
python -m uagent
```

終了:

- `:exit`

### 6.2 最小の環境変数（必須）

`uag` は LLM プロバイダ設定が無いと終了します。

- 必須: `UAGENT_PROVIDER`
- 必須: 選択した `UAGENT_PROVIDER` に対応する API キー（例: `UAGENT_OPENAI_API_KEY`）

最小例（OpenAI）:

```bat
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=YOUR_API_KEY
uag
```

サンプルファイルは `samples/` 配下にあります。

- 共通テンプレート: `samples/env.sample.env`
- 生成されるシェル別サンプル: `samples/env.sample.sh` / `samples/env.sample.ps1` / `samples/env.sample.bat`
- プロバイダ別テンプレート: `samples/provider.*.env.sample`
- 使い方詳細: `samples/README.md`

推奨（PyPI / pip インストール後）: `uag_setup` を実行して、カレントディレクトリに `.env`（および任意で `env.sh` / `env.ps1` / `env.bat`）を生成します。
必要なプロバイダ変数が不足している場合、`uag` は自動でセットアップウィザードを起動し、完了後に環境を再確認します。

```bat
uag_setup
```

（リポジトリ開発時）番号選択 + `b`（戻る）に対応した対話式ウィザードで、`samples/` 配下のシェル別サンプルを意図した文字コード/改行コードで生成・更新するには:

```bat
python samples/generate_env_samples.py
```

### 6.3（任意）Responses API 設定 (reasoning / verbosity)

Azure/OpenAI/Bedrock/OpenRouter/Ollama で **Responses API** (`UAGENT_RESPONSES=1`) を使用する場合、推論の試行回数や出力の冗長性を制御できます。

Bedrock では OpenAI互換ゲートウェイで message list `input` がバリデーションエラーになるケースを避けるため、文字列 `input` を使う Bedrock 専用の Responses リクエストビルダーを使用します。

その他のプロバイダでは、実行時にプロバイダ固有の経路または ChatCompletions にフォールバックします。Gemini / Claude / Vertex AI はネイティブ API を使い、`UAGENT_RESPONSES` は無視されます。

例:

```bat
set UAGENT_RESPONSES=1
set UAGENT_REASONING=auto
set UAGENT_VERBOSITY=medium
```

セッション内コマンド（CLI/GUI/Web）:

- `:r [0|1|2|3|auto|minimal|xhigh]`（引数なしで現在の設定を保持）
- `:v [0|1|2|3]`（引数なしで現在の設定を保持）

詳細は [`docs/README.ja.md`](docs/README.ja.md) の「Responses API」セクションを参照してください。

### 6.4（任意）自動 shrink_llm

コンテキスト上限に頻繁に達する場合は、自動要約を有効化できます。

- `UAGENT_SHRINK_CNT`（既定: `100`）
  - system を除いたメッセージ（user/assistant/tool）の件数がこの値に達すると、自動で `:shrink_llm` 相当を実行します。
  - `0` を設定すると無効化します。
- `UAGENT_SHRINK_KEEP_LAST`（既定: `20`）
  - 要約後に末尾へ残す件数です。

注意:

- 自動 shrink は全プロバイダ対応です。
- 圧縮（手動/自動）が動いたとき、現在セッションのログは圧縮後の履歴で書き戻され、ログ保存フォルダ直下の `<log_dir>/.backup/` に 1 世代バックアップが作成されます。

プロバイダごとの詳細（必要な環境変数、Base URL、モデル指定など）は、次を参照してください。

- [`docs/README.ja.md`](docs/README.ja.md)（Provider の説明）
- [`AGENTS.md`](AGENTS.md)（環境変数の一覧）

______________________________________________________________________

## 7. 動作確認（まず試す指示例）

補足:

- この環境では `:load 0` で直前のやりとり（会話）を復活できます。

起動後、プロンプトに指示を書きます。

例:

- フォルダ構造を調べる
  - 「このフォルダを解析して。重要なファイル、構成、実行方法を教えて」
- 特定ファイルを読ませる
  - 「[`docs/README.ja.md`](docs/README.ja.md) を読んで要点を整理して」

______________________________________________________________________

## 8. 次に読む

- [`docs/README.ja.md`](docs/README.ja.md)（全体像 / Provider / Web Inspector など）
- [`AGENTS.md`](AGENTS.md)（ツール一覧 / 環境変数 / MCP 最短例）
- `uag docs develop` / `uag docs webinspect`

______________________________________________________________________

## 9. ドキュメント参照（`uag docs`）

インストール後、同梱ドキュメントは `uag docs` で参照できます。

```bat
uag docs
uag docs webinspect
uag docs develop
uag docs --open webinspect
```
