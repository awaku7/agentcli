---
name: pypi-upload-dist
description: dist 配下の配布物（wheel / sdist）を PYPI_TOKEN で PyPI へアップロードするための手順を規定化したスキル。
license: Apache-2.0
---

# 目的

- `dist/` の配布物を PyPI にアップロードする。
- Windows でも安全に実行できるよう、twine の進捗表示を無効化する。

# 入力

必須:

- `PYPI_TOKEN`

任意:

- 配布対象ディレクトリ
  - 既定: `dist`
- 対象ファイル
  - 既定: `dist/*.whl` と `dist/*.tar.gz`

# 前提

- `dist/` にアップロード対象の成果物があること
- `python` と `twine` が利用可能であること

# 危険操作（必ず事前に確認する）

このスキルは PyPI へ公開します。実行前に必ずユーザーへ確認し、
**「実行して」** と返答された場合のみ続行する。

確認文（固定）:

- `dist/` の成果物を PyPI にアップロードします
- 既存の同一バージョンは上書きできません
- `PYPI_TOKEN` を使って公開します

# 実行フロー（固定）

## 0) 成果物確認

- `dist/` に `*.whl` / `*.tar.gz` があることを確認する。

## 1) アップロード

Windows では進捗表示の文字化け回避のため、次を使う。

```powershell
$env:TWINE_USERNAME='__token__'
$env:TWINE_PASSWORD=$env:PYPI_TOKEN
python -m twine upload --non-interactive --disable-progress-bar dist\*.whl dist\*.tar.gz
```

# 成功判定

- twine の出力が成功を示す
- PyPI のプロジェクトページが表示される

# 失敗時のよくある原因

- `PYPI_TOKEN` 未設定、または期限切れ
- 同一バージョンの再アップロード
- `dist/` に成果物がない
- `twine` の表示が Windows コンソールと合わない
