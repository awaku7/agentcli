# QUICKSTART（uag）

このドキュメントは、配布された `uag` の whl ファイル（`uag-<VERSION>-py3-none-any.whl`）を **pipでインストールして、CLI（`uag`）を使い始める** ための最短手順です。

対象OS: Windows

---

## 1. 前提

- Python **3.11以上**（`pyproject.toml` の `requires-python = ">=3.11"`）
- インストール後に `uag` コマンドを使う想定
- （推奨）仮想環境を使用

---

## 2. 作業フォルダの準備

この QUICKSTART は、次のようなフォルダ構成を想定します。

- この手順では「カレントディレクトリ直下にwhlがある」前提で説明します

---

## 3. 仮想環境の作成

作業フォルダ直下で実行します。
仮想環境は作らなくても良いですが、依存関係の衝突を避けるため推奨します。

```bat
python -m venv .venv
.\.venv\Scripts\activate
```

---

## 4. whl を pip でインストール

この手順では、**配布される whl は `uag-<VERSION>-py3-none-any.whl` のみ**という前提です。

### 4.1 インストール

```bat
python -m pip install uag-<VERSION>-py3-none-any.whl
```

### 4.2 インストール確認

```
uag --help
python -c "import uagent; print(uagent.__version__ if hasattr(uagent,'__version__') else 'ok')"
```

---

## 5. Git のインストール（インストール後に入れる場合）

### 5.1 必須: Git for Windows

1. https://git-scm.com/download/win からインストーラを取得
2. インストール後、**新しいターミナル**を開いて確認

```
git --version
```

### 5.2 winget が使える場合

```
winget install --id Git.Git -e
```

---
## 6. 起動方法（CLI: uag）

### 6.1 起動

```
uag
```

または

```
python -m uagent
```

補足:
- workdir を指定しない場合、起動した場所（カレントディレクトリ）が workdir になります。
  （`~/.scheck/`（旧名）/ `~/.uag/`（現行） はログ等の保存先であり、workdirそのものではありません）

起動時に以下のような情報が表示されます（例）。

- `[INFO] workdir = ... (source: CLI/ENV/auto)`
- `[INFO] provider = ...`

### 6.2 使い方（最低限）

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
