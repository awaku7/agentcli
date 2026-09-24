# MemoryとProfile

暗号化された `.uag` に含まれるMemory参照は未解決のIDのみです。Memory本体・派生projection・
権限・identity・ProjectContext tokenは移行しません。移行先の認証・認可に基づいて再開します。
詳細は [Session Portability v1](SESSION_PORTABILITY.md) を参照してください。

Status: **uag v0.7.14の現行runtime reference**

この文書では、現在のuagでユーザーとintegratorが期待できるMemory / Profileの動作を説明します。V2の設計経緯は `UAG_MEMORY_ARCHITECTURE_V2.md`、認証付きmulti-userの設計とsecurity invariantは `UAG_MEMORY_ARCHITECTURE_V3.md` を参照してください。

認証付きWebの設定・利用方法は [Web認証とMemory](WEB_IDENTITY_MEMORY.ja.md)、v0.7.14の実装レビューと残課題は [UAG v0.7.14 implementation review](UAG_0_7_14_IMPLEMENTATION_REVIEW.md) を参照してください。

______________________________________________________________________

## 1. 2つのruntime boundary

uagには、関連する2つのMemory利用形態があります。

| Mode | Identity boundary | 主なAPI / workflow | 主な用途 |
|---|---|---|---|
| **Local compatibility** | trusted local principal / V2 owner scope | CLI tools、local Profile、legacy `/api/memories`、`/api/profile` | CLI、GUI、trusted single-user Web |
| **Authenticated Web V3** | server-resolved `principal_id` + Project / Room policy | `/api/me/*`、`/api/rooms/*`、Project / Room membership API | multi-user Web |

local pathは既存環境との互換性を維持します。authenticated Web pathではbrowser指定ownerを信用せず、Room IDやProject IDをidentityとして扱いません。

______________________________________________________________________

## 2. Storageの既定値

### Session Store

session historyは既定でSQLiteに保存されます。

```text
UAGENT_SESSION_STORE=1
UAGENT_SESSION_BACKEND=sqlite
# 未設定時: user state directory/sessions/sessions.sqlite3
UAGENT_SESSION_STORE_PATH=
```

user / assistant / tool message、tool-call metadata、summaryを構造化保存します。credential、token、cookie、一般的なAPI key形式は永続化前にredactされます。

### Memory Store

Long-term Memoryも既定でSQLiteです。

```text
UAGENT_MEMORY_BACKEND=sqlite
# 未設定時: user state directory/memory.sqlite3
UAGENT_MEMORY_DB=
```

JSONLはlocal compatibility backendとして残りますが、authenticated multi-user V3のaudience / grantはSQLiteを必要とします。JSONLをmulti-user authorizationのfallbackとして使用しないでください。

______________________________________________________________________

## 3. Local Long-term MemoryとShared Memory

### Local Long-term Memory

local Long-term Memoryは、preference、constraint、継続的なenvironment情報などのstableなnoteを保存します。代表的なtoolは `add_long_memory`、`get_long_memory` です。

local V2 scopeの既定値:

```env
UAGENT_MEMORY_PROJECTION=1
UAGENT_MEMORY_STRICT_SCOPE=1
UAGENT_MEMORY_OWNER=
UAGENT_MEMORY_PROJECT=
```

local modeで `UAGENT_MEMORY_OWNER` を設定しない場合、V2 compatibility pathは現在のOS loginからlocal ownerを解決します。Strict ScopeではProject境界を確認できないrecordを除外します。

### Shared Memory compatibility store

既存Shared Memory storeは、trusted local deploymentでcross-session / agent contextを共有する互換機構です。V3のRoom Memoryや特定user向けread grantと同じauthorization modelではありません。

multi-user Webでは、compatibility Shared Memoryをaccess-control機構として使わず、scoped Personal / Room APIを利用します。

______________________________________________________________________

## 4. turn-local retrievalとprojection

Memory retrievalは既定でdeterministicかつtokenizer-freeです。概ね次の順で強いmatchを優先します。

1. normalized exact / phrase match
1. reliableなword boundaryがある場合のword-like token match
1. 空白がword boundaryとして十分でないscript向けのcharacter n-gram fallback
1. 弱いboilerplate matchを抑制するcandidate-relative ranking

