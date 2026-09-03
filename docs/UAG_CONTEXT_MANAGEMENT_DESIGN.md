# UAG Context Management Design

## 1. 概要

UAG（Universal Agent Runtime）は、長時間・複雑なAgentタスクにおいてContext Windowを効率的に利用するため、単一のContext Compression方式ではなく、複数のContext Management機構を組み合わせる。

基本方針は、

> **「Context Windowを大きくする」のではなく、「Context Windowに何を置くかをRuntimeが管理する」**

とする。

OpenAIの `tool_search` はTool定義の削減には有効だが、Tool Result、Conversation History、Task State、Memoryなどには直接対応しない。

したがってUAGでは以下の多層構造を採用する。

```text
                    Agent Context Manager
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
      Tool Context      Execution Context   State Context
          │                 │                 │
      tool_search       result management   structured state
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                            ▼
                       History Context
                            │
                       compaction
                            │
                            ▼
                         Memory
                            │
                        retrieval
                            │
                            ▼
                           LLM
```

---

# 2. 背景

Agentが長時間実行されると、Context Windowには以下が蓄積する。

```text
System Prompt
Tool Definitions
User Messages
Assistant Messages
Tool Calls
Tool Results
Reasoning
Intermediate Results
Task State
Previous Summaries
```

特にTool Resultは急速にContextを消費する。

例えば、

```text
read_file()
    ↓
500KB source code

search()
    ↓
100KB results

run_test()
    ↓
50KB log
```

をそのまま保持すると、Tool Call自体よりもTool ResultがContextの大部分を占有する。

そのため、Context Managementを以下の5領域に分離する。

1. Tool Definition Management
2. Tool Result Management
3. Conversation Compaction
4. Structured Agent State
5. Memory / Retrieval

---

# 3. 重要な設計方針

## 3.1 Tool Resultを最初から全部要約しない

Tool Resultを受け取った直後に、必ずLLMでSummaryを生成する方式にはしない。

理由：

- LLM呼び出しが増える
- レイテンシが増える
- Summary生成コストが発生する
- 小さなResultまで要約するのは無駄
- コードや構造化データでは原文の方が正確

代わりに、Tool Result受信直後にRuntimeがサイズ・種類・重要度を判定する。

```text
Tool Call
   ↓
Tool Result
   ↓
Result Manager
   │
   ├─ 小さいResult
   │      ↓
   │   そのままLLM
   │
   ├─ 中程度Result
   │      ↓
   │   必要に応じて構造化/切り詰め
   │
   ├─ 大きいResult
   │      ↓
   │   Summary + Reference
   │
   └─ 巨大Result
          ↓
      Artifact保存
          ↓
      Summary + Reference
```

## 3.2 HistoryとLLM Contextを分離する

Tool Resultを履歴から削除する必要はない。

```text
                    Tool Result
                         │
             ┌───────────┴───────────┐
             ↓                       ↓
       Persistent History       LLM Context
             │                       │
       完全な結果を保存           要約/必要部分
             │                       │
             ▼                       ▼
        SessionStore              Context
```

つまり、

> **「履歴に残さない」のではなく、「毎回LLMに再投入しない」**

ことを基本とする。

監査・デバッグ・再検索・再取得のために、Raw ResultはSessionStoreまたはArtifact側へ保存可能とする。

---

# 4. 設計目標

- 長時間Agent実行に耐える
- Context Windowの消費量を抑える
- Tool定義を必要最小限にする
- 巨大なTool Resultを永続Contextに残さない
- 古い会話を要約できる
- Agentの現在状態を明示的に保持する
- Session / Memoryから必要情報だけ復元できる
- ProviderごとのContext Management機能を利用できる
- OpenAI `tool_search` が利用できないProviderでも動作する
- Tool Resultの要約による追加LLMコストを必要最小限にする

## 4.1 非目標

初期実装では以下を行わない。

- すべてのTool ResultをLLMで要約する
- 完全な自律的Memory管理
- 全履歴のembedding化
- LLMによる無制限な自動要約
- Provider固有APIへの過度な依存

---

# 5. Contextの分類

Contextを以下の4種類に分類する。

```text
Context
│
├── Stable Context
│   ├── System instructions
│   ├── User preferences
│   └── Project configuration
│
├── Active Context
│   ├── Current task
│   ├── Recent conversation
│   ├── Active tools
│   └── Current agent state
│
├── Ephemeral Context
│   ├── Tool results
│   ├── Search results
│   ├── Logs
│   └── Intermediate output
│
└── Persistent Context
    ├── Session
    ├── Memory
    ├── Artifacts
    └── Task checkpoint
```

原則として、

