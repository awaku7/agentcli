# UAG ラウンドループのレビューと修正記録（2026-11-24）

- Status: done（RL-01〜05）/ deferred（RL-06）
- Priority: P1
- Source: `src/uagent/uagent_llm.py` のコードレビュー（`run_llm_rounds()` / `_run_one_round()`）
- 確認基準: `main` = `cdcee2d05`（v0.7.56、レビュー開始時）
- 完了時点: `main` = `53d865bea`（PR #462 マージ後）

## 目的

LLM ラウンドループ（ユーザー 1 ターン分の LLM 呼び出しとツール実行の繰り返し）の流れを整理し、レビューで見つかった不具合と保守性の問題を、小さな PR に分けて修正する。

## ラウンドループの構造（レビュー時点）

```text
run_llm_rounds()            ← ユーザー 1 ターン（Auto-Pilot は後続ラウンドごとに再呼び出し）
  ├ ターン前準備（1 回）     ← メモリ投影、状態/receipt 注入、予算、ツール選択
  ├ Computer Use 準備（URL 直接ナビゲーションのみなら LLM を呼ばずに返る）
  └ while True:
       ├ _run_one_round()   ← LLM 1 回とツール実行
       │    ├ 前処理: 割り込み確認 → メッセージ構築 → 圧縮 → コンテキスト計画 → 変換
       │    ├ 振り分け: registry → legacy（gemini/claude/deepseek/zai 等）→ openai_compatible
       │    └ 後処理: assistant 追加 → ツール実行（並列安全なものを先に実行）→ 4 段のループガード
       ├ ラウンド集計とログ（llm.round.completed）
       └ RS_OK なら未使用ツールを自動アンロード
```

`_run_one_round()` の戻り値: `_RS_RETURN`（エラー終了）/ `_RS_BREAK`（正常終了）/ `_RS_CONTINUE`（後処理なしで続行）/ `_RS_OK`（ツール実行後に続行）。

ループガード（どれかに当たると BREAK し、Responses の続きの状態を破棄）:

| ガード | 条件 | 既定値 |
|---|---|---|
| `check_mgmt_tool_loop` | 管理ツールを同じ対象で繰り返す | 4 |
| `check_general_tool_loop` | ツール名と引数がまったく同じ呼び出しを繰り返す | 4 |
| `check_repeating_tool_round_cycle` | 2〜4 ラウンドの周期が 3 周 | 履歴 12 |
| `check_consecutive_tool_calls` | 同じツール名が連続するラウンドに出る | 50 |
| 最後の上限 | `UAGENT_MAX_TOOL_ROUNDS` | 512 |

## 修正した項目

### RL-01: registry 経路で割り込みが無視されていた（PR #460）

- **問題:** openai 経路は、LLM の応答を受け取った後に割り込みフラグを確認し、ツールを実行せずに BREAK する。registry 経路（`_try_registry_simple_chat_round`）にはこの確認がなく、応答待ちの間に Ctrl+C を押しても、ツールが 1 回分実行されてから止まっていた。
- **修正:** 確認処理を `_consume_post_response_interrupt()` にまとめ、両方の経路で、assistant メッセージを履歴に追加する前に呼ぶ。

### RL-02: ループガードの状態がセッション間で共有されていた（PR #460）

- **問題:** `_TOOL_CALL_FINGERPRINTS` と連続回数のカウンタがモジュールのグローバル変数だった。`UAGENT_A2A_CONCURRENCY>1` の A2A はタスクを同じプロセスのスレッドで動かすため、あるセッションが別のセッションの最初の `tool_load` をブロックしたり、新しいターンを始めることで別セッションのカウンタを消したりできた。Web はルームごとに別プロセスなので影響しない。
- **修正:** 状態を `ContextVar` に移した（A2A はタスクごとに `copy_context()` して実行する）。新しいターンでは `begin_loop_guard_turn()` で作り直し、Auto-Pilot（`preserve_tool_loop_state=True`）は同じコンテキストの状態を引き継ぐ。`_TOOL_CALL_FINGERPRINTS` は互換のためにラッパーとして残した。
- **付随して修正:** `_run_one_round` が受け取った連続回数のカウンタを `check_consecutive_tool_calls` に渡しておらず、常にグローバル変数が使われていた。

### RL-03: Computer Use の戻り値が日本語で直書きされていた（PR #461）

