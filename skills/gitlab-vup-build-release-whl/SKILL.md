---
name: gitlab-vup-build-release-whl
description: |
  pyproject.toml の [project].version を patch +1 し、commit + push（origin/main）、wheel build を行ったうえで、
  dist の最新 .whl を GitLab Generic Package Registry にアップロードし、tag/release を作成して Release asset link を付与する。
  
  ※ vup-and-release-whl（runbook）を「自動実行スキル」として機械的に再現できるよう、入出力と確認手順を固定した版。
license: Apache-2.0
---

# 目的
- version up（patch +1）→ commit → push → build → GitLab へ upload + tag + release + link を一括で実行する。

# 入力（このスキルがユーザーに確認すること）
必須:
- なし（既定で自動決定する）

任意（必要に応じてユーザーへ確認）:
- リリース対象タグ（例: `v0.3.27`）
  - 既定: `v<pyproject.tomlのversion>`
- Release description
  - 既定: `--generate-description` を使用（直前タグとの差分コミットから生成）

# 前提（環境）
必須環境変数:
- `GITLAB_HOST`
- `GITLAB_PROJECT_ID`
- `GITLAB_TOKEN`

任意:
- `GITLAB_GENERIC_PACKAGE_NAME`（既定 `uag`）
- `GITLAB_GENERIC_VERSION`（通常不要。wheel名から自動抽出）

必要ツール:
- git
- python
- `python -m build`

# 危険操作（必ず事前に確認する）
このスキルはリモートへ変更を加えます。実行前に必ず次をユーザーへ提示し、
**「実行して」** と返答された場合のみ続行する。

確認文（固定）:
- `pyproject.toml` の version を patch +1 して commit します
- `origin/main` に push します
- wheel をビルドします（`python -m build`）
- GitLab へ最新 whl をアップロードします
- tag `vX.Y.Z` を `HEAD` に作成します
- Release `vX.Y.Z` を作成/存在確認し、asset link を追加（同名リンクがあれば上書き）

# 実行フロー（固定）

## 0) 作業ツリー確認
- `git status` が clean であること。

## 1) patch version +1
- `pyproject.toml` の `[project].version` を `X.Y.Z` → `X.Y.(Z+1)` に更新。
- 差分確認: `git diff -- pyproject.toml`

## 2) commit
- `git add -- pyproject.toml`
- `git commit -m "Bump version to X.Y.Z"`

## 3) push
- `git push origin main`

## 4) build
- `python -m pip install -U build`
- `python -m build`

## 5) tag/release/upload（GitLab）
- tag名: `vX.Y.Z`
- ref: `HEAD`（実体は `git rev-parse HEAD` の commit SHA）

実行コマンド（テンプレ・固定）:
```bash
python upload_whl_http.py --latest dist \
  --tag vX.Y.Z \
  --create-tag --tag-ref <COMMIT_SHA> \
  --ensure-release --release-ref <COMMIT_SHA> \
  --generate-description \
  --overwrite-link
```

# 成功判定（検証）
- `git status` が clean（想定通り）
- `git push` が成功
- `dist/` に新しい `.whl` が生成されている
- `upload_whl_http.py` の出力が以下を含む:
  - `HTTP 201`（upload/tag/link のいずれか）
  - `Release link added.`

# 失敗時のよくある原因
- 401 Unauthorized / invalid_token: `GITLAB_TOKEN` の期限切れ。新しい token を発行して環境変数を更新。
- push 失敗: 権限、ブランチ保護、ネットワーク。
- build 失敗: build依存関係不足、pyproject設定。
