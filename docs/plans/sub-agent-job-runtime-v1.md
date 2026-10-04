# Sub-Agent Job Runtime V1 設計

- Status: implemented (V1)
- Priority: P1
- Progress: PR 1 Runtime core, PR 2 CLI lifecycle/control, PR 3 CLI Main Agent tools, PR 4 Web/GUI integration, and PR 5 A2A task lifecycle/result retrieval are implemented; targeted regressions pass.
- Source: `docs/subagent.md`, merged PR #144（parallel groups）, Auto-pilot / Sub-Agent autonomy 実装
- Updated: 2026-10-04

## 目的

現在の UAG Sub-Agent は、複数 Sub-Agent を並列化できても、呼び出し元の Main Agent は
`run_sub_agent` / `run_sub_agent_chain` の完了まで待機する同期モデルである。

V1 では既存の同期 API を壊さずに、Sub-Agent をバックグラウンド Job として起動し、
Main Agent が別の推論・ツール実行・調整を継続できる実行基盤を追加する。

```text
Main Agent
  ├─ spawn A ────────────────┐
  ├─ spawn B ────────────┐   │
  ├─ Main 自身の作業       │   │
  ├─ send_message(A, ...) │   │
  ├─ wait(B) <────────────┘   │
  ├─ Main 自身の作業           │
  └─ wait(A) <────────────────┘
       ↓
     統合
```

## 設計原則

1. **Foreground と Background を分離する**
   - `core.status_busy` は Foreground の対話ターンだけを表す。
   - Background Sub-Agent Job は `core.status_busy` を保持しない。
   - Main Agent が終了すれば、Background Job が走っていても CLI は通常入力可能になる。

2. **既存同期 API を維持する**
   - `run_sub_agent` / `run_sub_agent_chain` は従来どおり完了まで待つ。
   - 将来的には同期 API を内部的に `spawn + wait` へ収束できる設計にする。

3. **Job は明示的に join する**
   - Background Job の結果を Main の会話履歴へ勝手に注入しない。
   - `wait/get_result` した時点で Main が結果を取得する。
   - 完了通知は UI 表示であり、Main のプロンプトコンテキストとは分離する。

4. **危険操作は Background でも確認を省略しない**
   - `human_ask` は Job ID と役割名を表示する。
   - 複数 Job の確認要求はホスト単位で直列化する。
   - non-interactive では確認が必要な操作を blocked とする。

5. **出力を Main のストリームと混ぜない**
   - Background Job の逐次ログ、tool trace、judge trace は Job Log へ格納する。
   - CLI へ標準表示するのは lifecycle の短い通知だけとする。

6. **Job を owner 単位で隔離する**
   - Job は `job_id` だけでは取得・操作できない。
   - spawn 時に entry point と session/room/task identity を owner として固定する。
   - get/wait/send/cancel は現在の runtime context と owner が一致する場合だけ許可する。
   - owner integration が未実装の entry point には Job tools を露出しない。

7. **実行数・queue・保持数を bounded にする**
   - worker 数だけでなく queued job 数、owner 単位の job 数、完了結果保持数にも上限を設ける。
   - 上限超過は structured rejection を返し、provider call を予約しない。

## 非目標

V1 では以下を必須にしない。

- 複数プロセス・複数ホストへの分散実行
- OS 再起動後の RUNNING Job の復旧
- Background Job 完了をトリガーに Main Agent を自動再起動するイベント駆動 continuation
- 任意の stdout/stderr をスレッド単位で完全キャプチャする仕組み
- Main Agent と Background Agent が同じ mutable conversation history を同時編集すること

## 現状との差

### 現在

```text
Main
  ↓
run_sub_agent_chain
  ├─ A ─┐
  ├─ B ─┼─ parallel
  └─ C ─┘
  ↓
barrier
  ↓
Main 再開
```

Main は Sub-Agent 群の終了まで待機する。

### V1

```text
Main
  ├─ spawn(A) -> job_a
  ├─ spawn(B) -> job_b
  ├─ Main の別処理
  ├─ get(job_b)
  ├─ Main の別処理
  └─ wait(job_a)
```

spawn は短時間で Job ID を返し、Main をブロックしない。

## Job API

V1 のツール面は以下を基本形とする。

