# UAG Memory Architecture v3 — Identity / Authentication / Shared Room 設計

## 0. 位置づけ

対象は `awaku7/agentcli` v0.7.12、基準 commit `4074cce99d2fe3a32b169b4095720821b0e1ad1e`。

v2 で定義した「正本と projection の分離」「owner / project / scope を検索前の境界にする」「turn-local frozen snapshot」「forget propagation」「評価してから既定化する」を継承する。

v0.7.12 では stable ID / revision、SQLite・JSONL migration、owner / project metadata、turn-local projection、Applicable User Guidance と Memory Evidence の分離、38 locale の contextual query、frozen snapshot、deterministic evaluation gate まで実装された。

v3 の目的は、同一 UAG Web process を複数人が利用し、さらに同じ room を共有する場合でも、Personal Memory / Profile を混線させず、Room Shared Memory は参加者間で共有できるようにすることである。

同時に、Memory のためだけに独自ログイン機構を持たず、Local / OIDC / Trusted Proxy / API credential を共通の Identity contract へ正規化する。

本書は設計書であり、v3 機能が現在実装済みであることを意味しない。

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

Web は `room_id` ごとに `WebRoom` を持ち、UI messages、LLM history、workdir、status、human_ask state、worker lock を room 単位で分離している。

同じ `WebRoom` へ複数 WebSocket connection を接続できるが、`room_id` は会話の部屋であり stable user identity ではない。

### 1.3 現在の問題

```text
room-X
├─ connection A ─┐
└─ connection B ─┴─> process-wide memory owner
```

この状態で Personal Memory Projection を multi-user Web へ有効化すると、A と B の Personal Memory を安全に分離できない。

Profile も同様に principal boundary を持たない。

既存 `/api/memories` も global long-memory store を直接扱うため、multi-user mode ではそのまま使用しない。

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

---

## 3. Identity と Authentication を分離する

Identity は「この turn を実行している principal は誰か」。Authentication は「その principal を名乗ってよいことをどう検証したか」である。

Memory core は login provider 固有処理を知らない。

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

### 3.1 正式対応方針

初期 v3 の正式方式:

1. `local`
2. `oidc`

拡張 contract:

3. `trusted_proxy`
4. `oauth`
5. `token` / service principal
6. `external`

独自 username/password database は v3 初期実装では採用しない。

---

## 4. IdentityContext

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

必須 invariant:

- browser / model / tool payload の `owner` を信用しない。
- `principal_id` は server-side で決める。
- `room_id` を principal identity に使わない。
- email を principal primary key にしない。
- raw access token / ID token / API key を principal ID にしない。
- identity 解決失敗時に `local` や別 user へ fallback しない。
- raw credential を Memory / Profile / Session metadata に保存しない。

---

## 5. Local IdentityResolver

CLI / Desktop GUI / trusted single-user Web は login 不要とする。

```text
principal_id = "local"
authn_kind   = "local"
authenticated= true
```

`local` は machine 全体のユーザーIDではなく、現在の UAG user-state namespace における local principal を意味する。

OS username を Memory key に直接使用しない。

既存 `UAGENT_MEMORY_OWNER` は local / legacy override として残せるが、multi-user Web の全 user 共通 owner には使わない。

---

## 6. OIDC IdentityResolver

multi-user Web の標準方式は OpenID Connect とする。

代表的な OIDC provider として Microsoft Entra ID、Google、Keycloak、Auth0、社内 OIDC Provider 等を接続可能な構造にする。

### 6.1 Stable identity

OIDC は email ではなく、検証済み token の `iss + sub` を identity source とする。

```text
issuer (iss)
subject (sub)
      ↓
opaque principal_id
```

概念例:

```python
principal_id = "oidc:" + stable_hash(issuer + "\x00" + subject)
```

`display_name` / `email` は表示 metadata にできるが ownership key にしない。

### 6.2 Validation

principal 生成前に少なくとも次を検証する。

- issuer
- signature
- audience / client ID
- expiration
- nonce / flow integrity where applicable
- provider configuration

未検証 claim から principal を作らない。

### 6.3 Browser session

推奨:

```text
Browser
   ↓
OIDC Authorization Code flow + PKCE
   ↓
UAG callback
   ↓
server-side session
   ↓
Secure + HttpOnly + SameSite cookie
```

browser JavaScript に Personal Memory owner を決めさせない。

### 6.4 WebSocket

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

同じ room に connection A / B がいても identity は connection 単位で保持する。

---

