# UAG Memory Architecture v3 — Identity / Authentication / Shared Room 設計

## 0. 位置づけ

対象は `awaku7/agentcli` v0.7.12、基準 commit `4074cce99d2fe3a32b169b4095720821b0e1ad1e`。

v2 で定義した次の原則を継承する。

- 正本と projection の分離
- owner / project / scope を検索前の境界にする
- turn-local frozen snapshot
- forget propagation
- deterministic evaluation gate
- 評価してから既定化する

v0.7.12 では stable ID / revision、SQLite・JSONL migration、owner / project metadata、turn-local projection、Applicable User Guidance と Memory Evidence の分離、38 locale の contextual query、frozen snapshot、deterministic evaluation gate まで実装された。

v3 の目的は v2 を作り直すことではない。v0.7.12 で顕在化した次の問題を解決する。

> **同一 UAG Web process を複数人が利用し、さらに同じ room を共有する場合でも、個人 Memory / Profile を混線させず、room 共有 Memory は参加者間で共有できること。**

同時に、Memory のためだけに独自ログイン機構を抱え込まず、Local / OIDC / Trusted Proxy / API credential を共通の Identity contract へ正規化する。

本書は設計書であり、記載した v3 機能が現在実装済みであることを意味しない。

---

## 1. v0.7.12 の現在地

### 1.1 Memory

structured personal memory は現在、少なくとも次を保持できる。

```text
memory_id
owner
project
kind
source
source_id
revision
status
supersedes_id
created_at
updated_at
note
```

`UAGENT_MEMORY_OWNER` は明示 owner の fallback、`UAGENT_MEMORY_PROJECT` は project override である。

Memory Projection は owner / project を利用できるが、owner は process / runtime 側の値であり、WebSocket connection ごとの発言者 identity ではない。

### 1.2 Web

Web は `room_id` ごとに `WebRoom` を持ち、次を room 単位で分離している。

- UI messages
- LLM history
- workdir
- status
- human_ask state
- worker lock

同じ `WebRoom` へ複数 WebSocket connection を接続できる。

しかし現在の `room_id` は「会話の部屋」であって「誰が発言しているか」を表す stable user identity ではない。

### 1.3 現在の問題

概念上、現在は次の状態になり得る。

```text
room-X
├─ connection A ─┐
└─ connection B ─┴─> process-wide memory owner
```

この状態で Personal Memory Projection を multi-user Web へ有効化すると、A と B の Personal Memory を安全に分離できない。

Profile も同様に principal boundary を持たない。

また既存 `/api/memories` は global long-memory store を直接扱うため、multi-user mode ではそのまま使用できない。

---

## 2. v3 の基本モデル

v3 では次を別概念として扱う。

| 概念 | 意味 | 例 |
|---|---|---|
| `principal_id` | 現在の人・サービスの stable identity | `local`, `u:...` |
| `room_id` | 会話・共同作業のコンテナ | `room:abc` |
| `project_id` | 作業対象 project / workspace | `agentcli` |
| `session_id` | 会話 session | opaque ID |
| Memory audience | Memory を読める主体 | personal / room / project / global |

最重要原則:

```text
principal_id != room_id != project_id != session_id
```

`room_id` を owner にしない。

同一人物は複数 room に参加でき、同一 room には複数人物が参加できるからである。

---

## 3. Identity と Authentication を分離する

### 3.1 Identity

Memory が必要とするのは「この turn を実行している principal は誰か」という identity である。

### 3.2 Authentication

Authentication は「その principal を名乗ってよいことをどう検証したか」である。

したがって Memory core は login UI、Google、Microsoft、GitHub、Keycloak 等を直接知らない。

```text
Authentication / Local Trust / API Credential
                  ↓
           IdentityResolver
                  ↓
            IdentityContext
                  ↓
              TurnContext
                  ↓
         MemoryAccessContext
```

### 3.3 v3 の正式対応方針

初期 v3 では次を正式方式とする。

1. `local`
2. `oidc`

次を拡張方式として contract を用意する。

3. `trusted_proxy`
4. `token` / service principal

独自の username/password database は v3 初期実装では採用しない。

---

## 4. IdentityContext

すべての entry point は identity を共通 contract へ正規化する。

