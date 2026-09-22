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

v3 の目的は、同一 UAG Web process を複数人が利用し、さらに同じ room を共有する場合でも、Personal Memory / Profile を混線させず、Room Shared Memory は参加者間で共有できるようにすることである。

同時に、Memory のためだけに独自ログイン機構を持たず、Local / OIDC / OAuth / Trusted Proxy / Active Directory / API credential を共通の Identity contract へ正規化する。

本書は設計書であり、v3 機能が現在実装済みであることを意味しない。

特定ユーザーへの共有設計を v0.7.13 / `8bec11d5cc16e1f87212033be775c651507458bb` を基準に追加した。以下の V3-4 以降の共有仕様は未実装である。

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

`UAGENT_MEMORY_OWNER` は明示 owner の override、`UAGENT_MEMORY_PROJECT` は project override である。V2のlocal/single-user実行では、owner未指定時に現在のOSログインIDをlocal ownerとして使用する。

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

同一人物は複数 room に参加でき、同一 room には複数人物が参加できるからである。

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

### 3.1 認証方式は選択可能にする

UAG v3 は認証方式を固定しない。運用環境ごとに identity mode を明示選択できる構成にする。

初期候補:

```text
local
OIDC
oauth
trusted_proxy
windows_ad
token
external
```

設定例:

```env
UAGENT_IDENTITY_MODE=local
```

または:

```env
UAGENT_IDENTITY_MODE=oidc
```

初期実装では原則として **1 process / 1 active identity mode** とする。

複数方式を同時に受け付ける `hybrid` / resolver chain は将来拡張とし、暗黙 fallback は行わない。

### 3.2 fail-closed

multi-user mode で identity 解決に失敗した場合:

- `local` へ fallback しない。
- `UAGENT_MEMORY_OWNER` へ fallback しない。
- anonymous user に既存 Personal Memory を見せない。
- Personal Memory Projection は無効化または request rejection とする。

---

## 4. IdentityContext

すべての entry point は identity を共通 contract へ正規化する。

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
- email / UPN / display name を principal primary key にしない。
- raw access token / ID token / API key / password を principal ID にしない。
- identity 解決失敗時に `local` や別 user へ fallback しない。
- raw credential を Memory / Profile / Session metadata に保存しない。

---

## 5. IdentityResolver interface

```python
class IdentityResolver:
    def resolve(self, request_context) -> IdentityContext:
        raise NotImplementedError
```

resolver の種類を Memory / Profile / Session / Projection は知らない。

実装候補:

```text
LocalIdentityResolver
OIDCIdentityResolver
OAuthIdentityResolver
TrustedProxyIdentityResolver
WindowsADIdentityResolver
TokenIdentityResolver
ExternalIdentityResolver
```

resolver factory は設定された mode から1つを選択する。

概念例:

```python
def create_identity_resolver(mode: str) -> IdentityResolver:
    if mode == "local":
        return LocalIdentityResolver()
    if mode == "oidc":
        return OIDCIdentityResolver()
    if mode == "oauth":
        return OAuthIdentityResolver()
    if mode == "trusted_proxy":
        return TrustedProxyIdentityResolver()
    if mode == "windows_ad":
        return WindowsADIdentityResolver()
    if mode == "token":
        return TokenIdentityResolver()
    if mode == "external":
        return ExternalIdentityResolver()
    raise ValueError("unsupported identity mode")
```

---

## 6. Local IdentityResolver

CLI / Desktop GUI / trusted single-user Web は login 不要とする。

```text
principal_id = "local"
authn_kind   = "local"
authenticated= true
```

`local` は machine 全体のユーザーIDではなく、現在の UAG user-state namespace における local principal を意味する。

V2はlocal ownerの互換ラベルとしてOSログインIDを使用するが、v3ではその文字列をstable `principal_id`として引き継がない。V3移行時にLocalIdentityResolverのprincipalへ正規化する。

既存 `UAGENT_MEMORY_OWNER` は local / legacy override として残せるが、multi-user Web の全 user 共通 owner には使わない。

---

## 7. OIDC IdentityResolver

multi-user Web の標準方式は OpenID Connect とする。

代表的な接続先として Microsoft Entra ID、Google、Keycloak、Auth0、社内 OIDC Provider 等を接続可能な構造にする。

### 7.1 Stable identity

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

`display_name` / `email` / `preferred_username` は表示 metadata にできるが ownership key にしない。