> **Ephemeral Contextは必要以上にContext Windowへ保持しない。**

---

# 6. Architecture

```text
                         ┌───────────────┐
                         │     User      │
                         └───────┬───────┘
                                 │
                                 ▼
                     ┌──────────────────────┐
                     │ Agent Runtime        │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ ContextManager       │
                     └──────────┬───────────┘
                                │
          ┌─────────────────────┼──────────────────────┐
          │                     │                      │
          ▼                     ▼                      ▼
 ┌────────────────┐   ┌────────────────┐    ┌────────────────┐
 │ Tool Manager   │   │ Result Manager │    │ History Manager│
 │                │   │                │    │                │
 │ tool_search    │   │ classification │    │ compaction     │
 │ tool_load      │   │ truncation     │    │ summarization  │
 │ tool_unload    │   │ summary        │    │ pruning        │
 └───────┬────────┘   │ artifact ref   │    └───────┬────────┘
         │            └───────┬────────┘            │
         └─────────────────────┼─────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Agent State Manager  │
                    │                      │
                    │ goal                 │
                    │ completed_steps     │
                    │ current_step        │
                    │ files               │
                    │ errors              │
                    │ next_action         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Session / Memory     │
                    │                      │
                    │ SessionStore         │
                    │ Memory               │
                    │ ArtifactManager      │
                    └──────────┬───────────┘
                               │
                               ▼
                          Retrieval
                               │
                               ▼
                              LLM
```

---

# 7. Tool Definition Management

## 7.1 基本方針

全Tool定義を常時LLMに渡さない。

```text
220 Tools
   ↓
Discovery
   ↓
Relevant Tools
   ↓
Active Tool Context
```

UAGの既存 `tool_catalog` / `tool_load` / `tool_unload` を利用する。

## 7.2 Provider Native Tool Search

OpenAIなどがNative Tool Searchを提供する場合は優先して利用する。

```text
Provider
   │
   ├── Native Tool Search
   │
   └── UAG Tool Catalog
```

Providerが対応していない場合はUAG側でDiscoveryを実行する。

## 7.3 Provider Capability

Provider Capabilityとして、

```python
supports_tool_search
supports_context_compaction
supports_context_editing
supports_reasoning
supports_structured_output
```

などを管理する。

Provider固有機能をAgent Loopに直接埋め込まない。

---

# 8. Tool Result Management

Tool ResultはContext Management上、最優先で削減対象とする。

## 8.1 Result Classification

Tool Resultを以下に分類する。

```text
Tool Result
│
├── Small / Direct
│   └── そのままContextへ
│
├── Structured
│   └── Python側で軽量な要約・整形
│
├── Large
│   └── Summary + Reference
│
└── Huge
    └── Artifact保存 + Summary + Reference
```

## 8.2 Result Processing

Tool Result受信時には、まずLLMではなくRuntimeで判定する。

```text
Tool Result
     │
     ▼
size / type / importance
     │
     ├── small
     │      └── direct
     │
     ├── medium
     │      └── truncate / structure
     │
     ├── large
     │      └── summarize
     │
     └── huge
            └── artifact + summarize
```

## 8.3 Tool Result Summary

Summaryが必要な場合のみLLMまたはTool固有の軽量要約処理を利用する。

LLM Summaryは、

```text
Tool Result
    ↓
Summary Generator
    ↓
Summary
```

とする。

ただし、Summary Generator自体が別の高コストLLM呼び出しにならないよう、以下を優先する。

1. Tool自身の構造化Result
2. Python側の軽量処理
3. truncation / extraction
4. 小型モデル
5. メインLLM

## 8.4 Result Reference

LLM Contextには必要に応じてReferenceを残す。

```text
[Tool Result]

summary:
OAuth callback validation failed.

result_id:
tr_8f29...

artifact_ref:
artifact://tr_8f29...
```

Agentが詳細を必要とした場合、

```text
result_id
   ↓
SessionStore / Artifact
   ↓
必要部分だけ取得
   ↓
LLM Context
```

とする。

---

# 9. Tool ResultをSQLiteとArtifactに分離する

SQLiteはAgentの「記憶・索引・状態」を保持し、大きな実データはArtifactへ保存する。

```text
                    Tool Result
                         │
                ┌────────┴────────┐
                ▼                 ▼
             Metadata          Raw Data
                │                 │
                ▼                 ▼
             SQLite           Artifact
                │                 │
                └────────┬────────┘
                         ▼
                   ContextManager
                         │
                         ▼
                        LLM
```

SQLiteに保持する候補：