英語に加え、日本語・中国語・タイ語などscript-aware fallbackを利用する言語のregression coverageがあります。

関連するProfile guidanceとMemory evidenceは、1 user turnのprovider-facing contextへprojectionされます。projectionした内容はdurableなuser / assistant historyへ追加されません。

概念上の順序:

1. Base System / Safety / Policy
1. Applicable User Guidance
1. authorized Memory Evidence
1. working conversation context
1. current user request

`UAGENT_MEMORY_PROJECTION=0` でturn projectionを無効化できます。`UAGENT_MEMORY_STRICT_SCOPE=0` はunknown-scope recordを許容するため、legacy互換性を意図的に評価する場合以外は推奨しません。

______________________________________________________________________

## 5. Authenticated Web Memory V3

Web deploymentではidentity modeを明示します。OIDCがbuilt-inのbrowser sign-in pathです。

```env
UAGENT_IDENTITY_MODE=oidc
UAGENT_OIDC_ISSUER=https://idp.example.com/...
UAGENT_OIDC_CLIENT_ID=your-client-id
UAGENT_OIDC_REDIRECT_URI=https://uag.example.com/auth/oidc/callback
UAGENT_MEMORY_BACKEND=sqlite
```

serverがauthenticated `principal_id` を解決し、browser / model payloadからMemory ownerを選ばせません。

### Personal Memory

```text
GET    /api/me/memories
POST   /api/me/memories
PUT    /api/me/memories/{memory_id}
DELETE /api/me/memories/{memory_id}
```

Personal writeでは現在principalから `owner_id` とpersonal audienceを導出します。updateはstable `memory_id` と `expected_revision` を使います。

### 特定userへのread-only共有

ownerは、確認済みrevisionだけを別principalへread-only grantできます。

```text
GET    /api/me/memories/{memory_id}/grants
POST   /api/me/memories/{memory_id}/grants
DELETE /api/me/memories/{memory_id}/grants/{grant_id}
```

受信側:

```text
GET /api/me/shared-memories
GET /api/me/shared-memories/{memory_id}
```

grantからedit / delete / reshare ownershipは得られません。source Memoryのrevisionが更新されても、旧grantだけで新しいrevisionは見えません。source Memoryをforgetするとgrantも利用できなくなります。

### Room Memory

```text
GET    /api/rooms/{room_id}/memories
POST   /api/rooms/{room_id}/memories
PUT    /api/rooms/{room_id}/memories/{memory_id}
DELETE /api/rooms/{room_id}/memories/{memory_id}
```

Room Memoryには、authorized Project access、persistされたRoom-to-Project binding、Room policy permissionが必要です。`room_id` を知っているだけではauthorizationになりません。

Personal Memoryが自動的にRoom Memoryへ昇格することはありません。

______________________________________________________________________

## 6. Project / Room authorization

authenticated multi-user Memoryでは、relevance評価より先にProject policyを適用します。

single-project deploymentでは次で固定できます。

```env
UAGENT_MEMORY_PROJECT=my-project
```

OIDCまたは認証済みnon-OIDCのmulti-project sessionでは、既にauthorization済みのProjectを次から選択できます。

```text
POST /api/project-context
```

選択したProjectContextはserver-sideに保存され、principal・authentication configuration・期限にbindされます。clientの `project_id` はselectorであり、server-bound contextと現在のmembership policyに一致しなければなりません。

Project管理API:

```text
GET    /api/projects/{project_id}/members
PUT    /api/projects/{project_id}/members/{principal_id}
DELETE /api/projects/{project_id}/members/{principal_id}
PUT    /api/projects/{project_id}/rooms/{room_id}
```

Room membership API:

```text
GET    /api/rooms/{room_id}/members
PUT    /api/rooms/{room_id}/members/{principal_id}
DELETE /api/rooms/{room_id}/members/{principal_id}
```

______________________________________________________________________

## 7. User Profile

### Local Profile

local compatibility Profileはenvironment、preferences、constraintsを保持します。代表的なcommandは `:profile`、`:profile-fromlog`、`:profile-clear` です。

### Authenticated principal Profile

authenticated WebではProfileもprincipal-keyedです。