### `spawn_sub_agent`

入力:

- `agent_name`
- `task`
- `provider`
- `model`
- `reasoning`
- `permission_level`
- `max_tool_turns`
- `max_agent_rounds`
- `timeout`（spawn受付時からの end-to-end Job deadline）
- `parent_goal`
- `load_keys`
- `store_key`

出力例:

```json
{
  "status": "accepted",
  "job_id": "sa_01J...",
  "agent_name": "planner"
}
```

### Job deadline semantics

`spawn_sub_agent(timeout=N)` の `timeout` は provider call単位ではなく、**spawnを受け付けた時点からの1本の絶対deadline** とする。

```text
deadline_at = accepted_at + timeout
remaining = deadline_at - monotonic_now()
```

deadline は以下すべてを含む。

- queue待ち
- provider retry
- Agent Round
- tool call
- human confirmation待ち
- inbox message処理
- completion judge

QUEUED中にdeadlineへ到達したJobは workerへ渡さず `TIMED_OUT` に遷移してqueue/admission capacityを即時解放する。
RUNNING中は各 provider/tool/retry/wait が `remaining` を参照し、通常timeoutとの小さい方を使用する。
`remaining <= 0` なら新しいprovider/tool callを開始せず `TIMED_OUT` に遷移する。

既存 runner の call単位 timeout を Job Runtime からそのまま再利用せず、Job absolute deadline を上限として注入する。

### `get_sub_agent_job`

non-blocking。

```json
{
  "job_id": "sa_01J...",
  "state": "running",
  "agent_name": "planner",
  "started_at": "...",
  "updated_at": "...",
  "progress": null
}
```

完了時は `result` / `error` / `reason` を含む。

### `wait_sub_agent_job`

指定 Job の完了を待つ。

- timeout 指定可能
- wait 中は **Foreground wait** として扱う
- CLI では `status_busy=True` にして F12 中断可能にする

### `send_sub_agent_message`

RUNNING Job へ追加指示を送る。

V1 は即時割り込み注入ではなく、**Agent Round 境界で取り込む inbox** とする。
accepted message には単調増加の sequence を付与し、Job state と inbox generation を同じ lock で更新する。

Agent loop の順序を固定する。

1. LLM/tool round 完了
2. cancellation/deadline check
3. inbox を sequence 順に atomically drain
4. inbox が1件以上あれば次 round の user instruction として注入し、completion judge を実行せず continue
5. inbox が空なら completion judge
6. COMPLETE 判定後、COMPLETED へ遷移する直前に同じ lock で inbox generation を再確認
7. 新着 message があれば completion を取り消して次 round へ進む

これにより `send_sub_agent_message` が accepted を返した message が完了直前に未読のまま失われる race を防ぐ。
COMPLETED/CANCELLED/FAILED/TIMED_OUT Job への send は rejected とする。

### `cancel_sub_agent_job`

Job 専用 cancellation を行う。

- Main Agent の interrupt flag と分離する
- `QUEUED` Job は manager lock下で queue entry を remove または tombstone 化し、workerを待たず即時 `CANCELLED` に遷移する
- queue/admission capacity は同じtransactionで即時解放する
- `WAITING_FOR_USER` は confirmation broker から purge + wake する
- `RUNNING` Job は cancellation token を set し cooperative cancellation
- terminal Job へのcancelは idempotent no-op/resultを返す
- tool/LLM wait 側は既存 interrupt 対応を再利用できる範囲で統合する

### 将来候補

- `spawn_sub_agent_chain`
- `wait_sub_agent_jobs`（any/all）
- `followup_sub_agent_job`
- dependency DAG

V1 初期実装では単体 Job を先に完成させる。

## Job Runtime

新規候補:

```text
src/uagent/runtime/sub_agent_jobs.py
```

主な型:

```python
class SubAgentJobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class SubAgentJob:
    job_id: str
    agent_name: str
    task: str
    state: SubAgentJobState
    created_at: float
    started_at: float | None = None
    completed_at: float | None = None
    result: str | None = None
    error: str | None = None
    owner: SubAgentJobOwner = ...
    job_root: str = ...
    cancel_event: threading.Event = ...
```

`SubAgentJobManager` が以下を持つ。