- `result_id`
- `session_id`
- `task_id`
- `tool_name`
- `summary`
- `artifact_ref`
- `size_bytes`
- `importance`
- `created_at`
- `evictable`
- 検索用metadata

巨大なRaw ResultはSQLite BLOBへ無制限に保存せず、Artifact側を利用する。

---

# 10. Tool Result Record

概念モデル：

```python
@dataclass
class ToolResultRecord:
    id: str
    session_id: str
    task_id: str | None
    tool_name: str

    summary: str | None
    artifact_ref: str | None

    size_bytes: int
    importance: float

    created_at: float
    evictable: bool
```

Raw Resultそのものは、必要に応じてArtifact Managerへ保存する。

---

# 11. History Compaction

Conversation Historyは一定条件でcompactする。

```text
Old Messages
     │
     ▼
Compaction
     │
     ▼
Summary
     │
     ▼
Recent Messages
```

基本構造：

```text
System
User Goal
Task State
Compacted Summary
Recent N turns
Active Tool definitions
Relevant Tool Results
```

---

# 12. Structured Agent State

単純なSummaryだけに依存しない。

Agent Stateを独立して保持する。

```python
@dataclass
class AgentState:
    goal: str
    current_step: str
    completed_steps: list[str]
    failed_steps: list[str]
    relevant_files: list[str]
    important_facts: list[str]
    errors: list[str]
    next_action: str
```

例えば、

```yaml
goal: Implement OAuth authentication

completed_steps:
  - OAuth client
  - token refresh
  - callback handler

failed_steps:
  - callback validation

relevant_files:
  - src/oauth.py
  - src/callback.py

errors:
  - invalid redirect URI

next_action:
  - inspect callback validation
```

とする。

これにより、100 roundの履歴を再投入しなくてもAgentの現在状態を復元できる。

---

# 13. Agent StateとSummaryの違い

SummaryとStateを同一視しない。

```text
Summary
  = 過去に何が起きたか

State
  = 現在どういう状態なのか
```

例えば、

```text
Summary:
OAuth implementation was added.
Several tests were executed.
A redirect URI issue was discovered.

State:
current_step = callback validation
tests_failed = 1
next_action = inspect redirect URI
```

Agent LoopではStateを優先する。

---

# 14. Session / Memory

UAGの既存SessionStoreをPersistent Stateの基盤として利用する。

SessionStoreはSQLiteを使用し、

```text
sessions
messages
tool_calls
message_search
summaries
```

などを保持する。

Context Managementからは、

```text
Agent Loop
    │
    ▼
SessionStore
    │
    ├── Recent History
    ├── Search
    ├── Tool Audit
    └── Summary
```

として利用する。

---

# 15. Retrieval

Contextが不足した場合、全履歴を戻さず検索する。

```text
Session / Memory
       │
       ▼
   Retrieval
       │
       ├── keyword
       ├── FTS
       ├── semantic
       └── metadata
       │
       ▼
Relevant Context
```

初期実装では既存SQLite FTS5を優先する。

Embedding / Vector DBは後段で追加可能とする。

---

# 16. Context Budget

ContextにはBudgetを設定する。

```text
Context Budget
│
├── System                 10%
├── Tool Definitions       15%
├── Agent State             5%
├── Recent History         30%
├── Tool Results           20%
└── Reserved               20%
```

これは固定値ではなくProvider/Modelごとに変更可能にする。

重要なのは、

> **Contextを埋め尽くすまで使わない**

ことである。

例えば、

```text
warning threshold = 70%
compaction threshold = 80%
emergency threshold = 90%
```

とする。

---

# 17. Context Management Policy

Policyとして各種動作を制御する。

```python
@dataclass
class ContextPolicy:
    max_context_tokens: int

    tool_result_direct_limit: int
    tool_result_summary_limit: int
    recent_message_count: int

    compaction_threshold: float
    emergency_threshold: float

    enable_tool_search: bool
    enable_result_management: bool
    enable_compaction: bool
    enable_retrieval: bool
```

---

# 18. Agent Loop Integration

Agent LoopにContextManagerを組み込む。

```text
                    Agent Loop
                         │
                         ▼
                 ContextManager
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
          Tool Search  History   Agent State
              │          │          │
              └──────────┼──────────┘
                         ▼
                        LLM
                         │
                         ▼
                     Tool Call
                         │
                         ▼
                  Tool Execution
                         │
                         ▼
                  Result Manager
                         │
                ┌────────┴────────┐
                ▼                 ▼
             Direct            Managed
                │                 │
                │          ┌──────┴──────┐
                │          ▼             ▼
                │      Summary        Artifact
                │          │             │
                └──────────┴─────────────┘
                           │
                           ▼
                        Context
```

