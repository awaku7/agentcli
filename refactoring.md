# Refactoring plan

## 目的
- `src/uagent` 配下の大きいモジュールを分割する
- 保守性を上げつつ、hot path の性能を落とさない
- 既存参照を壊しにくい移行にする

## 完了条件
- 旧モジュールから新モジュールへ責務が移っている
- 既存の起動経路と主要コマンドが動く
- 主要な import / 起動時間が悪化していない
- 旧パスの互換 shim を外せる状態になっている

## 非目標
- 機能の再設計
- 性能改善そのものの追求
- API の全面変更
- 細かすぎる分割

## 優先方針
- hot path は浅く保つ
- 細分化しすぎない
- 重い依存は遅延 import にする
- 旧パスは当面 shim として残す
- `__init__.py` での再exportは最小限にする
- `from ... import *` は避ける

## 責務分割の原則
- `runtime/`: 起動時設定、作業ディレクトリ、環境変数、バナー、記憶
- `tooling/`: ツール定義、登録、トレース、カタログ
- `llm/`: LLM 呼び出し、応答処理、ツール選択
- `ui/`: CLI / GUI / Web の入力出力と表示
- どの層にも他層の実装詳細を持ち込まない
- 依存は低い層から高い層へ一方向にする

## まず候補にするモジュール
1. `src/uagent/runtime_init.py`
2. `src/uagent/cli.py` / `src/uagent/gui.py` / `src/uagent/web.py` / `src/uagent/scheckgui.py`
3. `src/uagent/uagent_llm.py`
4. `src/uagent/util_tools.py`
5. `src/uagent/core.py`

## 推奨ディレクトリ案
```text
src/uagent/
  runtime/
    __init__.py
    init.py
    workdir.py
    banner.py
    env.py
    memory.py

  ui/
    __init__.py
    cli.py
    gui.py
    web.py
    scheckgui.py

  llm/
    __init__.py
    orchestrator.py
    responses.py
    errors.py
    tool_narrowing.py

  tooling/
    __init__.py
    callbacks.py
    specs.py
    trace.py
    catalog.py
```

## 依存方向
- `runtime` は他層への依存を最小にする
- `tooling` は独立した基盤として扱う
- `llm` は必要に応じて `tooling` を参照する
- `ui` は表示と入出力に寄せ、内部ロジックを持たない
- `core` は最上位の接着役として薄く保つ

## 公開APIの維持範囲
- 現行の public import はすべて維持する
- 現行の CLI / GUI / Web の起動経路は維持する
- 新しい内部実装は新パスへ寄せる
- 外部利用が多い名前は先に洗い出す

## 移行ルール
- 新ファイルを先に追加する
- 旧ファイルは削除せず、薄い互換 shim にする
- 新規コードは新パスのみ参照する
- 外部参照を段階的に新パスへ移す
- 安定後に shim を整理する

## shim の扱い
- shim は再exportだけに寄せる
- 余計な処理や副作用を入れない
- 依存が増える場合は shim 側に持たせない
- `__init__.py` の再exportは必要最小限にする
- `import *` を使わない
- shim = 古い import / API を残して新実装へ中継する薄い互換層

## shim 削除条件
- 旧パス参照がなくなる
- 主要テストが新パス前提で通る
- 起動経路が新実装へ統一される
- 1 リリース以上問題が出ていない

## 段階的な進め方
### Phase 1
- `runtime/` を切る
- `ui/` を切る
- この段階で起動経路と表示系の回帰を確認する

### Phase 2
- `uagent_llm.py` を分割する
- この段階で LLM 呼び出しと tool 選択の回帰を確認する

### Phase 3
- `util_tools.py` を分割する
- `core.py` を整理する
- この段階で主要コマンドと統合動作を確認する

## 検証手順
- `py_compile` で構文確認
- 主要テストを実行
- 起動時間を比較する
- import 時間を比較する
- 主要 CLI / GUI / Web の動作を確認する
- 各 Phase ごとに確認する

## 性能確認
- 起動時間
- 主要 CLI の初回応答時間
- import 時間
- GUI 起動時間
- 主要処理の回帰有無

## 計測方法
- 変更前後で同じコマンドを複数回実行する
- 可能なら簡易ベンチを固定化する
- 目視ではなく数値で比較する
- 変更ごとに記録を残す

## リスク
- `__init__.py` の再export過多
- 循環 import
- 起動時に重いモジュールを一括 import
- 小さすぎる分割で import 階層が深くなること

## 補足
- まずは分離を優先する
- 共通化は後で行う
- 性能確認は変更ごとに行う
- 互換 shim は期限を決めて削除する

## 作業ログ
- 作業過程は `refactoring-log.md` に追記する
- 変更の要点、判断理由、確認結果を簡潔に残す
- 失敗ややり直しも残す
- 秘密情報は書かない

## I18N方針
- ソース言語は英語を正本とする
- `ja.po` を再生成するときは、前版の `ja.po` を翻訳参照として残す
- 既存の訳語はできるだけ維持し、一貫性を優先する
- 新しい文言はまず英語で追加し、翻訳は後追いにする
- UI / CLI の文言は短く、意味優先にする
- コード内の直書き文字列は減らし、gettext 経由にする

## 合意事項
- 互換は現行の public import / コマンドをすべて維持する
- テストは全体を対象にする
- shim は薄い互換層として残す
- 旧パスがなくなり、十分な運用確認が取れてから shim を外す
