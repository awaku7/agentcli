# UAG Agent Runtime Design

## 1. 目的

UAGには、LLMプロバイダー、ツール、MCP、メモリ、スキル、セッション、ポリシー、サブエージェントなどの機能がすでに存在する。

本設計の目的は新機能を重複実装することではなく、既存機能を **Task単位の実行モデル** に統合し、次を安定して実現することである。

- 長いタスクの中断・再開
- ツール実行結果と成果物の永続化
- プロバイダー差分の局所化
- MCP、組み込みTool、A2Aの統一的な実行
- 権限・確認・監査の一貫性
- サブエージェントと並列処理の安全な管理

## 2. 設計方針

1. 既存のMemory、Skill、MCP、Session、Timer、A2Aを再実装しない。
1. `uagent_llm.py` の巨大な互換経路を一度に削除せず、段階的に新しいRuntimeへ移行する。
1. LLM、Tool、Session、Taskを別々の状態機械として扱い、境界を明示する。
1. 読み取り操作と書き込み操作を分離し、書き込みは確認可能にする。
1. 未知のProvider能力、未知のTool、未検証Skillは安全側に倒す。
1. ログ・イベント・APIの識別子は機械可読な安定値とし、表示文だけを翻訳する。

## 3. 現状の実装マップ

| 責務 | 既存実装 | 現状 |
| --- | --- | --- |
| LLMラウンド | `uagent_llm.py` | 主要な互換経路。Tool loop、Provider分岐、Responses状態を多く保持 |
| 新しいラウンド契約 | `runtime/round_contracts.py`, `runtime/round_orchestrator.py` | Provider非依存の境界を実装済み。一部経路から段階導入 |
| Provider実行 | `providers/*`, `runtime/provider_round_dispatcher.py` | Providerごとの互換処理が存在 |
| Agent状態 | `runtime/agent_state.py` | 進捗、現在ステップ、エラー、次アクションを保持 |
| Lifecycle | `runtime/lifecycle.py`, `runtime/execution.py` | CREATED/RUNNING/WAITING_TOOL等の状態遷移を実装 |
| セッション | `runtime/session_store.py` | SQLiteベースで会話、Tool呼び出し、成果物を保存 |
| Tool結果 | `runtime/tool_result_manager.py` | LLM/UI/履歴向けの結果投影とサイズ分類を実装 |
| Tool発見 | `runtime/tool_discovery.py` | Builtin、MCP、Skill、A2A等の候補を分離 |
| Tool実行 | `tools/*`, `llm_flow_helpers.py` | 既存のディスパッチ経路に分散 |
| 権限 | `runtime/policy_engine.py`, `tools/tool_policy.py`, `tools/enterprise_policy.py` | 統合Facadeは存在。全経路への適用を継続 |
| MCP | `tools/mcp/*`, `handle_mcp_v2` | stdio/HTTP系の接続とツール一覧を実装 |
| Plugin | `runtime/runtime_plugins.py`, `plugin_shared.py` | MCP、Agent role、Hook、Skillを起動時に統合 |
| Skill | `runtime/skill_lifecycle.py`, `tools/agent_skills_shared.py` | draft/reviewed/enabled/improved/deprecatedを実装 |
| 並列処理 | `runtime/dag_scheduler.py`, `runtime/multi_agent.py` | インメモリのDAG・Agent並列実行を実装 |
| リモートAgent | `runtime/remote_agent.py`, A2A tools | checkpoint、poll、cancel等を実装 |
| スケジュール | `set_timer`, `dag_scheduler` | タイマーと実行プリミティブはある。永続Taskとの統合が課題 |

## 4. 現状の主な課題

### 4.1 ラウンド実行の二重構造

新しい `RoundOrchestrator` と、互換性を維持する `uagent_llm.py` の主ループが並存している。

```text
現在:
entry point -> uagent_llm.py -> provider別round
                     └-> 一部だけRoundOrchestrator

目標:
entry point -> TaskSupervisor -> RoundOrchestrator -> ProviderRuntime
```

### 4.2 状態の責務が分散している

以下は別々に存在する。

