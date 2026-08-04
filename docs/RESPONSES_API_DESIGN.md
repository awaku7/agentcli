# Responses API 管理機能設計

## 目的

Responses APIの管理機能を、プロバイダー差異を隠した共通インターフェースとして追加する。P0ではOpenAI/Azureを対象に、既存のResponses Create処理を壊さずにRetrieve、Cancel、Count input tokensを実装する。

## 対象範囲

### Phase 1（P0）

- 共通管理インターフェース
- OpenAI / Azure
- Retrieve a response
- Cancel a response
- Count input tokens
- 既存`previous_response_id`状態との統合
- Ctrl-C / Web Stopとの連携

### Phase 2

- 手動Compact
- サーバーcompactとローカルshrinkのCapability切り替え
- OpenRouter、DeepSeek、BedrockのCapability対応

### Phase 3

- List input items
- Delete a response
- Ollama、Alibaba/Qwen、LM Studio、Sakanaの実機検証

### 対象外

- llama.cppへのResponses API実装
- Responses APIとChat Completionsの完全な相互変換
- プロバイダーごとの全API機能の抽象化

## 共通インターフェース案

新しいプロバイダー管理モジュールを追加し、既存の`client.responses.create()`経路とは分離する。

```python
class ResponsesManager(Protocol):
    def retrieve(self, response_id: str) -> Any: ...

    def cancel(self, response_id: str) -> Any: ...

    def delete(self, response_id: str) -> Any: ...

    def list_input_items(
        self, response_id: str, *, limit: int | None = None
    ) -> list[Any]: ...

    def count_input_tokens(
        self, *, model: str, input: Any, tools: list[dict] | None = None
    ) -> int: ...

    def compact(self, response_id: str) -> Any: ...
```

実装上はプロバイダーのOpenAI SDK clientを受け取り、管理APIが未対応の場合は`UnsupportedResponsesOperation`を返す。例外を握りつぶしてChat Completionsへ暗黙に切り替えない。

## Capability

プロバイダー・モデルごとに管理機能の可否を表す。

```python
@dataclass(frozen=True)
class ResponsesCapabilities:
    create: bool = False
    streaming: bool = False
    retrieve: bool = False
    cancel: bool = False
    delete: bool = False
    list_input_items: bool = False
    count_input_tokens: bool = False
    compact: bool = False
    previous_response_id: bool = False
```

初期値：

| Provider | Create | Retrieve | Cancel | Count tokens | Compact | Previous ID |
|---|---:|---:|---:|---:|---:|---:|
| OpenAI | yes | yes | yes | yes | yes | yes |
| Azure | yes | yes | yes | yes | yes | yes |
| OpenRouter | yes | no | no | no | no | no |
| DeepSeek | yes | no | no | no | no | no |
| Bedrock | yes | unknown | unknown | unknown | unknown | unknown |
| Ollama | yes | unknown | unknown | unknown | unknown | unknown |
| Alibaba / Qwen | probe | unknown | unknown | unknown | unknown | unknown |
| LM Studio | probe | no | no | no | no | no |
| Sakana / Fugu | yes | unknown | unknown | unknown | unknown | unknown |
| llama.cpp | no | no | no | no | no | no |

`unknown`は未検証を意味し、初期実装では非対応として扱う。実機検証後にのみ`yes`へ変更する。

## Response状態管理

既存の`responses_state`を継続利用し、管理操作に必要な情報を追加する。

```json
{
  "provider": "openai",
  "model": "gpt-5.4",
  "previous_response_id": "resp_...",
  "active_response_id": "resp_...",
  "active_response_started_at": 0,
  "last_response_status": "completed"
}
```

### 状態更新

- Create開始時: `active_response_id`は未設定
- Create完了時: `previous_response_id`と`active_response_id`を保存
- Cancel成功時: `last_response_status=cancelled`、継続IDを破棄
- Retrieveで404/期限切れ: 継続IDを破棄し、新規セッションへ移行
- provider/model変更時: 既存IDを再利用しない
- tool continuation失敗時: 既存の`clear_responses_continuation()`を使用

### 保存方針

- API keyや入力本文は保存しない
- Response ID、provider、model、状態、時刻だけ保存する
- 既存のプロバイダー・モデル別state fileを利用する

## Cancel設計

```text
ユーザーのCtrl-C / Web Stop
  ↓
active_response_idを読み取る
  ↓
Capability.cancelを確認
  ↓
responses.cancel(response_id)
  ↓
ストリーム・待機処理をローカルでも停止
  ↓
active_response_idを消去
  ↓
不完全なprevious_response_idを再利用しない
```

Cancel APIが未対応、またはResponse IDがない場合は、API呼び出しを行わずローカル中断だけを実行する。ユーザーには「API側キャンセル未対応」と通知する。

## Retrieve設計

Retrieveは次のタイミングで使用する。

- 起動時の保存済み`previous_response_id`検証
- セッション再開前の状態確認
- ユーザーの状態確認コマンド
- Cancel前のResponse存在確認が必要な場合

404、期限切れ、プロバイダー不一致の場合は、保存済みIDを破棄して新規セッションを開始する。ネットワークエラーの場合はIDを破棄せず、再試行可能なエラーとして扱う。

## Count input tokens設計

優先順位は以下とする。

1. プロバイダーのResponses token count API
2. 既存のローカル`llmcapa`推定
3. トークン数不明としてコンテキスト上限の安全側閾値を使用

画像、tool schema、reasoning設定を含む場合は、プロバイダーAPIの結果を優先する。APIが未対応の場合も、既存のローカルshrink処理を停止させない。

## Compact設計

- OpenAI/Azure: サーバーcompactを使用
- OpenRouter/DeepSeek: サーバーcompactを使用しない
- 未検証プロバイダー: ローカルshrinkへフォールバック
- 手動compactは`/compact`などのUIから呼び出す

Compact後は返却されたResponse IDを次の`previous_response_id`として保存する。compact失敗時は元の継続IDを直ちに破棄せず、再試行またはローカルshrinkを選択する。

## エラー処理

| エラー | 処理 |
|---|---|
| Unsupported | ローカル代替へフォールバックし、debugログに記録 |
| 404 / invalid response ID | 継続IDを破棄して新規セッション |
| 401 / 403 | 認証・権限エラーとしてユーザーに通知。自動再試行しない |
| 429 | 既存のrate-limit retry方針に従う |
| timeout / network error | IDを保持し、再試行可能として扱う |
| malformed response | IDを安全側で破棄し、診断情報を保存 |

## テスト計画

### Unit test

- Capability判定
- provider/model変更時のID破棄
- Retrieve成功、404、timeout
- Cancel成功、未対応、IDなし
- Count token API成功・失敗・ローカルfallback
- compact対応・非対応時のfallback
- state fileの保存と読み込み

### Mock integration test

- OpenAI Responses manager
- Azure Responses manager
- Ctrl-CからCancel APIまでの連携
- streaming中のCancel
- tool continuation中断後のID破棄

### 実機検証

1. OpenAI
2. Azure OpenAI
3. OpenRouter
4. DeepSeek
5. Bedrock

実機検証で確認できない機能はCapabilityを`unknown`のままにし、暗黙に有効化しない。

## 実装順

1. `ResponsesCapabilities`とUnsupported例外
2. OpenAI/Azure managerのRetrieve
3. `active_response_id`の状態管理
4. CancelとCtrl-C / Web Stop連携
5. Count input tokensとローカルfallback
6. 手動Compact
7. 他プロバイダーCapabilityと実機検証
8. List input items / Delete