- **問題:** URL を直接開く経路の戻り値（`ブラウザーを開きました。` など）が直書きで、どの言語でも日本語が表示されていた。`docs/ARCHITECTURE.md` の I18N 要件に反する。
- **修正:** msgid `Opened the browser.` / `Could not open the browser: %(diagnostic)s` に置き換え、`uagent.pot` と全 38 言語の `uag.po` に追記して `.mo` をコンパイルした。日本語以外の訳はネイティブ確認をしていない。

### RL-04: ターン前準備の例外処理が広すぎた／ループガードのコード重複（PR #462）

- **問題:** ターン前準備の 10 ステップが 1 つの `try / except Exception: pass` で囲まれていた。序盤の 1 か所で例外が起きると残りが黙って飛ばされ、予算が適用されず、**前のターンの `context_tool_specs` が次のターンに残っていた**。
- **修正:**
  - `_prepare_turn_context()` に移し、各ステップを `_run_turn_prep_step()` で個別に保護した。失敗は `llm.turn_prep.failed` ログイベント（`step`、`error_type`）として記録し、残りのステップは続けて実行する。
  - メモリのスナップショット、`active_context`、ツールの選択結果は、作り直す前にクリアする。
  - ステップの実行順は変えていない。
- **リファクタリング:** 4 つのループガードで繰り返されていた停止処理を `_block_tool_loop()` にまとめた。評価順、msgid、イベントの内容、破棄の理由は変えていない。古いコメント「128-round cap」を実際の上限（512）に直した。

## 先送りにした項目

### RL-05: 自動アンロード用のカウンタがグローバル変数のまま（対応済み: PR #465）

- `_TOOL_LAST_ROUND`、`_PRODUCTIVE_ROUNDS`、`_TOTAL_ROUNDS` はモジュールのグローバル変数のまま。
- 管理対象のツール一覧（`_LOADED_SINGLE_TOOLS`、`TOOL_SPECS`）自体がプロセス全体で 1 つなので、カウンタだけをセッション単位にしても意味が通らない。ツール一覧のセッション分離と合わせて設計から見直す必要がある。
- 影響するのは RL-02 と同じく、スレッド並列の A2A だけ。
- **対応（2026-11-25、PR #465）:** カウンタ 3 つを `_AutoUnloadState` にまとめ、RL-02 と同じく ContextVar で持つ形にした。セッション（スレッド／コピーされた文脈）ごとに時計と使用記録が分かれ、片方のラウンドがもう片方のツールを古くすることはなくなった。
- ツール一覧の分離は今回も見送り。一覧が共有である以上、アンロードの効果自体はプロセス全体に及ぶ。一覧ごと分ける必要が出たら、そのとき改めて設計する。

### RL-06: 巨大なファイルと関数の分割

- 候補: `runtime/session_store.py`（約 4,300 行）、`runtime/sandbox_worker.py`（約 4,000 行）、`uagent_llm.py`（約 3,500 行）、`tools/__init__.py`（約 3,200 行）。
- `_run_one_round()` は約 875 行あり、引数が 20 個、戻り値が 5 要素のタプル。前処理、振り分け、後処理の 3 段階に分け、戻り値を dataclass にする案がある。
- **一部対応（2026-11-24、PR #464）:** `_run_one_round()` を前処理・振り分け・後処理の 3 段階に分け、戻り値を `_RoundOutcome` dataclass にした。残りの 3 ファイルは未着手。

## テスト

| ファイル | 内容 |
|---|---|
| `tests/test_round_interrupt_and_loop_isolation.py` | registry/openai 両経路の割り込み、別スレッドのセッション間でのループガードと自動アンロード用カウンタの分離 |
| `tests/test_computer_use_navigation_i18n.py` | 全言語の訳とプレースホルダ、実行時の表示、直書きが残っていないこと |
| `tests/test_round_loop_turn_prep_and_guards.py` | ターン前準備の実行順と失敗時の扱い、共通化した停止処理 |

各 PR では関係する既存テストを手元で実行し、テストスイート全体は CI（`pull-request-tests` ほか）で確認した。PR #460〜#462 の CI はすべて成功し、Codex の自動レビューでも指摘はなかった。

## 更新履歴

- 2026-11-24: 作成。RL-01〜04 は PR #460〜#462 で完了。RL-05〜06 は先送り。
- 2026-11-25: RL-05 を PR #465 で対応。RL-06 は `_run_one_round()` の分割（PR #464）のみ済み、残りは先送りのまま。
