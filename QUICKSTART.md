# QUICKSTART（uag / Windows）

このドキュメントは、配布された `uag` の whl（`uag-<VERSION>-py3-none-any.whl`）を **pip でインストールし、CLI（`uag`）で最小構成で動作確認する** ための手順です。

対象OS: Windows

---

## 0. ドキュメント参照（`uag docs`）

インストール後、同梱ドキュメントは `uag docs` で参照できます。

```bat
uag docs
uag docs webinspect
uag docs develop
uag docs --open webinspect
```

---

## 1. 前提

- Python **3.11以上**（`pyproject.toml` の `requires-python = ">=3.11"`）
- （推奨）仮想環境（venv）を使用
- インストール後は `uag` コマンドで起動（見つからない場合は `python -m uagent` で起動可能）

---

## 2. 作業フォルダの準備

- 配布された `uag-<VERSION>-py3-none-any.whl` を作業フォルダに置きます
- 以降のコマンドは、その作業フォルダで実行します

---

## 3. 仮想環境の作成（推奨）

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

## 4. whl を pip でインストール

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

---

## 6. 必要なら Git をインストール（git 操作をさせたい場合）

`uag` の起動自体には不要ですが、`git_ops` や `git` コマンド実行をさせたい場合に必要です。

### 6.1 Git for Windows

1. https://git-scm.com/download/win からインストーラを取得
2. インストール後、**新しいターミナル**を開いて確認

```bat
git --version
```

### 6.2 winget が使える場合

```bat
winget install --id Git.Git -e
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

プロバイダごとの詳細（必要な環境変数、Base URL、モデル指定など）は、次を参照してください。

- `README.md`（Provider の説明）
- `AGENTS.md`（環境変数の一覧）

---

## 8. 動作確認（まず試す指示例）

補足:
- この環境では「`:load 0`」で直前のやりとり（会話）を復活できます。

起動後、プロンプトに指示を書きます。

例:

- フォルダ構造を調べる
  - 「このフォルダを解析して。重要なファイル、構成、実行方法を教えて」
- 特定ファイルを読ませる
  - 「`README.md` を読んで要点を整理して」

---

## 9. 次に読む

- `README.md`（全体像 / Provider / Web Inspector など）
- `AGENTS.md`（ツール一覧 / 環境変数 / MCP 最短例）
- `uag docs develop` / `uag docs webinspect`
