# subagent ツール改善メモ

## 目的
他の LLM が実装で迷わないように、subagent ツールの役割・入出力・判断基準を具体化する。

## この文書の使い方
- 新しい subagent 機能を追加する前に読む。
- 実装時は、この文書に書かれた JSON 形式と処理順を優先する。
- 曖昧な点があっても、まず後方互換を保つ。

## 設計原則
1. 既存の `agent_name` は壊さない。
2. 新しい引数はすべて optional にする。
3. JSON 出力を要求する場合でも、従来の text 出力は残す。
4. 参照した根拠を残す。
5. 役割ごとにテンプレートを分ける。
6. 破壊的変更は避ける。

## 推奨する機能構成

### 0. 文脈注入
`run` が受ける文脈は、まずここで揃える。

- `current_file` があるときは、存在確認だけで終わらせず、内容を読み込んで `relevant_snippets` に入れる。
- `ContextPack` は JSON 化して、system prompt か user prompt に必ず含める。
- `current_state` は少なくとも `PROCESSING` / `BLOCKED` / `DONE` / `ERROR` を使う。
- `recent_errors` は JSON 失敗や権限制御失敗の再試行時に更新する。

### 1. 構造化出力
`run_sub_agent` ではなく `run` の引数で制御する。

推奨引数:
- `response_mode`: `"json"` または `"text"`
- `response_schema`: JSON Schema 形式の辞書
- `required_fields`: 必須キー一覧
- `strict_output`: 必須キーや型の不一致をエラー扱いにする
- `evidence_required`: 根拠項目を要求する
- `evidence_min_items`: 最低件数

JSON モード時の返り値は、次のようなオブジェクトを基本にする。

```json
{
  "status": "completed",
  "role": "planner",
  "summary": "短い要約",
  "assumptions": ["前提1", "前提2"],
  "risks": ["注意点1"],
  "next_actions": ["次の作業1", "次の作業2"]
}
```

失敗時は次の形を返す。

```json
{
  "status": "error",
  "message": "失敗理由"
}
```

### 2. 役割テンプレート
用途ごとにプリセットを持つ。

候補:
- `planner`
- `reviewer`
- `summarizer`
- `patch_designer`
- `error_analyst`

役割ごとの期待値:
- `planner`: 手順、依存関係、リスクを整理する
- `reviewer`: 欠陥、抜け、危険な変更を指摘する
- `summarizer`: 長文を短くまとめる
- `patch_designer`: 最小変更の差分案を出す
- `error_analyst`: 原因、再現条件、対処案をまとめる

### 3. 根拠付き結果
以下を必須にすると、他の LLM が次の作業に進みやすい。

- 参照ファイル名
- 行番号
- 実行コマンド
- テスト結果
- 変更理由

`evidence_required=true` のときは `evidence` 配列を返す。

例:

```json
{
  "status": "completed",
  "role": "error_analyst",
  "summary": "JSON 解析失敗が原因",
  "root_cause": "出力が JSON 形式ではない",
  "evidence": [
    "raw_output に先頭テキストが含まれていた",
    "json.loads で例外が発生した"
  ],
  "proposed_actions": [
    "system prompt に JSON のみ出力する制約を追加する",
    "strict_output=true のときは mismatch をエラーにする"
  ]
}
```

### 4. ログ保存
`run_sub_agent` を使ったときは、親セッションログとは別にサブエージェント専用ログを残す。

- 1 回の実行ごとに `run_id` / `task_id` / `agent_name` / `timestamp` / `provider` / `model_name` / `current_file` / `scope_files` / `response_mode` を記録する。
- 可能なら `system_prompt` / `user_prompt` / `raw_output` / `parsed_result` / `status` / `error` も残す。
- 保存先は状態ディレクトリ配下の専用ログ領域に揃え、実装側で追いやすい名前にする。
- 保存失敗は本体処理を止めず、警告として扱う。
- 秘密情報は必ずマスクしてから保存する。

## 実装時の判断基準
- 既存の動作と衝突するなら、まず後方互換を優先する。
- 新しいフィールドを追加する場合は、既存の利用者が壊れない形にする。
- エラーは例外で投げっぱなしにせず、可能な限り構造化して返す。
- 必要情報が足りない場合は、推測で埋めずに不足として返す。

## 他の LLM が実装しやすくするためのルール
- 1 回の変更で目的を 1 つに絞る。
- 変更前に入出力仕様を先に決める。
- 実装後は必ずテスト可能な形で終える。
- 仕様変更がある場合は、使用例も同時に更新する。
- 迷ったら「最小変更」で実装する。

## 推奨ワークフロー
1. 目的を確認する。
2. 既存コードの責務を確認する。
3. JSON 形式を決める。
4. 実装する。
5. テストする。
6. 必要なら文書を更新する。

## 完了条件
この文書が十分に具体的である状態は、次の質問に答えられるとき。
- 何を入力として受け取るか。
- 何を出力するか。
- 失敗時に何を返すか。
- どの役割にどの制約を置くか。
- どの順番で実装するか。

## まず入れるなら
優先順は次の 3 つ。
1. 構造化出力
2. 根拠付き結果
3. 役割テンプレート

## 補足
- `response_mode`, `response_schema`, `required_fields`, `strict_output`, `evidence_required`, `evidence_min_items` を `run` 引数で扱う。
- JSON モード時は構造化出力と根拠を優先する。