概念 API:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class IdentityContext:
    principal_id: str
    authenticated: bool
    authn_kind: str
    issuer: str = ""
    subject: str = ""
    display_name: str = ""
```

### 4.1 必須 invariant

- browser / model / tool payload の `owner` を信用しない。
- `principal_id` は server-side で決める。
- `room_id` を principal identity として使用しない。
- email を principal primary key にしない。
- raw access token / ID token / API key を principal ID にしない。
- identity 解決失敗時に `local` や別 user へ fallback しない。
- raw credential を Memory / Profile / Session metadata に保存しない。

---

## 5. Local IdentityResolver

CLI / Desktop GUI / trusted single-user Web では login を要求しない。

```text
IdentityContext(
    principal_id="local",
    authenticated=True,
    authn_kind="local"
)
```

ここで `local` は machine 全体のユーザーIDではなく、**現在の UAG user-state namespace における local principal** を意味する。

OS username を Memory key に直接使用しない。

理由:

- username 変更
- domain 参加
- privacy
- platform 差
- service account / container 差

既存 `UAGENT_MEMORY_OWNER` は local / legacy override として残せるが、multi-user Web の全 user 共通 owner には使用しない。

---

## 6. OIDC IdentityResolver

multi-user Web の標準方式は OpenID Connect とする。

対応先を UAG 内で固定しない。

例:

- Microsoft Entra ID
- Google
- GitHub が OIDC-compatible provider として利用可能な構成
- Keycloak
- Auth0
- 社内 OIDC Provider

### 6.1 Stable identity

OIDC では email ではなく、検証済み token の次の組を identity source とする。

```text
issuer (iss)
subject (sub)
```

内部 `principal_id` は `iss + sub` から安定かつ opaque に導出する。

概念例:

```python
principal_id = "oidc:" + stable_hash(issuer + "\x00" + subject)
```

`display_name` や `email` は表示用 metadata として利用できるが、ownership key にしない。

### 6.2 OIDC token validation

IdentityResolver が principal を生成する前に少なくとも次を検証する。

- issuer
- signature
- audience / client ID
- expiration
- nonce / authorization-flow integrity where applicable
- provider configuration

未検証 claim から `principal_id` を生成してはいけない。

### 6.3 Browser session

ブラウザは毎回 raw OIDC token を Memory API に渡す方式を基本にしない。

推奨:

```text
Browser
   ↓
OIDC Authorization Code flow + PKCE
   ↓
UAG auth callback
   ↓
server-side session
   ↓
Secure + HttpOnly + SameSite cookie
```

server-side session は IdentityContext またはその参照を保持する。

ブラウザ JavaScript から Personal Memory の `owner_id` を自由指定できないようにする。

### 6.4 WebSocket

WebSocket でも query parameter で owner を渡さない。

不採用:

```text
/ws?room=abc&owner=user-A
```

採用:

```text
HTTP authenticated session / cookie
              +
        room=abc
              ↓
      WebConnectionContext
              ↓
        IdentityContext
              ↓
      TurnContext per input
```

connection A と connection B が同じ room に接続しても identity は別々に保持する。

---

## 7. Trusted Proxy IdentityResolver

社内 SSO や既存 reverse proxy を使う場合、UAG 自身が OIDC client を持たず upstream authentication を信頼する構成を許可する。

例:

```text
Browser
   ↓
Authenticating Reverse Proxy / SSO Gateway
   ↓
UAG
```

ただし arbitrary request header を identity として採用しない。

Trusted Proxy mode の必須条件:

- UAG へ直接到達できない network 構成、または trusted proxy source を検証する。
- proxy が外部入力の identity header を削除してから再付与する。
- UAG は明示設定した header 名のみ読む。
- unresolved identity は fail-closed。

概念 header:

```text
X-UAG-Authenticated-Subject
X-UAG-Authenticated-Issuer
X-UAG-Display-Name
```

header 名は実装時に確定する。

---

## 8. API / A2A IdentityResolver

API key や bearer token そのものを owner にしない。

```text
credential
   ↓ validate
service/account record
   ↓
