# Responses API 状態の JSONL 保存方針

## 目的

`previous_response_id` を専用の状態ファイルに保存する方式を廃止し、現在の会話ログ JSONL に保存する。

これにより、会話履歴と Responses API の継続状態を同じセッション単位で管理し、必要に応じて過去の Response チェーンへ戻れるようにする。

## 現状の問題

現在は、Responses API の状態を次のような専用ファイルへ保存している。

```text
~/.uag/responses_state_<provider>_<model>.json
```

この方式には次の問題がある。

- 会話ログと Response 状態の対応関係が分かりにくい
- 同じプロバイダー・モデルでも、どの会話の `response_id` か判別しにくい
- 過去の N 個前の Response へ戻れない
- `:load` やログの再構築と状態ファイルの整合性を保ちにくい

## JSONL への保存形式

通常の会話メッセージとは別に、`role` を持たないメタデータ行を追加する。

```json
{
  "type": "responses_state",
  "schema_version": 1,
  "provider": "openai",
  "model": "gpt-5.4",
  "response_id": "resp_abc123",
  "status": "completed",
  "turn": 12,
  "created_at": "2026-08-05T10:00:00Z"
}
```

### 必須フィールド

| フィールド | 説明 |
|---|---|
| `type` | `responses_state` 固定 |
| `schema_version` | メタデータ形式のバージョン |
| `provider` | Response を生成したプロバイダー |
| `model` | Response を生成したモデルまたはデプロイメント名 |
| `response_id` | `previous_response_id` として再利用する Response ID |
| `status` | 通常は `completed` |
| `created_at` | 保存時刻 |

`turn` は任意だが、ログ上の順序や表示を分かりやすくするため保存する。

APIキー、アクセストークン、プロンプトキャッシュの内容などの秘密情報は保存しない。

## 保存タイミング

Response の開始時ではなく、正常完了後にのみ保存する。

次の状態は保存対象外とする。

- ストリーム途中
- キャンセル済み Response
- API エラー
- ツール呼び出しが未完了
- stale な `response_id` のリトライ中

Response ID は、実際に次のターンで継続可能であることが確認できた後に記録する。

## Response の利用条件

`:load N` でログを明示的に読み込んだ場合、そのログに含まれる最新の完了済み Response を継続候補として扱う。次の条件をすべて満たす場合だけ使用する。

- `status == "completed"`
- `response_id` が `resp_` で始まる
- 保存時の `provider` と現在のプロバイダーが一致する
- 保存時の `model` と現在のモデルまたはデプロイメント名が一致する
- 現在のプロバイダーが `previous_response_id` に対応している
- stale 状態としてマークされていない

モデルが違う場合は使用しない。

```text
openai / gpt-5.4     -> openai / gpt-5.4-mini  : 無効
azure / deployment-a -> openai / gpt-5.4       : 無効
```

Azure のようにモデル名だけでは接続先を一意に特定できない場合は、秘密情報を含まないエンドポイント識別情報を追加で記録することを検討する。

## 非対応プロバイダー

`previous_response_id` に対応していないプロバイダーでは、JSONL に状態レコードが存在しても継続に使用しない。

現行コードで明示的に継続を無効化しているプロバイダーは次の通り。

- Grok
- OpenRouter
- DeepSeek

これらのプロバイダーでは、状態の表示は許可しても、継続には使用しない。

判定はプロバイダー名の固定リストだけでなく、既存のモデル能力判定と Responses API のランタイム条件を再利用する。

## stale Response の扱い

JSONL に Response ID が残っていても、API 側で次の状態になっている可能性がある。

- Response が削除済み
- 保持期間切れ
- プロバイダー側で無効化
- ツールチェーンが途中で切れている
- 現在の入力状態と整合しない

`:load` 時の継続確認に失敗した場合は、次のように処理する。

```text
load 時の継続確認失敗
  -> previous_response_id をクリア
  -> stale 状態を記録または無効化
  -> 新しい Response チェーンで再試行
```

既存の stale `previous_response_id` リトライ処理は維持する。

