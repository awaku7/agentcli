---
name: vup-and-release-whl
description: |
  pyproject.toml の version を patch で +1 し、commit + push したうえで
  dist/*.whl を GitHub Releases にアップロードする手順（および upload_whl_github.py の使い方）。

  対象リポジトリ例: https://github.com/awaku7/agentcli
license: Apache-2.0
---

# vup-and-release-whl

このスキルは **手順（運用Runbook）** です。ツールを自動実行するスキルではなく、
ローカルの作業手順と確認ポイントをまとめたものです。

## 目的

- `pyproject.toml` の `[project].version` を **patch で +1**（例: `0.3.9` → `0.3.10`）
- 変更を commit して `origin/main` に push
- wheel をビルドして、`upload_whl_github.py` で **GitHub Releases の asset としてアップロード**

## 前提

- Git の remote `origin` が GitHub を指していること
  - 例: `https://github.com/awaku7/agentcli.git`
- wheel を作れること（例: `python -m build` が実行できる、など）
- GitHub Releases に対して asset upload / tag / release 作成ができるトークンを用意できること

## 重要（安全）

- **commit/push は破壊的操作**です。push先ブランチが `main` でよいことを確認してください。
- 作業前に `git status` がクリーン、または意図した変更のみであることを確認してください。
- `GITHUB_TOKEN` は秘匿情報です。ログやコミットに含めないでください。

---

# 手順

## 1) 作業ツリー確認

```bash
git status
```

- 余計な変更がある場合は先に片付けます。

## 2) patch バージョンを 1 上げる

このリポジトリでは `pyproject.toml` のここが対象です。

- `pyproject.toml`:
  - `[project] version = "0.3.9"`

### 変更例

`0.3.9` → `0.3.10`

> 注意: `0.3.9` の patch は 9 ですが、次は `0.3.10` です（文字列比較ではなく数値として +1）。

編集後、差分を確認:

```bash
git diff -- pyproject.toml
```

## 3) commit

```bash
git add -- pyproject.toml
git commit -m "Bump version to 0.3.10"
```

※コミットメッセージは運用に合わせて変更してください。

## 4) push

```bash
git push origin main
```

---

# wheel を作る（例）

プロジェクトのビルド方法に依存します。一般的な例:

```bash
python -m pip install -U build
python -m build
```

成果物は通常 `dist/*.whl` に出ます。

---

# GitHub Release に wheel をアップロードする（upload_whl_github.py）

## 必要な環境変数

- `GITHUB_REPO`
  - 形式: `owner/repo`
  - 例: `awaku7/agentcli`
- `GITHUB_TOKEN`
  - 権限: `contents: write` 相当（tag/release/asset 操作に必要）

Windows PowerShell 例:

```powershell
$env:GITHUB_REPO = "awaku7/agentcli"
$env:GITHUB_TOKEN = "..."  # 秘匿
```

## よく使う呼び出し例（最新の wheel を dist から選ぶ）

```bash
python upload_whl_github.py --latest dist --tag v0.3.10 --create-tag --create-release
```

- `--latest dist` : `dist/` 配下の最新更新の `.whl` を選択
- `--tag v0.3.10` : リリース対象タグ（命名は運用に合わせて）
- `--create-tag` : GitHub API で `refs/tags/<tag>` を作成（存在すればスキップ）
- `--create-release` : Release が無ければ作成（あれば継続）

## 既に wheel パスが分かっている場合

```bash
python upload_whl_github.py dist/uag-0.3.10-py3-none-any.whl --tag v0.3.10 --create-tag --create-release
```

---

# トラブルシュート

## Release が無いと言われる

- `--create-release` を付けているか確認

## Tag が無い / 作れない

- `--create-tag` を付ける
- `GITHUB_TOKEN` の権限（contents: write）を見直す

## 同名 asset がある

- スクリプトは同名 asset を検出すると **先に削除してから再アップロード**します。
  権限不足だと失敗します。