---

# 19. Context Management Decision Flow

```text
Tool Result received
        │
        ▼
   Measure / Classify
        │
        ├── Small
        │    └── Direct Context
        │
        ├── Structured
        │    └── Lightweight processing
        │
        ├── Large
        │    └── Summary + Reference
        │
        └── Huge
             └── Artifact + Summary + Reference
```

---

# 20. Compaction Decision

```text
Context Usage
      │
      ▼
    < 70%
      │
      └──► Continue

    70～80%
      │
      └──► Prepare / mark evictable results

    80～90%
      │
      └──► Compact history

    > 90%
      │
      ├──► Manage / evict tool results
      ├──► Compact history
      ├──► Rebuild Agent State
      └──► Retrieval
```

---

# 21. Recovery

Context ManagementはProcess Restartにも対応する。

```text
Process
   │
   ▼
Task
   │
   ▼
Checkpoint
   │
   X
Process restart
   │
   ▼
SessionStore
   │
   ▼
Task checkpoint
   │
   ▼
Agent State rebuild
   │
   ▼
Relevant Memory retrieval
   │
   ▼
Agent Loop resume
```

ただし、Tool Callの途中状態を無条件に再実行しない。

外部副作用を持つToolについてはidempotency / execution statusを確認する。

---

# 22. Skillとの統合

SkillはContext Management Policyを持てるようにする。

例えば、

```text
Skill: repository-analysis

Tools:
  code_map
  grep
  read_file
  run_test

Context Policy:
  large_file_result = summarize
  test_log = summarize
  source_code = artifact
  symbols = state
```

これによりSkillごとに最適なContext戦略を選択できる。

---

# 23. Taskとの統合

TaskはContext StateをCheckpointに含める。

```text
TaskRecord
│
├── status
├── input_message
├── output_message
├── error
└── checkpoint
      │
      ├── agent_state
      ├── summary
      ├── active_skill
      ├── active_tools
      └── artifact_refs
```

これにより長時間TaskでもProcess Restart後にContextを再構築できる。

---

# 24. Provider Integration

Provider固有機能はAdapterで吸収する。

```text
                  ContextManager
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       OpenAI       Anthropic     Others
          │            │            │
     tool_search   context_edit   UAG
     compaction    compaction     fallback
```

原則：

> Provider Native機能が利用可能なら利用する。ただしUAGのContext ModelをProvider APIに依存させない。

---

# 25. 推奨Context Managementレイヤー

UAGでは以下の5層を基本構成とする。

```text
Layer 1: Tool Definition
    tool_search / catalog / load
              ↓
Layer 2: Tool Result
    classification / truncation / summary / artifact
              ↓
Layer 3: Conversation
    compaction / pruning / summarization
              ↓
Layer 4: Agent State
    current goal / progress / errors / next action
              ↓
Layer 5: Persistent Knowledge
    Session / Memory / Artifact / Retrieval
```

重要なのは、これらを同一の「圧縮」として扱わないことである。

---

# 26. Implementation Plan

## Phase 1: ContextManager基盤

既存機能を統合する。

- `tool_catalog`
- `tool_load`
- `tool_unload`
- SessionStore
- existing compaction
- Task checkpoint

新しい抽象化：

```text
ContextManager
ContextPolicy
AgentState
```

を追加する。

## Phase 2: Tool Result Management

- result size tracking
- result classification
- direct pass-through
- truncation
- lightweight extraction
- artifact reference
- LLM summary
- eviction

## Phase 3: Structured Agent State

- State generation
- State update
- State checkpoint
- State recovery

## Phase 4: Retrieval

- SQLite FTS5
- session retrieval
- memory retrieval
- relevant-context injection

## Phase 5: Provider Native Context Management

- OpenAI tool_search
- OpenAI compaction
- Anthropic context editing
- provider capability detection

---

# 27. 推奨クラス構成

```text
uagent/runtime/
│
├── context_manager.py
├── context_policy.py
├── context_budget.py
├── context_compaction.py
├── context_result_manager.py
├── context_eviction.py
├── agent_state.py
├── session_store.py
├── memory_store.py
└── artifact_manager.py
```

Tool関連：

```text
uagent/tools/
│
├── catalog_tool.py
├── load_tool.py
└── unload_tool.py
```

Task関連：

```text
uagent/a2a/
│
├── task_store.py
└── dag_scheduler.py
```

---

# 28. 最終Architecture