## 現在のログとの関係

現在のセッションログは次の形式で保存される。

```text
scheck_log_YYYYMMDD_HHMMSS.jsonl
```

`responses_state` レコードは、対応する assistant Response の後に追記する。

```jsonl
{"role":"user","content":"今日の天気"}
{"role":"assistant","content":"..."}
{"type":"responses_state","schema_version":1,"provider":"openai","model":"gpt-5.4","response_id":"resp_abc123","status":"completed","turn":1,"created_at":"..."}
```

## `:load` とログ再構築

既存の会話読み込み処理は `role` のない行を無視できるため、`responses_state` レコードを通常の messages 配列へ混入させない。

ただし、`rewrite_current_log_from_messages()` は現在の messages だけから JSONL を再構築するため、そのままでは状態レコードが消える。

再構築時は次のどちらかを実施する。

1. 元の JSONL から `responses_state` レコードを読み込み、再構築後に保持する
2. Response 状態を別のインメモリ配列で管理し、再構築時に末尾へ戻す

推奨は、元ログのメタデータを保持して再構築する方式である。

`:load` で別の JSONL を読み込んだ場合は、そのログに含まれる最新の `responses_state` レコードを継続候補にする。`:logs` では、状態レコードを持つログを識別できるように表示する。

`:load` は対象ログを現在のセッションへ流し込み、現在のセッションログの先頭へ対象ログを prepend する。元のログファイルは削除しない。読み込み後の会話は、引き続き現在のセッションログへ追記する。

読み込んだログに `responses_state` がある場合は、最新の完了済み Response ID を検証する。provider、model、対応能力、有効性の条件を満たした場合だけ、現在の `responses_state` に設定して継続する。検証に失敗した場合は、メッセージ履歴だけを読み込み、Response ID は設定しない。従来のように `:load` 後に無条件で `responses_state` を消去するのではなく、検証結果に応じて引き継ぐ。

## 専用状態ファイルの廃止

JSONL 方式へ移行後は、次を廃止する。

```text
responses_state_<provider>_<model>.json
UAGENT_RESPONSES_STATE_DIR
UAGENT_RESPONSES_STATE_FILE
```

既存の専用状態ファイルは、自動移行できる会話ログとの対応が保証できないため、原則として自動移行しない。

必要なら、明示的な移行コマンドで対象ログを指定して移行する。

## 起動時の動作

起動時に無条件で古い Response を再利用しない。

推奨動作は次の通り。

- `:logs` で Response 状態を持つログを識別できるようにする
- ユーザーが `:load N` を実行した場合だけ、そのログの最新 Response を検証
- 検証に成功した場合は継続 ID を設定
- 検証に失敗した場合は ID なしでログを読み込む

自動再開が必要な場合は、明示的な設定で有効化する。ただし、デフォルトは安全のため無効とする。

## 実装順序

1. JSONL の `responses_state` レコード読み書きヘルパーを追加
2. Response 正常完了時にメタデータを追記
3. 現在の専用状態ファイル読み込み・保存処理を停止
4. `:logs` に Response 状態の有無と概要を表示
5. `:load` で最新 Response の有効性と利用条件を検証
6. provider/model/対応能力の検証を追加
7. stale ID のフォールバックを既存処理と統合
8. `rewrite_current_log_from_messages()` でメタデータを保持
9. 既存の専用状態ファイル設定を廃止または非推奨化
10. OpenAI/Azure、非対応プロバイダー、異なるモデル、`:load`、ログ再構築をテスト

## 受け入れ条件

- Response 完了後、現在の JSONL に状態レコードが追加される
- 専用の `responses_state_*.json` が新規作成されない
- `:logs` で Response 状態を持つログを識別できる
- `:load N` で同一 provider/model の最新 Response を検証・継続できる
- 非対応プロバイダーでは保存済み ID を継続に使用しない
- stale ID で次の会話が停止しない
- `:load` 後も状態レコードを参照できる
- ログ再構築後も状態レコードが失われない
- 状態レコードに秘密情報が含まれない