principal_id
```

service principal も human principal と同じ IdentityContext contract に正規化する。

```text
authn_kind = token / oidc / external
principal_id = stable opaque ID
```

Memory policy は human / service の種別を必要に応じて別途評価できるが、raw credential を Memory boundary として使用しない。

---

## 9. IdentityResolver interface

概念 interface:

```python
class IdentityResolver:
    def resolve(self, request_context) -> IdentityContext:
        raise NotImplementedError
```

初期 implementation:

```text
LocalIdentityResolver
OIDCIdentityResolver
```

extension point:

```text
TrustedProxyIdentityResolver
TokenIdentityResolver
ExternalIdentityResolver
```

Memory / Profile / Session 層は resolver の種類を知らない。

---

## 10. Connection / Room / Turn boundary

identity を `WebRoom` に1個だけ持たせてはいけない。

```text
WebSocket A ─ Identity(user-A) ─┐
                               ├─ room-X
WebSocket B ─ Identity(user-B) ─┘
```

各 user input から immutable `TurnContext` を生成する。

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

`run_agent_worker()`、Memory Projection、tool execution、Profile extraction、Session persistence は同じ TurnContext を参照する。

### 10.1 Global mutable owner を禁止

不採用:

```python
core.memory_owner = current_web_user
```

理由:

- shared room の別 connection と衝突する。
- tool thread / sub-agent に誤 owner が漏れる。
- retry / cancellation 時の ownership が不明確になる。
- 将来並列実行を増やすと race になる。

明示引数を優先し、legacy bridge に必要なら `contextvars.ContextVar` 等の turn-local context を使う。

---

## 11. Memory owner と audience

v3 では **誰が所有・作成したか** と **誰に見せるか** を分離する。

### 11.1 MemoryRecord v3 logical contract

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

`audience_type`:

```text
personal
room
project
global
```

`audience_id`:

```text
personal -> principal_id
room     -> room_id
project  -> project_id
global   -> fixed / empty
```

### 11.2 DB

v3 の基本は **同じ SQLite DB を使い、レコード単位で論理分離する**。

```text
memory.sqlite3
  memories
    personal:user-A
    personal:user-B
    room:room-X
    project:agentcli
```

ユーザーごとに DB file を分割することを基本形にはしない。

理由:

- room shared memory を自然に扱える。
- project shared memory を自然に扱える。
- migration / backup / evaluation が単純になる。

将来 enterprise tenant isolation が必要なら tenant 単位 DB / schema / database を上位 boundary として追加できる。

### 11.3 Store-level filtering

別 user の Memory を一旦検索してから除外する設計にしない。

Personal の概念 SQL:

```sql
WHERE audience_type = 'personal'
  AND audience_id = :principal_id
  AND project_id = :project_id
```

Room の概念 SQL:

```sql
WHERE audience_type = 'room'
  AND audience_id = :room_id
```

access boundary は relevance ranking より前に適用する。

---

## 12. MemoryAccessContext

caller が arbitrary owner / audience を指定しない。

TurnContext と access policy から server-side で構築する。

```python
@dataclass(frozen=True)
class MemoryAccessContext:
    principal_id: str
    room_id: str
    project_id: str
    readable_audiences: tuple[tuple[str, str], ...]
```

例:

```text
principal=user-A
room=room-X
project=agentcli

readable:
- personal:user-A
- room:room-X
- project:agentcli   # policy で許可された場合
```

filtering order:

```text
identity / membership / audience
            ↓
project
            ↓
status / forget
            ↓
text candidate generation
            ↓
ranking / budget
            ↓
projection
```

---

## 13. Shared Room

同じ room を A と B が共有する場合:

```text
user-A turn
  -> Personal(user-A)
  +  Room(room-X)
  +  allowed Project Memory

user-B turn
  -> Personal(user-B)
  +  Room(room-X)
  +  allowed Project Memory
