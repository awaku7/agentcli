# UAG Memory Architecture v3 — Identity / Shared Room 設計

## 0. 位置づけ

対象は `awaku7/agentcli` v0.7.12、基準 commit `4074cce99d2fe3a32b169b4095720821b0e1ad1e`。

v2 で定義した「正本と projection の分離」「owner / project / scope を検索前の境界にする」「turn-local frozen snapshot」「forget propagation」「評価してから既定化する」という原則を継承する。

v0.7.12 では stable ID / revision、SQLite・JSONL migration、owner / project metadata、turn-local projection、Applicable User Guidance と Memory Evidence の分離、38 locale の contextual query、frozen snapshot、deterministic evaluation gate まで実装された。

v3 の目的は v2 を作り直すことではない。v0.7.12 で顕在化した次の境界を追加する。

> **同一 UAG Web process を複数人が利用し、さらに同じ room を共有する場合でも、個人 Memory / Profile を混線させず、room 共有 Memory は参加者間で共有できること。**

本書は設計書であり、記載した v3 機能が現在実装済みであることを意味しない。

---

## 1. v0.7.12 で確認できる現在地

### 1.1 Memory 側

現在の structured personal memory は以下を保持できる。

- `memory_id`
- `owner`
- `project`
- `kind`
- `source` / `source_id`
- `revision`
- `status`
- `supersedes_id`
- `created_at` / `updated_at`
- `note`

`UAGENT_MEMORY_OWNER` は明示的 owner の fallback であり、`UAGENT_MEMORY_PROJECT` は project の明示 override である。

Memory Projection は `owner + project` を使って候補を事前に絞り、strict scope では owner / project を検証できない legacy record を除外できる。

### 1.2 Web 側

Web は `room_id` ごとに `WebRoom` を生成し、次を room 単位で分離している。

- UI messages
- LLM history
- workdir
- status
- human_ask state
- worker lock

一つの `WebRoom` は複数の WebSocket connection を保持できるため、同じ room を複数ブラウザから共有できる。

一方、WebSocket connection から現在取得している主要な識別子は `room_id` であり、「この user_input を送った人は誰か」という stable principal identity は存在しない。

### 1.3 現在の owner との不整合

Memory Projection の owner は `core.memory_owner` または `UAGENT_MEMORY_OWNER` から解決される。これは process / runtime 側の値であり、WebSocket connection ごとの発言者 identity ではない。

したがって同じ room を A と B が共有した場合、現在のモデルは概念上次のようになる。

```text
room-X
├─ connection A ─┐
└─ connection B ─┴─> UAGENT_MEMORY_OWNER = one process-wide value
```

この状態で Personal Memory Projection を有効にすると、A と B を別 owner として安全に扱うことはできない。

また `/api/memories` は現在 global long-memory store を直接列挙・追加・更新・削除する経路であり、Web user identity による filter はない。

### 1.4 Profile も同じ問題を持つ

Profile は preferences / constraints / environment を保持し、Applicable User Guidance の入力になる。しかし現行 Profile は Web user ごとの identity boundary を持たない。

したがって multi-user Web では Memory だけでなく Profile も principal 単位に分離しなければならない。

---

## 2. v3 の基本判断

v3 では次の4つを別概念として扱う。

| 概念 | 意味 | 例 |
|---|---|---|
| `principal_id` | 今この turn を実行している人・サービスの stable identity | `local`, `user:123` |
| `room_id` | 会話・共同作業のコンテナ | `room:abc` |
| `project_id` | 作業対象の project / workspace | `agentcli` または path-derived ID |
| Memory audience | その Memory を誰が読めるか | personal / room / project / global |

最重要原則は次である。

```text
principal_id != room_id != project_id
```

`room_id` を owner にしない。`owner` を room にしない。

同一人物は複数 room に参加でき、同一 room には複数人物が参加できるからである。

---

## 3. Identity と Authentication を分離する

### 3.1 Identity

Memory に必要なのは「現在の turn の principal は誰か」という identity である。

