# subagent ツールの実装メモ

## 目的
他の LLM が実装で迷わないように、subagent ツールの役割・入出力・判断基準を具体化する。
この文書は実装完了後の実態を記録しており、今後の拡張時のリファレンスとして使う。

## 現在の実装状況（v0.5.43）

### 実装済み機能

| 機能 | 状態 | 詳細 |
|------|------|------|
| 6種の役割テンプレート | 完了 | planner, reviewer, summarizer, patch_designer, error_analyst, translator |
| 構造化出力 (response_mode) | 完了 | "json" / "text" 切替可能。デフォルト: summarizer以外はjson |
| required_fields 検証 | 完了 | strict_output=true 時、不足フィールドをエラー扱い |
| evidence_required / evidence_min_items | 完了 | evidence配列の件数検証 |
| response_schema 引数 | 完了 | system promptにJSON Schemaを注入（スキーマ自体のバリデーションは未実装） |
| ContextPack | 完了 | current_goal, current_state, constraints, relevant_snippets, recent_errors |
| current_file 注入 | 完了 | ファイル存在確認＋内容読込＋snippets化（最大20000文字） |
| DuplicateCallGuard | 完了 | 同一 agent_name + task の重複呼び出しをSHA256指紋で検出・ブロック |
| エラー応答の構造化 | 完了 | `{"status":"error","message":"..."}` 形式 |
| 個別プロバイダ設定 | 完了 | UAGENT_SUB_AGENT_{NAME}_PROVIDER/DEPNAME/API_KEY 環境変数で上書き可能 |
| UI通知(cb.log_message) | 完了 | サブエージェント開始時・完了時に結果をログ出力 |
| テスト | 完了 | tests/test_sub_agent_translator.py（単体テスト） |

### 未実装 / 未検証

| 機能 | 優先度 | 備考 |
|------|--------|------|
| 永続化ログ保存 | 中 | ドキュメントに記載あり。run_id/task_id/agent_name/timestamp等をファイルに保存する仕組み |
| PermissionLevel の実制御 | 低 | enum定義のみ。NONE固定でread_only/propose_only未使用 |
| recent_errors の自動設定 | 低 | ContextPackにフィールドありだが、呼び出し側が明示的にセットする想定 |
| current_state の動的更新 | 低 | 初期値PROCESSING固定。実行中にBLOCKED/DONE/ERRORに更新されない |
| response_schema の完全バリデーション | 低 | schema文字列をpromptに流すのみ。jsonschemaライブラリ未使用 |

## 設計原則
1. 既存の `agent_name` は壊さない。
2. 新しい引数はすべて optional にする。
3. JSON 出力を要求する場合でも、従来の text 出力は残す。
4. 参照した根拠を残す。
5. 役割ごとにテンプレートを分ける。
6. 破壊的変更は避ける。

## 実装済みの機能構成

### 0. 文脈注入
`run` が受ける文脈は、以下のように揃える。

- `current_file` があるときは、存在確認だけで終わらせず、内容を読み込んで `relevant_snippets` に入れる。
- `ContextPack` は JSON 化して system prompt に必ず含める。
- `current_state` は初期値 `PROCESSING` を使用する（現状動的更新なし）。
- `recent_errors` は呼び出し側が明示的に ContextPack にセットする想定（未実装）。

### 1. 構造化出力
`run_sub_agent` の引数で制御する。

実装済み引数:
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

重複呼び出しブロック時:

```json
{
  "status": "blocked",
  "message": "Duplicate call blocked for agent: planner with same arguments."
}
```

### 2. 役割テンプレート
用途ごとにプリセットを持つ。

| 役割 | 必須フィールド（デフォルト） |
|------|------------------------------|
| planner | status, role, summary, assumptions, risks, next_actions |
| reviewer | status, role, summary, findings, risks, recommended_actions |
| summarizer | status, role, summary, key_points, open_questions |
| patch_designer | status, role, summary, files, changes, risks, validation_steps |
| error_analyst | status, role, summary, root_cause, evidence, proposed_actions |
| translator | status, role, summary, translated_text, notes |

役割ごとの期待値:
- `planner`: 手順、依存関係、リスクを整理する
- `reviewer`: 欠陥、抜け、危険な変更を指摘する
- `summarizer`: 長文を短くまとめる
- `patch_designer`: 最小変更の差分案を出す
- `error_analyst`: 原因、再現条件、対処案をまとめる
- `translator`: テキスト・POファイルの翻訳（技術用語・プレースホルダ維持）

### 3. 根拠付き結果
`evidence_required=true` のときは `evidence` 配列を要求する。

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

### 4. 個別プロバイダ設定
環境変数でサブエージェントごとに異なるLLMプロバイダを指定可能。

- `UAGENT_SUB_AGENT_{NAME}_PROVIDER`: 個別プロバイダ（例: UAGENT_SUB_AGENT_PLANNER_PROVIDER=claude）
- `UAGENT_SUB_AGENT_{NAME}_DEPNAME`: 個別デプロイ名
- `UAGENT_SUB_AGENT_{NAME}_API_KEY`: 個別APIキー
- `UAGENT_SUB_AGENT_PROVIDER`: 全サブエージェントのフォールバック
- `UAGENT_SUB_AGENT_DEPNAME`: 全サブエージェントのフォールバック
- `UAGENT_SUB_AGENT_API_KEY`: 全サブエージェントのフォールバック

未設定の場合は親エージェントと同じプロバイダを使用する。

### 5. 重複呼び出しガード
`DuplicateCallGuard` が同一 agent_name + parent_goal + task + scope_files の組み合わせを SHA256 指紋で検出し、2回目の呼び出しを `{"status":"blocked"}` で拒否する。

## 現在のアーキテクチャ

```
run_tool(args) → SubAgentRunner.run() → make_client() → _call_llm_single_round()
                                         → _build_structured_prompt()
                                         → _build_user_prompt()
                                         → _validate_structured_output()
```

- 各LLMプロバイダ（openai/claude/gemini/vertexai）に対応
- 親エージェントの core モジュールはインポートせず、util_providers.py のみ使用
- スレッドセーフ：`_SUB_AGENT_ENV_LOCK` で環境変数操作を保護

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

## 推奨ワークフロー（新機能追加時）
1. 目的を確認する。
2. 既存コードの責務を確認する。
3. JSON 形式を決める。
4. 実装する。
5. テストする（tests/test_sub_agent_translator.py を参考に）。
6. 必要なら文書を更新する。

## 完了条件
この文書が十分に具体的である状態は、次の質問に答えられるとき。
- 何を入力として受け取るか → tool JSON の引数定義を参照
- 何を出力するか → 役割ごとのJSON形式を参照
- 失敗時に何を返すか → `{"status":"error","message":"..."}`
- どの役割にどの制約を置くか → 役割テンプレート表を参照
- どの順番で実装するか → 推奨ワークフローを参照