```

A の Personal Memory は B の turn に入らない。

### 13.1 RoomAccessPolicy

```python
can_join(principal_id, room_id)
can_read_room_memory(principal_id, room_id)
can_write_room_memory(principal_id, room_id)
can_delete_room_memory(principal_id, room_id, memory_id)
```

`room_id` を知っていることだけを permission としない。

Personal Memory から room shared memory への自動昇格は禁止する。

---

## 14. Profile v3

Profile も principal boundary を持つ。

```text
Profile(user-A) != Profile(user-B)
```

shared room の user message には actor metadata を保存する。

```text
role=user
actor_id=user-A
content=...
```

Profile extraction は actor の Profile にのみ反映する。

別参加者の発言や assistant proposal を personal preference として自動昇格しない。

multi-user mode では principal-keyed ProfileStore を導入する。

```text
profiles
- principal_id
- environment_json
- preferences_json
- constraints_json
- revision
- updated_at
```

single-user compatibility では既存 profile file を利用可能とする。

---

## 15. Session / Episodic Memory

SessionStore には少なくとも次を持たせる。

```text
principal_id
room_id
project_id
entry_point
```

shared room message には `actor_id` を保存する。

これにより「以前自分が言ったこと」と「room の別参加者が言ったこと」を区別する。

Episodic retrieval でも identity / audience filter を relevance より前に適用する。

---

## 16. Frozen Projection Snapshot v3

snapshot は content fingerprint だけでなく identity boundary と結び付ける。

最低限:

```text
principal identity fingerprint
room fingerprint
project ID
memory generation
readable audience set fingerprint
```

A 用 snapshot を B turn へ再適用しない。

retry / tool loop 中は同一 turn の snapshot を再利用する。

raw principal ID を診断ログへ出す必要はなく opaque hash を使用できる。

---

## 17. Context Projection order

Provider へ渡す概念順序:

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

projection された guidance / evidence は durable user / assistant history として保存しない。

---

## 18. Memory write / update / forget

### Personal

```text
TurnContext.principal_id
      ↓
owner_id
      ↓
audience=personal:<principal_id>
```

browser / model は arbitrary owner を指定できない。

### Room

room shared memory は別 operation または明示 audience operation とする。

```text
add_room_memory(note)
```

書込み前に RoomAccessPolicy を通す。

### Update / Forget

index ではなく stable `memory_id` を主 API とする。

Personal:
- owner principal のみ

Room:
- RoomAccessPolicy に従う

Admin / migration operation は通常 user operation と分離する。

---

## 19. Web API v3

### 19.1 Personal Memory

推奨:

```text
GET    /api/me/memories
POST   /api/me/memories
PUT    /api/me/memories/{memory_id}
DELETE /api/me/memories/{memory_id}
```

`/api/me` の principal は authenticated server session から決める。

不採用:

```text
GET /api/memories?owner=user-A
```

client が任意 owner を指定できるためである。

### 19.2 Room Memory

```text
GET    /api/rooms/{room_id}/memories
POST   /api/rooms/{room_id}/memories
PUT    /api/rooms/{room_id}/memories/{memory_id}
DELETE /api/rooms/{room_id}/memories/{memory_id}
```

全 operation で membership / permission を検証する。

### 19.3 Profile

```text
GET /api/me/profile
PUT /api/me/profile
```

Admin API と本人 API は分離する。

---

## 20. 管理機能

共通 DB を採用するため、管理機能は identity / audience aware にする。

### 20.1 My Memory

本人が扱えるもの:

- Personal Memory list/search
- add/update/forget
- Profile
- export
- projected / applicable diagnostics where safe

### 20.2 Room 管理

room ごとに:

- members
- role / permission
- Room Shared Memory
- read/write/delete policy
- audit

Room role の名称に Memory の `owner_id` と衝突する `owner` を安易に使わない。

例:

```text
admin
editor
member
```

### 20.3 Administrator

- principals
- rooms
- Memory counts / size
- audience distribution
- legacy / unknown-scope records
- migration status
- identity leak diagnostics
- forget / stale projection diagnostics
- backup / vacuum / integrity check

Admin 全体検索は通常 user API と分離し、明示 authorization を要求する。

### 20.4 API principle

本人 API では client が principal ID を選べない。

Room API では client が room ID を選べても、server が membership / permission を検証する。

---

## 21. Proposed configuration

名称は実装時に確定するが責務は分ける。

```env
# Memory rollout
UAGENT_MEMORY_PROJECTION=0
UAGENT_MEMORY_STRICT_SCOPE=0

# Existing compatibility
UAGENT_MEMORY_OWNER=
UAGENT_MEMORY_PROJECT=

