---
name: vup-and-release-whl
description: |
  pyproject.toml の version を patch で +1 し、commit + push したうえで
  dist/*.whl を GitHub Releases または GitLab (Generic Package + Release link) にアップロードする手順。

  対象リポジトリ例:
  - GitHub: https://github.com/awaku7/agentcli
  - GitLab(オンプレ): http(s)://<host>[/<subpath>]/...
license: Apache-2.0
---

# vup-and-release-whl

このスキルは **手順（運用Runbook）** です。ツールを自動実行するスキルではなく、
ローカルの作業手順と確認ポイントをまとめたものです。

---

# 0) 最初に選ぶ（GitHub / GitLab）

最初に、どちらへ配布するかを決めます。

- **GitHub Releases にアップロード**する → [GitHub 手順](#github-手順)
- **GitLab（Generic Package Registry + Release asset link）**にアップロードする → [GitLab 手順](#gitlab-手順)

> 注: 「GitLab の PyPI Registry に載せたい」用途は、この手順の対象外です。
> GitLab 側は `upload_whl_http.py` により **Generic package（ファイル）**としてアップロードします。

---

# 共通（GitHub/GitLab 共通）: version up 〜 push 〜 wheel build

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

> 重要: commit/push は破壊的操作です。push先ブランチが `main` でよいことを確認してください。

---

# wheel を作る（例）

プロジェクトのビルド方法に依存します。一般的な例:

```bash
python -m pip install -U build
python -m build
```

成果物は通常 `dist/*.whl` に出ます。

---

# GitHub 手順

## 前提

- Git の remote `origin` が GitHub を指していること
  - 例: `https://github.com/awaku7/agentcli.git`
- GitHub Releases に対して asset upload / tag / release 作成ができるトークンを用意できること

## 重要（安全）

- `GITHUB_TOKEN` は秘匿情報です。ログやコミットに含めないでください。

## GitHub Release に wheel をアップロードする（upload_whl_github.py）

### 必要な環境変数

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

### よく使う呼び出し例（最新の wheel を dist から選ぶ）

```bash
python upload_whl_github.py --latest dist --tag v0.3.10 --create-tag --create-release
```

- `--latest dist` : `dist/` 配下の最新更新の `.whl` を選択
- `--tag v0.3.10` : リリース対象タグ（命名は運用に合わせて）
- `--create-tag` : GitHub API で `refs/tags/<tag>` を作成（存在すればスキップ）
- `--create-release` : Release が無ければ作成（あれば継続）

### 既に wheel パスが分かっている場合

```bash
python upload_whl_github.py dist/uag-0.3.10-py3-none-any.whl --tag v0.3.10 --create-tag --create-release
```

---

# GitLab 手順

## 前提

- GitLab がオンプレで、`GITLAB_HOST` がサブパス付きでも良い（例: `http://host/gitlab/`）
- GitLab Generic Package Registry に PUT でアップロードできること
- GitLab Release / Tag を API で作成できる権限のトークンを用意できること

## 重要（安全）

- `GITLAB_TOKEN` は秘匿情報です。ログやコミットに含めないでください。

## GitLab に wheel をアップロードする（upload_whl_http.py）

### 必要な環境変数

- `GITLAB_HOST`
  - 例: `http://wgspace.sbc.nttdata-sbc.co.jp/gitlab/`
- `GITLAB_PROJECT_ID`
  - 例: `340`
- `GITLAB_TOKEN`
  - GitLab Personal Access Token（ヘッダ `Private-Token`）

任意:
- `GITLAB_GENERIC_PACKAGE_NAME`（既定 `uag`）
- `GITLAB_GENERIC_VERSION`（wheel名から抽出する version を上書きしたい場合）

Windows PowerShell 例:

```powershell
$env:GITLAB_HOST = "http://wgspace.sbc.nttdata-sbc.co.jp/gitlab/"
$env:GITLAB_PROJECT_ID = "340"
$env:GITLAB_TOKEN = "..."  # 秘匿
```

### よく使う呼び出し例（最新の wheel を dist から選ぶ）

```bash
python upload_whl_http.py --latest dist --tag v0.3.10 --create-tag --ensure-release --generate-description --overwrite-link
```

意味:
- `--create-tag` : GitLab API で tag を作成（存在すればスキップ）
- `--ensure-release` : Release が無ければ作成（あれば継続）
- `--generate-description` : 直前タグとの差分コミットから description を生成
- `--overwrite-link` : 同名の Release asset link があれば削除して作り直し

### 既に wheel パスが分かっている場合

```bash
python upload_whl_http.py dist/uag-0.3.10-py3-none-any.whl --tag v0.3.10 --create-tag --ensure-release --generate-description --overwrite-link
```

### 直前タグが検出できない/意図と違う場合

- `--base-tag <tag>` で比較元タグを固定します。

例:

```bash
python upload_whl_http.py --latest dist --tag v0.3.10 --base-tag v0.3.9 --generate-description --ensure-release --overwrite-link
```

---

# トラブルシュート（共通）

## Release が無いと言われる

- GitHub: `--create-release` を付けているか確認
- GitLab : `--ensure-release` または `--create-release` を付けているか確認

## Tag が無い / 作れない

- GitHub: `--create-tag` を付ける / トークン権限（contents: write）を見直す
- GitLab : `--create-tag` を付ける / トークン権限（api, write_repository 等）を見直す

## 同名 asset/link がある

- GitHub: 同名 asset は **先に削除してから再アップロード**します（権限不足だと失敗）
- GitLab : `--overwrite-link` を付けると、同名 Release asset link を **削除してから再作成**します