## 7. OAuth Identity Adapter

OIDC ではない OAuth user-login provider も将来接続できるよう `OAuthIdentityResolver` を拡張 point として用意する。

OAuth access token そのものを principal ID にせず、provider の user identity endpoint で検証した stable provider user ID と issuer/provider namespace から opaque principal を導出する。

例として GitHub user login を対応する場合はこの OAuth adapter 側で扱い、OIDC ID token 前提の処理へ混ぜない。

---

## 8. Trusted Proxy IdentityResolver

社内 SSO / authenticating reverse proxy を使う場合、UAG 自身が OIDC client を持たず upstream authentication を信頼する構成を許可する。

```text
Browser
   ↓
Authenticating Reverse Proxy / SSO Gateway
   ↓
UAG
```

ただし arbitrary request header を identity として採用しない。

必須条件:

- UAG への直接 bypass を防ぐ。
- proxy が外部入力の identity header を削除して再付与する。
- UAG は明示設定した header のみ読む。
- trusted source / transport boundary を検証する。
- unresolved identity は fail-closed。

---

## 9. API / A2A IdentityResolver

API key / bearer token そのものを owner にしない。

```text
credential
   ↓ validate
service/account record
   ↓
principal_id
```

service principal も同じ IdentityContext contract に正規化する。

---

## 10. IdentityResolver interface

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

extension:

```text
OAuthIdentityResolver
TrustedProxyIdentityResolver
TokenIdentityResolver
ExternalIdentityResolver
```

Memory / Profile / Session は resolver の種類を知らない。

---

## 11. Connection / Room / Turn boundary

identity を `WebRoom` に1個だけ持たせない。

```text
WebSocket A ─ Identity(user-A) ─┐
                               ├─ room-X
WebSocket B ─ Identity(user-B) ─┘
```

各 user input から immutable TurnContext を生成する。

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

### 11.1 Global mutable owner を禁止

不採用:

```python
core.memory_owner = current_web_user
```

明示引数を優先し、legacy bridge に必要なら `contextvars.ContextVar` 等の turn-local context を使用する。

---

## 12. Memory owner と audience

v3 では「誰が所有・作成したか」と「誰に見せるか」を分離する。

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

### 12.1 DB

基本は同じ SQLite DB を使い、レコード単位で論理分離する。

```text
memory.sqlite3
  memories
    personal:user-A
    personal:user-B
    room:room-X
    project:agentcli
```

将来 enterprise tenant isolation が必要なら tenant 単位 DB / schema を上位 boundary として追加できる。

### 12.2 Store-level filtering

別 user の Memory を一旦検索してから除外しない。

Personal 概念 SQL:

```sql
WHERE audience_type = 'personal'
  AND audience_id = :principal_id
  AND project_id = :project_id
```

Room 概念 SQL:

```sql
WHERE audience_type = 'room'
  AND audience_id = :room_id
```

access boundary は relevance ranking より前に適用する。

---

## 13. MemoryAccessContext

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
- project:agentcli   # policy 許可時
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

## 14. Shared Room

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

A Personal Memory は B turn に入らない。

RoomAccessPolicy:

```python
can_join(principal_id, room_id)
can_read_room_memory(principal_id, room_id)
can_write_room_memory(principal_id, room_id)
can_delete_room_memory(principal_id, room_id, memory_id)
```

`room_id` を知っていることだけを permission としない。

Personal -> Room Shared Memory の自動昇格は禁止する。

---

## 15. Profile v3

```text
Profile(user-A) != Profile(user-B)
```

shared room user message には actor metadata を保存する。

```text
role=user
actor_id=user-A
content=...
```

Profile extraction は actor の Profile にのみ反映する。

multi-user mode では principal-keyed ProfileStore を導入する。

---

## 16. Session / Episodic Memory

SessionStore は少なくとも次を保持する。

```text
principal_id
room_id
project_id
entry_point
```

shared room message は `actor_id` を保持する。

Episodic retrieval でも identity / audience filter を relevance より前に適用する。

---

## 17. Frozen Projection Snapshot v3

snapshot は少なくとも次へ bind する。

```text
principal identity fingerprint
room fingerprint
project ID
memory generation
readable audience set fingerprint
```

A snapshot を B turn へ再利用しない。

retry / tool loop 中は同一 turn snapshot を再利用する。

---

## 18. Context Projection order

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

projection content は durable user / assistant history として保存しない。

---

## 19. Memory write / update / forget

Personal:

