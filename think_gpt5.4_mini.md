# サブエージェント機能の実装方針メモ

## 結論

サブエージェントの反復制御は `batch_state` に寄せず、会話ループ側のフックに寄せる。`batch_state` は進行状態の永続化と復元だけを担当し、LLM の誤操作防止や順序制御は外側で担保する。

## 役割分担

### `batch_state` に置くもの

- `task_description`
- `instructions`
- `targets`
- `current_target`
- `next_index`
- `current_file`
- `completed_files`
- `skipped_files`
- `error_files`
- `pending_files`
- `done_count`
- `pending_count`
- `init` / `load` / `current` / `complete_file` / `skip_file` / `error_file` / `status` / `finalize`

### 会話ループ側に置くもの

- `current_file` の注入
- ツール allowlist
- 空振り応答の検知
- `file == current_file` の検証
- ループ兆候の検出
- 処理結果の妥当性確認

## なぜ分けるか

- `batch_state` は台帳として単純なほど壊れにくい
- `current` / `next` / `advance` / `complete_file` のような類似語は LLM を迷わせる
- `file` の整合性検証や危険操作の遮断は、ツール内部より会話ループ側の方が確実

## 推奨アーキテクチャ

```text
before_llm_call
  -> current_file を取得して注入
  -> allowed_tools を絞る

LLM call
  -> 1ファイルだけ処理

after_llm_response
  -> 空振り/予定説明/反復兆候を検出

before_tool_call
  -> batch_id と file を検証
  -> current_file との一致を強制

after_tool_call
  -> 完了判定
  -> complete / skip / error を確定
```

## 最小実装

1. `batch_state` は既存の永続化をそのまま使う
1. LLM 呼び出し前に `current_file` を 1 件だけ注入する
1. LLM に見せるツールを allowlist で絞る
1. 応答後に `current_file` 以外を触っていないか検証する
1. 成功したら `complete_file`、失敗なら `skip_file` / `error_file` を呼ぶ

## `batch_state` の公開範囲

LLM に通常公開するのは最小限でよい。

- `current`
- `complete_file`
- `skip_file`
- `error_file`
- `status`
- `finalize`

管理用の `load` / `list` / `update` / `reset` / `delete` は通常ループでは非公開にする。

## 廃止・非公開候補

- `next`: `current` と意味が近く、誤解を招く
- `advance`: `complete_file` と重複する
- `update`: 状態破壊リスクが高い

## まず入れる保護

- `current_file` を毎回明示する
- `file != current_file` を拒否する
- `next` / `advance` を非公開にする
- 同じ tool-call の連続回数に上限を付ける
- 空振り応答が続いたら中断する

## 懸念点

1. 既存挙動への影響

   - 公開アクションを減らすと既存テストや管理操作が壊れる可能性がある
   - 通常モードと管理モードを分けるのが安全

1. LLM の空振り

   - 「次は〜します」だけ返すことがある
   - 本文だけでなく tool-call も監視する必要がある

1. 状態ズレ

   - `current` 取得後に状態が変わると、古い `current_file` で完了してしまう
   - `batch_id + current_file + version` などで整合性確認したい

1. リトライ地獄

   - 自動再試行を入れすぎると無限ループになりやすい
   - 再試行回数の上限を決めるべき

1. 実装範囲の拡大

   - 最初から GUI/Web/CLI 全部に入れると重い
   - まずは CLI か共通ループだけに入れて、後で広げるのが無難

## 実装判断

- 状態の真実は `batch_state`
- 反復の真実は会話ループ
- LLM には今の 1 件だけ渡す
- 危険な自由度は最初から与えない

## 相談用の要点

- `batch_state` は台帳
- フックは監視
- 外側ループが制御
- LLM は 1 件だけ処理
- `next` / `advance` / `update` は通常ループから外す
