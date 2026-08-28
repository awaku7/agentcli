---
name: batch-state-runbook
description: batch_state を使う反復作業で、順番の崩れ・脱線・処理漏れを防ぐための実行用スキル。 状態を load/update しながら、1ステップずつ着実に処理する。
license: Apache-2.0
version: 1.1.0
---

# Batch State Runbook

## 目的

`batch_state` を使う作業で、LLM が途中で順番を飛ばしたり、未処理を忘れたりしないようにする。

## 強制ルール

1. 毎ターン最初に `batch_state(load)` を確認する。SQLite（`~/.uag/batches/task_history.sqlite3`）の状態と`task_events`の経過を正とする。
1. 判断は `batch_state` の内容だけで行う。会話履歴が失われても、保存済みの`instructions`と`conversation_id`で再開する。
1. 1ターンで処理するのは原則 1 件だけ。
1. 次の対象は `targets[current_target]` の `files[next_index]` とする。
1. 1件を終えたら必ず`batch_state(complete_file)`、`skip_file`、または`error_file`を行う。
1. 途中経過は`message`または`reason`として状態に残す。
1. `pending_files`が空になったら`batch_state(finalize)`する。
1. 記憶や推測で対象を増やさない。
1. `current_target` や `next_index` が曖昧なら、処理を止めて再 `load` する。

## 推奨ワークフロー

1. `load`
1. `targets[current_target].files[next_index]` を 1 件だけ処理
1. `complete_file`、`skip_file`、または`error_file`
1. 必要に応じて`message`/`reason`を保存
1. 次のターンで再`load`

## 進め方の基準

- 完了済みは `next_index` を進めて管理する。
- `targets` は未処理のグループだけを残す。
- 途中で対象を変更する場合は、必ず `update` で状態を直してから続ける。
- 失敗した場合は、失敗内容を `append_log` に書き、次の候補を勝手に飛ばさない。

## 出力の方針

- 返答は簡潔にする。
- まず「現在の対象」と「次の1手」を明示する。
- 余計な候補列挙はしない。

## 適用場面

- i18n の `.po` 更新
- 複数ファイルの査読
- 連番処理が必要な修正
- `batch_state` を使う全反復作業