- manager-owned fixed-size daemon worker threads
- **明示的に bounded な pending queue**
- owner-scoped job registry
- state lock
- per-job inbox
- per-job event/log buffer
- completion notification callback
- shutdown/cancel_all

`ThreadPoolExecutor` は worker 数を制限しても submission queue 自体は無制限なので、
Job Runtime ではそのまま submit し続ける構造にしない。manager が bounded queue を所有し、
空き worker にだけ実行を渡す。

設定候補:

```text
UAGENT_SUB_AGENT_JOB_WORKERS=4
UAGENT_SUB_AGENT_JOB_QUEUE_LIMIT=16
UAGENT_SUB_AGENT_JOB_OWNER_LIMIT=8
UAGENT_SUB_AGENT_JOB_COMPLETED_LIMIT=100
UAGENT_SUB_AGENT_JOB_RESULT_TTL_SEC=3600
UAGENT_SUB_AGENT_JOB_EVENT_LIMIT=1000
UAGENT_SUB_AGENT_JOB_LOG_MAX_BYTES=1048576
UAGENT_SUB_AGENT_JOB_RESULT_MAX_BYTES=1048576
```

spawn 時に global と owner 単位の admission limit を原子的に確認する。
上限超過時は `status: rejected`, `reason: queue_full` を返し、Job/provider call を予約しない。
queue entry は job_id でremove/tombstone可能なmanager-owned構造とし、QUEUED cancel/timeoutはworker dequeueを待たずterminal遷移とcapacity解放を行う。
完了済み Job は TTL と件数上限の両方で eviction する。

各Job内部も bounded にする。

- event buffer: event件数上限、古いdebug/trace eventからdrop
- log buffer: byte上限、超過分は bounded rotating spill-to-disk または明示truncation
- result: byte上限を超える場合は metadata + bounded artifact/log reference を返し、巨大本文をregistryに保持しない
- error stack/tool output: secret masking後に同じbyte budgetへ算入

drop/truncate が発生したことは Job metadata に `truncated: true` として残す。

既存 `parallel_group` の worker limit と同一値へ強制的にまとめず、Job Runtime 側で全体上限を管理する。
後続で共通 concurrency budget に統合可能な構造にする。

## 実行 Context

Job spawn 時に現在の ContextVar を snapshot し、worker へ伝播する。

継承対象:

- IdentityContext / TurnContext
- locale
- Web room context
- tracing / correlation context
- project/session context
- immutable job_root
- Sub-Agent nesting/call-chain context

ただし Main の mutable message list は共有しない。

Background Job 自身には Job ContextVar を追加する。

```text
CURRENT_SUB_AGENT_JOB_ID
CURRENT_SUB_AGENT_JOB_MODE = foreground | background
```

この ContextVar を tool trace、status、human_ask、logging から参照できるようにする。

Sub-Agent nesting/call-chain は merged PR #144 で既に `_SUB_AGENT_CALL_CHAIN: ContextVar[tuple[str, ...]]`
へ移行済みで、同じ role の並列実行が circular call 扱いにならない回帰テストも存在する。
Job Runtime はこの context-local call chain をそのまま継承し、mutable process-global call chain を再導入しない。

## Filesystem / workdir isolation

spawn 時の current workdir を正規化して immutable な `job_root` として Job に保存する。

Background Job の file/path tool は process-global `os.getcwd()` を trust source にせず、
`job_root` を基準に相対pathを解決し、path guard も同じ root を使用する。

```text
Main :cd project-B
Background Job (spawned in project-A)
    -> relative path / safe-file root = project-A
```

Background Job では process-global cwd を変更する操作を禁止する。

- `change_workdir` は background allowed_tools から除外
- background tool が `os.chdir()` を直接呼ぶ経路は eligibility audit で不許可
- CLI の `:cd` は Main の foreground workdir を変更できるが、既存 Job の `job_root` は変えない

Background-capable file tools は明示的な root/context を受け取る方式へ段階的に統一する。
root-aware化できていない filesystem tool は V1 background 対応を無効化する。

## Ownership / entry-point exposure

spawn 時に Job owner を immutable に記録する。owner 値は LLM/tool 引数ではなく trusted runtime context から生成する。

```python
@dataclass(frozen=True)
class SubAgentJobOwner:
    entry_point: str
    session_id: str
    room_id: str | None = None
    a2a_task_id: str | None = None
```

