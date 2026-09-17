# UAG リファクタリング候補（現行 v0.7.7）

## 結論

最優先は **`llm_round_helpers.py` を一度に作り替えることではなく、LLM 1 ラウンドのオーケストレーションから「コンテキスト構築」「プロバイダ差異」「Responses の継続状態」「ストリーム描画」「復旧」を段階的に外へ出すこと**である。現状はすでに `ContextManager`、`ResponsesManager`、`provider_context` という良い分割の芽がある。一方で、`llm_round_helpers.py`（1,876 行）と `uagent_llm.py` の provider 分岐に、複数レイヤーの判断と副作用が残っている。

この文書の初期調査は、公開リポジトリの `main`、コミット [`2435ad6`](https://github.com/awaku7/agentcli/tree/2435ad6a69244cf8dabe18286389bb0389c3cfde)（`pyproject.toml` は v0.7.7）を基準にした設計メモである。後半の「現行実装との比較」は、その後の実装を反映して更新している。機能追加ではなく、互換性を保ちながら依存方向を整えるための順序を示す。

## 調査した現在の構造

- [`llm_round_helpers.py`](https://github.com/awaku7/agentcli/blob/2435ad6a69244cf8dabe18286389bb0389c3cfde/src/uagent/llm_round_helpers.py) は、入力正規化、翻訳、Responses / Chat の選択、プロバイダ固有 request/stream 処理、`previous_response_id`、リトライ、HTTP/SDK エラー処理、context overflow を併せ持つ。
- [`uagent_llm.py`](https://github.com/awaku7/agentcli/blob/2435ad6a69244cf8dabe18286389bb0389c3cfde/src/uagent/uagent_llm.py) は `ContextManager` で履歴と tool schema を最適化した後、複数の provider 分岐で各 round helper を呼ぶ。
- [`runtime/context_manager.py`](https://github.com/awaku7/agentcli/blob/2435ad6a69244cf8dabe18286389bb0389c3cfde/src/uagent/runtime/context_manager.py) は budget、retrieval、decision、active context、tool definition 選択をすでに統合している。[`runtime/provider_context.py`](https://github.com/awaku7/agentcli/blob/2435ad6a69244cf8dabe18286389bb0389c3cfde/src/uagent/runtime/provider_context.py) は、その出力を provider-safe な message へ投影する境界として存在する。
- [`providers/responses_manager.py`](https://github.com/awaku7/agentcli/blob/2435ad6a69244cf8dabe18286389bb0389c3cfde/src/uagent/providers/responses_manager.py) は管理 API と `ResponsesCapabilities` を分離済み。ただし生成時の継続・再試行状態は依然 round 側にある。
- [`providers/llm_inception.py`](https://github.com/awaku7/agentcli/blob/2435ad6a69244cf8dabe18286389bb0389c3cfde/src/uagent/providers/llm_inception.py) は Mercury の diffusion snapshot を CLI/GUI/Web へ直接描画する特殊実装を持つ。
- [`tools/llm_tool_narrowing.py`](https://github.com/awaku7/agentcli/blob/2435ad6a69244cf8dabe18286389bb0389c3cfde/src/uagent/tools/llm_tool_narrowing.py) は GPT-5.4 の native / legacy tool search を判断する。`ContextManager.optimize_tool_definitions()` との機能境界が一部重なる。

## 推奨アーキテクチャ

```mermaid
flowchart TB
    U[User / Host UI] --> OR[RoundOrchestrator]
    OR --> CR[ContextRuntime]
    CR --> CB[Budget · Retrieval · Decision]
    CR --> TD[ToolDiscovery]
    TD --> TC[Tool catalog · MCP · Skills · native tool_search]
    OR --> CAP[CapabilityResolver]
    CAP --> REG[ProviderRuntime Registry]
    REG --> MP
    subgraph PROJ["ProviderRuntime.project()"]
        MP[MessageTransformPipeline] --> PP[ProviderProjection] --> SR[SerializedRequest]
    end
    REG --> CH[Chat adapter]
    REG --> RR[ResponsesRuntime]
    RR --> RM[ResponsesManager: lifecycle API]
    OR --> REC[ContextRecoveryManager]
    REG --> SE[StreamEvent]
    SE --> RENDER[CLI / GUI / Web renderers]
    OR --> TR[ToolRuntime]
    TR --> CR
```

### 依存ルール

1. `ContextRuntime` は provider SDK、UI、ネットワーク I/O を知らない。出力は provider-neutral な `ContextPlan`（active context / tool selection / decision telemetry）に限定する。`RecoveryPlan` は `ContextRecoveryManager` だけが生成する。
1. `CapabilityResolver` が「何が可能か」を答え、adapter は「どう呼ぶか」を担当する。round loop は個別 provider 名を原則判断しない。
1. `ResponsesRuntime` は continuation state と retry を持ち、`ResponsesManager` は retrieve/cancel/delete/count/compact など API 操作だけを担当する。
1. adapter は provider event を `StreamEvent` に変換するだけで、端末制御や Web の message payload を直接操作しない。
1. `RoundOrchestrator` だけが、context → request → stream/response → tool result → 次 round の順序とトランザクション境界を持つ。

### 入力境界の契約

`PreparedRound` という曖昧な名称は採用しない。以下の三つを別型として固定する。

```text
ContextPlan → ProviderProjection → SerializedRequest
```

| 型 | 所有者 | 含めるもの | 含めないもの |
|---|---|---|---|
| `ContextPlan` | `ContextRuntime` | provider-neutral messages、選択済み capability references、tool selection、decision / budget telemetry、論理 `plan_id` | provider wire format、SDK object、HTTP parameter |
| `ProviderProjection` | `ProviderRuntime` | provider/model/transport 向けに正規化した messages・tools・reasoning/output policy、`plan_id`、`projection_id` | JSON bytes、client、永続履歴の変更 |
| `SerializedRequest` | adapter request projector | SDK / HTTP に渡す payload、request options、`request_id` | context 選択の判断、UI 描画処理 |

`ContextPlan` は再試行・再投影の基準となる論理コンテキストであり、送信直前の投影を保持しない。翻訳を含む semantic transform は `ProviderRuntime.project()` の先頭で、`ContextPlan` を mutate しない形で適用する。その結果から provider 固有 message shape、structured-output schema、transport option を含む `ProviderProjection` を構築し、続けて `SerializedRequest` を作る。これで cache/retry は `plan_id` と `projection_id` の双方を比較できる。

### ID と fingerprint の契約

- `plan_id` は、canonical JSON にした immutable message ID と内容、tool schema revision、selection / context policy version、provider-neutral budget policy を、**installation / workspace 単位の安定鍵**による HMAC-SHA-256 で hash して作る。順序は保持し、telemetry、時刻、turn / round / attempt ID、表示用文言など volatile field は含めない。同じ workspace の同じ history / policy / schema revision でのみ安定する。外部観測には content-derived な ID を出さず、ランダムな opaque `plan_observation_id` を使う。
- `projection_id` は `plan_id`、provider/model/transport、transform / structured-output / reasoning policy revision を canonicalize して hash する。
- `turn_id` は一つのユーザー入力から tool loop 完了まで、`round_id` は tool loop 内の一回の LLM 実行、`attempt_id` はその round の送信試行、`request_id` は provider request、`stream_id` はその request の event stream を表す。これらは hash input にしない。
- `input_fingerprint` は restore 可否の照合専用である。生の prompt hash は保持せず、session key を使う HMAC-SHA-256 とし、session / recovery journal の TTL を超えた時点で破棄する。session key は key ID とともに OS secure key store に保存し、journal には key ID だけを記録する。key を復元できない場合は fingerprint を信頼せず、full rebuild か continuation clear を選ぶ。

### canonical JSON の固定仕様

`plan_id` と `projection_id` の canonicalization は [RFC 8785 (JSON Canonicalization Scheme)](https://www.rfc-editor.org/rfc/rfc8785) を採用する。文字列は canonicalization 前に Unicode NFC へ正規化する。object key は RFC 8785 の順序、数値は JCS の IEEE 754 表現を使い、`NaN` と無限大は入力として拒否する。`null` は明示値として保持し、任意フィールドの欠落は serialization 前に既定値を補完せず「欠落」のままにする。これにより、言語ランタイムや serializer の差によって `plan_id` が変わることを防ぐ。

## 優先順位一覧

| 優先度 | 対象ファイル / 責務 | 現状 | リファクタ案 |
|---|---|---|---|
| P0 | `llm_round_helpers.py` | 1 モジュールに request 組み立て、翻訳、Responses、stream、compat、recovery、retry が混在 | `RoundOrchestrator` を薄い入口にし、下記 P0/P1 の collaborator へ抽出 |
| P0 | `uagent_llm.py` と Context Runtime の境界 | context を複数箇所で build/project し、tool selection も round loop が保持 | `ContextPlan → ProviderProjection → SerializedRequest` の明示的な hand-off にする |
| P0 | Provider 分岐 | `uagent_llm.py` と `_call_openai_azure_round()` に `if/elif provider` が多数 | `ProviderRuntime` registry + adapter の capability declaration に移す |
| P1 | Context Overflow Recovery | `_is_context_overflow_error()` と `_rollback_largest_recent_history()` が helper にある。最大 message から末尾を破棄する副作用が強い | `ContextRecoveryManager` が `RecoveryPlan` を返し、orchestrator が適用・再実行する |
| P1 | Responses 継続 | manager は lifecycle API を分離済みだが、`previous_response_id` の検証・破棄・full-history retry が request loop にある | `ResponsesRuntime` に状態機械を置く |
| P1 | Capability | `provider_caps.py`、`llmcapa_util.py`、`ResponsesCapabilities`、env 判定に事実が分散 | 合成可能な `CapabilityResolver` と provider/model keyed な snapshot に統一 |
| P1 | Streaming | Inception は snapshot 描画、他は provider ごとの parse/display | 共通 `StreamEvent` と host renderer を作る |
| P1 | Tool Discovery | legacy narrowing、native tool_search、ContextManager の tool budget が分散 | `CapabilityCatalog`、`ToolSelectionPolicy`、`ToolDeliveryStrategy` に三分割する |
| P2 | Message transforms | surrogate 正規化、翻訳、image/reasoning/structured output 互換が request 生成に混在 | ordered `MessageTransformPipeline` と provider projection に分離 |
| P2 | Error / retry policy | stale RID、proxy、thinking/tool unsupported、429、SSL、overflow が同一 try/except | `LLMErrorClassifier` と `RetryPolicy`。retry 可否と UI 表示を分離 |
| P2 | Reasoning / structured output | provider 固有パラメータの変換が adapter と loop に分散 | `ReasoningPolicy` / `OutputPolicy` を provider request projection へ渡す |
| P2 | I18N（38 ロケール） | 本体は gettext、Tool は JSON key-value で、抽出・翻訳・検証経路が異なる | 新設・移動する表示文言を両方式で管理し、38 ロケールの key / placeholder / JSON 構造を CI で確認。翻訳品質は別レビュー |
| P3 | CLI/GUI/Web 表示 | provider parser が host 固有 callback / payload を知る | `StreamRenderer` と `RuntimeEvent` を各 host 側へ置く |
| P3 | command / operational interface 周辺 | Responses / session command は runtime state と persistence をまたいで操作する | application command → runtime service → persistence の境界を整える |

## P0: `llm_round_helpers.py` の責務分離

### 現状の問題

同ファイルには少なくとも次の独立した変更理由がある。

- request 入力の正規化と翻訳（`_normalize_surrogates`、翻訳 helper）
- runtime flag の判定（`_resolve_round_runtime_flags`）
- Gemini / Claude / OpenAI-compatible などの送信経路
- Responses の `previous_response_id`、server-side tool search、compaction 連携
- reasoning / structured output / provider compatibility
- provider ごとの stream parser と tool call 集約
- stale continuation、429、proxy、SSL、context overflow の retry / エラー表示

このままでは provider を一つ増やすだけで、フラグ判定・request 投影・例外処理・UI 表示のすべてを横断しやすい。実際に新 provider 追加時に複数ファイル更新を要することがリポジトリの開発規約にも明記されている。

### 提案する最初の分割

| 新しい責務 | 最初に移すもの | 備考 |
|---|---|---|
| `runtime/round_orchestrator.py` | 1 round の順序、tool loop への結果返却 | provider 個別の `if` を持たない薄い coordinator |
| `runtime/context_plan.py` | `ContextPlan`、decision / budget / tool-selection telemetry | immutable に近づけ、再試行の論理入力を固定する |
| `providers/request_projection.py` | `ProviderProjection`、`SerializedRequest`、request options | provider wire format と SDK payload をここで完結させる |
| `runtime/message_transforms.py` | surrogate、translation、共通正規化 | 変換順を明示し、入力履歴を mutate しない |
| `runtime/recovery.py` | overflow detect/plan、retry decision | P1 で実装。P0 では interface と呼出点だけ先に作る |
| `providers/provider_runtime.py` | adapter protocol / registry | 既存 provider 関数を最初は adapter から委譲するだけでよい |

`_call_openai_azure_round()` を直ちに細分化する必要はない。先に adapter interface の裏に隠し、入出力を固定してから、Responses と Chat を別の runtime に抽出する方が安全である。

## P0: Context Runtime と LLM 実行の境界

現在は `ContextManager.build_message_context()`、provider projection、auto-shrink projection、tool schema の最適化が `uagent_llm.py` の前処理と round 実行に跨る。既存の `provider_context.py` は良い境界だが、境界オブジェクトがないため同種の処理が再適用される余地がある。

提案する hand-off は次の通り。

```mermaid
sequenceDiagram
    participant O as RoundOrchestrator
    participant C as ContextRuntime
    participant P as ProviderRuntime
    participant R as Recovery
    O->>C: plan(history, task, tool catalog, policy)
    C-->>O: ContextPlan(messages, tool_specs, decisions, telemetry)
    O->>P: project(ContextPlan, capabilities, session state)
    P-->>O: ProviderProjection
    O->>P: serialize(ProviderProjection)
    P-->>O: SerializedRequest
    O->>P: run(SerializedRequest)
    alt context overflow
        P-->>O: ContextOverflow(error, request facts)
        O->>R: plan(ContextPlan, ProviderProjection, error)
        R-->>O: RecoveryPlan
        O->>C: rebuild(RecoveryPlan)
    else normal
        P-->>O: RoundResult(events, assistant, tool_calls, continuation)
    end
```

`ContextPlan` に raw history 自体は持たせず、provider-neutral messages、tool specs、選択理由、budget 使用量を持たせる。`ProviderProjection` に projection revision を持たせる。これにより、rollback/compaction があった場合も「どの論理入力を、どの provider 投影で実行したか」をログとテストで再現できる。

## P0: Provider 分岐を adapter / strategy に集約

### 実行 primitive の契約

```python
class ProviderRuntime(Protocol):
    capabilities: ProviderCapabilities
    def project(self, plan: ContextPlan, session: ProviderSession) -> ProviderProjection: ...
    def serialize(self, projection: ProviderProjection) -> SerializedRequest: ...
    def run(
        self, request: SerializedRequest, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]: ...
```

`run()` を唯一の I/O primitive にする。stream 対応 provider は逐次 event を yield し、非 stream provider は `ResponseStarted` と最終結果を含む `ResponseCompleted` を yield する。orchestrator 内の collector が event 列から一度だけ `RoundResult` を組み立てるため、`execute()` と `stream()` の二重 contract は設けない。consumer が中断した場合は iterator を必ず `close()` し、adapter は cancellation token、timeout、close のいずれでも remote stream / socket / spinner を解放して terminal event を一度だけ emit する。async 化する場合は同じ意味論の `AsyncIterator` に置換し、同期・非同期を同じ interface に混在させない。

```text
RoundResult
├── turn_id / round_id / attempt_id / plan_id / projection_id / request_id / stream_id
├── status: completed | interrupted | failed | cancelled | timed_out
├── assistant_text / reasoning_text / partial_text
├── tool_calls[] / usage / provider_metadata
├── continuation_update
└── error / recovery_hint
```

実装クラスを最初から provider ごとに増やし過ぎない。まずは `OpenAICompatibleRuntime`、`ResponsesRuntime`、`GeminiRuntime`、`ClaudeRuntime`、`InceptionRuntime` のように **プロトコル差** で分け、provider 固有の request patch は small projector に残す。PLaMo、DeepSeek、OpenRouter 等は既存 helper を再利用しながら段階的に移す。

### 分岐を capability に置換できる例

| 現在の判断 | 置換する capability / policy |
|---|---|
| Responses API を使うか | `supports.responses.create` と transport preference |
| `previous_response_id` を送れるか | `supports.responses.continuation` |
| native tool search を使うか | `supports.tool_discovery.native_search` + model feature |
| streaming を許すか | `supports.streaming` + transform policy |
| Inception の snapshot | `streaming.mode = snapshot` |
| OpenAI Fast mode | provider-specific request option。capability ではなく projector 所有 |

重要なのは、capability を「利用可能性」、policy を「今回使うか」、projector を「wire format」に限定することだ。この三者を一つの bool 群に混ぜない。

## P1: Context Overflow Recovery

現在の rollback は直近 `lookback=10` の最大 message を探し、その message と以降を削除した後、再計画を促す system notice を追加する。ツール操作の完了を誤認させない通知がある点はよい。一方で、履歴を直接変更し、削除理由・代替案・再試行回数が first-class なデータになっていない。

### `ContextRecoveryManager` の提案

```text
detect(error, request_facts)
  -> classify: context_overflow | stale_continuation | other
plan(context_plan, provider_projection, classification)
  -> no-op | provider_compact | client_projection | bounded_rollback
apply_local(plan, context_plan)
  -> rebuilt ContextPlan
RoundOrchestrator -> RemoteRecoveryPort.apply(
  plan, provider_session, expected_session_generation
)
  -> RemoteSessionUpdate
```

優先順は次が妥当である。

1. provider が対応し、session が連続しているなら provider native compaction を試す。この操作は remote session mutation として扱う。
1. artifact / tool-result projection、再取得、budget 選択で client-side active context を再構築する。
1. 最終手段として bounded rollback を行う。削除範囲、最大 message、再試行カウントを telemetry に残す。

Recovery は原則として persistent history を変更しない。rollback は **送信用 projection の再構築**として実施し、元の history と、採用した plan を recovery journal に保存する。session restore 後は、history の immutable message ID と journal の plan を使って同じ projection を再構築する。永続履歴の要約・削除が必要な将来の機能は、別の明示的な user-visible command / policy とし、通常の overflow retry に混ぜない。

| `RecoveryPlan` の必須項目 | 意味 |
|---|---|
| `recovery_id`（冪等性キー） | 同じ request / failure を二重に再適用しない |
| `plan_id` / `projection_id` | 対象の論理コンテキストと送信投影を特定する |
| `local_history_mutation` | 通常は常に `false`。将来 true を許す場合も明示的 policy が必要 |
| `remote_session_mutation` | provider native compact / cancel 等で外部 session を変えたか |
| `projection_mutation` | omission / rebuild により送信用投影を変えたか |
| `omitted_message_ids` | 削除ではなく送信から省略した immutable message ID |
| `strategy` / `reason` | native compact、rebuild、bounded rollback 等と分類理由 |
| `attempt_id` / `attempt_budget_snapshot` | 現在の試行と消費済み budget を記録する。上限自体は `RoundAttemptBudget` だけが所有する |
| `input_fingerprint` | restore 時に plan を再利用してよい history / policy か検証する |

`ContextRecoveryManager` は `apply_local()` で local history を変更せず、新しい `ContextPlan` と projection omission を作る。provider native compact / cancel などの外部状態変更は、`RoundOrchestrator` が `RemoteRecoveryPort`（provider adapter が実装）へ委譲する。port は `expected_session_generation` と現在の remote generation を比較してから操作し、不一致なら remote mutation を行わず stale update を返す。`recovery_id` を provider が許容する idempotency key として添えられる場合は添える。したがって recovery 層は provider SDK / I/O に依存しない。remote compaction が成功した場合は、新しい `session_generation` と compacted response ID を journal に記録する。restore 時は provider capability と generation を再検証できた場合だけ継続する。検証不能、provider switch、または旧経路への feature-flag rollback 時は remote continuation を clear し、local history から新 generation を開始する。

| `RemoteSessionUpdate` の必須項目 | 意味 |
|---|---|
| `session_generation` | compact / cancel 後の remote session 世代。旧 generation での continuation を禁止する |
| `compacted_response_id` | provider が返した continuation 用 response ID。未発行なら `null` |
| `remote_mutation_status` | `not_attempted` / `applied` / `rejected` / `unknown` |
| `continuation_allowed` | 次 request がこの remote session を継続してよいか |
| `journal_entry_id` | local recovery journal と remote mutation を対応付ける ID |

## P1: Responses Runtime

`ResponsesManager` は lifecycle API のラッパーとして残す。そこへ generate/stream state を詰め込まない。新しい `ResponsesRuntime` は次を所有する。

- `previous_response_id` の provider capability 検証
- active / previous response ID の状態遷移と永続化
- stale / expired / incompatible continuation に対する full-history retry の候補作成（実行判断は `RoundAttemptBudget` 経由）
- count-input-tokens / compact の使用判断
- tool output を伴う continuation の整合性

```mermaid
stateDiagram-v2
    [*] --> Fresh
    Fresh --> Active: create
    Fresh --> Restored: session restore
    Restored --> Continuing: valid continuation + invariant check
    Restored --> Fresh: invalid / provider switch
    Continuing --> Active: create
    Active --> AwaitingToolOutput: function call(s)
    AwaitingToolOutput --> Continuing: all matching outputs accepted
    AwaitingToolOutput --> Failed: failed tool / duplicate / unknown output
    Active --> Interrupted: interrupt
    Active --> Cancelled: cancellation accepted
    Active --> TimedOut: timeout
    Active --> Stale: stale / expired continuation
    Stale --> Fresh: RetryRequest accepted by attempt budget
    Interrupted --> Fresh: clear continuation
    Cancelled --> Fresh: clear continuation
    TimedOut --> Fresh: clear continuation
    Failed --> Fresh: retry policy / new turn
    Active --> Fresh: completed
```

状態には interrupted、expired / stale、provider switch、session restore、failed tool call、duplicate tool output、cancellation、timeout を含める。状態遷移時の不変条件は次の通り。

- `response_id` は provider / model / session generation に属し、provider switch 後に再利用しない。
- 各 pending tool call は `(response_id, tool_call_id)` で一意である。tool output は同じ組に一度だけ紐付けられる。
- continuation を送るには、前 response の pending tool call がすべて完了し、順序・call ID・session generation が一致していなければならない。
- interrupt / cancel / timeout / stale / restore validation failure は continuation を clear し、次回は full history から開始する。
- 重複・未知・失敗した tool output は continuation を進めず、`Failed` と recovery / user-action policy に渡す。

既存テストの `test_previous_response_id_compat.py`、`test_responses_manager.py`、`test_interrupt_clears_responses_rid.py` は移行時の回帰防止資産である。OpenRouter が null 以外を拒否すること、DeepSeek が stateless であること、LM Studio / OpenAI / Azure の扱いを behavior test として維持する。

## P1: Capability Resolver

`ResponsesCapabilities` は実績のある出発点だが、現在は Responses 管理 API に閉じている。`provider_caps.py` と `llmcapa_util.py` の情報を削除せず、resolver がそれらを合成する構造にする。

```text
CapabilityResolver.resolve(provider, model, transport)
  -> ProviderCapabilitySnapshot
       responses: create / stream / continuation / compact / lifecycle
       streaming: delta / snapshot
       tools: chat_tools / native_search / client_catalog
       reasoning: effort / summary / provider projection
       output: structured_output / images
       context: known window / native compaction
```

モデル catalog がない、または vendor の仕様確認が不十分な場合は false / unknown を区別する。Meta の continuation のように確認度が限定的な値は provenance（documented / tested / assumed）も持たせると保守に効く。

| capability 状態 | native feature の使用 | fallback |
|---|---|---|
| `true / documented` | 許可 | 不要 |
| `true / tested` | 許可。ただし provider/version を telemetry に残す | 実行失敗時は policy に従う |
| `unknown` | 原則禁止 | 保守的な Chat / client-catalog / non-continuation 経路 |
| `false` | 禁止 | 定義済みの非 native 経路。なければ診断付き失敗 |

feature flag で unknown を試験的に許可する場合も、既定値は false とし、provider/model/version を限定する。

## P1: StreamEvent と host renderer

`llm_inception.py` の diffusion mode は「delta ではなく全文 snapshot を置換表示する」という違いを明確にしている。この違いを provider parser に閉じ込めず、正規化イベントにする。

```text
StreamEvent
├── ResponseStarted(stream_mode, ids, timestamp)
├── TextDelta(text)
├── TextSnapshot(text)       # Mercury diffusion
├── ReasoningDelta(text)
├── ToolCallDelta(index, tool_call_id, name_fragment, arguments_fragment)
├── ToolCallCompleted(tool_call_id, name, validated_arguments)
├── ResponseCompleted(metadata)
├── ResponseFailed(error)
├── ResponseCancelled(reason)
├── ResponseTimedOut(timeout)
└── ResponseInterrupted(reason)
```

### StreamEvent の意味論

- 一つの `stream_id` では `TextDelta` と `TextSnapshot` を混在させない。mode は `ResponseStarted` の `stream_mode`（`delta` / `snapshot`）で固定する。provider が mode を切り替える場合は旧 stream を `ResponseFailed` で終端し、新しい `stream_id` を開始する。
- `TextSnapshot` は同じ stream のそれまでの **表示対象テキスト全体**を置換する。部分範囲の patch ではない。`TextDelta` は直前までの確定テキストへ追記する。
- `ToolCallDelta` は `(response_id, tool_call_id)` ごとに順序付ける。`ToolCallCompleted` を明示的に追加し、name と arguments が検証可能な完全形になるまで実行しない。
- event は一つの `stream_id` 内で `sequence_number` の単調増加を保証する。provider が順序を保証しない場合は adapter が並べ替え、保証できない場合は protocol error とする。
- 一つの `stream_id` には terminal event を必ず一つだけ emit する。`ResponseCompleted` と `ResponseFailed`、または他の terminal event との二重発行は禁止する。
- adapter は provider 例外を原則 `ResponseFailed` に変換し、`run()` の外へ未分類例外を送出しない。cancel / timeout / interrupt でも、対応する terminal event（`ResponseCancelled`、`ResponseTimedOut`、`ResponseInterrupted`）を必ず一つ emit する。

CLI renderer は ANSI 描画、GUI renderer は callback、Web renderer は現在の payload 形式へ変換する。parser は `core._is_web`、`log_message`、GUI callback、TTY 判定を知らない。これにより `test_llm_inception.py` の snapshot/concat テストを event contract テストへ発展でき、他 provider の streaming も同じ表示保証を得る。

## P1: Tool Discovery を Context Runtime に統合

既存の `ContextManager.optimize_tool_definitions()` は whole schema を保持し、budget と decision を扱える。これを schema 選択の実装基盤とする。一方、`llm_tool_narrowing.py` は GPT-5.4 native / legacy の transport 選択を持つ。

提案する分担は次の通り。

| 層 | 責務 |
|---|---|
| `CapabilityCatalog` | tool / MCP / skill / A2A の metadata、権限、schema 参照を候補として提供。実行権限は付与しない |
| `ToolSelectionPolicy` | task、budget、policy により候補を選択し理由を記録。`ContextManager` の whole-schema 選択を利用 |
| `ToolDeliveryStrategy` | client-side selected schemas / `tool_catalog` steering / provider native tool_search のいずれで届けるかを選ぶ |
| `ProviderRuntime` | 選ばれた delivery を provider wire format に投影 |

native tool search ではサーバーに full catalog を渡すため、client-side budget 選択を無効化するのではなく、telemetry と fallback 用の decision として残す。legacy に落とした際に同じ task で選択結果を再利用できるようにする。

## P2: transforms、error policy、reasoning policy

### MessageTransformPipeline

順序は固定し、各段階は input/output を返す pure transformation を基本にする。

```text
ContextPlan
  -> semantic transforms（surrogate / translation / modality。`project()` 内で immutable に実施）
  -> ProviderProjection（provider-specific messages / tools / policies）
  -> SerializedRequest（SDK / HTTP payload）
```

translation が streaming を止める現行挙動は policy として保持する。transform が変わったことを `ProviderProjection` の metadata に記録すれば、cache plan と retry が入力同一性を正しく判断できる。

### Error / Retry

`LLMErrorClassifier` は例外を `RateLimited`、`ContextOverflow`、`StaleContinuation`、`UnsupportedFeature`、`ProxyBlocked`、`TransportFailure`、`FatalRequest` に分類する。adapter は文字列判定だけでなく、HTTP status、SDK error type、provider error code、retry-after、response metadata を構造化して classifier に渡す。例外文字列は provider 固有の最後の fallback とする。

再試行は `RoundAttemptBudget` が一元管理する。`ResponsesRuntime`、`ContextRecoveryManager`、`RetryPolicy` は retry を直接ループせず、理由付きの `RetryRequest` を返す。budget は stale continuation、context overflow recovery、feature fallback、transport retry、provider client 再作成を理由別・総数の両方で上限管理し、各 attempt の消費を journal と telemetry に記録する。`RoundOrchestrator` だけが次 attempt を開始できる。

## P2: I18N を 38 ロケールの完了条件にする

このリファクタでは、表示文言の追加・移動・key の変更を「英語だけ通れば完了」と扱わない。UAG は 38 ロケールを対象にしているため、runtime event、recovery notice、capability fallback、tool discovery の診断を含め、ユーザーに届く文言は全ロケールで検証する。

特に、本体と Tool で翻訳機構が異なる点に注意する。

| 対象 | 方式 | 主な配置 | 実装時の注意 |
|---|---|---|---|
| UAG 本体（runtime、provider、CLI/GUI/Web） | gettext | `src/uagent/locales/*/LC_MESSAGES/` | `from .i18n import _` を用い、msgid と placeholder を全ロケールで同期する |
| Tool モジュール | JSON key-value | `src/uagent/tools/*_tool.json` | `make_tool_translator(__file__)` を用い、tool JSON の key と全翻訳値を同期する |

`StreamEvent`、`RecoveryPlan`、`LLMErrorClassifier` は表示用の完成文を内部型に持たず、安定した event / reason code と interpolation parameter を持つのがよい。host renderer または Tool が、適切な翻訳機構で最終文言にする。これにより英語文言を program logic の分岐条件に使わず、文言移動時に 38 ロケールの更新漏れを検出しやすくなる。

### I18N の実施・検証ルール

1. 本体で新規・変更した msgid は各 gettext カタログへ反映し、placeholder 名・型・エスケープを全ロケールで一致させる。
1. Tool の新規 key は対応する `*_tool.json` に追加し、Tool 用の JSON 検証を通す。本体の `.po` へ同じ key を追加しても Tool の翻訳にはならない。
1. provider / recovery 内部の event code は翻訳しない。翻訳するのは host / Tool 境界の表示文言だけにする。
1. リファクタの各 PR で `python scripts/compile_locales.py`、`python scripts/po_qc_summary.py`、`python scripts/i18n_tools_check.py` と、変更した Tool JSON の検証を実行する。
1. CI の完了条件は key、placeholder、JSON 構造、コンパイル可能性であり、翻訳品質そのものは locale owner / human review の別工程にする。English fallback は意図的な fallback として記録する。欠落 key や placeholder 不一致は CI エラーとする。

## P3: Host と command 層

stream を正規化できれば、CLI/GUI/Web は `RuntimeEvent` を購読する renderer になり、provider code から UI callback を外せる。Responses command や session command のような command 系は、その後に application service 経由で runtime state を操作するよう整理する。これは P0/P1 の前提ではないため、先行して大規模に触らない。

## 実施順序

1. **契約を先に追加する**: `ContextPlan`、`ProviderProjection`、`SerializedRequest`、`RoundResult`、`ProviderCapabilitySnapshot`、`StreamEvent` の型と contract test を導入する。既存挙動は変えない。**終了条件:** 同じ workspace の同じ history/policy/schema revision から安定した `plan_id` が生成される。
1. **Context hand-off を固定する**: `ContextManager` / `provider_context.py` の出力を三段階の型に分け、message build と tool selection の重複をなくす。**終了条件:** provider adapter が context selection の判断を持たない。
1. **adapter registry を導入する**: 現行 helper を包む adapter から開始し、`uagent_llm.py` の top-level provider `if/elif` を registry lookup に置換する。**終了条件:** 対象 provider 群が旧経路と event/結果互換で、flag により個別に旧経路へ戻せる。
1. **ResponsesRuntime を抽出する**: stateful continuation と stale retry を移す。management API は `ResponsesManager` のままにする。**終了条件:** response/tool-call/tool-output の不変条件と interrupt/restore/provider-switch test が通る。
1. **Recovery を抽出する**: overflow の検出、plan、適用、再試行回数を型にする。まず既存 rollback を `bounded_rollback` strategy として移植する。**終了条件:** persistent history を変更せず、journal から同じ projection を再構築できる。
1. **StreamEvent を一 provider で通す**: Inception を最初の対象にして snapshot と delta を renderer に移す。次に Responses stream、Chat stream を移行する。**終了条件:** event collector と各 renderer の final result が一致する。
1. **CapabilityResolver と三分割した Tool Discovery を統合する**: duplicated boolean と native / legacy tool delivery を合成し、provider add の更新箇所を減らす。**終了条件:** `unknown` capability が既定で native call を行わない。
1. **I18N を各段階で更新・検証する**: 新しい event / recovery / tool discovery の表示契約を、本体 gettext と Tool JSON の両方で 38 ロケールへ反映する。**終了条件:** 構造的 CI と翻訳品質 review が別々に記録される。
1. **残りの P2/P3 を実施する**: transforms、error policy、reasoning projection、host renderer、command 層を順に整理する。

## 移行時の注意点

- **一括移動を避ける**: `llm_round_helpers.py` は大きいが、最初は wrapper と protocol を置くだけにする。各段階で挙動差分を小さくし、provider 一群ずつ移す。
- **continuation は session contract**: `previous_response_id` を message history の最適化とは別の状態として扱う。tool output のペアリング、interrupt、session restore、provider 切替を必ずテストする。
- **recovery は data loss を可視化する**: rollback の対象、理由、再試行回数を保存・表示する。永続履歴と送信用 projection を混同しない。
- **capability の不明を安全側に倒す**: provider/model/version による機能差は大きい。`unknown` は native feature を使わず fallback する。
- **tool schema の完全性を守る**: budget 都合で tool schema を途中で切らない。現行 `context_tools` の whole-schema 選択を回帰条件にする。
- **stream の表示と結果を分離する**: snapshot の「表示を置換」と最終テキストの「確定」は別の契約である。非 TTY、Web reconnect、GUI callback の終了通知を test matrix に含める。
- **キャッシュ入力を明示する**: translation、auto-shrink、tool selection、recovery により投影が変わると provider cache の安全性も変わる。projection revision を cache plan に渡す。
- **I18N の経路を混ぜない**: 本体の gettext と Tool JSON は互換な代替手段ではない。runtime 文言を Tool JSON に置く、または Tool 文言を `.po` だけ更新する、といった片側更新をしない。
- **段階ロールバックを用意する**: adapter registry の各 provider 群、ResponsesRuntime、Inception `StreamEvent`、native tool search を個別 feature flag で旧経路へ戻せるようにする。flag は session 開始時に固定して telemetry に記録し、同一 tool loop 中に切り替えない。

## 性能・観測性の基準

構造分割によって context build、tool selection、translation、event 収集が増える可能性がある。新旧比較を可能にするため、各 round に少なくとも次を structured telemetry として記録する。本文や tool argument の生データは記録せず、ID・サイズ・時間・回数に限定する。

| 指標 | 用途 |
|---|---|
| round total latency / context-build latency / provider latency | 分割による待ち時間増加を検出 |
| request token 数・tool schema size・projection size | context / tool delivery の効果を比較 |
| recovery 回数・strategy・再試行回数 | overflow と retry の悪化を検出 |
| provider fallback / feature-flag fallback 回数 | capability 誤判定や移行不具合を検出 |
| stream event 数・duplicate / out-of-order event 数 | renderer reconnect と重複排除を検証 |
| retry による追加 request / token cost | continuation / recovery の実コストを把握 |

`StreamEvent`、`RoundResult`、telemetry、recovery journal は同じ `turn_id` / `round_id` / `attempt_id` 階層を使う。`StreamEvent` にはさらに `session_generation`、`stream_id`、`request_id`、単調増加する `sequence_number`、発生時刻を含める。renderer は `(session_generation, stream_id, sequence_number)` を重複排除キーに使う。reconnect により request ID が変わっても、再開 token から同じ stream を復元できる場合だけ既存 stream に接続する。out-of-order event は短い reorder buffer に保持し、欠番が解消しなければ renderer を最新 snapshot で再同期する。delta mode で再同期不能な場合は stream を失敗として終端し、重複表示よりも整合性を優先する。performance gate は既存 baseline に対する許容範囲を先に計測して設定し、機能契約テストとは別に監視する。

## 互換性・ロールバック方針

移行中は旧実装を削除しない。新旧経路を provider 単位・機能単位で並行させ、既定値を段階的に切り替える。

| feature flag の単位 | 切り戻し対象 | 固定するタイミング |
|---|---|---|
| provider adapter | registry 経由の adapter ↔ 現行 helper | session start |
| Responses runtime | 新 state machine ↔ 現行 continuation / retry | session start |
| Inception streaming | `StreamEvent` renderer ↔ 現行 snapshot renderer | request start |
| native tool search | native delivery ↔ legacy `tool_catalog` | session start |

切り戻し時にも `ContextPlan` / telemetry schema は維持し、比較可能にする。Responses の active continuation を別経路へ途中移管しない。切替が必要な場合は continuation を clear し、full history から新しい session generation として開始する。

## 根拠コミットとの差分確認

本書は `2435ad6` を根拠にしている。実装着手前と各設計レビューでは、対象 branch の `HEAD` をこのコミットと比較し、少なくとも `llm_round_helpers.py`、`uagent_llm.py`、`runtime/context_*`、`providers/responses_manager.py`、`providers/llm_inception.py`、`tools/llm_tool_narrowing.py`、対応テストの差分を確認する。差分がある場合は、本文の「現状」欄と contract / capability matrix を先に更新してから変更を開始する。

## 推奨する回帰テストの追加

既存の `test_context_manager_pipeline.py`、`test_context_tools.py`、`test_responses_manager.py`、`test_previous_response_id_compat.py`、`test_responses_compaction.py`、`test_llm_inception.py` を土台に、次を追加する。

- `ContextPlan` が history を mutate せず、同じ workspace の同じ input / policy / schema revision から同じ `plan_id` を作る。`ProviderProjection` は provider policy を変えた場合だけ別の `projection_id` になる。
- RFC 8785 canonical JSON の key order、Unicode NFC、`null` / 欠落、数値表現の等価ケースは同じ ID になり、`NaN` / 無限大は拒否される。
- overflow の各 strategy が persistent history と request projection を区別し、最大再試行回数を守る。
- provider switch、interrupt、session restore 後に invalid `previous_response_id` を送らない。
- `StreamEvent` の delta/snapshot/tool-call sequence、terminal event、reconnect / out-of-order event が CLI/GUI/Web renderer で同じ final result になる。
- native tool search から legacy fallback しても、tool catalog と tool-call ID の整合が崩れない。
- capability が `unknown` の provider/model では安全な Chat / client-catalog fallback になる。
- 本体 gettext と Tool JSON の双方で、38 ロケールに欠落 key・不正 JSON・placeholder 不一致がない。
- `RecoveryPlan` が `local_history_mutation=false` のまま、restore 後に同じ input fingerprint の projection を再現する。remote compaction 後は session generation を検証できなければ continuation しない。
- `apply_local()` と `RemoteRecoveryPort.apply()` が独立して検証でき、`RemoteSessionUpdate` の `continuation_allowed=false` では remote continuation を送らない。
- `RemoteRecoveryPort.apply()` は `expected_session_generation` 不一致時に remote mutation を行わず、同じ `recovery_id` の再送を冪等に扱う。
- secure key store から session HMAC key を復元できる場合だけ fingerprint を照合し、復元できない場合は full rebuild / continuation clear に落ちる。
- provider switch、interrupt、cancel、timeout、expired/stale、duplicate / failed tool output が continuation を不正に再利用しない。
- 新旧経路の latency、token、tool schema size、recovery / fallback / retry cost を比較できる telemetry が出力される。

## 完了の判定

以下を満たした時点で、今回の中心リファクタは成功と判断できる。

1. `uagent_llm.py` の round dispatch は provider 名の大規模 `if/elif` を持たず、registry 経由で実行できる。
1. `llm_round_helpers.py` は compatibility projector または adapter 実装へ縮小され、Context / recovery / UI renderer を直接所有しない。
1. `ContextPlan` → `ProviderProjection` → `SerializedRequest` の hand-off が一意で、decision/telemetry が失われない。
1. `ResponsesRuntime` が continuation の state/retry を所有し、tool output との不変条件を検証する。`ResponsesManager` は API lifecycle wrapper のままである。
1. Recovery は `apply_local()` と `RemoteRecoveryPort.apply()` の境界を持ち、`RemoteSessionUpdate` が remote mutation と continuation 可否を明示する。
1. provider parser は順序情報付きで terminal event が一つだけの `StreamEvent` を返し、CLI/GUI/Web の直接描画を持たない。
1. 本体 gettext と Tool JSON の I18N が、38 ロケールすべてで構造的なコンパイル・QC・Tool 検証を通る。翻訳品質レビューは別工程として完了記録を持つ。
1. 新旧経路を個別 flag で切り戻せ、切替時に continuation を不正再利用しない。
1. latency、token、recovery、fallback、schema size、stream event、retry cost の telemetry を比較できる。
1. 既存の provider / context / responses / streaming テスト群に加え、上記の contract test が通る。

## 現行実装との比較に基づく優先度再評価

設計文書の基準コミット `2435ad6` と、再評価時点の `HEAD` `5f79f8c9`（`origin/main` と一致）の実装を比較した結果、P0〜P3 は次の順に細分化して実施する。再評価時点の作業ツリーは変更なしであった。以後の判断は、このスナップショットを基準にする。

### P0-A: 実行経路を一本化する

対象は `src/uagent/uagent_llm.py`、`src/uagent/runtime/round_orchestrator.py`、`src/uagent/runtime/round_contracts.py`、`src/uagent/providers/runtime_registry.py`、`src/uagent/runtime/legacy_round_registry.py` である。

最優先の理由は、`uagent_llm.py` に新旧の実行経路が併存しているためである。現在は `_try_registry_simple_chat_round()` の後に `run_legacy_provider_round()` と `call_legacy_openai_compatible_round()` が残っている。registry 経路も OpenAI/Azure が中心で、他の provider は legacy registry に流れる。また、`uagent_llm.py` には Gemini、Vertex、Grok、Inception などの provider 分岐が残っている。

新規 provider を先に追加すると、新旧どちらの経路を修正すべきかが不明確になるため、先に実行経路を固定する。

終了条件:

1. `uagent_llm.py` は provider 名ではなく `ProviderRuntimeRegistry` を呼ぶ。
1. legacy 実装は adapter の内部へ隠す。
1. 新旧経路の切り替えは orchestrator 外部の feature flag で行う。
1. `ContextPlan → ProviderProjection → SerializedRequest` を一度だけ通す。
1. provider ごとの既存テストが同じ `RoundResult` / `StreamEvent` 契約で通る。

`round_orchestrator.py` 自体は存在し、単体テストも通っているため、次の作業は新規設計よりも `uagent_llm.py` の実行経路をそこへ移すことになる。

### P0-A の最初の修正単位（完了）

registry 経路へ入れる provider の判定を `providers/runtime_registry.py` の
`supports_provider_runtime()` に集約した。これにより、`uagent_llm.py` が
`openai` / `azure` の allow-list を個別に持たず、registry が所有する対応範囲を
そのまま参照する。provider 名の正規化もこの境界で行い、未移行 provider は従来通り
legacy 経路へフォールバックする。

この単位では実行経路そのものは変更していない。次の修正単位では、registry / legacy /
OpenAI-compatible の選択ポリシーを `provider_round_dispatcher.py` に集約し、
`uagent_llm.py` から provider ごとの経路判断をさらに減らす。

### P0-A の第2修正単位（完了）

registry 経路へ進める条件（対応 Provider、環境変数による有効化、Responses 対応、
tool schema の準備、legacy catalog との競合）を `runtime/provider_round_dispatcher.py`
の `registry_round_allowed()` に集約した。`uagent_llm.py` は条件を個別に評価せず、
この gate の結果だけで registry runner を試す。既存の直接呼び出しテストも維持し、
Provider adapter の実行失敗時に legacy 経路へフォールバックする挙動は変更していない。

次の単位では、`dispatch_provider_round()` が route eligibility と runner 実行を一体で
扱える形にし、`uagent_llm.py` に残る registry runner の構築判断をさらに外へ出す。

### P0-A の第3修正単位（完了）

`dispatch_provider_round()` に `registry_allowed` を追加し、registry runner を実行するか
どうかを dispatcher 自身が制御するようにした。`uagent_llm.py` は judgment mode の
判定を `registry_runner=None` という runner の差し替えで表現せず、dispatcher に明示的に
渡す。拒否時も legacy → OpenAI-compatible の順序は維持される。

registry 固有の Provider / tool / Responses 判定は引き続き
`registry_round_allowed()` が担当する。次はこの判定結果も dispatcher の入力契約へ統合し、
`uagent_llm.py` に残る route policy の組み立てを縮小する。

### P0-A の第4修正単位（完了）

registry の eligibility を単なる boolean ではなく `RegistryRoundRoute` として表現し、
`resolve_registry_round_route()` で一度だけ解決して dispatcher に渡す入力契約へ変更した。
route の拒否理由も `unsupported_provider`、`legacy_catalog_conflict` などの安定した値で
保持する。`uagent_llm.py` は route を組み立てるための入力を用意するだけになり、
`_try_registry_simple_chat_round()` は dispatcher から渡された route がある場合に再判定を
行わない。直接呼び出し時の旧 gate は互換性のために残している。

この単位で P0-A の route selection 境界は固定された。以後は registry adapter の実行結果を
`RoundResult` へ戻す処理と、legacy provider adapter の同一契約化を provider 単位で進める。

### P0-A の第5修正単位（完了）

registry の `RoundResult` を既存の round loop が受け取る tuple へ変換する
`registry_result_to_legacy_tuple()` を dispatcher 境界へ移した。tool call の `id`、`type`、
`function`、引数の形をここで正規化し、`uagent_llm.py` に残っていた provider-neutral
結果の変換処理を削減した。未完了・空結果は従来通り `None` として compatibility path
へフォールバックする。

次は legacy handler の tuple 結果にも同じ provider-neutral metadata を付与できるよう、
まず handler の戻り値を壊さずに `RoundResult` 相当の内部 outcome へ包む。

### P0-A の第6修正単位（完了）

legacy provider registry に `LegacyRoundOutcome` と
`run_legacy_provider_outcome()` を追加した。既存 handler の tuple は `raw_result` として
そのまま保持しつつ、provider、status、assistant text を provider-neutral な内部 outcome
へ付与する。`uagent_llm.py` の通常 dispatch はこの outcome を経由するが、外部に返す
legacy tuple は従来と同一である。

これにより registry と legacy の両経路で、結果の変換・互換性処理を dispatcher 境界へ
寄せる準備ができた。次は OpenAI-compatible legacy tuple も同じ outcome に包み、
`dispatch.source` に依存した unpack を縮小する。

### P0-A の第7修正単位（完了）

OpenAI-compatible legacy 経路にも `call_legacy_openai_compatible_outcome()` を追加し、
`LegacyRoundOutcome` に raw tuple、client、assistant text、reasoning、tool calls、
XAI gRPC 判定を格納するようにした。`uagent_llm.py` は legacy registry と
OpenAI-compatible の双方で outcome を受け取り、外部互換用の raw tuple は境界で unwrap
する。既存の公開 tuple 関数は変更していない。

これで registry / legacy registry / OpenAI-compatible の各実行経路が、同じ内部 outcome
へ移行できる状態になった。次は `dispatch.source` ごとの分岐を outcome の capability
判定へ置換する。

### P0-A の第8修正単位（完了）

`ProviderRoundDispatch` に共有 `outcome` view を追加した。registry の tuple 結果も
`LegacyRoundOutcome(flow="registry")` に変換し、legacy registry と OpenAI-compatible
の outcome と同じ入口から参照できるようにした。元の `result` と `dispatch.source` は
互換性のために保持するが、`uagent_llm.py` の dispatch 後処理は `outcome.flow` と
`outcome.raw_result` を使う構造へ変更した。

これにより dispatch 結果の source 判定は orchestration loop から除去され、次は
`flow` 自体を status / tool-loop / host-rendering capability に分解する。

### P0-A の第9修正単位（完了）

`LegacyRoundOutcome` に `RoundOutcomeCapabilities` を追加し、結果の扱いを flow 名では
なく capability で表現できるようにした。現時点では次の capability を固定している。

- `handles_collected_result`: registry の収集済み結果を round loop が処理する
- `owns_tool_execution`: legacy handler が tool 実行と round 制御を所有する
- `host_rendered`: legacy handler が host への最終描画まで完了している

`uagent_llm.py` の dispatch 後処理は `flow` を直接参照せず、これらの capability を使う。
`flow` は観測・互換用に残し、将来の telemetry と段階移行に利用する。

### P0-A の第10修正単位（完了）

OpenAI-compatible outcome にも capability を明示した。tool call が存在する場合は
`supports_tool_continuation=True`、XAI gRPC または Inception の streaming で既に host
へ描画済みの場合は `host_rendered=True` とする。`uagent_llm.py` の最終描画抑制は、
Provider 名の個別判定ではなく `host_rendered` を参照するように変更した。

通常の OpenAI-compatible 経路は `owns_tool_execution=False` のままなので、tool 実行と
継続処理は共通 round loop が担当する。これで host rendering の重複出力を避ける判定も
outcome capability に移った。

### P0-A の第11修正単位（完了）

`supports_tool_continuation` を registry / OpenAI-compatible outcome から dispatch 後処理へ
接続した。tool call がある outcome の場合だけ tool-loop 継続可能と判定し、registry と
OpenAI-compatible の no-tool 終了処理を同じ capability に基づけた。従来の
`if not tool_calls_list` は、round outcome が提供する継続 capability を参照する構造へ
置き換えた。

legacy handler は `owns_tool_execution=True` で既に自身の tool-loop を完了させるため、
共通 loop で二重実行しない。raw tuple と tool call list は互換性・詳細処理のために保持する。

### P0-A の第12修正単位（完了）

Responses の continuation state 更新と tool 実行に渡す continuation flag を、
`round_supports_tool_continuation` capability と `use_responses_api` の組み合わせから解決
するようにした。これにより、tool call がない round や legacy handler の完了済み tool-loop
で Responses state を誤って更新しない。registry / OpenAI-compatible の tool continuation
だけが `ResponsesRuntime` の tool-output invariant を進める。

### 並行修正: SessionStore の SQLite lock recovery（完了）

実機確認で、終了時の session summary 処理と別の session write が競合し、
`sqlite3.OperationalError: database is locked` が対話処理まで終了させる事象を確認した。
`SessionStore._execute()` に lock 専用の指数 backoff retry を追加し、短時間の複数 entry point
競合を吸収する。retry 後もロックが残る場合は、interactive callback の session persistence
だけを無効化し、LLM 処理本体は継続できるようにした。SQLite の保存失敗を理由にユーザー
操作全体を abort しないことを完了条件とする。

また、Ctrl+C 後の終了時 summary で Gemini が reasoning-only の応答を返し、表示上は
要約を考えているように見える一方、最終テキストが空で保存されない事象も確認した。
history compression の Gemini 呼び出しでは tools を無効化し、thinking を `off` として、
summary 用の final text を要求する。

### P0-B: Tool Discovery の判断を一本化する

対象は `src/uagent/runtime/tool_discovery.py`、`src/uagent/tools/llm_tool_narrowing.py`、`src/uagent/uagent_llm.py`、`src/uagent/llm_round_helpers.py`、`src/uagent/util_cmd_session.py`、`src/uagent/core_impl/prompt.py` である。

### P0-B の最初の修正単位（完了）

bootstrap 時に management tools を提示する条件を `ToolDiscoveryDecision` の
`uses_management_bootstrap()` に集約した。`uagent_llm.py` は legacy catalog と
Chat Completions 上の native-search fallback の複合条件を直接持たず、discovery decision
へ委譲する。Responses native search では management tools を送らず、legacy catalog と
selected schemas の fail-closed 方針は従来通り維持する。

### P0-B の第2修正単位（完了）

未使用だった `_is_legacy_mode()` compatibility predicate を削除した。legacy / native /
off の判定は `ToolDiscoveryDecision` に統一され、GPT-5.4 target 判定だけは既存テストとの
互換性のため `_is_gpt54_tool_search_target()` wrapper として残している。これにより、
直接の環境変数判定を新しい呼び出し側へ増やさない境界が明確になった。

`CapabilityCatalog`、`ToolSelectionPolicy`、`ToolDeliveryStrategy` と共通 resolver は `runtime/tool_discovery.py` に追加され、`llm_tool_narrowing.py` の互換ラッパーも共通 resolver へ委譲するようになった。一方、選択・delivery の呼び出し側には旧経路が残っており、`_is_gpt54_tool_search_target()` はテスト互換のために import/re-export として残る。したがって判断・選択・delivery の全経路が一つの契約へ統合された状態ではない。

直近のコミットでは Gemini の tool discovery、built-in search との分離、missing context tool specs、legacy tool call 実行が連続して修正されている。この領域は現在最も回帰しやすいため、全 provider の registry 移行に先立って判断契約を固定する。

終了条件:

1. native search、legacy `tool_catalog`、selected schemas の判断を一つの resolver に集約する。
1. Gemini の built-in tool と UAG tool discovery を別 capability として扱う。
1. discovery fallback 後も tool-call ID と schema が一致する。
1. capability が `unknown` の場合は native search を使用しない。
1. `uagent_llm.py` と `llm_round_helpers.py` から直接の narrowing 判定を除去する。

### P1-A: Context hand-off を標準経路にする

対象は `src/uagent/runtime/context_plan_builder.py`、`src/uagent/runtime/context_manager.py`、`src/uagent/runtime/round_contracts.py`、`src/uagent/uagent_llm.py` である。

`ContextPlan`、`ProviderProjection`、`SerializedRequest` の型と生成処理は存在する。auto-shrink は ContextPlan 作成より前に処理される標準経路へ移り、auto-shrink 後に ContextPlan を作り直す構造は解消された。一方、ContextManager と ContextPlan bridge は `uagent_llm.py` に残り、feature flag に依存する経路もあるため、hand-off が一意という完了条件にはまだ達していない。

終了条件:

- ContextManager は `ContextPlan` を作るだけにする。
- provider adapter は context 選択を判断しない。
- auto-shrink は RecoveryPlan を通して実行する。
- 同じ ContextPlan から projection を再生成できるようにする。
- persistent history と request projection を分離する。

### P1-B: Recovery の fingerprint と restore 検証を完成させる

`ContextRecoveryManager`、`ResponsesRecoveryPort`、SQLite recovery journal、remote recovery の冪等処理に加え、recovery metadata の生成・保存・照合を標準経路へ統合した。`ContextPlan` の `input_fingerprint`、`plan_id`、`projection_id`、`history_revision`、`schema_revision` を recovery journal と remote update に引き継ぎ、restore 前に現在の context/projection と照合する。不一致時は continuation を破棄し、full rebuild 経路へ移行する。

終了条件:

1. session key を復元できる場合だけ fingerprint を照合する。
1. key を復元できない場合は fingerprint を信頼しない。
1. full rebuild または continuation clear に移行する。
1. fingerprint に prompt 本文を直接保存しない。
1. remote recovery 後に同じ projection を再構築できる。

主要な metadata 生成・保存・照合は実装済みである。SQLite journal と remote recovery の metadata 不一致、および provider session metadata の不一致を回帰テストで検証している。ただし、これは P1-B の recovery 契約に関する進捗であり、P1-A の hand-off 一本化や全 provider 経路の統合まで完了したことを意味しない。

### P1-C: ResponsesRuntime を全経路へ統合する

`ResponsesRuntime` の state machine、continuation、stale、interrupt、cancel、timeout、provider switch、duplicate / unknown / failed tool output の検証は実装済みで、関連テストも通っている。

進捗として、registry の simple chat round から `ResponsesRuntime.session_generation` を `RoundIdentifiers` へ引き渡す bridge を実装した。runtime が利用できない場合は従来の `responses_state` をフォールバックとして参照し、値を安全に整数化する。`test_registry_round_identifiers_use_responses_session_generation` を追加し、registry 経路で `session_generation=0` に固定される回帰を検出できるようにした。関連する targeted test は成功している。

registry 経路で `session_generation=0` に固定されていた箇所は、ResponsesRuntime を優先し、旧 `responses_state` へフォールバックする共通 helper の利用へ変更した。さらに Inception の compatibility collector も同じ helper を使うようにし、provider 固有の `core.session_generation` 読み取りを除去した。残作業は state machine の再設計ではなく、`uagent_llm.py` との bridge が有効になる全 provider の標準経路、provider 切替、continuation、tool output の整合性を確認することにある。characterization / integration test を追加しながら段階的に移行する。

### P1-D: CapabilityResolver を旧判定の置換に使う

`CapabilityResolver` は存在し、`unknown` を安全側に倒す設計もできている。しかし、`provider_caps.py`、`llmcapa_util.py`、`ResponsesCapabilities`、environment flag、各 provider の個別判定が併存している。

先に adapter interface を固定し、その後に capability の取得元を `CapabilityResolver` へ集約する。これを同時に行うと変更範囲が大きくなるため、P0-A の後に実施する。

### P1-E: StreamEvent から host callback を除去する

`inception_stream_events()`、`StreamEventValidator`、`CollectingStreamRenderer`、`CallbackStreamRenderer` により、正規化イベントの基盤はできている。

ただし `providers/llm_inception.py` には `_emit_snapshot()` と互換 collector が残り、CLI/GUI/Web callback を直接扱う経路がある。provider parser を完全に host-neutral にする作業は、provider adapter 統合後に実施する。

### P2: transforms、retry、reasoning、telemetry

`message_transform.py`、`llm_error_classifier.py`、`retry_coordinator.py`、reasoning renderer は追加済みだが、legacy 経路にも同種の判断が残っている。P0-A で実行経路を一本化した後に重複を削除する。

structured telemetry については、round ID と structured logging はあるが、request token 数、tool schema size、projection size、recovery strategy、fallback 回数、duplicate / out-of-order event 数、retry による追加 token / request cost が不足している。契約と実行経路を固定した後に追加する。

### 並行トラック: I18N strict audit

I18N は中心ランタイムとは分離して進める。ただし完了条件には含まれる。strict audit では次の指摘が残っている。

- `host_gettext_findings`: 44
- `structural_findings`: 117
- `tool_json_findings`: 73
- `total_findings`: 117（重複を除いた集計値。上記3項目の単純合計ではない）

新しい runtime 文言を増やさず、gettext と Tool JSON の不一致を解消し、strict audit を CI 条件にする。翻訳品質レビューは構造検証と分離する。

### P3: CLI/GUI/Web と command 層

CLI/GUI/Web の大規模な表示層変更と session command の application service 化は後回しにする。`StreamEvent` と `RoundResult` の契約が固まる前に host 層を変更すると、各 UI 経路で移行を繰り返すことになる。

## 再評価後の実施順序

```text
P0-A  RoundOrchestrator を標準実行経路にする
P0-B  Tool Discovery の判断を一本化する
P1-A  ContextPlan → Projection → Request の hand-off を固定する
P1-B  Recovery fingerprint と restore 検証を完成させる
P1-C  ResponsesRuntime を全経路へ統合する
P1-D  CapabilityResolver へ旧 capability 判定を集約する
P1-E  StreamEvent から host callback を除去する
P2    transform / retry / reasoning / telemetry
並行  I18N strict audit の解消
P3    CLI/GUI/Web と command 層の整理
```

直近の実装対象を一つに絞る場合は、全 provider を registry に移す前に、P0-A と P0-B の境界を固定する characterization test を追加する。これにより、Gemini tool discovery 修正と同種の回帰が他 provider へ広がることを防ぐ。この characterization test と registry bridge の回帰テストは追加済みである。次は P1-C の残る標準経路を対象にする。

`60ab7dd0` の進捗記録時点では、関連する11個の targeted test file、計77件が成功していた。直近の registry bridge 変更についても、registry round integration 17件、provider round dispatcher 4件、context recovery integration 7件を個別に確認済みである。その後も回帰テストは追加されているため、77件は現行の総テスト数ではない。再評価時点ではこの文書の更新作業として全テストを再実行したものではなく、I18N strict audit の117件の指摘も未解消である。
