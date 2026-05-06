---
name: batch-state-runbook
description: >
  batch_state を使う反復作業で、順番の崩れ・脱線・処理漏れを防ぐための実行手順スキル。
  毎ターン load/update を強制し、1件ずつ順番に処理する。
license: Apache-2.0
version: 1.0.0
---

# Batch State Runbook

## 目的

`batch_state` を使う作業で、LLM が途中で順番を飛ばしたり、未処理を忘れたりしないようにする。

## 強制ルール

1. 毎ターン最初に `batch_state(load)` を確認する。
1. 以後の判断は `batch_state` の内容だけで行う。
1. 1ターンで処理するのは原則 1 件だけ。
1. `pending_files` の先頭 1 件だけを次の対象にする。
1. その 1 件を終えたら必ず `batch_state(update)` を行う。
1. 途中経過は必ず `batch_state(append_log)` に残す。
1. `pending_files` が空になったら `batch_state(finalize)` する。
1. 記憶や推測で対象を増やさない。
1. `current_file` 相当の状態が曖昧なら、処理を止めて再 `load` する。

## 推奨ワークフロー

1. `load`
2. `pending_files[0]` を 1 件だけ処理
3. `update`
4. `append_log`
5. 次のターンで再 `load`

## 進め方の基準

- `done_files` は完了済みだけを入れる。
- `pending_files` は未処理だけを残す。
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