`get_sub_agent_job` / `wait_sub_agent_job` / `send_sub_agent_message` /
`cancel_sub_agent_job` は current owner と完全一致する場合だけ許可する。

Job tools は lifecycle integration が完成した entry point だけへ露出する。

さらにV1では、**Job orchestration tools は Foreground Main Agent context にだけ公開する。**
Background Job context（`CURRENT_SUB_AGENT_JOB_MODE=background`）では
`spawn_sub_agent` / `get_sub_agent_job` / `wait_sub_agent_job` /
`send_sub_agent_message` / `cancel_sub_agent_job` を tool catalog から除外する。

理由:

- fixed worker内で child Job をspawnして blocking waitすると starvation/deadlockを作れる
- background waitが foreground `status_busy` を触る意味論を持ち込むとCLI非同期性を壊す
- V1の目的はMain Agent orchestrationであり、recursive/background orchestrationは必須ではない

Background Jobからのnested async orchestrationはV2候補とし、worker lease/release型schedulerまたは別executor budgetを設計してから有効化する。

| Entry point | 初期公開 | 公開条件 |
|---|---:|---|
| CLI | PR 3 で有効 | session owner + CLI lifecycle 完成 |
| GUI | 無効 | GUI owner / status / confirmation integration 完成後 |
| Web | 無効 | room owner / reconnect / confirmation integration 完成後 |
| A2A | 無効 | task owner / task cancel / task completion policy 完成後 |

Web では room ID、A2A では task ID を owner に含める。未対応 entry point では runtime rejection だけに頼らず、tool catalog/exposure filter からも隠す。

## CLI 状態表示

### 最重要方針

**Background Job は `core.status_busy` を変更しない。**

現在の CLI では `status_busy=True` が以下を兼ねている。

- 通常入力プロンプトの抑止
- spinner 表示
- F12 interrupt の受付条件
- status label
- GUI/Web の互換状態

したがって Background Job がこれを握ると Main Agent を非同期化した意味がなくなる。

### Foreground status

既存の `core.status_busy` / `core.status_label` はそのまま Foreground 専用とする。

例:

```text
⠋ [LLM] ...
⠴ [tool:search_web] ...
```

Main が処理中なら、Background Job が何件あっても spinner の所有者は Main だけである。

### Background summary

Background Job 数は別 API から取得する。

候補:

```python
SubAgentJobManager.running_count()
SubAgentJobManager.summary()
```

Idle prompt には短い badge を付けられるようにする。

```text
agentcli[bg:2]>
```

0 件なら現行表示を変えない。

```text
agentcli>
```

Foreground が BUSY の間は prompt badge を無理に更新しない。

### lifecycle 通知

標準出力へ出すのは短い通知だけ。

```text
[JOB sa_01 planner] started
[JOB sa_02 reviewer] started
[JOB sa_01 planner] completed (18.2s)
[JOB sa_02 reviewer] failed: timeout
```

result 本文は自動で全文表示しない。

理由:

- Main の streaming と混ざらない
- 長い Sub-Agent 出力で CLI を汚さない
- token/tool/judge の内部ログをユーザー表示から分離できる

### prompt redraw

Job 完了通知は worker thread から直接雑に `print()` しない。

Job Manager は notification event をホストへ送る。

CLI では既存の `print_lock` / prompt redraw 制御を経由して表示する。

候補:

```python
core.event_queue.put({
    "kind": "sub_agent_job_notice",
    "job_id": job_id,
    "state": "completed",
    ...
})
```

ただし Main event loop が Foreground LLM 実行で塞がれている間にも通知したい場合があるため、
最終的な表示経路は次の2案を比較する。

A. UI-safe notification callback を追加し、`print_lock` 経由で即時表示
B. 専用 display queue/thread を設ける

V1 は A を優先する。

### Background 内部ログ

デフォルトでは CLI に流さない。

保存対象:

- Agent Round
- completion judge
- tool calls
- tool results
- retry
- token/cost
- error stack
- user confirmation wait

閲覧:

```text
:jobs
:job sa_01
:job logs sa_01
:job follow sa_01
:job cancel sa_01
```

`:job follow` 中だけ対象 Job の event をライブ表示する。