### 7.2 Validation

principal 生成前に少なくとも次を検証する。

- issuer
- signature
- audience / client ID
- expiration
- nonce / flow integrity where applicable
- provider configuration

未検証 claim から principal を作らない。

### 7.3 Browser session

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

### 7.4 WebSocket

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

## 8. Active Directory / Microsoft identity

UAG v3 は Active Directory 系を1つの専用 DB や独自 password login として実装しない。

環境に応じて次のいずれかへ接続する。

### 8.1 Microsoft Entra ID

```text
Microsoft Entra ID
       ↓ OIDC
OIDCIdentityResolver
       ↓
IdentityContext
```

Entra ID は `oidc` mode として扱う。

### 8.2 AD FS / Federation

AD FS または federation gateway が OIDC を提供する構成では `oidc` mode を利用する。

OIDC を直接利用しない federation / SSO 構成では、認証済み reverse proxy / gateway を介して `trusted_proxy` mode に接続できる。

### 8.3 On-premises Active Directory + Windows Integrated Authentication

Windows Integrated Authentication / Kerberos / Negotiate を利用する環境は次の2方式を許可する。

推奨:

```text
Browser
   ↓
IIS / reverse proxy / enterprise gateway
   ↓ Windows Integrated Authentication
Active Directory
   ↓ verified principal
TrustedProxyIdentityResolver
   ↓
IdentityContext
```

直接 integration が必要な環境では `windows_ad` mode を用意する。

```text
Browser / Windows client
   ↓ Negotiate / Kerberos
WindowsADIdentityResolver
   ↓
IdentityContext
```

ただし direct `windows_ad` implementation は platform dependency が強いため、Memory core から分離する。

### 8.4 AD identity key

次の表示値を Memory ownership key に直接使わない。

```text
DOMAIN\username
user@domain.example
email
CN / displayName
```

resolver は認証基盤から得られる stable directory object identity / stable subject を provider namespace と組み合わせ、opaque `principal_id` へ正規化する。

例:

```text
ad/entra stable subject
       ↓
principal_id = "u:" + stable_hash(provider_namespace + subject)
```

### 8.5 AD Group mapping

AD / Entra group は authentication identity と分け、authorization input として利用できる。

例:

```text
UAG-Admins
    -> admin role

UAG-AgentCLI
    -> project:agentcli access

Development-Team
    -> room:development membership
```

Group membership を Personal Memory owner にしない。

Group / role 情報は `RoomAccessPolicy` / `ProjectAccessPolicy` / Admin authorization へ渡す。

---

## 9. OAuth Identity Adapter

OIDC ではない OAuth user-login provider も接続できるよう `OAuthIdentityResolver` を用意する。

OAuth access token そのものを principal ID にせず、provider の user identity endpoint で検証した stable provider user ID と provider namespace から opaque principal を導出する。

GitHub user login 等はこの OAuth adapter 側で扱い、OIDC ID token 前提の処理へ混ぜない。

---

## 10. Trusted Proxy IdentityResolver

社内 SSO / authenticating reverse proxy を使う場合、UAG 自身が login protocol を終端せず upstream authentication を信頼する構成を許可する。

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

Active Directory / Windows Integrated Authentication を proxy 側で終端する場合もこの方式を利用できる。

---

## 11. API / A2A IdentityResolver

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

## 12. Authentication mode selection

### 12.1 Configuration

設計上の候補:

```env
UAGENT_IDENTITY_MODE=local
# local | oidc | oauth | trusted_proxy | windows_ad | token | external
```

必要な mode-specific setting だけを読む。

#### OIDC

```env
UAGENT_IDENTITY_MODE=oidc
UAGENT_OIDC_ISSUER=
UAGENT_OIDC_CLIENT_ID=
UAGENT_OIDC_CLIENT_SECRET=
UAGENT_OIDC_REDIRECT_URI=
# Browser cookie / server-side session controls
UAGENT_OIDC_COOKIE_SECURE=1
UAGENT_OIDC_SESSION_TTL=28800
UAGENT_OIDC_SESSION_MAX=4096
```

#### OAuth

```env
UAGENT_IDENTITY_MODE=oauth
UAGENT_OAUTH_PROVIDER=
UAGENT_OAUTH_CLIENT_ID=
UAGENT_OAUTH_CLIENT_SECRET=
UAGENT_OAUTH_REDIRECT_URI=
```

#### Trusted Proxy