### 3.2 Authentication

Authentication は「その principal を名乗ることをどう検証したか」である。

したがって、v3 はログイン画面そのものを Memory の必須要件にしない。

```text
IdentityResolver
       ↓
 principal_id
       ↓
MemoryAccessContext
```

Authentication は `IdentityResolver` の入力の一つとする。

### 3.3 Entry point ごとの既定

#### CLI / Desktop GUI / trusted single-user Web

ユーザー state directory 自体が OS user 境界なので、ログインは不要とする。

```text
principal_id = "local"
```

ここで `local` は machine 全体の一意 ID ではなく、「この user state namespace の local principal」を意味する。

OS username を Memory key に直接使用しない。ユーザー名変更、domain 参加、個人情報露出を避けるためである。

#### Multi-user Web

multi-user mode では stable principal を server-side に解決する。

候補は次のいずれでもよい。

- OIDC / OAuth subject
- reverse proxy / SSO が検証した subject
- UAG 将来の account ID
- enterprise gateway の authenticated principal

Memory 層は具体的な login provider を知らない。

#### A2A / API

API key 自体を owner にしない。検証済み credential から stable principal / service principal を解決する。

---

## 4. IdentityResolver

v3 では entry point ごとに identity を直接組み立てず、共通契約へ集約する。

概念 API:

```python
@dataclass(frozen=True)
class IdentityContext:
    principal_id: str
    authenticated: bool
    authn_kind: str
    display_name: str = ""


def resolve_identity(request_context) -> IdentityContext:
    ...
```

### 4.1 必須契約

- client payload の `owner` をそのまま信用しない。
- `principal_id` は server-side resolver が決定する。
- `room_id` query parameter を principal identity として使用しない。
- arbitrary HTTP header を無条件に identity として採用しない。
- trusted-header mode を設ける場合は trusted reverse proxy からの接続であることを別途保証する。
- identity 解決失敗時に別ユーザーの Personal Memory へ fallback しない。

### 4.2 Compatibility

`UAGENT_MEMORY_OWNER` は v3 では legacy / single-user override と位置づける。

優先順位の案:

```text
explicit trusted IdentityContext
    > entry-point local identity
    > UAGENT_MEMORY_OWNER (legacy override)
    > no principal
```

multi-user Web では `UAGENT_MEMORY_OWNER` を全 user 共通 owner として使用しない。

---

## 5. Connection / Room / Turn の境界

同じ room に異なる user が接続できるため、identity を `WebRoom` に1個だけ持たせてはいけない。

必要なのは connection 単位の context である。

```text
WebSocket connection A
    IdentityContext(user-A)
           │
           ├──────────┐
           │          │
           v          v
        room-X     user turn A

WebSocket connection B
    IdentityContext(user-B)
           │
           ├──────────┐
           │          │
           v          v
        room-X     user turn B
```

### 5.1 TurnContext

各 user input から immutable な TurnContext を作る。

```python
@dataclass(frozen=True)
class TurnContext:
    principal_id: str
    room_id: str
    project_id: str
    session_id: str
    entry_point: str
    authenticated: bool
    authn_kind: str
```

`run_agent_worker()`、Memory Projection、tool execution、Profile extraction、Session persistence は同一 TurnContext を参照する。

### 5.2 Global mutable owner を禁止

次のような実装は行わない。

```python
core.memory_owner = current_web_user
```

理由:

- 同じ room の別 connection と衝突する。
- tool thread / sub-agent へ誤った owner が漏れる。
- 将来 global worker lock を緩和した時に race になる。
- retry / cancellation 時の ownership が不明確になる。

明示引数を優先し、必要な legacy bridge には `contextvars.ContextVar` 等の request / turn local context を使う。

ThreadPool / tool worker へは context を明示伝播する。

---

## 6. Memory の owner と audience

v2 / v0.7.12 の `owner` は Personal Memory の境界として有効だが、room 共有を表現するには不足する。

v3 では **誰が所有・作成したか** と **誰に見せるか** を分離する。

