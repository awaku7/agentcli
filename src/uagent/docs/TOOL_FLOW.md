# Tool Sending Flow

## 概要

LLM にツールを送る方式はプロバイダとモードによって異なります。

## 方式一覧

### A. Chat Completions API（DeepSeek 等、Responses API 未使用）

```
req_tools = tools.get_tool_specs() if send_tools_this_round else None
```

- `tools.get_tool_specs()` は `TOOL_SPECS` から全ツールを返す
- `TOOL_SPECS` への登録は `tool_level` / `tool_genre` / genre mask で制御される
- デフォルトでは基本ツールのみ登録され、その他は `tool_catalog` → `tool_load` で動的ロード
- `UAGENT_GPT54_TOOL_SEARCH` の影響は受けない

### B. Responses API + OpenAI/Azure + GPT-5.4+（デフォルト = native mode）

```python
responses_tool_specs = None  # → build_responses_request 内で get_tool_specs()
```

- 全ツールをサーバに送信し、サーバ側 tool_search が narrow
- 管理ツール（tool_catalog / tool_load / unload_tool）も含まれる
- auto-unload: スキップ（`_is_gpt54_tool_search_target` が True）
- compaction: 自動適用（`_get_shrink_max_tokens` の閾値）

### C. Responses API + OpenAI/Azure + GPT-5.4+ + `UAGENT_GPT54_TOOL_SEARCH=legacy`

```python
responses_tool_specs = _select_tool_specs_legacy(call_messages)
```

- 初期は `tool_catalog` / `tool_load` / `unload_tool` / `human_ask` のみ
- LLM が `tool_catalog` で目的のツールを検索 → `tool_load` で動的ロード
- `_select_tool_specs_legacy()` はユーザーメッセージに基づいてツールを絞り込む

### D. Responses API + OpenAI/Azure + GPT-5.4+ + `UAGENT_GPT54_TOOL_SEARCH=native`

- A と同じく全ツール送信
- ただし管理ツール（tool_catalog / tool_load / unload_tool）は除外される（サーバ側 tool_search に任せる）
- `_should_preload_lazy_specs()` が True になり、genre フィルタをバイパスして全ツールが強制登録される

## モード判定

| モード | `_get_gpt54_tool_search_mode()` | `_should_preload_lazy_specs()` | 備考 |
|---|---|---|---|
| デフォルト（A / B） | `"native"` | `False` | view 3, 4 参照 |
| legacy（C） | `"legacy"` | `False` | 明示設定が必要 |
| native（D） | `"native"` | `True` | `UAGENT_GPT54_TOOL_SEARCH=native` が必要 |

## auto-unload スキップ条件

```python
if not (_should_preload_lazy_specs()
        or _is_gpt54_tool_search_target(...)
        or bool(core.responses_state.get("previous_response_id"))):
    # auto-unload 実行
```

以下のいずれかに該当する場合はスキップ:

1. `_should_preload_lazy_specs()` が True（native mode 明示）
1. `_is_gpt54_tool_search_target()` が True（OpenAI/Azure + GPT-5.4+ の Responses API）
1. `previous_response_id` が設定されている（全プロバイダの Responses API）

## tool_catalog による動的ツールロード

LLM に最初から全ツールを送るのではなく、必要に応じてツールを動的にロードする仕組みです。

### 動作の流れ

1. 初期状態では `tool_catalog` / `tool_load` / `unload_tool` / `human_ask` のみが LLM に送られる
1. LLM が `tool_catalog` を呼び出すと、利用可能な全ツールの一覧が返る\
   → クエリ（`query`）指定時は、先頭（最高スコア）の未ロードツールが自動的にロードされる\
   → レスポンスの `auto_loaded` フィールドに自動ロードされたツール名が格納され、該当ツールの `loaded` が `true` に更新される
1. 上記以外で必要なツールは `tool_load(tool_name)` で動的ロードする
1. ロードされたツールは次ラウンド以降のツールリストに追加される
1. `unload_tool(tool_name)` で明示的にアンロードできる
1. 一定ラウンド使われなかったツールは auto-unload される（`UAGENT_AUTO_UNLOAD_ROUNDS`、デフォルト `10`）\
   → 自動ロードされたツールもこの対象となる（`_LOADED_SINGLE_TOOLS` に登録されるため）

### 適用されるケース