- `AgentState`
- `AgentLifecycle`
- `SessionStore`
- `responses_state`
- `responses_runtime`
- Tool結果・Artifact状態

各状態は必要だが、Task IDで関連付けられていない経路がある。特に中断・再開時に、LLM継続IDだけを再利用してはいけない。

### 4.3 Tool実行境界

Tool discovery、Policy判定、実行、結果永続化、UI表示が複数経路に分散している。新しいTool経路では、次の順序を強制する。

```text
discover -> authorize -> confirm -> execute -> classify -> persist -> project
```

### 4.4 DAGとサブエージェントが非永続

`run_dag()`と`run_agents()`は実行プリミティブとして有用だが、現状は呼び出し側が checkpoint、retry、cancel、Task Storeを管理する。長時間実行ではSupervisorの管理下に置く。

## 5. 目標アーキテクチャ

```text
CLI / GUI / Web / A2A / Scheduler
              |
       Conversation Manager
              |
         Task Supervisor
       /       |        \
  Policy   RoundRunner   TaskStore
    |         |            |
 ToolRouter  Provider     Checkpoint
    |         |            |
 Builtin / MCP / A2A   SessionStore
    |
 ToolResultManager -> ArtifactManager -> Notification
```

### 5.1 Task Supervisor

長い作業の単位を管理する新しい論理コンポーネント。既存の `AgentState`、`AgentLifecycle`、`SessionStore` を束ねる。

責務:

- Taskの作成、開始、停止、再開
- checkpointの保存・復元
- round予算とretry予算の管理
- Tool loop guardとの連携
- 子Taskの権限継承
- 完了、失敗、キャンセル、タイムアウトの確定
- 通知要求の生成

Taskの最小モデル:

```text
TaskRecord
  task_id
  parent_task_id
  session_id
  project_key
  goal
  status
  current_step
  next_action
  provider
  model
  permission_level
  checkpoint_ref
  retry_state
  created_at
  updated_at
```

### 5.2 RoundRunner

`RoundOrchestrator`を1ラウンドの標準入口とする。

```text
ContextPlan
  -> provider projection
  -> serialized request
  -> normalized stream events
  -> RoundResult
```

Provider固有処理は `ProviderRuntimeRegistry` の下に置く。RoundRunnerはProvider SDKを直接呼ばない。

### 5.3 ToolRouter

Toolの発見と実行を分離する。

```text
ToolCandidate (発見結果)
  -> ToolSpec (LLMへ渡す定義)
  -> PolicyDecision
  -> Confirmation
  -> ToolExecution
  -> ToolResultRecord
```

Toolの出所は次のメタデータで表す。

```text
builtin | mcp | skill | a2a | provider_native
```

出所は権限を意味しない。MCPだから自動許可、Builtinだから安全、とは扱わない。

### 5.4 Task StoreとSession Store

役割を分離する。

```text
Task Store:
  実行状態、checkpoint、retry、親子関係

Session Store:
  会話、Tool呼び出し、Tool結果、成果物参照、要約

Memory Store:
  セッションを越えて再利用する知識
```

同じSQLiteファイルを利用してもよいが、テーブルとAPIの責務は分ける。

### 5.5 Responses継続状態

`previous_response_id`はTaskのcheckpointではない。未完了Tool callの継続にだけ使う。

次の場合は継続IDを破棄する。

- ユーザー割り込み
- Tool loop guard発動
- Providerエラー
- Provider/model切替
- Tool call outputが欠落
- Context projectionが不一致
- Taskを別Workerへ移行

## 6. 権限モデル

既存の `UnifiedPolicy` を全Toolの実行入口へ適用する。

```text
NONE < READ_ONLY < PROPOSE_ONLY < WRITE < ADMIN
```

基本ルール:

- 子Taskの権限は親Taskを超えない。
- 読み取りToolは既定で並列実行可能。
- 外部送信、破壊操作、Credential利用は確認対象。
- `PROPOSE_ONLY` は変更案を作れるが、実行はしない。
- 未知Toolは確認・直列実行側に倒す。
- PolicyDecisionをSession/監査ログへ保存する。

## 7. MemoryとSkill

### Memory