### 6.1 MemoryRecord v3 logical contract

物理 backend を直ちに統合する必要はないが、logical contract として次を持つ。

```text
memory_id
owner_id
project_id
audience_type
audience_id
kind
note
source
source_id
revision
status
supersedes_id
created_at
updated_at
```

`owner_id`:
- record の論理 owner / creator
- Personal Memory では必ず現在 principal
- shared record では作成者または管理主体

`audience_type`:
- `personal`
- `room`
- `project`
- `global`

`audience_id`:
- personal: `principal_id`
- room: `room_id`
- project: `project_id`
- global: fixed / empty

### 6.2 代表例

```text
Personal Memory
owner_id     = user-A
audience_type= personal
audience_id  = user-A
project_id   = agentcli
```

```text
Room Shared Memory
owner_id     = user-A
audience_type= room
audience_id  = room-X
project_id   = agentcli
```

```text
Project Shared Memory
audience_type= project
audience_id  = agentcli
```

`global` は legacy compatibility / administrator-managed knowledge を主用途とし、multi-user strict mode で無条件に personal guidance と混ぜない。

---

## 7. MemoryAccessContext

検索時に caller が任意の owner / audience を指定する方式にしない。

TurnContext と room access policy から readable audience を server-side に構築する。

概念 API:

```python
@dataclass(frozen=True)
class MemoryAccessContext:
    principal_id: str
    room_id: str
    project_id: str
    readable_audiences: tuple[tuple[str, str], ...]
```

user-A が room-X で agentcli を操作する例:

```text
readable:
- personal:user-A
- room:room-X
- project:agentcli      # policy で許可される場合
```

### 7.1 Filtering order

必ず以下の順で行う。

```text
identity / membership / audience filter
              ↓
project filter
              ↓
status / forget filter
              ↓
text relevance candidate generation
              ↓
ranking / budget
              ↓
projection
```

アクセス境界を relevance score へ混ぜない。

「score が高いから別 user の Memory を採用する」という状態を構造上不可能にする。

---

## 8. 同じ room を共有した場合の動作

### 8.1 user-A の turn

```text
user-A
  ↓
room-X
  ↓
Personal Memory(user-A)
+ Room Memory(room-X)
+ allowed Project Memory
  ↓
frozen MemoryProjectionSnapshot(A, room-X)
```

### 8.2 次に user-B が発言

```text
user-B
  ↓
room-X
  ↓
Personal Memory(user-B)
+ Room Memory(room-X)
+ allowed Project Memory
  ↓
frozen MemoryProjectionSnapshot(B, room-X)
```

A の Personal Memory は B の turn に入らない。

### 8.3 Snapshot の追加契約

Snapshot は content fingerprint だけでなく、少なくとも以下の identity boundary と結び付ける。

- principal identity fingerprint
- room ID または room fingerprint
- project ID
- memory generation
- readable audience set fingerprint

A 用 Snapshot を B の turn へ再適用してはいけない。

診断ログに raw principal ID を出す必要はなく、opaque hash / internal reference でよい。

---

## 9. Room Shared Memory

### 9.1 Personal から Shared への自動昇格は禁止

Personal Memory は room に参加しただけで共有されない。

```text
personal:user-A
   X automatic promotion
room:room-X
```

room shared memory へ書く場合は明示的な shared operation または明確な approval contract を要求する。

### 9.2 Room access

`room_id` を知っていることだけを永続的な user identity の証拠にしない。

RoomAccessPolicy を独立させる。

```python
can_join(principal_id, room_id)
can_read_room_memory(principal_id, room_id)
can_write_room_memory(principal_id, room_id)
can_delete_room_memory(principal_id, room_id, memory_id)
```

single-user local mode では単純な allow policy でよい。

multi-user mode では authenticated membership、external ACL、または将来の room capability model を接続できるようにする。

Memory core は login UI や membership DB の実装方式を固定しない。

---

## 10. Profile v3

Profile は Personal Memory と同じく principal boundary を必要とする。

