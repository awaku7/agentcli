______________________________________________________________________

## name: vup-build-release-whl description: | pyproject.toml の [project].version を patch +1 し、commit + push（origin/main）、wheel build を行ったうえで、 dist の最新 .whl を GitHub Releases または GitLab（Generic Package + Release asset link）へアップロードし、tag/release を作成して紐付ける。 license: Apache-2.0

## ※ vup-and-release-whl（runbook）を「自動実行スキル」として機械的に再現できるよう、入出力と確認手順を固定した版。

# 目的

- version up（patch +1）→ commit → push → build → GitHub/GitLab へ upload + tag + release（+ link/asset）を一括で実行する。

# 入力（このスキルがユーザーに確認すること）

必須:

- 配布先（GitHub / GitLab）
  - 既定: GitLab

任意（必要に応じてユーザーへ確認）:

- リリース対象タグ（例: `v0.3.27`）
  - 既定: `v<pyproject.tomlのversion>`
- Release description
  - 既定: 差分から生成（GitLab: `--generate-description`、GitHub: スクリプトのデフォルト動作）

# 前提（環境）

## 共通

必要ツール:

- git
- python
- `python -m build`

## GitLab へ配布する場合

必須環境変数:

- `GITLAB_HOST`
- `GITLAB_PROJECT_ID`
- `GITLAB_TOKEN`

任意:

- `GITLAB_GENERIC_PACKAGE_NAME`（既定 `uag`）
- `GITLAB_GENERIC_VERSION`（通常不要。wheel名から自動抽出）

## GitHub へ配布する場合

必須環境変数:

- `GITHUB_REPO`（例: `awaku7/agentcli`）
- `GITHUB_TOKEN`

# 危険操作（必ず事前に確認する）

このスキルはリモートへ変更を加えます。実行前に必ず次をユーザーへ提示し、
**「実行して」** と返答された場合のみ続行する。

確認文（固定）:

- 最新のコミット履歴に基づき、`CHANGELOG.md`（英語版）および `CHANGELOG.ja.md`（日本語版）の変更履歴を自動で更新/新規作成します
- `pyproject.toml` の version を更新するか確認します
- *ユーザーが希望する場合のみ* patch +1 と合わせて変更履歴（CHANGELOG）ファイルを commit します
- `origin/main` に push します
- wheel をビルドします（`python -m build`）
- 配布先（GitHub/GitLab）へ最新 whl をアップロードします
- tag `vX.Y.Z` を `HEAD` に作成します
- Release `vX.Y.Z` を作成/存在確認し、成果物を紐付けます
  - GitLab: Release asset link を追加（同名リンクがあれば上書き）
  - GitHub: Release asset（whl）をアップロード（同名assetがあれば削除して再アップロード）

# 実行フロー（固定）

## 0) 作業ツリー確認

- `git status` が clean であること。

## 0-B) CHANGELOGの自動作成/更新

- 最新のコミット履歴（`git log`）および今回の追加機能（差分）に基づき、`CHANGELOG.md`（英語）および `CHANGELOG.ja.md`（日本語）の双方に変更内容（バージョンアップに含む全変更点）を自動で作成または追記する。

## 1) patch version +1

- `pyproject.toml` の `[project].version` を `X.Y.Z` → `X.Y.(Z+1)` に更新。
- 差分確認: `git diff -- pyproject.toml`

## 2) commit

- `git add -- pyproject.toml CHANGELOG.md CHANGELOG.ja.md`
- `git commit -m "Bump version to X.Y.Z and update CHANGELOG"`

## 3) push

- `git push origin main`

## 4) build

- `python -m pip install -U build`
- `python -m build`

## 5A) tag/release/upload（GitLab）

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

## 5B) tag/release/upload（GitHub）

- tag名: `vX.Y.Z`
- target: `HEAD`（実体は `git rev-parse HEAD` の commit SHA）

実行コマンド（テンプレ・固定）:

```bash
python upload_whl_github.py --latest dist \
  --tag vX.Y.Z \
  --create-tag --target <COMMIT_SHA> \
  --create-release
```

補足:

- `upload_whl_github.py` は Release 作成時の本文を、既定で「直前タグとの差分」から生成します。
  - 固定したい場合は `--release-body`（スクリプト側オプション）を使います。

# 成功判定（検証）

- `git status` が clean（想定通り）
- `git push` が成功
- `dist/` に新しい `.whl` が生成されている
- 配布スクリプトの出力が成功を示す（例: HTTP 201 / asset upload成功メッセージ）

# 失敗時のよくある原因

- GitLab: 401 Unauthorized / invalid_token: `GITLAB_TOKEN` の期限切れ。新しい token を発行して環境変数を更新。
- GitHub: 401/403: `GITHUB_TOKEN` 権限不足（contents: write）。
- push 失敗: 権限、ブランチ保護、ネットワーク。
- build 失敗: build依存関係不足、pyproject設定。