```text
TurnContext.principal_id
      ↓
owner_id
      ↓
audience=personal:<principal_id>
```

browser / model は arbitrary owner を指定できない。

Room Shared Memory は別 operation または明示 audience operation とし、RoomAccessPolicy を通す。

update / forget は stable `memory_id` を主 API とする。

Admin / migration operation は通常 user operation と分離する。

---

## 20. Web API v3

### Personal Memory

```text
GET    /api/me/memories
POST   /api/me/memories
PUT    /api/me/memories/{memory_id}
DELETE /api/me/memories/{memory_id}
```

`/api/me` principal は authenticated server session から決める。

不採用:

```text
GET /api/memories?owner=user-A
```

### Room Memory

```text
GET    /api/rooms/{room_id}/memories
POST   /api/rooms/{room_id}/memories
PUT    /api/rooms/{room_id}/memories/{memory_id}
DELETE /api/rooms/{room_id}/memories/{memory_id}
```

全 operation で membership / permission を検証する。

### Profile

```text
GET /api/me/profile
PUT /api/me/profile
```

---

## 21. 管理機能

### My Memory

- Personal Memory list/search
- add/update/forget
- Profile
- export
- safe diagnostics

### Room

- members
- role / permission
- Room Shared Memory
- read/write/delete policy
- audit

Room role は `admin / editor / member` 等とし、Memory の `owner_id` と用語を衝突させない。

### Administrator

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

---

## 22. Proposed configuration

```env
# Memory rollout
UAGENT_MEMORY_PROJECTION=0
UAGENT_MEMORY_STRICT_SCOPE=0

# Existing compatibility
UAGENT_MEMORY_OWNER=
UAGENT_MEMORY_PROJECT=

# Identity
UAGENT_IDENTITY_MODE=local
# local | oidc | oauth | trusted_proxy | token | external

# OIDC
UAGENT_OIDC_ISSUER=
UAGENT_OIDC_CLIENT_ID=
UAGENT_OIDC_CLIENT_SECRET=
UAGENT_OIDC_REDIRECT_URI=

# Trusted proxy
UAGENT_TRUSTED_PROXY_IDENTITY_HEADER=
UAGENT_TRUSTED_PROXY_ISSUER_HEADER=
```

multi-user mode で identity 解決に失敗した場合、Personal Memory Projection は fail-closed とする。

process-wide common owner へ fallback しない。

---

## 23. Security invariants

1. user-B request から user-A Personal Memory を取得できない。
2. request payload の `owner=user-A` で境界を越えられない。
3. room-X member でない principal は room-X Memory を取得できない。
4. project mismatch record は候補にならない。
5. forgotten record は stale snapshot / retry / provider continuation から復活しない。
6. Profile は principal 間で混ざらない。
7. shared room の他 user 発言を自分の Personal Profile / Memory として自動学習しない。
8. identity context は tool thread / sub-agent / retry で別 turn と混ざらない。
9. unresolved identity を privileged `local` principal へ昇格しない。
10. raw token / API key / password を principal ID として保存しない。
11. email を stable ownership key にしない。
12. OIDC claim は検証成功後のみ identity source に使う。
13. WebSocket owner を query parameter / payload から決定しない。
14. trusted proxy header は trusted transport boundary なしで使用しない。
15. Admin API と user-facing API の authorization を分離する。

---

## 24. Evaluation v3

追加 fixture:

### Identity isolation

- A personal は A で recall。
- 同一 query を B が実行しても A personal は0件。
- spoofed owner input は無効。

### OIDC

- same `iss + sub` は session を跨いでも同一 principal。
- same `sub` でも issuer 違いは別 principal。
- email 変更で principal は変わらない。
- invalid signature / issuer / audience / expiry は resolution failure。

### Shared room

- room-X memory は A/B member に見える。
- A personal は B に見えない。
- room-Y user には room-X memory が見えない。

### WebSocket

- same room connection A/B で identity が混ざらない。
- reconnect 後も server session identity を再解決できる。

### Profile

- A preference は A Guidance のみ。
- B preference は B Guidance のみ。

### Frozen snapshot

- A snapshot を B turn へ再利用しない。
- retry 中は同じ A snapshot。

### Trusted proxy

- untrusted direct request の forged identity header を拒否。
- trusted path の verified header は principal に解決。

### Legacy

- local mode で v0.7.12 compatibility を維持。
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

## 25. 実装順序

### PR V3-1: IdentityContext / TurnContext