### tool trace

現在の `[SUB-AGENT: planner] [TOOL] ...` のような trace は、
Background Job Context がある場合は通常 CLI へ出さず Job Log Sink へ送る。

Main/同期 Sub-Agent の既存 trace は変更しない。

重要:
Python の `sys.stdout` を worker ごとに redirect しない。
`sys.stdout` は process-global なので並列 Job で安全ではない。

中央の logging / tool trace / Sub-Agent event emission を ContextVar 対応させて制御する。

### direct print の扱い

Background 実行経路で direct `print()` を行う tool は、初期実装時に監査する。

V1 acceptance では少なくとも以下の中央経路からの出力が制御下にあることを必須とする。

- tool trace
- Sub-Agent start/stop
- completion judge event
- retry event
- status update
- lifecycle event

direct print が残る tool は別途修正対象として列挙する。

## human_ask / 確認

Background Job が危険操作の確認を必要とする場合も確認を必須とする。

CLI は現状一つの stdin を共有するため、複数 Job の `human_ask` を同時表示してはいけない。

```text
[JOB sa_03 patch_designer] confirmation required
[REPLY job:sa_03] >
```

確認要求は Job ID を持つ FIFO request として confirmation broker が直列化する。

```python
ConfirmationRequest(
    job_id=...,
    owner=...,
    message=...,
    reply_event=...,
)
```

確認中のみ通常入力を一時的に譲り、回答後は通常 prompt へ戻る。

Background Job が確認待ちの間:

```text
state = WAITING_FOR_USER
```

`:job cancel <job_id>`、Job timeout、owner/session shutdown が発生した場合、broker は対象 Job の
queued/displayed confirmation を原子的に cancel し、waiting worker を即時 wake する。
private reply queue の通常300秒timeoutまで残してはいけない。表示中のrequestをcancelした場合は
stdin ownershipも解放し、次requestまたは通常promptへ移る。

non-interactive Job では既存 `human_ask` の autonomous continuation 経路を使用しない。
Job Context が background かつ non-interactive の場合は confirmation request を enqueue する前に
fail closed し、`BLOCKED` / `cancelled:true` を返す。confirmation-dependent dangerous operation は実行しない。

別 Job と Main Agent は、共有 resource の制約がなければ継続可能。

Web は room 単位、CLI は process/stdin 単位、GUI は dialog owner 単位で confirmation broker を持つ。

## Interrupt / Cancel

### F12

F12 は **Foreground のみ**を停止する。

理由:

- Background Job が複数存在し得る
- どの Job を止めるか曖昧
- 誤って長時間調査 Job を全停止しないため

Foreground が Idle で Background Job だけ動いている場合、F12 は background 全停止には使わない。

Background Job は:

```text
:job cancel <job_id>
```

で停止する。

将来的に `:jobs cancel-all` は追加可能。

### explicit wait

Main が `wait_sub_agent_job` を呼んで待機している場合、その wait は Foreground 処理であるため
F12 を受け付ける。

F12 で wait を抜けても、Job 自体を自動 cancel するかは引数で選択可能にする。

既定:

```text
cancel_job_on_interrupt = false
```

## CLI session transition

CLI owner は `session_id` を含むため、`:load` / `:sessions load` で session を切り替える前に
Job Runtime へ transition hook を必ず通す。

V1 では Job の owner transfer は行わない。切替手順は次のとおり。

1. current session の新規 spawn を停止
2. current session owner の QUEUED/RUNNING/WAITING_FOR_USER Job を cancel
3. 対象 confirmation request を purge/wake
4. bounded timeout まで terminal state を待つ
5. 全Jobが terminal になった場合だけ `bind_session()` を実行
6. timeout 後も非terminal Job が残る場合は **session切替を中止**し、current sessionを維持して Job ID を表示する
7. abort path では current owner の spawn admission を atomically reopen する

これにより session rebind 後に旧owner Jobが操作不能になる状態を作らない。
portable/session resume tool など session切替を間接的に起動する経路も同じ transition hook を使用する。

設定候補:

```text
UAGENT_SUB_AGENT_JOB_SESSION_SWITCH_TIMEOUT=5
```

## Main Agent との結果統合

Background 完了時に Main history を worker thread から変更してはいけない。

