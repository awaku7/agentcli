# Web認証とMemory

このガイドでは、uag v0.7.14で利用できる認証付きマルチユーザーWebの動作を説明します。対象は、ユーザー識別、Project / Roomのアクセス制御、Personal Memory、共有Memory、Profileの分離です。

内部設計とsecurity invariantは [UAG Memory Architecture V3](UAG_MEMORY_ARCHITECTURE_V3.md)、実装状況のレビューは [UAG v0.7.14 implementation review](UAG_0_7_14_IMPLEMENTATION_REVIEW.md) を参照してください。

## 1. 利用形態を選ぶ

### Local / single-user

既定のidentity modeは `local` です。

```env
UAGENT_IDENTITY_MODE=local
```

local resolverは、信頼された1人のローカルprincipalとして動作します。既存のローカルMemory/Profileコマンドと、互換用Web APIの `/api/memories`、`/api/profile` はこのmodeで引き続き利用できます。

### 認証付きmulti-user Web

ブラウザーでサインインする場合はOIDCを使用します。

```env
UAGENT_IDENTITY_MODE=oidc
UAGENT_OIDC_ISSUER=https://idp.example.com/...
UAGENT_OIDC_CLIENT_ID=your-client-id
UAGENT_OIDC_REDIRECT_URI=https://uag.example.com/auth/oidc/callback
# Provider / client registrationでclient secretを使う場合のみ設定
UAGENT_OIDC_CLIENT_SECRET=

# HTTPS運用ではsecure cookieを維持する。既定値: 1
UAGENT_OIDC_COOKIE_SECURE=1
# server-side sessionの有効時間（秒）。既定値: 28800
UAGENT_OIDC_SESSION_TTL=28800

# Memory V3のmulti-user APIはSQLite Memoryを使用する
UAGENT_MEMORY_BACKEND=sqlite
```

uagはAuthorization Code + PKCEを使用し、provider metadata、署名鍵、ID tokenのclaimを検証した後に、opaqueなserver-side sessionを作成します。ブラウザー側から `principal_id` を指定することはできません。

1つのProjectだけを扱うdeploymentでは、サーバー側でProjectを固定できます。

```env
UAGENT_MEMORY_PROJECT=my-project
```

OIDCで複数Projectを扱う場合は、Project membership設定後、認証済みsessionから `/api/project-context` を使ってアクセス可能なProjectを選択します。

## 2. サインインと状態確認

Web UIを起動後、次を開きます。

```text
/auth/oidc/login
```

認証に成功すると、uagはHttpOnly session cookieを作成し、`/`へ戻します。

安全な認証状態の確認:

```text
GET /api/auth/status
```

設定中のmode / healthと現在の認証状態を返します。raw tokenやproviderのraw subjectは返しません。

ログアウト:

```text
POST /auth/logout
```

`UAGENT_ADMIN_PRINCIPALS` に設定されたadministratorは次を利用できます。

```text
GET /api/admin/auth/status
```

このAPIはactive OIDC session数などの安全な運用情報のみを返し、token、client secret、raw identity claimは返しません。

## 3. Project accessはサーバー側で決める

ブラウザーが送信する `project_id` はselectorであり、それ自体はアクセス権限になりません。

固定Project運用では `UAGENT_MEMORY_PROJECT` がserver-side bindingになります。固定していないOIDC sessionでは、認証後に次でProjectを選択します。

```http
POST /api/project-context
Content-Type: application/json

{"project_id":"my-project"}
```

選択できるのは、認証済みprincipalがそのProjectのviewer以上の権限を持っている場合だけです。

Project membership管理API:

```text
GET    /api/projects/{project_id}/members
PUT    /api/projects/{project_id}/members/{principal_id}
DELETE /api/projects/{project_id}/members/{principal_id}
```

RoomをProjectへbindするAPI:

```text
PUT /api/projects/{project_id}/rooms/{room_id}
```

Project IDやRoom IDを知っているだけではauthorizationになりません。

## 4. Personal Memory

認証付きPersonal Memoryのownerは、常にserver-sideの現在principalから決まります。ブラウザーから別userのownerを指定することはできません。

```text
GET    /api/me/memories
POST   /api/me/memories
PUT    /api/me/memories/{memory_id}
DELETE /api/me/memories/{memory_id}
```

作成例:

```json
{
  "project_id": "my-project",
  "note": "リリース要約は簡潔な形式を好む"
}
```

更新・削除ではstableな `memory_id` と `expected_revision` を使います。古いrevisionを指定した更新は、新しい内容を黙って上書きせず拒否されます。

## 5. Personal Memoryを特定userへ共有する

Personal Memoryは、確認済みrevisionに対するread-only grantとして共有できます。

共有先一覧:

```text
GET /api/me/memories/{memory_id}/grants
```