```text
短期: 現在のLLMコンテキスト
セッション: 作業履歴、判断、失敗、成果物
長期: ユーザー設定、プロジェクト知識、再利用情報
```

自動で長期保存せず、既存のMemory APIと評価・forget処理を通す。

### Skill

Skillは手順の再利用単位とする。生成されたSkillは即時有効化しない。

```text
draft -> reviewed -> enabled -> improved -> deprecated
```

`security_scan`、テスト、依存Tool、必要権限、対象WorkspaceをSkillメタデータに紐付ける。

## 8. サブエージェントとDAG

既存の `DagNode`、`AgentTask`、A2A runtimeをTask Supervisorから呼び出す。

```text
ParentTask
  ├─ ChildTask: research
  ├─ ChildTask: implement
  └─ ChildTask: review
```

各ChildTaskは次を持つ。

- task_id
- parent_task_id
- permission_level
- workspace/artifact scope
- cancellation token
- result_ref
- checkpoint

DAGの並列化は、読み取り専用または明示的に安全と判定できる処理に限定する。

## 9. 実装フェーズ

### Phase 0: 境界テスト

- 既存の`uagent_llm.py`経路を壊さない
- `RoundOrchestrator`のProvider範囲を確認
- Task ID、Session ID、Round IDの関連をテスト
- 既存のResponses継続・割り込み・loop guardテストを維持

### Phase 1: 実行コンテキスト

新規に巨大なクラスを作らず、既存状態を束ねる薄いコンテキストを追加する。

```text
ExecutionContext
  lifecycle
  agent_state
  session
  task_id
  cancellation
  policy
  responses_runtime
```

まず読み取り専用で導入し、既存のCore状態と差分を記録する。

### Phase 2: ToolRouter統合

- Policy判定を共通入口にする
- Tool実行結果を`ToolResultManager`で分類
- Artifact参照とSession記録を統一
- MCP/Builtin/A2Aの結果形式を正規化

### Phase 3: RoundOrchestrator移行

Provider単位で段階移行する。

```text
1. Inceptionなど既存対応済み経路
2. OpenAI/Azure Responses
3. OpenAI-compatible
4. Gemini/Claude/その他Legacy
```

各移行で、旧経路と新経路の結果、Tool call、継続状態、Usageを比較する。

### Phase 4: Durable Task

- SQLiteにTaskテーブルを追加
- checkpointとretry状態を保存
- 再起動後のresumeを実装
- cancel/timeoutをTask状態に反映
- `set_timer`とTask Supervisorを接続

### Phase 5: 子Task・通知

- DAG/AgentTaskをTask Storeへ接続
- 親子権限を適用
- 完了・失敗・承認待ちをCLI/Web/A2Aへ通知

## 10. GitHub連携の試験ケース

最初の外部統合はGitHub読み取り専用MCPとする。

```text
github_get_repository
  github_get_file
  github_list_pull_requests
  github_get_pull_request_diff
```

書き込みは別Toolとして分離する。

```text
github_post_pull_request_comment
```

コメント投稿は必ず `PROPOSE_ONLY` または確認付き `WRITE` とする。GitHub TokenはTool引数やSession本文に保存しない。

## 11. 受け入れ条件

- Tool loop guard発動後にResponses継続IDを再利用しない。
- 中断、失敗、タイムアウト、Provider切替後にTaskを再開できる。
- Tool実行ごとにPolicy判定と結果参照を記録できる。
- Tool結果の全文をLLMコンテキストへ無制限に投入しない。
- 子Taskが親Task以上の権限を取得できない。
- 読み取りToolの並列化と書き込みToolの確認がテストされている。
- 既存のCLI、GUI、Web、A2Aの入口で同じ状態モデルを利用する。
- Ruff、Black、pytest、受け入れテストが成功する。

## 12. 結論

UAGの次の課題は機能追加ではなく、既存部品を次の一本の実行経路へ統合することである。

```text
Entry Point
  -> Task Supervisor
  -> Round Orchestrator
  -> Tool Router
  -> Policy / Confirmation
  -> Result / Artifact / Session Store
```

Hermes型の常駐実行、cron、Skill改善、サブエージェントは、この境界の上に段階的に追加する。