- IdentityContext
- TurnContext
- LocalIdentityResolver
- explicit / ContextVar propagation
- CLI / GUI / Web / A2A adapter
- behavior change なし

完了条件: global mutable owner なしで同一 turn の全処理へ identity が届く。

### PR V3-2: Web connection identity boundary

- WebConnectionContext
- connection-local IdentityContext
- `run_agent_worker(..., turn_context=...)`
- same-room A / B separation
- unresolved multi-user identity fail-closed

完了条件: 同じ room の2 connection に異なる principal を割り当てられる。

### PR V3-3: OIDC authentication

- Authorization Code + PKCE
- discovery / token validation
- server-side authenticated session
- Secure / HttpOnly / SameSite cookie
- `iss + sub` -> opaque principal
- WebSocket session inheritance

完了条件: login session と WebSocket turn が stable principal で結ばれる。

### PR V3-4: Memory audience contract

- audience_type / audience_id
- schema migration
- MemoryAccessContext
- store-level pre-retrieval filter
- legacy owner mapping

完了条件: Personal / room isolation を store-level fixture で証明。

### PR V3-5: Projection / Profile / Session integration

- principal-keyed ProfileStore
- actor metadata
- identity-bound frozen snapshot
- episodic retrieval boundary
- forget propagation

完了条件: Personal Guidance / Memory / Profile が cross-user leak しない。

### PR V3-6: Web management API / Room policy

- `/api/me/*`
- `/api/rooms/*`
- stable memory ID API
- RoomAccessPolicy
- Room Shared Memory
- admin authorization boundary

完了条件: browser から arbitrary principal の Personal Memory を操作できない。

### PR V3-7: OAuth / Trusted Proxy / API adapters

- OAuthIdentityResolver
- TrustedProxyIdentityResolver
- TokenIdentityResolver
- spoof prevention tests

完了条件: OIDC 以外も Memory core を変えず接続できる。

### PR V3-8: Evaluation / rollout

- deterministic multi-user fixtures
- auth / identity leak gates
- migration tests
- docs / env
- shadow -> opt-in multi-user projection

完了条件: leak metrics 0、single-user regression なし。

---

## 26. Rollout

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
OAuth / Trusted Proxy / API adapters
        ↓
Default decision
```

Memory Projection の default ON と multi-user authentication rollout は別判断とする。

---

## 27. 採らない設計

- `owner = room_id`
- `owner = IP address`
- `owner = email`
- browser random ID を authenticated user と同等に扱う
- client が owner を自由指定
- `UAGENT_MEMORY_OWNER` を multi-user Web 全員に適用
- raw OIDC token / OAuth access token / API key を owner として保存
- shared room 会話を全参加者の Personal Profile に学習
- 独自 username/password account DB を v3 Memory の前提にする
- login system を MemoryStore に直接組み込む

---

## 28. 最終アーキテクチャ

```text
 Local trust      OIDC       OAuth      Trusted Proxy      API credential
     │              │          │              │                   │
     └──────────────┴──────────┴───────┬──────┴───────────────────┘
                                       │
                                IdentityResolver
                                       │
                                 IdentityContext
                                       │
                ┌──────────────────────┼─────────────────────┐
                │                      │                     │
              CLI/GUI             Web Connection           A2A/API
                │              user-A / user-B               │
                └──────────────────────┼─────────────────────┘
                                       │
                                   TurnContext
                          principal + room + project
                                       │
                               MemoryAccessContext
                                       │
                ┌──────────────────────┼─────────────────────┐
                │                      │                     │
       personal:<principal>        room:<room>       project:<project>
                │                      │                     │
                └──────────────────────┼─────────────────────┘
                                       │
                          store-level access filtering
                                       │
                          relevance / ranking / budget
                                       │
                           Frozen Projection Snapshot
                                       │
                ┌──────────────────────┴─────────────────────┐
                │                                            │
     Applicable Principal Guidance                 Retrieved Evidence
                │                                            │
                └──────────────────────┬─────────────────────┘
                                       │
                                    Provider
```

ローカル単一ユーザーは login なしで現在の使い勝手を維持する。

multi-user Web は OIDC を標準方式とする。OIDC ではない user-login provider は OAuth adapter、社内 SSO は Trusted Proxy、API / A2A は service-principal adapter で接続する。

Memory core は認証 provider 固有処理を持たない。

v3 の中心はログイン画面ではなく、**identity を信頼できる方法で確定し、principal / room / project / audience を分離し、その境界を Memory / Profile / Session / Projection / 管理 API のすべてで一貫して守ること**である。
