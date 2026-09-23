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

## 実行範囲と所要時間

- 修正途中は影響するテストを実行し、コードの最終版で全テストを確認します。
- 通常の文書変更だけならMarkdown整形と `git diff --check` を確認します。
- CIは `docs/**/*.md`、ルートの `README*.md`、`AGENTS.md`、このREADMEだけの変更ではPython検証を省略します。その他の変更や差分取得失敗時は検証を実行します。prompt / skill / fixtureのMarkdownは省略対象ではありません。
- コード変更のPR / mainではPython 3.12で全テスト、3.11 / 3.13 / 3.14で互換性テストを実行します。夜間・手動実行では引き続き4バージョンで全テストを実行します。
- 全テストのCIログには遅い30件を表示します。ローカルでも以下で確認できます（setup / teardownを含む）。

```bash
python -m pytest -q . --durations=30
```

所要時間を根拠に待機や初期化を改善し、認証・権限取消などの回帰テストは維持します。

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