```text
GET /api/me/profile
PUT /api/me/profile
```

runtimeはdisplay nameやemailではなく、stable principal IDをhashしたper-user Profile pathを利用します。

別principalから共有されたMemory evidenceは出典付きevidenceのままであり、受信者のpreferences / constraintsへ自動昇格しません。

legacy `/api/profile` はlocal identity modeに制限されています。

______________________________________________________________________

## 8. Snapshot invalidationとrevocation

authenticated projection snapshotは、principal / project / room / Memory access generationなどのidentity・access stateへbindされます。

Memory write、grant変更、関連authorization変更によって古くなったprojection stateは拒否されます。provider / tool continuationでも、取消前に作ったsnapshotを無条件に再利用しません。

ただし、既にuserへ表示・export済み、または外部providerへ送信済みの情報をrevocationで遡って消去できるわけではありません。revocationが制御するのは、その後のauthorized use / reuseです。

______________________________________________________________________

## 9. Directory group

検証済みdirectory group claimとMicrosoft Graphで解決したEntra group-overage IDをProject / Room policyへ利用できますが、groupはauthorization inputでありPersonal Memory ownership keyではありません。

Entra OIDCのgroup overageは、`UAGENT_OIDC_GRAPH_SCOPE` に `GroupMember.Read.All` を設定しtenant consentを得た場合にlogin時のMicrosoft Graph照会で解決します。`UAGENT_DIRECTORY_GROUP_POLICY` は解決済みgroup IDをProject / Room roleへmappingするpolicy設定であり、Directory clientやsession中のmembership refreshではありません。

______________________________________________________________________

## 10. Legacy Web API

次のcompatibility endpointは、requestがlocal identityとして解決された場合だけ利用できます。

```text
/api/memories
/api/profile
```

authenticated multi-user Webでは `/api/me/*` と `/api/rooms/*` を使用します。legacy endpointを別user owner指定の迂回経路として利用することはできません。

______________________________________________________________________

## 11. Security constraints

- password、API key、access token、ID token、cookieをMemory / Profileに保存しない。
- authenticated ownershipをemail、UPN、display name、Room ID、browser指定ownerから導出しない。
- multi-user MemoryはSQLiteとserver-controlled identity / Project / Room policyを使用する。
- direct read grantはread-onlyかつrevision-bound。
- shared evidenceを受信者本人のProfile guidanceへ黙って変換しない。
- non-local modeのidentity解決失敗時に暗黙で `local` へfallbackしない。

______________________________________________________________________

## 12. main `68083fb3` 時点の残る制約

V3の主要authorization / Memory boundaryは実装されていますが、deployment rolloutは完了していません。

- OIDC sessionはprocess-localです。再起動でsign-outし、multi-instance / HAにはdurable session設計が必要です。
- non-OIDC userはmembership確認済みProjectをserver-side ProjectContextへ選択・bindingできます。信頼済みworkspaceから既定Projectを自動導出する機能はdeployment側の課題です。
- Entra group overageは設定済みdelegated scopeとtenant consentの下でlogin時にMicrosoft Graphから解決します。session中のmembership refresh / revoke反映とEntra以外のDirectory APIは未対応です。Graph応答のbyte上限はstreaming中に適用され、redirectやunsafeなpagination、上限超過はfail-closedです。
- Private Web Roomにはconfigurableなidle expiryがあり、active connection / runと`human_ask`待機中のroomはevictされません。期限切れではroom binding、room限定Memory、関連session historyをcleanupし、upgrade時の既存roomには再接続猶予を付与します。
- Trusted Proxy / OAuth / Windows AD / External modeは、deployment固有のverified adapter / trust boundaryを検証する必要があります。
- multi-user / shared-roomのdefault rolloutはV3のisolation / revocation evaluation gateを通してから判断します。

Web Memoryのrequest境界store cleanupは実装済みです。これはPrivate Room / sessionのretentionとは別です。詳細は [Web認証とMemory](WEB_IDENTITY_MEMORY.ja.md)、[Memory V3 security hardening](UAG_MEMORY_V3_SECURITY_HARDENING.md)、[歴史的なv0.7.14 implementation review](UAG_0_7_14_IMPLEMENTATION_REVIEW.md) を参照してください。
