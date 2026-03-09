# QUICKSTART（uag / Windows）

このドキュメントは、配布された `uag` の whl（`uag-<VERSION>-py3-none-any.whl`）を **pip でインストールし、CLI（`uag`）で最小構成で動作確認する** ための手順です。

対象OS: Windows

---

## 1. 前提

- Python **3.11以上**（`pyproject.toml` の `requires-python = ">=3.11"`）
- （推奨）仮想環境（venv）を使用
- インストール後は `uag` コマンドで起動（見つからない場合は `python -m uagent` で起動可能）

---

## 2. Git をインストール（必須）

`uag` は起動時に Git のインストールをチェックします。事前に Git をインストールしてください。

### 2.1 Git for Windows

1. https://git-scm.com/download/win からインストーラを取得
2. インストール後、**新しいターミナル**を開いて確認

```bat
git --version
```

### 2.2 winget が使える場合

```bat
winget install --id Git.Git -e
```

---

## 3. 作業フォルダの準備

- 配布された `uag-<VERSION>-py3-none-any.whl` を作業フォルダに置きます
- 以降のコマンドは、その作業フォルダで実行します

---

## 4. 仮想環境の作成（推奨）

作業フォルダ直下で実行します。

```bat
python -m venv .venv
.\.venv\Scripts\activate
```

（PowerShell の場合、実行ポリシーの設定が必要になることがあります。その場合は次を実行してから、もう一度 activate してください。）

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## 5. whl を pip でインストール

まず作業フォルダ内の whl 名を確認します。

```bat
dir *.whl
```

次に、そのファイル名を指定してインストールします。

```bat
python -m pip install .\uag-<VERSION>-py3-none-any.whl
```

（whl が1つだけの場合は、次でも構いません）

```bat
python -m pip install .\uag-*.whl
```

---

## 6. インストール確認

```bat
uag --help
where uag
python -c "import uagent; print(getattr(uagent, '__version__', 'ok'))"
```

`where uag` で見つからない場合は、次で起動できます。

```bat
python -m uagent --help
```

---

## 7. 起動と最小設定（CLI）

### 7.1 起動

```bat
uag
```

`uag` が見つからない場合:

```bat
python -m uagent
```

終了:

- `:exit`

### 7.2 最小の環境変数（必須）

`uag` は LLM プロバイダ設定が無いと終了します。

- 必須: `UAGENT_PROVIDER`
- 必須: 選択した `UAGENT_PROVIDER` に対応する API キー（例: `UAGENT_OPENAI_API_KEY`）

最小例（OpenAI）:

```bat
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=YOUR_API_KEY
uag
```

### 7.3（任意）Responses API 設定 (reasoning / verbosity)

OpenAI互換プロバイダで **Responses API** (`UAGENT_RESPONSES=1`) を使用する場合、推論の試行回数や出力の冗長性を制御できます。

例:

```bat
set UAGENT_RESPONSES=1
set UAGENT_REASONING=auto
set UAGENT_VERBOSITY=medium
```

セッション内コマンド (CLI/GUI/Web):
- `:r [0|1|2|3|auto|minimal|xhigh]` (引数なしで現在の設定表示)
- `:v [0|1|2|3]` (引数なしでサイクル切り替え)

詳細は [`README.ja.md`](README.ja.md) の「Responses API」セクションを参照してください。

### 7.4（任意）自動 shrink_llm

コンテキスト上限に頻繁に達する場合は、自動要約を有効化できます。

- `UAGENT_SHRINK_CNT`（既定: `100`）
  - system を除いたメッセージ（user/assistant/tool）の件数がこの値に達すると、自動で `:shrink_llm` 相当を実行します。
  - `0` を設定すると無効化します。
- `UAGENT_SHRINK_KEEP_LAST`（既定: `20`）
  - 要約後に末尾へ残す件数です。

注意:
- 自動圧縮は `UAGENT_PROVIDER=gemini` または `UAGENT_PROVIDER=claude` の場合は **無効** です。
- 圧縮（手動/自動）が動いたとき、現在セッションのログは圧縮後の履歴で書き戻され、ログ保存フォルダ直下の `<log_dir>/.backup/` に 1 世代バックアップ（`.org`）が作成されます。

プロバイダごとの詳細（必要な環境変数、Base URL、モデル指定など）は、次を参照してください。

- [`README.ja.md`](README.ja.md)（Provider の説明）
- [`AGENTS.md`](AGENTS.md)（環境変数の一覧）

---

## 8. 動作確認（まず試す指示例）

補足:
- この環境では「`:load 0`」で直前のやりとり（会話）を復活できます。

起動後、プロンプトに指示を書きます。

例:

- フォルダ構造を調べる
  - 「このフォルダを解析して。重要なファイル、構成、実行方法を教えて」
- 特定ファイルを読ませる
  - 「[`README.ja.md`](README.ja.md) を読んで要点を整理して」

---

## 9. 次に読む

- [`README.ja.md`](README.ja.md)（全体像 / Provider / Web Inspector など）
- [`AGENTS.md`](AGENTS.md)（ツール一覧 /環境変数 / MCP 最短例）
- `uag docs develop` / `uag docs webinspect`

---

## 10. ドキュメント参照（`uag docs`）

インストール後、同梱ドキュメントは `uag docs` で参照できます。

```bat
uag docs
uag docs webinspect
uag docs develop
uag docs --open webinspect
```