```text
                              ┌──────────────┐
                              │     User     │
                              └──────┬───────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │    Agent Runtime    │
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │   Context Manager   │
                          └──────────┬──────────┘
                                     │
       ┌─────────────────────────────┼───────────────────────────┐
       │                             │                           │
       ▼                             ▼                           ▼
┌───────────────┐            ┌───────────────┐          ┌───────────────┐
│ Tool Context  │            │ History       │          │ Agent State   │
│               │            │               │          │               │
│ tool_search   │            │ compaction    │          │ goal          │
│ tool_load     │            │ pruning       │          │ current step  │
│ tool_unload   │            │ summarizing   │          │ progress      │
└───────┬───────┘            └───────┬───────┘          └───────┬───────┘
        │                            │                          │
        └────────────────────────────┼──────────────────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │     LLM      │
                              └──────┬───────┘
                                     │
                                     ▼
                               Tool Execution
                                     │
                                     ▼
                           ┌───────────────────┐
                           │ Result Manager    │
                           └─────────┬─────────┘
                                     │
                   ┌─────────────────┼─────────────────┐
                   ▼                 ▼                 ▼
                Direct           Summary           Artifact
                   │                 │                 │
                   │                 │                 ▼
                   │                 │            Raw Result
                   │                 │                 │
                   └─────────────────┴─────────────────┘
                                     │
                                     ▼
                                  Context
                                     │
                                     ▼
                                    LLM

Persistent side:

             ┌──────────────────────────────────────┐
             │              Storage                 │
             │                                      │
             │ SQLite                               │
             │ ├── Session                          │
             │ ├── Messages                         │
             │ ├── Tool Results Metadata            │
             │ ├── Summaries                        │
             │ └── Agent State                      │
             │                                      │
             │ Artifact                             │
             │ └── Large Raw Results                │
             │                                      │
             │ TaskStore                            │
             │ └── Checkpoints                      │
             └──────────────────┬───────────────────┘
                                │
                                ▼
                            Retrieval
                                │
                                ▼
                             Context
```

---

# 29. 最重要な設計原則

## Principle 1

**Tool SearchはContext Management全体ではない。**

Tool Definitionを削減する機構として扱う。

## Principle 2

**Tool Resultは一律にLLMで要約しない。**

サイズ・種類・重要度に応じて、

- そのまま渡す
- 軽量処理する
- Summaryを生成する
- Artifactへ退避する

を選択する。

## Principle 3

**Tool Resultは履歴から削除する必要はない。**

Persistent Storageには完全な情報を保持し、LLM Contextには必要最小限だけ入れる。

## Principle 4

**SummaryとAgent Stateを分離する。**

Summaryは過去、Stateは現在。

## Principle 5

**MemoryはContextではない。**

MemoryはPersistent Storageであり、必要なときだけContextへRetrievalする。

## Principle 6

**Provider Native機能を利用するが、UAG内部モデルはProvider非依存にする。**

## Principle 7

**Context ManagementはAgent Loopの外側に置く。**

Agent Loop自身が「いつ何をContextに入れるか」を直接管理しない。

ContextManagerが一元管理する。

---

# 30. 期待される効果

この設計により、UAGは、

```text
Small Task
    ↓
通常Context

Medium Task
    ↓
Tool Search + Result Management

Large Task
    ↓
Tool Search
+ Result Management
+ Compaction
+ Agent State

Long-running Task
    ↓
Tool Search
+ Result Management
+ Compaction
+ Agent State
+ Session
+ Memory
+ Retrieval
+ Checkpoint
```

という段階的なContext Managementが可能になる。

最終的な目標は、

> **Context WindowのサイズにAgentの実行時間を制約させない。**

ことである。

---

# 31. 結論

UAG Context Managementは、

```text
tool_search
     +
result classification
     +
result summary
     +
artifact offloading
     +
compaction
     +
structured agent state
     +
memory
     +
retrieval
     +
checkpoint
```

を統合した**多層Context Management Architecture**とする。

特に重要なのは、

```text
Tool Definition
Tool Result
History
State
Memory
Task
```

をすべて同じ「Context」として扱わないことである。

それぞれに異なる寿命・重要度・保存場所を与えることで、長時間AgentのContext効率を最大化する。

## 推奨するTool Resultの基本動作

```text
Tool Result
    │
    ▼
Runtimeでサイズ・種類・重要度を判定
    │
    ├── 小さい
    │     └── 原文をLLMへ
    │
    ├── 中程度
    │     └── 軽量な整形/抽出
    │
    ├── 大きい
    │     └── Summary + result_id
    │
    └── 巨大
          └── Artifact + Summary + result_id
```

したがって、

> **「Tool Resultを一発目からSummaryだけにする」のではなく、「一発目のResultをContext Managerが分類し、必要な場合だけSummary化する」**

ことをUAGの標準動作とする。
