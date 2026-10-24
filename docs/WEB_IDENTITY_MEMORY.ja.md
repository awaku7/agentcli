# Web認証とMemory

このガイドでは、既定のブラウザーごとの匿名guest sessionと、認証付きmulti-user Webのidentity modeを説明します。対象はユーザー識別、Project / Roomのアクセス制御、Personal Memory、共有Memory、Profileの分離です。

内部設計とsecurity invariantは [UAG Memory Architecture V3](UAG_MEMORY_ARCHITECTURE_V3.md)、オンプレミスActive Directory / IIS Windows認証を使う場合は [Active Directory / Windows認証 導入ガイド](ACTIVE_DIRECTORY.ja.md)、現行の実装・セキュリティ境界は [Memory V3 security hardening](UAG_MEMORY_V3_SECURITY_HARDENING.md) を参照してください。

## 1. 利用形態を選ぶ

### 既定: ブラウザーごとの匿名セッション

既定のidentity modeは `browser` です。UAGはブラウザープロファイルごとにランダムな署名付きbearer Cookieを発行し、Cookieから別々のguest principalと専用Projectを導出します。CookieはHttpOnly / SameSite=Laxで、HTTPSでは既定でSecure、既定有効期間は1年です。署名鍵はUAG state directoryの `browser_session.key` に保存し、必要なら `UAGENT_BROWSER_SESSION_SECRET` で固定できます。

```env
# 既定値。通常は指定不要
UAGENT_IDENTITY_MODE=browser
# Cookie有効期間（秒、既定: 31536000）
UAGENT_BROWSER_SESSION_TTL=31536000
# 複数プロセスで同じCookieを検証する場合の任意共有鍵（32 byte以上）
# 未指定ならUAG state directoryにランダム鍵を作成
UAGENT_BROWSER_SESSION_SECRET=
# TLS終端プロキシの背後でアプリがHTTPSを認識できない場合に指定
UAGENT_BROWSER_COOKIE_SECURE=1
```

これにより左側の履歴とprivate Memoryはブラウザープロファイルごとに分離されます。Cookieが有効でPrivate Roomが保持されていれば、ページ再読み込みや通常のブラウザー再起動後も同じRoomを再表示できます。Webサーバー再起動後も、idle TTL内でPrivate RoomとSQLite sessionが残っていれば、会話履歴を復元します。ただし、idle TTL（既定24時間、設定可能範囲60秒〜30日）を過ぎてPrivate Roomが削除されると、関連するWeb session履歴も削除されます。Cookieの有効期間だけでは削除済み履歴を復元できません。履歴一覧の選択ではセッションIDで`:load`を行わず、セッションに結び付いた元のRoomを再表示します。履歴一覧自体も現在のprincipalが所有し、元のRoomに結び付いたセッションに限定されます。これは**ログインや実在人物の認証ではありません**。Cookieをコピーされた相手は有効期限までそのguest identityを使えます。Cookieを紛失・削除するとそのブラウザーから以前の履歴へ戻れず、ブラウザー側からCookieを消してもコピー済みCookieは失効しません。実ユーザーの識別や機密性の高いmulti-user運用にはOIDCまたは適切に保護した `trusted_proxy` を使ってください。匿名guest identityを機密Projectのアクセス制御境界として扱わないでください。

従来の単一principal動作が必要な場合は、明示的に指定します。

```env
UAGENT_IDENTITY_MODE=local
```

`local`では全ブラウザーが同一principalとなり、履歴も共有されます。Cookie identity導入前の既存sessionは`local` principalに結び付いている場合があり、guest cookieへ自動移行されません。外部proxy/tunnelで中継しない信頼済み単独利用に限定してください。厳密な`127.0.0.1` bindでは、既定`browser`または明示Identity=`local`のどちらもtrusted local WebとしてSandbox offを維持します。その他のbind/identity構成はRemote profileとなりMXC policyを使います。browser cookieはローカルブラウザー間の履歴分離用であり、同じlocal serverを使う敵対ユーザー間の認可境界ではありません。

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

# WebSocket handshakeで許可するbrowser Originをexact指定する
# ネットワーク公開する場合に指定。wildcardは使用できない
UAGENT_WEB_ALLOWED_ORIGINS=https://uag.example.com

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

固定Project運用では `UAGENT_MEMORY_PROJECT` がserver-side bindingになります。固定していないOIDC session、またはProjectContext cookieを使う認証済みnon-OIDC sessionでは、認証後に次でProjectを選択します。

```http
POST /api/project-context
Content-Type: application/json

{"project_id":"my-project"}
```

選択できるのは、認証済みprincipalがそのProjectのviewer以上の権限を持っている場合だけです。