### 10.1 原則

```text
Profile(user-A) != Profile(user-B)
```

同じ room でも混ぜない。

### 10.2 Shared room での抽出

Session message に `actor_id` metadata を保持する。

```text
message
- role=user
- actor_id=user-A
- content=...
```

Profile extraction は user-A の発言から user-A の preference / constraint を学習する。

B の発言を A の Profile に取り込まない。

assistant の提案や room の他参加者の発言を personal preference として自動昇格しない。

### 10.3 Storage

single-user compatibility では既存 `scheck_profile.jsonl` を利用できる。

multi-user mode では principal-keyed ProfileStore を使用する。

例:

```text
profiles
- principal_id
- environment_json
- preferences_json
- constraints_json
- revision
- updated_at
```

既存 file を無理に multi-user 共用しない。

---

## 11. Session / Episodic Memory

SessionStore にも identity metadata を追加する。

最低限:

- `principal_id`
- `room_id`
- `project_id`
- `entry_point`

shared room の user message には actor metadata を保存する。

これにより「以前自分が決めたこと」と「room の別参加者が言ったこと」を区別できる。

Episodic retrieval でも access filter を relevance より前に適用する。

---

## 12. Context Projection v3

Provider へ渡す概念順序は次とする。

```text
Base System / Safety / Policy
        ↓
Principal Applicable Guidance
        ↓
Room / Project Policy Guidance
        ↓
Retrieved Memory Evidence
        ↓
Working Context / Conversation
        ↓
Current User Request
```

### 12.1 Principal Applicable Guidance

現在 principal の preferences / constraints のみ。

### 12.2 Room / Project Policy

room や project に明示的に定義された共同作業上のルール。

Personal preference と同じ Profile table に混ぜない。

### 12.3 Retrieved Evidence

MemoryAccessContext が許可した audience の record のみ。

### 12.4 Durable history boundary

v2 と同様、projection された guidance / evidence は durable conversation history へ user / assistant 原文として保存しない。

ただし診断用 metadata として projection ID、audience fingerprint、source memory ID を安全な形で記録することは許可する。

---

## 13. Memory write path

### 13.1 Personal write

`add_long_memory` の owner を model / browser が自由指定しない。

```text
TurnContext.principal_id
      ↓
owner_id
      ↓
audience=personal:<principal_id>
```

migration / admin tool だけが明示 owner override を使用できる。

### 13.2 Room write

room shared memory は別 operation とする。

```text
add_room_memory(note)
```

または generic API なら server-side policy が audience を決定する。

### 13.3 Forget / Update

Personal:
- owner principal のみ update / forget

Room:
- RoomAccessPolicy に従う
- creator-only / moderator / room-admin 等を将来拡張可能にする

index ベース API より stable `memory_id` を使用する。

---

## 14. Web API v3

現在の `/api/memories` は global store を扱うため、multi-user mode ではそのまま使用しない。

推奨 API contract:

```text
GET    /api/v2/memories?audience=personal
POST   /api/v2/memories
PUT    /api/v2/memories/{memory_id}
DELETE /api/v2/memories/{memory_id}
```

server は request identity から access context を作る。

Request body に `owner_id=user-B` を渡して B の Personal Memory を操作できる設計にしない。

room memory の場合も `room_id` への write permission を検証する。

### 14.1 WebSocket

現在:

```text
/ws?room=<room_id>
```

v3:

```text
HTTP/WebSocket authentication context
        + room_id
        ↓
WebConnectionContext
        ↓
TurnContext per user_input
```

identity は WebSocket connection lifecycle に結び付け、room object に単一 identity として保存しない。

---

## 15. Local mode と backward compatibility

v3 導入で CLI / GUI に login を要求しない。

### local single-user

```text
principal_id = local
room_id      = local/session-specific
```

既存 owner が空の record は migration / compatibility mode で local principal にのみ解釈できる。

### legacy owner record

既に `owner` が設定されている record は Personal audience へ機械的に map 可能である。