| ケース | tool_catalog が使われるか |
|---|---|
| Chat Completions API（DeepSeek 等） | はい（genre mask で絞られた残りを動的ロード） |
| Responses API + GPT-5.4+（デフォルト） | いいえ（全ツール送信、サーバ側 tool_search） |
| Responses API + GPT-5.4+ + `legacy` | はい（`_select_tool_specs_legacy` で明示的に使用） |
| Responses API + GPT-5.4+ + `native` | いいえ（tool_catalog 自体が除外される） |

### 実装

- `tool_catalog` / `tool_load` / `unload_tool` は `tools/catalog_tool.py` に実装
- これらは `tool_genre: "devel"` に属し、`tool_level=0`（常時有効）
- `_select_tool_specs_legacy()` はユーザーメッセージを解析し、関連ツールを初期セットに追加する

## 環境変数

| 変数 | デフォルト | 説明 |
|---|---|---|
| `UAGENT_GPT54_TOOL_SEARCH` | (未設定 = native) | `native` / `legacy` / `off` |
| `UAGENT_RESPONSES` | (自動) | `1` で強制有効化 |
| `UAGENT_AUTO_UNLOAD_ROUNDS` | `10` | 未使用ツールをアンロードするラウンド数 |

## Responses API management and state

This section consolidates the former Responses API design, support matrix, and JSONL state policy. The tool flow sections above remain the canonical description of tool dispatch; this section is the canonical description of Responses lifecycle and continuation state.

### Responses API 管理機能設計

## 目的

Responses APIの管理機能は、プロバイダー差異を隠した共通インターフェースとして実装済みである。現在はOpenAI/Azureを対象に、既存のResponses Create処理と分離したRetrieve、Cancel、Delete、List input items、Count input tokens、Compactを提供する。

## 対象範囲

### 実装状況（P0）

- 共通管理インターフェース
- OpenAI / Azure
- Retrieve a response（実装済み）
- Cancel a response（実装済み）
- Count input tokens（実装済み）
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
1. 既存のローカル`llmcapa`推定
1. トークン数不明としてコンテキスト上限の安全側閾値を使用

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
1. Azure OpenAI
1. OpenRouter
1. DeepSeek
1. Bedrock

実機検証で確認できない機能はCapabilityを`unknown`のままにし、暗黙に有効化しない。

## 実装順

1. `ResponsesCapabilities`とUnsupported例外
1. OpenAI/Azure managerのRetrieve
1. `active_response_id`の状態管理
1. CancelとCtrl-C / Web Stop連携
1. Count input tokensとローカルfallback
1. 手動Compact
1. 他プロバイダーCapabilityと実機検証
1. List input items / Delete

### Responses API 対応状況と今後の優先順位

> **現状: P0実装済み・実機検証継続**
>
> Responses API管理機能の共通ラッパーとCLI操作は実装済み。残作業は実機検証、回帰テスト、Web Stop経路の確認である。

## 現在の対応状況

| Responses API | 対応状況 | 備考 |
|---|---:|---|
| Create a response | 対応済み | `client.responses.create()` を通常・ストリーミングで使用 |
| Retrieve a response | 対応済み | `ResponsesManager.retrieve()` / `:response status` |
| Delete a response | 対応済み | `ResponsesManager.delete()` / `:response delete` |
| List input items | 対応済み | `ResponsesManager.list_input_items()` / `:response items` |
| Count input tokens | 対応済み | `ResponsesManager.count_input_tokens()` / `:response tokens` |
| Cancel a response | 対応済み | `ResponsesManager.cancel()` / `:response cancel`、Ctrl-C経路 |
| Compact a response | 部分対応 | Create時に`context_management`を指定し、サーバー側コンパクションを要求 |

## プロバイダー別の対応レベル

ここでいうレベルは、公式APIの網羅的な実機検証ではなく、agentcliの現在の実装経路に基づく分類である。