結果取得は tool call を介する。

```text
get_sub_agent_job(job_id)
wait_sub_agent_job(job_id)
```

これにより:

- history race を防止
- いつ結果をコンテキストへ入れるか Main が制御
- 長大結果を不要に Main context へ入れない
- 複数 Job の選択的 join が可能

## Shared Store

既存の同期 Sub-Agent API の shared store 互換動作は維持するが、**Background Job の store は owner namespace を必須**とする。

Background Job の論理 key は内部的に次の形で扱う。

```text
(owner_identity, store_key)
```

`load_keys` / publish / collision check / eviction はすべて trusted runtime context から得た immutable owner 内だけで行う。
LLM/tool 引数から owner namespace を指定させない。Job ID と同様、別 owner が key 名を知っていても read/write できない。

Web/GUI/A2A exposure を有効にする前に、shared-store API と既存 `publish_shared_result` の Background Job 経路を owner-aware にする。
legacy synchronous `run_sub_agent` / `run_sub_agent_chain` は既存 store behavior を維持し、Job Runtime 経路だけを owner-scoped adapter 経由にする。

公開タイミングは Job 完了時とし、review gate を使用する場合は approve された最終結果だけを publish する既存原則を維持する。
同一 owner/key への同時 write は version/check policy を定義し、V1 では暗黙の last-write-wins を採用しない。
owner単位のstore件数/byte上限と eviction を設ける。

## Shutdown

V1 では `ThreadPoolExecutor.shutdown()` を shutdown deadline の根拠にしない。
executor worker は interpreter 終了時に join されるため、長い provider/tool call が残ると
設定した grace period を超えて CLI 終了を待たせる可能性がある。

初期CLI実装では manager-owned の daemon worker threads と bounded queue を使い、次の protocol を実行する。

1. 新規 spawn を停止する
2. QUEUED Job を CANCELLED にして queue から除去する
3. RUNNING Job に cancellation token を通知する
4. Job/provider/tool に remaining shutdown deadline を伝播する
5. grace period まで worker completion を待つ
6. deadline 到達後は manager shutdown を完了し、未終了 Job を `orphaned_on_shutdown` として記録する

daemon worker は「何もしなくてもよい」という意味ではなく、CLI process の終了が worker join によって
無期限に阻害されないための最後の境界である。通常経路では必ず cancel + bounded join を行う。

設定候補:

```text
UAGENT_SUB_AGENT_JOB_SHUTDOWN_TIMEOUT=5
```

Background Job から利用可能な provider/tool は、少なくとも次のいずれかを満たすものに限定する。

- cancellation token を監視する
- remaining deadline を timeout として受け取れる
- manager が所有する child process として実行される

契約を満たさない tool/provider は background 対応を有効化しない。
通常 timeout と Job/shutdown remaining deadline の小さい方を実 timeout として使用する。

Web/A2A は long-lived process なので、room/task cancel 後に in-flight work が残らないことを
integration test で確認できるまで Job tools を露出しない。必要なら process-isolated worker を
その entry point の公開条件とする。

## 永続化

V1 の Job registry は process-local でよい。

ただし完了済み Job metadata/result/log は既存 Sub-Agent log と統合可能にする。

OS 再起動後:

- RUNNING を復旧しない
- 前回異常終了 Job は orphaned 相当としてログ上識別可能にする

## Security / isolation

Background Job は同期 Sub-Agent と同等以上の isolation を維持する。

必須:

- provider credential isolation
- ContextVar identity propagation
- Web room/locale propagation
- permission level
- dangerous-tool confirmation
- immutable per-job filesystem root / project boundary
- background cwd-changing operation blocking
- cancellation ownership
- owner-scoped get/wait/send/cancel authorization
- unsupported entry-point exposure blocking
- owner-scoped Background shared store
- bounded admission / retention / per-job buffers
- background-safe provider/tool deadline contract
- secret masking
- per-job observability correlation

Job ID は秘密情報を含めない。

## 同期 API との関係

初期実装:

```text
run_sub_agent              -> 既存同期実装
spawn_sub_agent            -> 新 Job Runtime
wait_sub_agent_job         -> Job Runtime
```

安定後:

```text
run_sub_agent
  -> spawn internally
  -> wait
  -> return result
```

