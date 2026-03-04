# Tests (pytest)

このディレクトリには `src/uagent/tools` 配下のツール群に対する pytest ベースのテストを配置します。

## 実行方法

```bash
python -m pytest -q
```

詳細ログが必要な場合:

```bash
python -m pytest -vv
```

特定ファイルだけ:

```bash
python -m pytest -q tests/test_replace_in_file_tool.py
```

## 方針

- **pytest を採用**（最も一般的でモダン）
- ツールは副作用（ファイル操作・ネットワーク・コマンド実行等）が多いため、原則として以下を徹底します。
  - 一時ディレクトリ（`tmp_path`）を使い、リポジトリ配下を汚さない
  - 外部通信やOS依存機能は **モック** もしくは **条件付きスキップ**
  - 危険操作（削除・実行・上書きなど）は **dry-run / preview** を優先して検証
- テストは **AAA（Arrange-Act-Assert）** を意識し、可読性と失敗時の診断性を優先

## 依存

pytest は別途インストールしてください（例）:

```bash
python -m pip install -U pytest
```