| プロバイダー | レベル | Create / streaming | 継続 | 自動compact | 実装上の注意 |
|---|:---:|---|---|---|---|
| OpenAI | A | 対応 | 対応 | 対応 | 標準のResponsesリクエストビルダーを使用 |
| Azure OpenAI | A | 対応 | 対応 | 対応 | OpenAI互換経路。APIバージョン・モデル差異は要確認 |
| Amazon Bedrock | B | 対応 | 送信を試行 | 送信を試行 | inputを単一文字列へ変換し、tool定義もフラット化 |
| OpenRouter | B | 対応 | 無効化 | 無効化 | inputを文字列化。継続はローカル履歴で処理 |
| DeepSeek | B | 対応 | 非対応 | 非対応 | stateless。現状は`deepseek-v4-flash`前提 |
| Ollama | C | 対応 | サーバー依存 | サーバー依存 | `extra_body`と`max_output_tokens`を補正。固有機能は要検証 |
| Alibaba / Qwen | C | 汎用経路で試行 | 要検証 | 要検証 | 専用Responses互換処理なし |
| LM Studio | C | 汎用経路で試行 | 要検証 | 要検証 | ローカルサーバーの対応バージョンに依存 |
| Sakana AI / Fugu | C | 汎用経路で試行 | 要検証 | 要検証 | FuguはResponses APIを自動有効化する対象 |
| llama.cpp | D | 非対応 | 非対応 | 非対応 | 標準`llama-server`はChat Completions中心。Responses API変換プロキシが必要 |

### レベルの意味

- **A**: OpenAI/Azure形式に近く、Create、streaming、tool calling、継続、自動compactを実装上扱える。
- **B**: Create、streaming、tool callingは扱えるが、独自形式または一部機能の無効化が必要。
- **C**: OpenAI互換の汎用経路でCreateを試行できるが、継続・compact等は要検証。
- **D**: 現在の実装ではResponses経路を推奨できない。

## プロバイダー共通の制約

- Retrieve、Delete、List input items、Count input tokens、Cancelは `ResponsesManager` と `:response` コマンドから利用できる。
- 「継続」「自動compact」は、管理エンドポイントではなくCreateリクエストの関連パラメーターを指す。
- OpenRouterは`previous_response_id`と`context_management`を削除し、ローカル履歴を文字列化して送る。
- DeepSeekはstatelessとして扱い、`previous_response_id`と`context_management`を使用しない。
- Bedrock、Ollama、Alibaba/Qwen、LM Studio、Sakanaは、接続するゲートウェイやモデルごとの差異が大きい。
- llama.cppを使う場合は`UAGENT_RESPONSES=0`としてChat Completions経路を使う。

## 残作業の優先順位

OpenAI/Azureの実機検証と回帰テストを先に行い、その後にOllama、Alibaba/Qwen、LM Studio、SakanaなどのCapability検証へ進む。

1. **Cancel a response** — Ctrl-C、WebのStop、タイムアウトとAPI側の停止を連携する。
1. **Retrieve a response** — `previous_response_id`の有効性確認とセッション復元に使う。
1. **Count input tokens** — コンテキスト上限、compact、コスト計算を正確にする。
1. **手動 Compact** — 既存の自動compactに`/compact`操作を追加する。
1. **List input items** — サーバー側履歴を正式なストレージとして利用する場合に対応する。
1. **Delete a response** — 履歴削除や機密情報消去が必要になった段階で対応する。

## 今後の方針

1. 共通のResponses管理APIクライアントを追加する。
1. プロバイダーごとに`retrieve`、`cancel`、`input_items.list`、`input_tokens`、`compact`のCapabilityを定義する。
1. Capabilityが不明または非対応の場合は、ローカル履歴・ローカルtoken推定・ローカルshrinkへフォールバックする。
1. 最初の実機検証対象はOpenAI、Azure、OpenRouter、DeepSeekとする。

## 参照

- [llama.cpp #19138: Support OpenAI Responses API](https://github.com/ggml-org/llama.cpp/issues/19138)

### Responses API 状態の JSONL 保存方針

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
1. Response 状態を別のインメモリ配列で管理し、再構築時に末尾へ戻す

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
1. Response 正常完了時にメタデータを追記
1. 現在の専用状態ファイル読み込み・保存処理を停止
1. `:logs` に Response 状態の有無と概要を表示
1. `:load` で最新 Response の有効性と利用条件を検証
1. provider/model/対応能力の検証を追加
1. stale ID のフォールバックを既存処理と統合
1. `rewrite_current_log_from_messages()` でメタデータを保持
1. 既存の専用状態ファイル設定を廃止または非推奨化
1. OpenAI/Azure、非対応プロバイダー、異なるモデル、`:load`、ログ再構築をテスト

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