read grantの追加:

```text
POST /api/me/memories/{memory_id}/grants
```

例:

```json
{
  "project_id": "my-project",
  "grantee_principal_id": "<server principal id>",
  "expected_revision": 1
}
```

grantの取消:

```text
DELETE /api/me/memories/{memory_id}/grants/{grant_id}
```

受信側は次から自分に共有されたMemoryを参照できます。

```text
GET /api/me/shared-memories
GET /api/me/shared-memories/{memory_id}
```

read grantからownership、編集、削除、再共有の権限は得られません。ownerがMemoryを更新した場合、新しいrevisionは改めて共有されるまで受信者には見えません。元Memoryをforgetすると、すべての共有先から参照できなくなります。

他userから共有されたPersonal Memoryは、出典付きの参考情報として扱われます。受信者本人のProfileやPersonal Guidanceへ自動変換されません。

## 6. Room Memory

Room MemoryはPersonal Memoryとは別物で、Project membershipとRoom policyの両方で制御されます。

```text
GET    /api/rooms/{room_id}/memories
POST   /api/rooms/{room_id}/memories
PUT    /api/rooms/{room_id}/memories/{memory_id}
DELETE /api/rooms/{room_id}/memories/{memory_id}
```

Room membership管理:

```text
GET    /api/rooms/{room_id}/members
PUT    /api/rooms/{room_id}/members/{principal_id}
DELETE /api/rooms/{room_id}/members/{principal_id}
```

Personal Memoryが自動的にRoom Memoryへ昇格することはありません。また、Bだけに直接共有したMemoryを、BとCが参加するRoomで自動的に利用可能とは扱いません。

## 7. user別Profile

認証付きWebでは、Profileもprincipal単位で分離されます。

```text
GET /api/me/profile
PUT /api/me/profile
```

Profileはenvironment、preferences、constraintsを認証principalごとに保持します。他userから共有されたMemory evidenceを、受信者本人のpreference / constraintへ自動学習しません。

互換用 `/api/profile` はlocal identity modeでのみ利用できます。

## 8. Memory Projectionと権限取消

関連するMemory / Profileは、turnごとのprovider contextへprojectionされます。認証付きnon-local turnではsnapshotが少なくとも次へbindされます。

- principal
- project
- room
- Memory access generation

Memory、grant、policyが変更されると古いsnapshotは失効します。runtimeはprojection boundaryを再確認し、取消前のsnapshotをそのままprovider呼出しやtool continuationへ再利用しないようにします。

local V2 projectionは既定で有効です。

```env
UAGENT_MEMORY_PROJECTION=1
UAGENT_MEMORY_STRICT_SCOPE=1
```

## 9. Entra ID / directory group

検証済みOIDC `groups` claimは、Project / Room authorization policyの入力にできます。group IDはauthorization inputであり、Personal Memoryのownerにはなりません。

Entraが完全なgroup一覧ではなくgroup-overage markerを返した場合、現在のverifierはfail-closedで拒否します。overage解決とmembershipの鮮度・取消反映には、deployment固有の信頼できるDirectory API adapterが必要です。

`UAGENT_DIRECTORY_GROUP_POLICY` は、検証済みgroup IDをProject / Room roleへmappingできますが、identity verifierやDirectory clientの代替ではありません。

## 10. v0.7.14時点の制約

- OIDC sessionはprocess-localです。process再起動で再ログインが必要です。multi-instance / HA運用には将来のdurable session設計が必要です。
- OIDCのProject選択はserver-side sessionへbindされていますが、non-OIDCのmulti-user / multi-project運用にはserver-derived ProjectContextの追加integrationが必要です。
- Entra group overageの解決にはdeployment固有のDirectory API adapterが必要です。
- Trusted Proxy、OAuth、Windows AD、External modeにはresolver / verifier contractがありますが、本番deploymentでは信頼境界と検証adapterを用意して検証する必要があります。失敗時に暗黙で `local` へfallbackしません。
- multi-user / shared-room Memoryのdefault化は、APIが存在するだけで決めず、V3 architectureのisolation / revocation gateを通した後に判断します。

## 11. Security checklist

- OIDC WebはHTTPSで運用し、`UAGENT_OIDC_COOKIE_SECURE=1` を維持する。
- password、API key、access token、ID token、cookieをMemory / Profileへ保存しない。
- email、display name、UPN、Room ID、browser指定ownerをstable authenticated ownership keyとして扱わない。
- multi-user Memory APIを公開する前にProject / Room membershipを設定する。
- `/api/memories`、`/api/profile` はlocal compatibility APIとして扱い、認証付きmulti-user clientは `/api/me/*`、`/api/rooms/*` を利用する。
- identity、directory、proxy、Project bindingの設定を変更したらisolation / revocationを再テストする。