へ収束させる。

一度にそこまで変更しない。

## 実装 PR 分割

### PR 1: Job Runtime core + ownership/capacity

- `runtime/sub_agent_jobs.py`
- state model
- immutable owner identity
- bounded pending queue + fixed daemon workers
- global/per-owner admission limits
- completed-result TTL/retention
- spawn/get/wait/cancel
- ContextVar propagation
- cancellation/deadline contract
- shutdown protocol
- unit tests

この段階では Job tools を user-facing catalog に登録しない。

### PR 2: CLI lifecycle / output control

- Foreground/Background status 分離
- `agentcli[bg:N]>`
- lifecycle notice
- `:jobs`
- `:job ...`
- job log sink
- prompt redraw
- F12 semantics
- confirmation broker
- CLI owner binding

この PR で Background Job が CLI を BUSY にしないことを厳密にテストする。

### PR 3: CLI Main Agent tools

- `spawn_sub_agent`
- `get_sub_agent_job`
- `wait_sub_agent_job`
- `send_sub_agent_message`
- `cancel_sub_agent_job`
- CLI-only exposure gate
- tool catalog / docs / i18n

この時点では Web / GUI / A2A へ Job tools を露出しない。

### PR 4: Web / GUI integration

- Web room ownership
- Web reconnect / job events
- Web confirmation routing
- GUI owner / job list / confirmation UI
- integration 完了した entry point だけ exposure gate を解除

### PR 5: A2A lifecycle integration

- A2A Task owner は `entry_point="a2a"` と `task_id` を immutable owner として使う。
- A2A Task の Main Agent 実行 context にだけ task-owned Job manager を bind し、ほかの task からの cross-access を拒否する。
- `tasks/{id}:cancel` はその task owner の QUEUED/RUNNING/WAITING_FOR_USER Jobs をすべてキャンセルする。
- Main Agent が返答した後も、子 Job が terminal になるまでは親 Task を `IN_PROGRESS` のままにする。親 Task の cancel/failure/shutdown は残った子 Job を cancel する。
- 成功時は `outputMessage.background_jobs` に最大32件の terminal result/error/reason を付ける。超過時は `background_jobs_truncated=true` を付ける。子 Job の結果は assistant 文面へ勝手に混ぜない。
- 上記の ownership、cancel、completion、result retrieval policy の integration 完了後に A2A exposure を有効化する。

## 受け入れ条件

### Runtime

- spawn が blocking せず Job ID を返す
- Main Agent は Job 実行中に別 tool/LLM work を継続できる
- Job result は明示 join 前に Main history へ入らない
- cancel が対象 Job のみへ作用する
- ContextVar identity/locale/room が正しく伝播する
- worker limit を超える Job は bounded queue 内で QUEUED になる
- global/per-owner limit 超過は provider call を予約せず rejected になる
- completed Job は TTL/件数上限で eviction される
- per-job event/log/result buffer は byte/event上限を持ち、truncation/dropをmetadataで検出できる
- owner が異なる get/wait/send/cancel は拒否される
- Background shared store の read/write/collision/eviction は immutable owner namespace 内に限定される
- unsupported entry point には Job tools が露出しない
- shutdown remaining deadline が background provider/tool に伝播する
- accepted inbox message は completion transition と競合しても未読のまま失われない
- Job の相対 filesystem 操作は spawn 時の immutable job_root を基準にする
- Main の `:cd` 後も既存 Job の filesystem root は変化しない
- background `change_workdir` / direct cwd mutation は許可されない
- 同一 role の複数 Job が call-chain 衝突せず並列実行できる

### CLI

- Background Job が `core.status_busy=True` を保持しない
- Background Job 実行中でも通常 prompt が表示され入力できる
- Foreground spinner は Background Job に奪われない
- Job 内部 trace が標準では Main stream に混ざらない
- start/complete/fail notice が安全に表示される
- prompt が壊れず再描画される
- `:jobs` で active/completed state を確認できる
- `:job cancel` が対象 Job のみ停止する
- F12 は Foreground のみ停止する
- Background human_ask は Job ID 付きで直列化される
- non-interactive Background confirmation は autonomous continuation せず BLOCKED になる
- Job cancel/timeout/shutdown で queued/displayed confirmation が即時解除される
- session切替は旧session所有Jobがterminalになった場合だけrebindし、残存Jobがあれば切替を中止する