固定Project、OIDC session binding、選択済みProjectContext cookieがない認証済みnon-OIDC requestでは、startup時にconfigured `UAGENT_WORKDIR`を適用したcaptured startup workdirから既定値を導出します。request-timeのCWDや環境変数変更は既定値に影響しません。`GET /api/me/projects`はprincipalにviewer membershipがある場合だけ、その既定値を`bound_project`として返しますが、読み取り専用でありProjectContext sessionやcookieを新規作成しません。永続的な選択は明示的な`POST /api/project-context`、またはmembership再確認後の`POST /api/me/private-room`で行います（ProjectContextの容量上限に達した場合はcookieを発行せず、認可済みPrivate Roomのserver-side bindingを維持します）。既定候補へのmembershipがなければ、利用者が認可済みProjectを明示選択する必要があります。OIDCとlocal identityの動作は変更しません。

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

### Private Web Sessionのlifecycle

`POST /api/me/private-room` は、server-sideのidentityとProject認可を確認した後に、owner専用のPrivate Web Roomを作成します。切断後のidle sessionは、既定で24時間の再接続猶予期間を持ちます。`UAGENT_WEB_ROOM_IDLE_TTL_SECONDS` で変更できます（設定可能範囲: 60秒〜30日）。利用があればidle期限が更新されます。WebSocket接続中、agent実行中（streamingを含む）、または`human_ask`待機中のroomはevictされません。schema upgrade時には、既存のPrivate Roomへ作成日時起点ではなく新しい再接続猶予期間を付与します。

idle期限を過ぎると、Private Roomのbinding、room限定Memory、および関連するWeb session履歴を削除します。Personal Memoryは削除しません。期限切れのPrivate Roomには再接続できません。

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

Entraが署名検証済みgroup-overage markerを返した場合、authorization-code交換でdelegated access tokenを取得し、`UAGENT_OIDC_GRAPH_SCOPE` に `GroupMember.Read.All` を設定してtenant consentを得ていれば、UAGはlogin時にMicrosoft Graphからgroup IDを解決します。access tokenは一時利用で、sessionやMemoryへ保存しません。Graph hostは検証済みissuerに対応するcloudへ限定し、redirectを無効化し、pagination URLを検証します。page / group / bodyの上限超過やlookup failureはfail-closedです。これはlogin時の解決であり、session中のmembership live refreshや即時revoke反映ではありません。

`UAGENT_DIRECTORY_GROUP_POLICY` は、検証済みgroup IDをProject / Room roleへmappingするpolicy設定であり、identity verifierやDirectory clientの代替ではありません。Graph応答のbyte上限はstreaming中に適用され、redirectやunsafeなpagination URL、上限超過はfail-closedです。

## 10. main `68083fb3` 時点の制約

- OIDC sessionはprocess-localです。process再起動で再ログインが必要です。multi-instance / HA運用にはdurable session設計が必要です。
- non-OIDC userはmembership確認済みProjectをserver-side ProjectContextへ選択・bindingできます。信頼済みdeployment workspaceから既定Projectを自動導出する機能は未実装です。
- Entra group overageは設定済みdelegated scopeとtenant consentの下でlogin時にMicrosoft Graphから解決します。session中のmembership refresh / revoke反映は対象外です。Graph応答のbyte上限はstreaming中に適用され、redirectやunsafeなpagination、上限超過はfail-closedです。
- Private Web Roomにはconfigurableなidle expiryがあります。active WebSocket、agent実行 / streaming、`human_ask`待機中のroomは保護され、期限切れではroom binding、room限定Memory、関連session historyをcleanupします。upgrade時には既存roomへ新しい再接続猶予を付与します。
- Web Memory APIはdenied / exception pathを含め、request単位のstoreをcloseします。これはPrivate Roomのretentionとは別です。
- Trusted Proxy、OAuth、Windows AD、External modeにはresolver / verifier contractがありますが、本番deploymentでは信頼境界と検証adapterを用意して検証する必要があります。失敗時に暗黙で `local` へfallbackしません。
- multi-user / shared-room Memoryのdefault化は、APIが存在するだけで決めず、V3 architectureのisolation / revocation gateを通した後に判断します。

## 11. Security checklist

- OIDC WebはHTTPSで運用し、`UAGENT_OIDC_COOKIE_SECURE=1` を維持する。
- password、API key、access token、ID token、cookieをMemory / Profileへ保存しない。
- email、display name、UPN、Room ID、browser指定ownerをstable authenticated ownership keyとして扱わない。
- multi-user Memory APIを公開する前にProject / Room membershipを設定する。
- `/api/memories`、`/api/profile` はlocal compatibility APIとして扱い、認証付きmulti-user clientは `/api/me/*`、`/api/rooms/*` を利用する。
- identity、directory、proxy、Project bindingの設定を変更したらisolation / revocationを再テストする。