```env
UAGENT_IDENTITY_MODE=trusted_proxy
UAGENT_TRUSTED_PROXY_IDENTITY_HEADER=
UAGENT_TRUSTED_PROXY_ISSUER_HEADER=
```

#### Windows / AD

```env
UAGENT_IDENTITY_MODE=windows_ad
UAGENT_AD_REALM=
UAGENT_AD_PROVIDER_NAMESPACE=
```

具体的 Kerberos / Negotiate / SPN 等の設定は WindowsAD adapter 側へ閉じ込める。

#### Token / API

```env
UAGENT_IDENTITY_MODE=token
```

credential storage / verification mechanism は別 security component とする。

### 12.2 Startup validation

mode ごとに required setting を startup で検証する。

例:

- `oidc` なのに issuer/client ID がない -> 起動失敗または Web auth disabled を明示。
- `trusted_proxy` なのに trusted boundary 定義がない -> multi-user Web では起動拒否を第一候補。
- `windows_ad` なのに platform / adapter dependency が満たせない -> fail-fast。
- unknown mode -> fail-fast。

### 12.3 UI selection

将来管理画面から選択可能にする場合でも、secret 値は通常の UI state と同じ場所に保存しない。

管理 UI は次を表示できる。

```text
Authentication mode: OIDC
Provider: Microsoft Entra ID
Status: configured / healthy
```

変更は administrator 権限を要求し、再認証または server restart が必要な設定は明示する。

### 12.4 hybrid mode

将来、例えば次を同時に許可する需要がある。

```text
employees -> OIDC / Entra ID
service agents -> token
internal legacy -> trusted proxy
```

その場合は `hybrid` mode と resolver chain を追加できる。

ただし selection rule は entry point / trusted transport / explicit route で決め、失敗した resolver から別 resolver へ無条件 fallback しない。

v3 初期実装では single selected mode を優先する。

---

## 13. Connection / Room / Turn boundary

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

### 13.1 Global mutable owner を禁止

不採用:

```python
core.memory_owner = current_web_user
```

明示引数を優先し、legacy bridge に必要なら `contextvars.ContextVar` 等の turn-local context を使用する。

ThreadPool / tool worker / sub-agent へは context を明示伝播する。

---

## 14. Memory owner と audience

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

### 14.1 DB

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

### 14.2 Store-level filtering

権限のない別 user の Memory を一旦検索してから除外しない。

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

access boundary は relevance ranking より前に適用する。上の SQL は本人向け・room 向けの個別条件であり、特定ユーザーへの共有は次の grant 条件を追加して評価する。

### 14.3 特定ユーザーへの共有

A が選んだ記憶を B が参考にできるようにする。所有者と閲覧者を分離し、共有後も `owner_id=A` と `audience=personal:A` を保持する。B 向けのコピーや所有権移転は行わない。

| 範囲 | 閲覧条件 |
|---|---|
| Personal | 本人、または当該レコードへの有効な個別 read grant |
| Room | RoomAccessPolicy が許可する参加者 |
| Project | ProjectAccessPolicy が許可する参加者 |
| Global | 明示的な global policy が許可する主体 |

特定ユーザー共有は新しい単一 audience 値ではなく、同じ SQLite DB の `memory_grants` に保持する。1件の記憶を複数人へ共有でき、`personal:A` 全体への権限付与にはならない。初期対象は所有者が明確な Personal Memory の個別レコードとする。

| 項目 | 意味 |
|---|---|
| grant_id | 共有許可の stable ID |
| memory_id / memory_revision | 共有する記憶と、所有者が確認した版 |
| grantee_principal_id | 閲覧を許可する認証済み principal |
| permission | 初期実装は read のみ |
| granted_by | サーバーで確認した所有者 principal |
| status / revision | active / revoked と権限変更の版 |
| created_at / revoked_at | 付与・取消日時 |

所有者だけが付与・取消を行う。B は参照できるが、変更・削除・再共有・権限付与はできない。管理者の操作は別の明示的な管理権限と監査経路を使う。編集権限を追加する場合も read から推定せず、別権限として設計する。

共有先は stable principal で確定し、表示名やメールの一致だけで決めない。API payload は共有先の指定に使えても、共有する側の所有権の証明には使わない。

検索・ID取得・件数・export は同じアクセス条件を使う。Personal Memory は「本人」または「当該 memory_id / memory_revision に対する active な read grant」を store 内で判定した後、project / status / forget 条件を適用する。grant は project 境界を越える許可にはならない。別 project での参照は初期実装の対象外とする。