### Compatibility

- 既存 `run_sub_agent` の同期動作を変えない
- 既存 `run_sub_agent_chain` / `parallel_group` を壊さない
- CLI / GUI / Web で同期 Sub-Agent の既存表示を維持する
- Job tools未対応の Web/GUI/A2A では既存 lifecycle と tool catalog を変えない

## テスト計画

最低限:

1. spawn latency test
2. Main continuation while Job RUNNING
3. foreground `status_busy` independence
4. idle prompt with active bg count
5. foreground spinner ownership
6. completion notice + prompt redraw
7. two concurrent Jobs
8. worker queue saturation
9. cancel one of multiple Jobs
10. wait timeout
11. wait interrupt without Job cancel
12. result retrieval
13. history isolation
14. identity ContextVar propagation
15. Web room/locale propagation
16. confirmation serialization
17. dangerous operation confirmation
18. non-interactive blocked confirmation
19. tool trace routing to Job Log
20. shutdown cancellation
21. global queue saturation rejection
22. per-owner quota rejection
23. completed-result TTL/retention eviction
24. cross-owner get/wait/send/cancel denial
25. unsupported Web/A2A tool exposure
26. Web room cross-access denial（Web integration PR）
27. A2A task cancel propagation（A2A integration PR）
28. shutdown remaining-deadline propagation
29. background provider/tool eligibility audit
30. immutable job_root while Main changes cwd
31. background change_workdir rejection
32. two concurrent same-role Jobs do not trip circular-call detection
33. non-interactive background confirmation fail-closed
34. queued confirmation cancellation wakes worker immediately
35. displayed confirmation cancellation releases stdin ownership
36. owner-scoped shared-store read/write isolation
37. accepted inbox message delivered before completion
38. message arriving during completion transition forces another round
39. completed Job rejects send
40. session load cancels old-owner Jobs before bind
41. session switch aborts if old-owner Job remains nonterminal
42. per-job event/log/result byte limits and truncation metadata
43. Black / Ruff / full-tests / Python compatibility

## リスク

### status_busy の責務過多

現在 `status_busy` は表示だけでなく入力制御・interrupt 条件にも使われている。

Background Job 用に再利用してはいけない。

将来的には:

- foreground execution state
- input ownership
- background jobs
- UI status

をさらに分離する余地がある。

### direct print

Background thread の direct print は Main output と競合する。

process-global stdout redirect は使用せず、中央出力経路を context-aware にする。

### human_ask

stdin は単一資源なので Job-aware confirmation broker が必要。
cancel/timeout/shutdown は waiting confirmation を即時 purge + wake し、non-interactive Background Job は fail closed とする。

### process-global state

provider env、cwd、legacy globals など、Background 化で既存の process-global state race が再び顕在化する可能性がある。
PR #144 で見つかった credential / Web context 問題と同様、Job Runtime 導入時に監査する。
filesystem は process-global cwd を Job の基準にせず immutable job_root に固定する。

### queue / retention exhaustion

worker数だけを制限しても pending submission と完了結果が無制限ならメモリ・provider costを抑制できない。
admission control と retention eviction をRuntime coreの必須要件とする。

### owner isolation

Web room / A2A task / CLI session の境界を Job ID の推測困難性だけに依存してはいけない。
trusted runtime context 由来の owner match をすべての Job API で検証する。

### shutdown boundary

Python thread 自体には安全な強制停止機構がない。
V1は daemon worker + cancellation/deadline contract でCLI終了をboundedにし、
long-lived entry point は追加のlifecycle条件を満たすまで非公開とする。

## 更新履歴

- 2026-10-04: V1 初版。Foreground/Background status 分離、CLI Job 表示、Job API、PR 分割を定義。
- 2026-10-04: review反映。owner isolation、entry-point exposure gate、bounded queue/retention、shutdown contract、A2A lifecycle を追加。
- 2026-10-04: review反映。immutable job_root、PR #144 call-chain baseline、non-interactive fail-closed、Job-aware confirmation cancellation を追加。
- 2026-10-04: review反映。owner-scoped shared store、round-boundary inbox delivery、CLI session transition、per-job buffer上限を追加。