# Identity
UAGENT_IDENTITY_MODE=local
# local | oidc | trusted_proxy | token | external

# OIDC example
UAGENT_OIDC_ISSUER=
UAGENT_OIDC_CLIENT_ID=
UAGENT_OIDC_CLIENT_SECRET=
UAGENT_OIDC_REDIRECT_URI=

# Trusted proxy example
UAGENT_TRUSTED_PROXY_IDENTITY_HEADER=
UAGENT_TRUSTED_PROXY_ISSUER_HEADER=
```

secret 名・保存方式は実装時に security review する。

multi-user mode で identity provider が未設定または identity 解決に失敗した場合、Personal Memory Projection は fail-closed とする。

process-wide common owner へ fallback しない。

---

## 22. Security invariants

v3 必須 invariant:

1. user-B request から user-A Personal Memory を取得できない。
2. request payload の `owner=user-A` で境界を越えられない。
3. room-X member でない principal は room-X Memory を取得できない。
4. project mismatch record は候補にならない。
5. forgotten record は stale snapshot / retry / provider continuation から復活しない。
6. Profile は principal 間で混ざらない。
7. shared room の他 user 発言を自分の Personal Profile / Memory として自動学習しない。
8. identity context は tool thread / sub-agent / retry で別 turn と混ざらない。
9. unresolved identity を privileged `local` principal へ自動昇格しない。
10. raw token / API key / password を principal ID として保存しない。
11. email address を stable ownership key にしない。
12. OIDC claim は検証成功後のみ identity source に使う。
13. WebSocket owner を query parameter / user payload から決定しない。
14. trusted proxy header は trusted transport boundary なしで使用しない。
15. Admin API と user-facing API の authorization を分離する。

---

## 23. Evaluation v3

既存 deterministic Memory Evaluation に multi-user fixture を追加する。

### Identity isolation

- A personal が A では recall される。
- 同一 query を B が実行しても A personal は0件。
- spoofed owner input が無効。

### OIDC identity

- same `iss + sub` は session を跨いでも同じ principal。
- same `sub` でも issuer が違えば別 principal。
- email 変更で principal が変わらない。
- invalid signature / issuer / audience / expiry は identity resolution failure。

### Shared room

- A と B が room-X member。
- room-X memory は両者に見える。
- A personal は B に見えない。
- room-Y user には room-X memory が見えない。

### WebSocket

- 同一 room の connection A / B で IdentityContext が混ざらない。
- reconnect 後も server session identity を正しく再解決する。

### Profile

- A preference は A Guidance のみ。
- B preference は B Guidance のみ。

### Frozen snapshot

- A snapshot を B turn へ再利用しない。
- retry 中は同じ A snapshot。

### Trusted proxy

- untrusted direct request の forged identity header を拒否する。
- trusted path の verified header は principal に解決できる。

### Legacy

- local mode では v0.7.12 compatibility を維持。
- owner 不明 record は multi-user strict mode で除外。

追加 metric:

```text
identity_leak_count
audience_violation_count
profile_leak_count
snapshot_identity_mismatch_count
unauthenticated_fallback_count
```

すべて 0 を gate とする。

---

## 24. 実装順序

大きな account system を最初に作らない。

### PR V3-1: IdentityContext / TurnContext

- IdentityContext
- TurnContext
- LocalIdentityResolver
- explicit / ContextVar propagation
- CLI / GUI / Web / A2A adapter
- behavior change なし

完了条件:

> global mutable owner なしで同一 turn の全処理へ identity が届く。

### PR V3-2: Web connection identity boundary

- WebConnectionContext
- connection-local IdentityContext
- `run_agent_worker(..., turn_context=...)`
- same-room A / B separation
- unresolved multi-user identity fail-closed

完了条件:

> 同じ room の2 connection に異なる principal を安全に割り当てられる。

### PR V3-3: OIDC authentication

- Authorization Code + PKCE
- OIDC discovery / token validation
- server-side authenticated session
- Secure / HttpOnly / SameSite cookie
- `iss + sub` -> opaque principal ID
- WebSocket session inheritance

完了条件:

> login session と WebSocket turn が stable principal で結ばれ、client owner parameter が不要になる。

### PR V3-4: Memory audience contract

- audience_type / audience_id
- schema migration
- MemoryAccessContext
- store-level pre-retrieval access filter
- legacy owner mapping

完了条件:

> Personal / room audience isolation を store-level fixture で証明する。

### PR V3-5: Projection / Profile / Session integration

- principal-keyed ProfileStore
- actor metadata
- identity-bound frozen snapshot
- episodic retrieval boundary
- forget propagation

完了条件:

> shared room 内で Personal Guidance / Memory / Profile が cross-user leak しない。

### PR V3-6: Web management API / Room policy

- `/api/me/*`
- `/api/rooms/*`
- stable memory ID API
- RoomAccessPolicy
- Room Shared Memory
- admin authorization boundary

完了条件:

> browser request から arbitrary principal の Personal Memory を操作できない。

### PR V3-7: Trusted Proxy / API identity adapters

- TrustedProxyIdentityResolver
- TokenIdentityResolver contract
- spoof prevention tests

完了条件:

> OIDC 以外の enterprise / API entry point も Memory core を変えず接続できる。

### PR V3-8: Evaluation / rollout

- deterministic multi-user fixtures
- auth / identity leak gates
- migration tests
- docs / env
- shadow -> opt-in multi-user projection

完了条件:

> leak metrics 0、single-user regression なし。

---

## 25. Rollout

推奨順序:

```text
v0.7.12 single-user baseline
        ↓
IdentityContext (no behavior change)
        ↓
Web identity shadow
        ↓
OIDC opt-in
        ↓
Audience-aware retrieval shadow
        ↓
Authenticated multi-user projection opt-in
        ↓
Shared-room Memory opt-in
        ↓
Trusted Proxy / API adapters
        ↓
Default decision
```

Memory Projection の default ON と multi-user authentication rollout は別判断とする。

---

## 26. 採らない設計

### owner = room_id

不採用。同一 user が別 room に移るたび別人になる。

### owner = IP address

不採用。NAT / VPN / mobile / privacy / shared terminal で stable identity ではない。

### owner = email

不採用。変更可能で provider 間 collision / privacy 問題もある。

### owner = browser random ID を authenticated user と同等に扱う

不採用。client instance ID と authorization identity は別。

### client が owner を自由指定

不採用。

### UAGENT_MEMORY_OWNER を multi-user Web 全員に適用

不採用。

### raw OIDC token / API key を owner として保存

不採用。

### shared room 会話を全参加者の Personal Profile に学習

不採用。

###独自 username/password account DB を v3 Memory の前提にする

不採用。まず OIDC / local trust を採用する。

### login system を MemoryStore に直接組み込む

不採用。IdentityResolver / AccessPolicy の外側に置く。

---

## 27. 最終アーキテクチャ

```text
 Local trust     OIDC       Trusted Proxy      API credential
     │            │              │                   │
     └────────────┴───────┬──────┴───────────────────┘
                          │
                   IdentityResolver
                          │
                    IdentityContext
                          │
        ┌─────────────────┼──────────────────┐
        │                 │                  │
      CLI/GUI        Web Connection        A2A/API
        │          user-A / user-B            │
        └─────────────────┼──────────────────┘
                          │
                      TurnContext
             principal + room + project
                          │
                  MemoryAccessContext
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
 personal:<principal>  room:<room>   project:<project>
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
             store-level access filtering
                          │
             relevance / ranking / budget
                          │
              Frozen Projection Snapshot
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
Applicable Principal Guidance      Retrieved Evidence
        │                                   │
        └─────────────────┬─────────────────┘
                          │
                       Provider
```

ローカル単一ユーザーでは login なしで現在の使い勝手を維持する。

multi-user Web では OIDC を標準方式として stable principal を得る。

社内環境では Trusted Proxy / SSO Gateway、API / A2A では service principal adapter を追加できる。

Memory core が認証 provider 固有処理を持たないため、将来の認証方式追加で Memory schema / retrieval / projection を再設計しない。

v3 の中心は「ログイン画面」ではない。

> **identity を信頼できる方法で確定し、principal / room / project / audience を分離し、その境界を Memory / Profile / Session / Projection / 管理 API のすべてで一貫して守ること。**
