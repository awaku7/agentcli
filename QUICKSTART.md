# QUICKSTART（uag）

このドキュメントは、配布された `uag` の whl ファイル（`uag-<VERSION>-py3-none-any.whl`）を **pipでインストールして、CLI（`uag`）を使い始める** ための手順です。

対象OS: Windows

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

## 3. 仮想環境の作成

作業フォルダ直下で実行します。
仮想環境は作らなくても良いですが、依存関係の衝突を避けるため推奨します。

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

### 4.1 インストール

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

### 4.2 インストール確認

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

## 5. Git のインストール（git操作をさせたい場合）

`uag` の起動自体に必要です

### 5.1 Git for Windows

1. https://git-scm.com/download/win からインストーラを取得
2. インストール後、**新しいターミナル**を開いて確認

```bat
git --version
```

### 5.2 winget が使える場合

```bat
winget install --id Git.Git -e
```

---

## 6. 起動方法（CLI: uag）

### 6.1 起動

```bat
uag
```

`uag` が見つからない場合:

```bat
python -m uagent
```

---

## 7. 最低限必要な環境変数（必須のみ）

このツール（`uag`）を **LLM と接続して通常利用する場合**、実装上「未設定だと起動後に `sys.exit(1)` で終了する」必須の環境変数があります。

根拠（実装）:
- `src/uagent/util_providers.py`
  - `detect_provider()` が `UAGENT_PROVIDER` を参照し、未設定なら終了します。
  - `make_client()` が各プロバイダの API キー等を `core.get_env(...)` / `core.get_env_url(...)` で取得し、未設定なら終了します。
- `src/uagent/core.py`
  - `get_env(name)` / `get_env_url(name, default=None)` が、未設定時にエラーメッセージを出して終了します。

---

### 7.1 必須: `UAGENT_PROVIDER`

- `UAGENT_PROVIDER` は利用する LLM プロバイダを指定します。
- 未設定の場合、`src/uagent/util_providers.py:detect_provider()` により起動後に終了します。

許容値（`detect_provider()` の実装でチェック）:

- `azure`
- `openai`
- `openrouter`
- `gemini`
- `grok`
- `claude`
- `nvidia`

---

### 7.2 必須: 選択した `UAGENT_PROVIDER` に応じた API キー等

以下は `src/uagent/util_providers.py:make_client()` が必須として要求する環境変数です（未設定なら `core.get_env*` 経由で終了します）。

#### `UAGENT_PROVIDER=openai` の場合（OpenAI / OpenAI互換）

- 必須: `UAGENT_OPENAI_API_KEY`

#### `UAGENT_PROVIDER=azure` の場合（Azure OpenAI）

- 必須: `UAGENT_AZURE_BASE_URL`
- 必須: `UAGENT_AZURE_API_KEY`
- 必須: `UAGENT_AZURE_API_VERSION`

#### `UAGENT_PROVIDER=openrouter` の場合（OpenRouter / OpenAI互換）

- 必須: `UAGENT_OPENROUTER_API_KEY`

#### `UAGENT_PROVIDER=grok` の場合（xAI Grok / OpenAI互換）

- 必須: `UAGENT_GROK_API_KEY`

#### `UAGENT_PROVIDER=nvidia` の場合（NVIDIA / OpenAI互換）

- 必須: `UAGENT_NVIDIA_API_KEY`

#### `UAGENT_PROVIDER=gemini` の場合（Google Gemini / google-genai）

- 必須: `UAGENT_GEMINI_API_KEY`

#### `UAGENT_PROVIDER=claude` の場合（Anthropic Claude）

- 必須: `UAGENT_CLAUDE_API_KEY`

---

### 7.3 設定例（cmd / PowerShell）

#### cmd（このターミナルだけに設定）

例: OpenAI

```bat
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=YOUR_API_KEY
```

例: Azure OpenAI

```bat
set UAGENT_PROVIDER=azure
set UAGENT_AZURE_BASE_URL=YOUR_AZURE_ENDPOINT
set UAGENT_AZURE_API_KEY=YOUR_AZURE_API_KEY
set UAGENT_AZURE_API_VERSION=YOUR_API_VERSION
```

#### PowerShell（このターミナルだけに設定）

例: OpenAI

```powershell
$env:UAGENT_PROVIDER = "openai"
$env:UAGENT_OPENAI_API_KEY = "YOUR_API_KEY"
```

例: Azure OpenAI

```powershell
$env:UAGENT_PROVIDER = "azure"
$env:UAGENT_AZURE_BASE_URL = "YOUR_AZURE_ENDPOINT"
$env:UAGENT_AZURE_API_KEY = "YOUR_AZURE_API_KEY"
$env:UAGENT_AZURE_API_VERSION = "YOUR_API_VERSION"
```

---

## 8. 使い方（最低限）

`uag` は対話型のローカルAIエージェントです。起動後、プロンプトに指示を書きます。

例:

- フォルダ構造を調べる
  - 「このフォルダを解析して。重要なファイル、構成、実行方法を教えて」
- 特定ファイルを読ませる
  - 「`README.md` を読んで要点を整理して」
- コード解析
  - 「`src/uagent/cli.py` の処理フローと注意点を説明して」

終了:

- `:exit`（実装側でコマンドとして扱われます）

---