記憶を更新した場合、以前の版への grant で新しい内容を自動公開しない。旧版も通常検索へ戻さず、所有者による新しい版の共有を必要とする。移行時は既存記憶へ grant を自動生成しない。

---

## 15. MemoryAccessContext

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

個別 grant はサーバーが store 内で評価する。`readable_audiences` に `personal:A` を追加して A の全記憶へアクセスを広げない。アクセス判定には grant / membership / policy の世代も含める。

filtering order:

```text
identity / membership / audience / per-record grant
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

## 16. Shared Room

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

共有されていない A Personal Memory は B turn に入らない。A が B に共有した個別記憶は、次の配信先制約を満たす B turn の参考情報にできる。

### 16.1 参照権限と配信先

B にだけ許可された記憶を、C もいる共有 room の応答・履歴・tool result に流さない。共有 room の通常応答に利用するには、その room の履歴を読める対象全体への共有許可を必要とする。初期実装では個別 grant による記憶は B 専用の非共有 session でのみ参照し、共有 room で使うには所有者の明示的な Room 共有と RoomAccessPolicy を必要とする。

RoomAccessPolicy:

```python
can_join(principal_id, room_id)
can_read_room_memory(principal_id, room_id)
can_write_room_memory(principal_id, room_id)
can_delete_room_memory(principal_id, room_id, memory_id)
```

`room_id` を知っていることだけを permission としない。

Personal -> Room Shared Memory の自動昇格は禁止する。

AD / Entra group mapping を利用する場合も、group membership は RoomAccessPolicy の入力とする。

---

## 17. Profile v3

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

A から B へ共有された記憶は、A の情報という出典を保持した Retrieved Memory Evidence とする。A の好み・経験・指示を B の Profile / Applicable Guidance として自動学習しない。共有によって Profile 全体の閲覧権限を与えない。

multi-user mode では principal-keyed ProfileStore を導入する。

single-user compatibility では既存 profile file を利用できる。

---

## 18. Session / Episodic Memory

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

## 19. Frozen Projection Snapshot v3

snapshot は少なくとも次へ bind する。

```text
principal identity fingerprint
room fingerprint
project ID
memory generation
readable audience set fingerprint
grant / membership / policy generation
```

A snapshot を B turn へ再利用しない。

retry / tool loop 中は、アクセス権限が変わっていない場合だけ同一 turn snapshot を再利用する。共有取消・forget・対象版の変更は frozen snapshot より優先し、影響する snapshot / cache を無効化する。

各 provider 呼出し前と応答配信前にアクセス世代を再確認する。取消された記憶を含む実行中応答は配信せず、影響する tool continuation も止める。provider continuation に取消済み情報が残る場合、その continuation を破棄して許可済み context で作り直す。

認証 session refresh が発生しても同一 turn の principal identity が変化しないことを保証する。

---

## 20. Context Projection order

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

## 21. Memory write / update / forget

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

### 21.1 個別共有と取消

read grant は参考情報へのアクセス許可であり、B の Personal Memory への自動複製や再共有の許可ではない。共有元の memory_id / revision、所有者、利用した grant を出典として保持し、要約・派生 cache にも依存元を記録する。

取消は grant の無効化とアクセス世代の更新を同じ transaction で確定する。以後の検索・取得・export・projection と派生 cache の再利用を拒否する。元記憶の forget は全 grant からの参照を止める。B への取消で A や別の有効な共有先の権限を失わせない。

既に閲覧・export 済みの内容や provider へ送信済みの内容を、取消で遡って回収できるとは扱わない。保存済みの回答・要約を再び LLM に渡す場合は共有元への依存を検証し、失効した派生情報を除外する。取消後の利用禁止と、配信済み情報の回収限界を区別する。

---

## 22. Web API v3

### 22.1 Personal Memory

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

### 22.2 Room Memory

```text
GET    /api/rooms/{room_id}/memories
POST   /api/rooms/{room_id}/memories
PUT    /api/rooms/{room_id}/memories/{memory_id}
DELETE /api/rooms/{room_id}/memories/{memory_id}
```

全 operation で membership / permission を検証する。

### 22.3 Profile

```text
GET /api/me/profile
PUT /api/me/profile
```

### 22.4 Authentication status

```text
GET /api/auth/status
```

返却例:

```json
{
  "mode": "oidc",
  "authenticated": true,
  "display_name": "User"
}
```

raw subject / token / secret は通常 UI に返さない。

---

### 22.5 特定ユーザー共有 API

所有者向けに `/api/me/memories/{memory_id}/grants` で共有先の一覧・read grant 付与を、同配下の `/{grant_id}` で取消を提供する。受信側の一覧・参照は `/api/me/shared-memories` と `/api/me/shared-memories/{memory_id}` に分離する。

全操作で認証済み principal と対象 memory / grant の関係をサーバーが検証する。通常の `/api/me/memories` の所有者向け更新・削除権限を、共有の read grant で通さない。共有先へ不要な他の受信者一覧や raw identity claim を返さない。

---

## 23. 管理機能

### 23.1 My Memory

- Personal Memory list/search
- 自分の記憶の共有先・対象版・取消、および共有された参考情報の一覧
- add/update/forget
- Profile
- export
- safe diagnostics

### 23.2 Room

- members
- role / permission
- Room Shared Memory
- read/write/delete policy
- audit

Room role は `admin / editor / member` 等とし、Memory の `owner_id` と用語を衝突させない。

### 23.3 Authentication administration

管理画面で少なくとも次を確認できる設計にする。

```text
Identity mode
Provider / issuer
Configuration status
Health / discovery status
Session count
Last authentication error summary
```

secret / token 自体は表示しない。

選択可能な mode:

```text
Local
OpenID Connect
OAuth
Trusted Proxy / SSO
Windows / Active Directory
API Token / Service Principal
External
```

### 23.4 Active Directory administration

AD / Entra integration では次を policy mapping として管理できる余地を持たせる。

```text
Directory group -> UAG admin role
Directory group -> room membership
Directory group -> project access
```

UAG Memory DB に AD password を保存しない。

Directory の全 user / group を Memory DB へ同期することを必須にしない。必要な authorization cache を持つ場合も source-of-truth は外部 directory とする。

### 23.5 Administrator

- principals
- rooms
- Memory counts / size
- audience distribution
- legacy / unknown-scope records
- migration status
- identity leak diagnostics
- forget / stale projection diagnostics
- authentication mode / health
- backup / vacuum / integrity check

Admin 全体検索は通常 user API と分離し、明示 authorization を要求する。

---

## 24. Proposed configuration

```env
# V2 Memory rollout baseline (default-on)
UAGENT_MEMORY_PROJECTION=1
UAGENT_MEMORY_STRICT_SCOPE=1