```text
owner=alice
    ↓
audience_type=personal
audience_id=alice
```

ただし owner が空の legacy record を multi-user principal へ推測割当しない。

### legacy Shared Memory

既存 Shared Memory は `global legacy shared` として扱う。

multi-user strict mode での自動 projection は opt-in とし、いきなり全 user へ公開しない。

---

## 16. Proposed configuration

名前は実装時に最終確定するが、責務は分ける。

```env
# Existing rollout
UAGENT_MEMORY_PROJECTION=0
UAGENT_MEMORY_STRICT_SCOPE=0

# Legacy / local override
UAGENT_MEMORY_OWNER=
UAGENT_MEMORY_PROJECT=

# Proposed identity mode
UAGENT_IDENTITY_MODE=local

# Example future modes
# local
# trusted_header
# oidc
# external
```

Web multi-user mode で identity provider が未設定の場合は Personal Memory Projection を fail-closed にする案を第一候補とする。

「identity が分からないので process 共通 owner を使用する」は行わない。

---

## 17. Security invariants

v3 の必須 invariant:

1. user-B の request から user-A の Personal Memory を取得できない。
2. user-B は request payload で `owner=user-A` を指定して境界を越えられない。
3. room-X の member でない principal は room-X Memory を取得できない。
4. project mismatch record は access filter 後も候補にならない。
5. forgotten record は stale snapshot / retry / provider continuation から復活しない。
6. Profile は principal 間で混ざらない。
7. shared room の他 user 発言を自分の Personal Profile / Personal Memory として自動学習しない。
8. identity context は tool thread / sub-agent / retry で別 turn と混ざらない。
9. anonymous / unresolved identity を privileged local principal へ自動昇格しない。
10. raw authentication token、API key、OIDC token を Memory owner ID として保存しない。

---

## 18. Evaluation v3

既存 deterministic Memory Evaluation に multi-user fixture を追加する。

最低限のケース:

### Identity isolation

- A の Personal Memory が A では recall される。
- 同一 query を B が実行しても A の Memory は0件。
- spoofed owner input を無視すべきこと。

### Shared room

- A と B が同じ room-X に参加。
- room-X memory は両者に見える。
- A personal は B に見えない。
- room-Y user には room-X memory が見えない。

### Same user across rooms

- A が room-X と room-Y の両方で Personal Memory を利用できる。
- room-specific memory は対象 room だけ。

### Profile isolation

- A preference は A Guidance にだけ入る。
- B preference は B Guidance にだけ入る。

### Frozen snapshot

- A turn の snapshot を B turn へ再利用しない。
- retry 中は同じ A snapshot を再利用する。

### Concurrency / context propagation

- 複数 connection の交互 turn で principal が入れ替わっても leak しない。
- tool worker / sub-agent が呼出元 TurnContext を保持する。

### Legacy

- single-user `local` では v0.7.12 compatibility を維持。
- owner 不明 record は multi-user strict mode で除外。

評価指標は既存の recall / irrelevant injection / scope violation に加え、少なくとも次を持つ。

```text
identity_leak_count
audience_violation_count
profile_leak_count
snapshot_identity_mismatch_count
```

すべて 0 を必須 gate とする。

---

## 19. 実装順序

大きな login system を先に作らない。Memory boundary から独立して段階導入する。

### PR V3-1: IdentityContext / TurnContext

- `IdentityContext`
- `TurnContext`
- local resolver
- ContextVar / explicit propagation
- CLI / GUI / Web / A2A adapter
- behavior は既存 single-user と同じ

**完了条件:** owner を global mutable state に設定しなくても同一 turn の全処理へ identity を渡せる。

### PR V3-2: Web connection identity boundary

- WebConnectionContext
- per-connection identity
- `run_agent_worker(..., turn_context=...)`
- shared room で connection A / B を区別
- unresolved multi-user identity は Personal Projection fail-closed

**完了条件:** 同一 room の2 connection に異なる principal を割り当てられる。

### PR V3-3: Memory audience contract

- `audience_type` / `audience_id`
- schema migration
- MemoryAccessContext
- pre-retrieval access filter
- legacy owner mapping

**完了条件:** Personal / room audience isolation が store level fixture で証明される。

### PR V3-4: Projection / Profile / Session integration

- Principal ProfileStore
- actor metadata in shared room messages
- identity-bound frozen snapshot
- episodic retrieval boundary
- forget propagation per access context

**完了条件:** Personal Guidance と Personal Memory が同一 room の別 user に漏れない。

### PR V3-5: Web Memory API / Room policy

- stable memory ID API
- identity-filtered list/update/delete
- RoomAccessPolicy hook
- room shared write path

**完了条件:** browser request から arbitrary owner を操作できない。

### PR V3-6: Evaluation / rollout

- deterministic multi-user fixtures
- identity leak gates
- migration tests
- docs / environment options
- shadow → opt-in multi-user projection

**完了条件:** leak metrics が0で、single-user regression がない。

---

## 20. Rollout

推奨順序:

```text
v0.7.12 single-user baseline
        ↓
IdentityContext (no behavior change)
        ↓
Web identity shadow diagnostics
        ↓
Audience-aware retrieval shadow
        ↓
Single-user projection unchanged
        ↓
Authenticated multi-user opt-in
        ↓
Shared-room Memory opt-in
        ↓
Default decision
```

Memory Projection の既定 ON と multi-user identity rollout は別判断にする。

単一ユーザーで Projection が安全でも、multi-user sharing が安全とは限らない。

---

## 21. v3 で採らない設計

### `owner = room_id`

不採用。同一 user が別 room に移るたび別人になる。

### `owner = IP address`

不採用。NAT、VPN、mobile network、privacy、共有端末で stable identity にならない。

### `owner = browser generated random ID` を認証済み user と同等に扱う

不採用。便利な client instance ID と authorization identity は別物である。

### client が owner を自由指定

不採用。アクセス制御にならない。

### `UAGENT_MEMORY_OWNER` を multi-user Web 全員へ適用

不採用。Personal Memory の cross-user leakage を起こす。

### Shared room の会話を全参加者の Personal Profile に学習

不採用。発言者 identity を失う。

### login system を MemoryStore に直接組み込む

不採用。IdentityResolver / AccessPolicy の外側に置く。

---

## 22. 最終アーキテクチャ

```text
                           ┌──────────────────────┐
                           │ Authentication / SSO │
                           │ or local trust       │
                           └──────────┬───────────┘
                                      │
                               IdentityResolver
                                      │
                                IdentityContext
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
        CLI/GUI                  Web Connection                 A2A/API
          │                    user-A / user-B                     │
          └───────────────────────────┼───────────────────────────┘
                                      │
                                  TurnContext
                    principal + room + project + session
                                      │
                             MemoryAccessContext
                                      │
                  ┌───────────────────┼──────────────────┐
                  │                   │                  │
          personal:<principal>    room:<room>      project:<project>
                  │                   │                  │
                  └───────────────────┼──────────────────┘
                                      │
                         relevance / ranking / budget
                                      │
                         Frozen Projection Snapshot
                                      │
                 ┌────────────────────┴────────────────────┐
                 │                                         │
      Applicable Principal Guidance              Retrieved Evidence
                 │                                         │
                 └────────────────────┬────────────────────┘
                                      │
                                   Provider
```

この構造なら、ローカル単一ユーザーではログインなしで現在の使い勝手を維持できる。

同時に Web を複数人で使う場合は identity provider を差し込むだけで、同一 user の Personal Memory を複数 room で継続利用し、room Shared Memory だけを参加者間で共有できる。

v3 の中心は「ログイン機能」ではない。

> **principal identity、room、project、Memory audience を分離し、全 Memory / Profile / Session retrieval を同じ access context で守ること。**

これを先に契約として固定すれば、将来の OIDC、社内 SSO、外部 gateway、room ACL、A2A service identity を Memory core の再設計なしで追加できる。