# V2 local compatibility / explicit overrides
# UAGENT_MEMORY_OWNER unset -> current OS login ID
UAGENT_MEMORY_OWNER=
UAGENT_MEMORY_PROJECT=

# Identity selection
UAGENT_IDENTITY_MODE=local
# local | oidc | oauth | trusted_proxy | windows_ad | token | external

# OIDC
UAGENT_OIDC_ISSUER=
UAGENT_OIDC_CLIENT_ID=
UAGENT_OIDC_CLIENT_SECRET=
UAGENT_OIDC_REDIRECT_URI=

# OAuth
UAGENT_OAUTH_PROVIDER=
UAGENT_OAUTH_CLIENT_ID=
UAGENT_OAUTH_CLIENT_SECRET=
UAGENT_OAUTH_REDIRECT_URI=

# Trusted Proxy / SSO
UAGENT_TRUSTED_PROXY_IDENTITY_HEADER=
UAGENT_TRUSTED_PROXY_ISSUER_HEADER=

# Windows / AD
UAGENT_AD_REALM=
UAGENT_AD_PROVIDER_NAMESPACE=
```

実際の secret は可能なら environment / secret store / deployment platform credential mechanism から供給し、repository や Memory store へ保存しない。

---

## 25. Security invariants

1. user-B request から、B への有効な個別 grant がない user-A Personal Memory を取得できない。
2. request payload の `owner=user-A` で境界を越えられない。
3. room-X member でない principal は room-X Memory を取得できない。
4. project mismatch record は候補にならない。
5. forgotten record は stale snapshot / retry / provider continuation から復活しない。
6. Profile は principal 間で混ざらない。
7. shared room の他 user 発言を自分の Personal Profile / Memory として自動学習しない。
8. identity context は tool thread / sub-agent / retry で別 turn と混ざらない。
9. unresolved identity を privileged `local` principal へ昇格しない。
10. raw token / API key / password を principal ID として保存しない。
11. email / UPN / `DOMAIN\\username` を stable ownership key にしない。
12. OIDC claim は検証成功後のみ identity source に使う。
13. WebSocket owner を query parameter / payload から決定しない。
14. trusted proxy header は trusted transport boundary なしで使用しない。
15. Admin API と user-facing API の authorization を分離する。
16. identity mode 未設定・不正設定を暗黙 `local` として扱わない（multi-user entry point）。
17. AD group membership を Personal Memory owner として扱わない。
18. Windows Integrated Authentication の未検証 username/header を principal として採用しない。
19. resolver failure 時に別 authentication mode へ自動 fallback しない。
20. 認証方式変更後に既存 session を無条件継続しない。
21. 個別 read grant は所有権・編集・削除・再共有権限を与えない。
22. 共有情報を受信者本人の Profile / Guidance に自動変換しない。
23. 共有取消・forget 後に snapshot / cache / 派生情報からアクセスを復活させない。
24. 個別共有を、権限のない参加者が読める room 応答・履歴に流さない。

---

## 26. Evaluation v3

追加 fixture:

### Identity isolation

- A personal は A で recall。
- 同一 query を B が実行しても、未共有の A personal は0件。
- spoofed owner input は無効。

### Authentication mode selection

- `local` は local resolver のみ。
- `oidc` は OIDC resolver のみ。
- `trusted_proxy` で forged direct header を拒否。
- unsupported mode は fail-fast。
- resolver failure から他 mode へ暗黙 fallback しない。

### OIDC

- same `iss + sub` は session を跨いでも同一 principal。
- same `sub` でも issuer 違いは別 principal。
- email / display name 変更で principal は変わらない。
- invalid signature / issuer / audience / expiry は resolution failure。

### Active Directory / Entra

- Entra OIDC user は stable principal に解決される。
- username / UPN 表示変更で ownership key が変わらない契約を検証する。
- group A member の room permission と Personal Memory ownership を混同しない。
- trusted proxy AD identity header は trusted path 以外で拒否。
- Windows AD resolver failure は `local` に fallback しない。

### Shared room

- room-X memory は A/B member に見える。
- 未共有の A personal は B に見えない。
- room-Y user には room-X memory が見えない。

### Direct sharing

- A の記憶 M1 だけを B へ共有すると、B は M1 を参照でき、A の未共有 M2 と C からの M1 取得は0件。
- ID 直接取得・検索・件数・export で同じ判定を行う。
- B は read grant で更新・削除・再共有できず、偽造した owner / grant payload でも越権できない。
- B 向け取消後、A と別の有効な共有先は参照できるが、B の cache / retry / 派生要約からは復活しない。
- 更新後の版は再共有まで B に見えず、forget 後は全共有先から見えない。
- 共有した A の好みを B の Profile / Guidance として扱わない。
- B 専用 session では参照できるが、個別 grant だけでは B/C 共有 room に入らない。
- grant があっても project mismatch は候補にならない。
- migration は自動で共有許可を作らない。

### WebSocket

- same room connection A/B で identity が混ざらない。
- reconnect 後も authenticated session identity を再解決できる。

### Profile

- A preference は A Guidance のみ。
- B preference は B Guidance のみ。

### Frozen snapshot

- A snapshot を B turn へ再利用しない。
- 権限が不変の retry 中は同じ A snapshot。
- retry / provider 呼出し / 応答配信と取消が競合しても、失効後の利用・配信を拒否する。

### Legacy

- local modeではV2のdefault-on strict projectionとOS-login owner fallbackを維持する。
- multi-user modeではV2のOS-login ownerをauthenticated principalへ移行し、owner不明recordをfail-closedで扱う。

追加 metric:

```text
identity_leak_count
audience_violation_count
profile_leak_count
snapshot_identity_mismatch_count
unauthenticated_fallback_count
auth_mode_fallback_count
directory_role_violation_count
unauthorized_shared_memory_use_count
shared_memory_profile_attribution_error_count
revoked_grant_reuse_count
```

すべて 0 を gate とする。

---

## 27. 実装順序

### PR V3-1: IdentityContext / TurnContext

- IdentityContext
- TurnContext
- IdentityResolver interface
- resolver factory / identity mode selection
- LocalIdentityResolver
- explicit / ContextVar propagation
- CLI / GUI / Web / A2A adapter
- behavior change なし

完了条件: global mutable owner なしで同一 turn の全処理へ identity が届き、mode selection が deterministic である。

### PR V3-2: Web connection identity boundary

- WebConnectionContext
- connection-local IdentityContext
- `run_agent_worker(..., turn_context=...)`
- same-room A / B separation
- unresolved multi-user identity fail-closed

完了条件: 同じ room の2 connection に異なる principal を割り当てられる。

V3-2 の接続境界実装では、WebSocket handshake 時に選択中の resolver で identity を確定し、接続ごとに保持する。user input と LLM 実行 command は接続から生成した immutable TurnContext を worker に渡す。未解決・未認証接続は room に参加させず、非 local mode の直接 worker 起動も拒否する。現段階では local resolver のみが利用可能で、異なる実ユーザーの認証は V3-3 以降で実装する。共有 room の UI 履歴と既存 Memory store のアクセス制御は V3-4 以降の対象である。

### PR V3-3: OIDC authentication

- Authorization Code + PKCE
- discovery / token validation
- server-side authenticated session
- Secure / HttpOnly / SameSite cookie
- `iss + sub` -> opaque principal
- WebSocket session inheritance

完了条件: login session と WebSocket turn が stable principal で結ばれる。

実装状況: browser binding、Authorization Code + PKCE callback、ID token検証、server-side opaque session、cookie経由のWebSocket identity resolverまで実装済み。永続session store、管理API、複数認証方式のhybrid化は未実装。

V3-3 は認証境界ごとに分割する。最初に browser binding に紐付く一回限りの state / nonce / PKCE S256 transaction と期限・容量制限を実装する。次に検証済み discovery / JWKS / ID token（issuer、signature、audience、expiry、nonce）と Authorization Code callback を接続し、最後に server-side session / WebSocket cookie inheritance を確認する。transaction 単体ではログイン機能を有効にせず、`oidc` mode は検証経路が完成するまで fail-closed のままにする。

署名検証段階では HTTPS discovery の issuer 一致と signing key の JWKS を検証し、RS256 ID token の issuer / audience / expiry / nonce / authorized party を確認した後だけ `iss + sub` から principal を導出する。

現在は、browser binding cookie、Authorization Code + PKCE callback、ID token検証、opaqueなserver-side session、`Secure` / `HttpOnly` / `SameSite=Lax` cookie、WebSocketからのsession継承までを接続する。session token自体は保存せず、ハッシュ化したキーと検証済みIdentityContextだけをprocess-localなbounded storeで保持する。process再起動でsessionが失効することは意図した初期実装の制約であり、永続session storeは後続フェーズで追加する。

未実装のidentity modeはlocalへfallbackせずfail-closedとする。OIDC loginは `UAGENT_IDENTITY_MODE=oidc` と issuer / client ID / redirect URI の設定が揃った場合だけ有効になる。

### PR V3-4: Memory audience contract

- audience_type / audience_id とレコード・版単位の memory_grants
- read / edit / reshare の分離（初期 grant は read のみ）
- schema migration
- MemoryAccessContext
- store-level pre-retrieval filter
- legacy owner mapping

完了条件: 未共有 Personal / room の分離、許可した個別共有の成功、取消・版変更・forget 後の拒否を store-level fixture で証明。

### PR V3-5: Projection / Profile / Session integration

- principal-keyed ProfileStore
- actor metadata
- identity / grant generation-bound frozen snapshot
- 共有元の出典保持、本人 Profile への誤学習防止、派生情報の権限継承
- 個別共有の非共有 session 限定と応答配信先の検証
- episodic retrieval boundary
- forget propagation

完了条件: Personal Guidance / Memory / Profile が cross-user leak しない。

### PR V3-6: Web management API / Room policy

- `/api/me/*`
- `/api/rooms/*`
- stable memory ID API
- RoomAccessPolicy
- Room Shared Memory
- 個別 read grant の付与・取消・共有された参考情報の API
- admin authorization boundary

完了条件: browser から arbitrary principal の Personal Memory を操作できず、明示共有された記憶だけを受信者が閲覧できる。

### PR V3-7: Enterprise authentication adapters

- OAuthIdentityResolver
- TrustedProxyIdentityResolver
- WindowsADIdentityResolver
- TokenIdentityResolver
- AD / Entra group-to-policy adapter contract
- spoof prevention tests

完了条件: OIDC 以外の認証方式も Memory core を変えず接続できる。

### PR V3-8: Authentication management

- authentication mode status API
- admin configuration validation
- provider health diagnostics
- session invalidation on security-sensitive mode changes
- secret handling boundary documentation

完了条件: 選択中の認証方式と健全性を安全に管理できる。

### PR V3-9: Evaluation / rollout

- deterministic multi-user fixtures
- auth / identity leak gates
- AD / Entra / trusted proxy contract fixtures
- migration tests
- docs / env
- shadow -> opt-in multi-user projection

完了条件: leak metrics 0、single-user regression なし。

---

## 28. Rollout

```text
V2 single-user default-on strict projection
        ↓
IdentityContext + selectable resolver
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
Enterprise adapters (AD / Trusted Proxy / OAuth / Token)
        ↓
Authentication management UI/API
        ↓
Multi-user default decision
```

V2 Memory Projectionはすでにdefault ONである。v3で判断するのは、authenticated multi-user projection / shared-room Memoryをどの段階でdefault化するかであり、V2のlocal defaultを再びOFFへ戻すことではない。

認証方式ごとに同じ Memory isolation gate を通す。

---

## 29. 採らない設計

- `owner = room_id`
- `owner = IP address`
- `owner = email / UPN / DOMAIN\\username` をv3のstable authenticated principalとして使う
- browser random ID を authenticated user と同等に扱う
- client が owner を自由指定
- `UAGENT_MEMORY_OWNER` を multi-user Web 全員に適用
- raw OIDC token / OAuth access token / API key を owner として保存
- AD password を UAG Memory DB に保存
- AD group を Personal Memory owner として扱う
- forged `X-User` 等の header を直接信用
- authentication failure 時に別 resolver へ暗黙 fallback
- read grant から edit / reshare を推定
- 個別共有した参考情報を受信者の Personal Memory / Profile へ自動複製
- shared room 会話を全参加者の Personal Profile に学習
- 独自 username/password account DB を v3 Memory の前提にする
- login system を MemoryStore に直接組み込む

---

## 30. 最終アーキテクチャ

```text
 Local trust      OIDC/Entra      OAuth      Trusted Proxy/AD      Windows AD      API credential
     │                │             │               │                   │                 │
     └────────────────┴─────────────┴───────────────┴─────────┬─────────┴─────────────────┘
                                                              │
                                                       Selected IdentityResolver
                                                              │
                                                        IdentityContext
                                                              │
                              ┌───────────────────────────────┼───────────────────────────┐
                              │                               │                           │
                            CLI/GUI                      Web Connection                 A2A/API
                              │                        user-A / user-B                    │
                              └───────────────────────────────┼───────────────────────────┘
                                                              │
                                                          TurnContext
                                                 principal + room + project
                                                              │
                                                      MemoryAccessContext
                                                              │
                              ┌───────────────────────────────┼───────────────────────────┐
                              │                               │                           │
                     personal:<principal>                 room:<room>             project:<project>
                              │                               │                           │
                              └───────────────────────────────┼───────────────────────────┘
                                                              │
                                                 store-level access filtering
                                                              │
                                                 relevance / ranking / budget
                                                              │
                                                  Frozen Projection Snapshot
                                                              │
                              ┌───────────────────────────────┴───────────────────────────┐
                              │                                                           │
                   Applicable Principal Guidance                              Retrieved Evidence
                              │                                                           │
                              └───────────────────────────────┬───────────────────────────┘
                                                              │
                                                           Provider
```

ローカル単一ユーザーは login なしで現在の使い勝手を維持する。

multi-user Web は運用環境に応じて認証方式を明示選択する。

推奨対応関係:

| 環境 | identity mode |
|---|---|
| CLI / Desktop / single-user Web | `local` |
| Microsoft Entra ID | `oidc` |
| Google / Keycloak / Auth0 / OIDC IdP | `oidc` |
| GitHub user login 等 | `oauth` |
| 社内 SSO gateway | `trusted_proxy` |
| On-prem AD + IIS/Proxy Windows認証 | `trusted_proxy` |
| On-prem AD direct Kerberos/Negotiate | `windows_ad` |
| A2A / service account | `token` / `external` |

Memory core はどの認証 provider を使ったかに依存しない。

v3 の中心はログイン画面ではなく、**選択された認証方式から principal identity を信頼できる形で確定し、principal / room / project / audience を分離し、その境界を Memory / Profile / Session / Projection / 管理 API のすべてで一貫して守ること**である。
