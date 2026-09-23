# GitLab MCP / OAuth連携設計

- Status: planned
- Priority: P1
- Source: GitLab公式MCP Server仕様、UAG現行MCP/OAuth実装、UAG Web Identity / Memory V3設計
- Survey date: 2026-09-23
- Target baseline: UAG `0.7.13` / `main` commit `92923ea69beca43a0b5d0c14ac44dda974e9078e`

## 目的

UAGからGitLab.comおよびGitLab Self-Managed / DedicatedのGitLab MCP Serverへ安全に接続し、Issue、Merge Request、Repository、Pipeline等のGitLab機能をMCP toolとして利用できるようにする。

GitLab専用REST toolを大量に追加するのではなく、UAGの汎用MCP OAuth機能を完成させ、GitLabを最初の主要ユースケースとして対応する。

特に社内GitLabでは、UAGを社内LANまたはVPN内で実行し、GitLabをインターネットへ公開せずに接続できる構成を主要対象とする。

また、UAG Webは複数ユーザーが同一UAGプロセスを利用できるため、MCP OAuth credentialは必ずUAGの認証済み`principal_id`に所有させる。Web AuthenticationとGitLab OAuthは別の認証境界として扱い、credentialの共有や暗黙のfallbackを行わない。

## 背景

GitLab公式MCP Serverは以下のエンドポイントを提供する。

```text
https://<gitlab-host>/api/v4/mcp
```

GitLab公式ドキュメントではHTTP transportが推奨されている。HTTP transportはGitLab 18.6で導入された。stdio経路では`mcp-remote`を利用できる。

GitLab MCP ServerはOAuth Dynamic Client Registration（DCR）に対応し、初回接続時にクライアントを自動登録できる。また、管理者がDCRを無効化した環境や共有クライアント運用では、事前登録済みOAuth Applicationの`clientId`を利用できる。

GitLab 19.3ではSelf-Managed / DedicatedでDCRを無効化する管理設定が導入され、無効化時は事前登録済みOAuth Applicationが必要になる。

GitLab公式仕様の参照先:

- https://docs.gitlab.com/user/model_context_protocol/mcp_server/
- https://docs.gitlab.com/user/model_context_protocol/mcp_server_tools/
- https://docs.gitlab.com/administration/settings/account_and_limit_settings/

## 現行UAGの状態

### MCP / OAuth

UAGにはすでに以下が実装されている。

- MCP Streamable HTTP
- MCP stdio
- Legacy / Stateless接続
- `tools/list` / `tools/call`
- Resources / Prompts
- OAuth Protected Resource Metadata取得
- Authorization Server Metadata取得
- issuer / endpoint trust検証
- PKCE S256
- Authorization Code交換
- refresh token交換
- localhost callback listener
- browser OAuth
- Bearer token付与
- 401時のrefresh再試行
- 暗号化Token Store / CredentialStore
- Proxy設定
- 企業CA設定
- CIMD取得・検証

一方、GitLab MCPへのネイティブHTTP接続には以下が不足している。

1. OAuth DCRの実行処理がない。
2. OAuthが必要なMCP endpointへ未認証で接続した場合の401 bootstrapがない。
3. DCRで取得した`client_id`と`redirect_uri`を永続化する仕組みがない。
4. 現行`MCPClient(protocol_mode="auto")`はOAuth bootstrap前に`server/discover`をprobeするため、未認証401で接続が停止する可能性がある。
5. `mcp_servers.json`にOAuth接続方式を表現する正式schemaがない。
6. MCP OAuth tokenがWebの`principal_id`で分離されていない。
7. Webで利用できるMCP OAuth callback routeがない。

### Web Authentication / Identity

UAG Webは認証provider固有情報を`IdentityContext`へ正規化し、`principal_id`をユーザー境界として利用する。

代表的なidentity mode:

```text
local
oidc
oauth
trusted_proxy
windows_ad
token
external
```

Web OIDCでは`uag_oidc_session`のserver-side sessionを利用し、各requestから`IdentityContext`を解決する。Memory V3やProject Accessも`identity.principal_id`を認可境界としている。

Agent turnでは`TurnContext`へ`principal_id`が入り、ContextVarで実行経路へ伝播する。

GitLab MCP credentialも同じ境界へ統合する。ただし、GitLabのremote identityをUAGの`principal_id`へ置換してはならない。

## 非目標

本計画では以下を直接の対象にしない。

- GitLab REST APIを網羅する専用`gitlab_*_tool.py`群の実装
- GitLab OAuthをUAG Webへのログイン方式として利用すること
- UAGユーザーとGitLabユーザーをemailやusernameで自動同一視すること
- GitLab RunnerやGitLab Serverの管理者操作を自動化すること
- GitLabの権限をUAG側で拡張・迂回すること
- GitLabのアクセス権限を独自キャッシュしてGitLab ACLより優先すること
- LLMへ送信する情報の組織ポリシーを自動決定すること

GitLab側のユーザー権限がremote serviceの最終的な認可境界であり、UAGはそれを越えるアクセスを行わない。

## 認証境界

UAGでは次の2つを明確に分離する。

```text
UAG Authentication
  → このUAG操作を誰が行っているか
  → IdentityContext.principal_id

GitLab OAuth
  → GitLabへどのremote accountで接続するか
  → access_token / refresh_token
```

両者は同一人物であることが多いが、設計上は同一性を仮定しない。

```text
UAG principal Alice
        │
        └── owns ── GitLab OAuth credential X

UAG principal Bob
        │
        └── owns ── GitLab OAuth credential Y
```

GitLab側でremote account名を取得できる場合は表示用metadataとして保持してよいが、UAGの`principal_id`やProject/Room権限へ変換しない。

## 設計原則

### 1. GitLab専用認証にしない

DCR、pre-registered client、PKCE、OAuth metadata discovery、credential isolationはMCP共通機能として実装する。

```text
src/uagent/tools/mcp/
  oauth_registration.py
  oauth_bootstrap.py
  oauth_provider.py
  oauth_metadata.py
  oauth_authorization.py
  oauth_transactions.py
  connection.py
```

GitLab固有処理は、必要最小限の相互運用テスト・ドキュメント・推奨設定に限定する。

### 2. UAG principalをcredential ownerにする

Webではcurrent `TurnContext.principal_id`または認証済みWeb requestの`IdentityContext.principal_id`を必須とする。

CLI / GUIのsingle-user local modeでは`principal_id="local"`を利用する。

multi-user modeでprincipalを解決できない場合、process-global tokenへfallbackせずfail closedする。

### 3. Client RegistrationとUser Tokenを分離する

OAuth client registrationはUAG application側の情報であり、通常はユーザーごとに作成しない。

```text
UAG application / callback profile
  └── client_id / redirect_uri

principal Alice
  └── access_token / refresh_token

principal Bob
  └── access_token / refresh_token
```

DCR registrationはcallback profileとresource単位で共有できる。一方、access token / refresh tokenは`principal_id`単位で必ず分離する。

### 4. OAuth bootstrapをprotocol detectionより前に置く

未認証MCP serverでは401はLegacy判定材料ではなく認証要求である。

```text
resolve principal + server config
      ↓
create HTTP client
      ↓
resolve callback profile
      ↓
resolve registration + principal token
      ↓
必要ならOAuth bootstrap
      ↓
認証済みauthorization_provider生成
      ↓
MCP protocol detection
      ↓
server/discover or initialize
      ↓
tools/list / tools/call
```

401を単純にLegacy fallback対象へ追加してはならない。

### 5. Callbackはentry pointごとに切り替える

CLI / GUIではlocalhost callbackを利用する。

Webではlocalhost callbackを使用しない。ユーザーのbrowserから到達できるUAG Web serverの固定HTTPS callback routeを利用する。

### 6. Node.js依存はfallbackに限定する

`mcp-remote`は動作確認・互換fallbackとしてサポートするが、最終形はUAGネイティブHTTP + OAuthとする。

## 全体構成

```text
                         ┌──────────────────────┐
                         │ UAG Identity Layer   │
                         │ IdentityContext      │
                         │ TurnContext          │
                         │ principal_id         │
                         └──────────┬───────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────┐
│ UAG                                                 │
│                                                     │
│ public MCP tools / Web MCP API                      │
│              │                                      │
│              ▼                                      │
│        MCPConnectionResolver                        │
│              │                                      │
│      ┌───────┴────────┐                             │
│      ▼                ▼                             │
│ RegistrationStore  Principal-scoped Token Store     │
│ app/callback scope  user scope                      │
│      │                │                             │
│      └───────┬────────┘                             │
│              ▼                                      │
│        MCPOAuthBootstrap                            │
│         │          │                                │
│         │          └─ DCR                           │
│         ▼                                           │
│      MCPClient                                      │
└─────────┬───────────────────────────────────────────┘
          │ HTTPS / MCP
          ▼
┌──────────────────────────────┐
│ GitLab                       │
│ /.well-known/...             │
│ /oauth/register              │
│ /oauth/authorize             │
│ /oauth/token                 │
│ /api/v4/mcp                  │
└──────────────────────────────┘
```

## 接続モード

### A. Native HTTP + Dynamic Client Registration

推奨する標準経路。

```text
UAG
 ↓
GET protected resource metadata
 ↓
GET authorization server metadata
 ↓
resolve callback profile
 ↓
POST registration_endpoint（未登録時）
 ↓
client_id取得
 ↓
browser authorization + PKCE
 ↓
token exchange
 ↓
registrationはapp scopeへ保存
user tokenはprincipal scopeへ保存
 ↓
MCP接続
```

### B. Native HTTP + Pre-registered OAuth Application

企業環境で推奨する管理可能な経路。

```text
管理者
 ↓
GitLab OAuth Application作成
 scope=mcp
 Confidential=false
 ↓
client_id配布
 ↓
UAG設定
 ↓
各principalがbrowser authorization + PKCE
 ↓
各principal専用token保存
 ↓
MCP接続
```

### C. stdio + mcp-remote

移行・互換fallback。

```text
UAG
 ↓ stdio
npx mcp-remote
 ↓ HTTPS/OAuth
GitLab MCP
```

`mcp-remote`が外部でtokenを管理する場合、UAGのprincipal-scoped credential model外となるため、multi-user Webの標準経路にはしない。local single-user検証・互換用途を主用途とする。

## `mcp_servers.json`拡張

### Native HTTP / auto DCR

```json
{
  "mcp_servers": [
    {
      "name": "company-gitlab",
      "transport": "streamable-http",
      "protocol_mode": "auto",
      "url": "https://gitlab.company.local/api/v4/mcp",
      "oauth": {
        "mode": "auto",
        "scope": "mcp",
        "callback_mode": "auto",
        "callback_host": "127.0.0.1",
        "callback_port": 8765,
        "callback_path": "/callback",
        "web_redirect_uri": "https://uag.company.local/auth/mcp/oauth/callback"
      },
      "headers": {
        "X-Gitlab-Mcp-Server-Tool-Name-Prefix": "gitlab_"
      }
    }
  ]
}
```

### Pre-registered client

```json
{
  "mcp_servers": [
    {
      "name": "company-gitlab",
      "transport": "streamable-http",
      "protocol_mode": "auto",
      "url": "https://gitlab.company.local/api/v4/mcp",
      "oauth": {
        "mode": "pre_registered",
        "client_id": "<gitlab-oauth-application-id>",
        "scope": "mcp",
        "callback_mode": "auto",
        "callback_host": "127.0.0.1",
        "callback_port": 8765,
        "callback_path": "/callback",
        "web_redirect_uri": "https://uag.company.local/auth/mcp/oauth/callback"
      }
    }
  ]
}
```

## OAuth設定schema

初期実装では以下を許可する。

```text
oauth.mode                   none | auto | dynamic | pre_registered
oauth.client_id              optional string
oauth.scope                  optional string
oauth.callback_mode          auto | local | web
oauth.callback_host          default 127.0.0.1
oauth.callback_port          default 8765
oauth.callback_path          default /callback
oauth.web_redirect_uri       optional absolute HTTPS URL
oauth.authorization_timeout default 300
oauth.allow_browser          default true
```

`callback_mode=auto`は`TurnContext.entry_point`または呼出元adapterから決定する。

```text
web      → web
cli/gui  → local
a2a      → interactive callbackなしを既定
```

`web_redirect_uri`をrequestの`Host` headerから無条件生成してはならない。reverse proxy配下でもcanonical public URLを明示設定する。

`client_secret`は初期実装では設定schemaへ入れない。MCP public client + PKCEを標準とし、confidential client対応は別計画とする。

## Callback設計

### Local callback

CLI / GUIでは固定callback portを既定とする。

```text
http://127.0.0.1:8765/callback
```

`OAuthCallbackListener`へ明示port指定を追加する。

```python
OAuthCallbackListener(
    host="127.0.0.1",
    port=8765,
    path="/callback",
)
```

`pre_registered`ではport競合時に別portへ自動変更しない。登録済みredirect URIと一致しないため、構造化エラーを返す。

`dynamic` / `auto`で未登録の場合のみ、設定で`callback_port=0`が明示されたときephemeral portを許可してよい。

### Web callback

Webではlocalhost callbackを使用しない。

```text
https://uag.company.local/auth/mcp/oauth/callback
```

を例とする固定routeをUAG Webへ追加する。

Web callbackは以下を満たす。

1. HTTPSを既定必須とする。
2. callback URIは明示したcanonical URLを使用する。
3. OAuth `state`をserver-side transactionへ紐付ける。
4. callback requestから現在のUAG `IdentityContext`を解決する。
5. transactionの`principal_id`と現在の`principal_id`が一致しない場合は拒否する。
6. tokenをcallback requestのprincipal scopeへ保存する。
7. 任意外部URLへのopen redirectを許可しない。

### Callback Profile

DCR registrationはredirect URIに依存するため、registration keyにはcallback profileを含める。

例:

```text
local:http://127.0.0.1:8765/callback
web:https://uag.company.local/auth/mcp/oauth/callback
```

同じGitLab resourceでもlocal clientとWeb clientは別registrationになり得る。

## Dynamic Client Registration

新規モジュール:

```text
src/uagent/tools/mcp/oauth_registration.py
```

主な型:

```python
@dataclass(frozen=True)
class OAuthClientRegistration:
    client_id: str
    redirect_uris: tuple[str, ...]
    token_endpoint_auth_method: str
    registration_client_uri: str | None
    registration_access_token: str | None
    raw: dict[str, Any]
```

主な関数:

```python
async def register_oauth_client(
    registration_endpoint: str,
    *,
    redirect_uris: list[str],
    client_name: str,
    scope: str | None,
    http_client: Any,
) -> OAuthClientRegistration:
    ...
```

DCR request基本形:

```json
{
  "client_name": "UAG",
  "redirect_uris": ["https://uag.company.local/auth/mcp/oauth/callback"],
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none"
}
```

Local callback profileではredirect URIをlocalhostへ置き換える。

DCR応答では最低限以下を検証する。

- `client_id`が空でない
- `redirect_uris`が返る場合、要求したURIが含まれる
- `token_endpoint_auth_method`が未指定なら`none`として扱う
- confidential clientを要求する応答は初期実装では拒否する
- registration endpointはissuer trust境界とenterprise policyを満たす

## Registration Store

Client registrationはUAG application / callback profile側の状態として保存する。

論理抽象:

```text
MCPRegistrationStore
```

resource keyとcallback profile keyはSHA-256由来のopaque keyを利用する。

```text
mcp-registration/<callback-profile-key>/<resource-key>
```

保存項目:

```text
client_id
issuer
resource
redirect_uri
callback_profile
token_endpoint_auth_method
registration_client_uri
created_at
```

`registration_access_token`がある場合はsecretとして保存する。

Registration Storeに`principal_id`は入れない。registrationをユーザーtokenと同じライフサイクルにしない。

## Principal-scoped Token Store

### 必須要件

現行のprocess-wide `CredentialStore`はbackendとして再利用できるが、MCP user tokenのlookup keyは必ずprincipal scopeを含む。

```text
principal_key = sha256(normalized principal_id)
resource_key  = sha256(normalized resource URL)

mcp-token/<principal-key>/<resource-key>
```

保存対象:

```text
access_token
refresh_token
expires_at
scope
token_type
issuer
resource
```

raw `principal_id`をcredential nameへ直接埋め込まない。

### legacy migration

既存形式:

```text
mcp/<resource>
```

のcredentialは、`principal_id="local"`のsingle-user local modeに限り読み取りとlazy migrationを許可する。

Web / OIDC / AD / trusted proxy等のmulti-user identity modeでは、process-global legacy credentialを特定ユーザーへ自動移行してはならない。これはcredential leakage防止のためfail closedとする。

## OAuth Transaction

Web callbackでは短命なserver-side transactionを使用する。

新規候補:

```text
src/uagent/tools/mcp/oauth_transactions.py
```

最低限保持する値:

```text
state
code_verifier
principal_id
server_name
resource
client_id
redirect_uri
callback_profile
created_at
expires_at
browser_binding
```

access token / refresh tokenはtransactionへ保存しない。

### Browser binding

Web OAuth開始時に、現在のUAG sessionに加えてMCP OAuth専用の短命browser bindingを利用してよい。

例:

```text
uag_mcp_oauth_binding
```

属性:

```text
HttpOnly
Secure
SameSite=Lax
短いTTL
```

callback時は少なくとも次を検証する。

```text
state一致
transaction未使用
transaction未期限切れ
UAG session有効
current principal_id == transaction principal_id
browser binding一致
redirect URI一致
```

callback中にUAG sessionが失効していた場合、tokenを誰かへ推測して保存せず認証失敗とする。

## OAuth Bootstrap

新規モジュール:

```text
src/uagent/tools/mcp/oauth_bootstrap.py
```

責務:

1. callerの`principal_id`を確定
2. MCP server configからOAuth modeを解決
3. callback profileを解決
4. principal-scoped tokenを確認
5. app-scoped registrationを確認
6. Protected Resource Metadata取得
7. Authorization Server Metadata取得
8. client identityを決定
9. 必要ならDCR
10. 必要ならbrowser authorization
11. `OAuthTokenProvider`をprincipal-scoped credentialへ接続
12. MCPClientへ渡す

想定API:

```python
@dataclass
class MCPOAuthContext:
    provider: OAuthTokenProvider
    principal_id: str
    issuer: str
    resource: str
    client_id: str
    redirect_uri: str | None
    callback_profile: str

async def resolve_mcp_oauth_context(
    *,
    principal_id: str,
    resource_url: str,
    oauth_config: dict[str, Any],
    callback_context: Any,
    http_client: Any,
    credential_store: CredentialStore,
) -> MCPOAuthContext | None:
    ...
```

`principal_id`を省略可能にはしない。local adapterが明示的に`local`を渡す。

## Client identity選択順序

`oauth.mode="auto"`では次の順序とする。

```text
1. callback profileに一致する保存済みMCPRegistrationStore
2. 設定のoauth.client_id
3. 設定済みCIMD client_id URL
4. Authorization Serverのregistration_endpointを使うDCR
5. 利用可能な方式がなければ構造化エラー
```

`pre_registered`では2のみ使用する。

`dynamic`では保存済みregistrationまたはDCRのみ使用する。

## 401処理

### 接続前bootstrap

OAuth設定が`none`以外なら、MCP protocol probeより先にOAuth bootstrapを行う。

### 接続中401

認証済みrequestで401が返った場合:

1. caller principalのrefresh tokenがあれば1回だけrefresh
2. refresh成功なら同じMCP requestを1回だけ再送
3. refresh失敗またはrefresh tokenなしなら`MCP_OAUTH_REAUTH_REQUIRED`
4. interactive authorization可能なentry pointでは再接続フローを案内
5. 無限401 loopは禁止

別principalのrefresh tokenへfallbackしてはならない。

## MCPConnectionResolver

複数public toolに重複する以下を共通化する。

- current TurnContext / principal解決
- `mcp_servers.json`読込
- server_name解決
- URL / command / args / env解決
- headers環境変数展開
- protocol_mode解決
- OAuth config解決
- callback profile解決
- Proxy / CA config解決
- principal-scoped OAuth context解決

候補:

```text
src/uagent/tools/mcp/connection.py
```

主な型:

```python
@dataclass(frozen=True)
class MCPConnectionConfig:
    name: str | None
    principal_id: str
    entry_point: str
    url: str | None
    command: str | None
    args: tuple[str, ...]
    env: dict[str, str]
    headers: dict[str, str]
    protocol_mode: str
    oauth: MCPOAuthConfig | None
    http_config: MCPHTTPConfig | None
```

## TurnContext / Web / Room統合

### Agent turn

MCP tool実行時は`get_current_turn_context()`からprincipalを取得する。

Web agent worker、CLI、GUI、A2A等は既存のTurnContext伝播を利用する。

TurnContextが必要なidentity modeで未設定の場合は、process-global credentialへfallbackしない。

### Shared Room

Roomは会話・memory共有境界であってcredential共有境界ではない。

```text
Room R
 ├─ Alice turn → AliceのGitLab token
 ├─ Bob turn   → BobのGitLab token
 └─ Carol turn → CarolのGitLab token
```

Room ownerのtokenを他メンバーへ継承しない。

### Sub-agent

Sub-agentは親turnのprincipalを明示的に継承する。

別principalへ切り替えるAPIをMCP OAuth層へ持たせない。

### Background / scheduler

Web userのcredentialを使うbackground taskは、作成元principalを安全に保持する仕組みがある場合のみ許可する。

principal不明のbackground processが最初に見つかったtokenを利用する挙動は禁止する。

## Web MCP OAuth API

UIそのものは後続でもよいが、multi-user安全性のため以下のserver API / routeはP1とする。

例:

```text
POST /api/mcp/servers/{server_name}/oauth/connect
GET  /auth/mcp/oauth/callback
GET  /api/mcp/servers/{server_name}/oauth/status
POST /api/mcp/servers/{server_name}/oauth/disconnect
```

### connect

- UAG Authentication必須
- requestの`IdentityContext.principal_id`をtransactionへbind
- Project/Room memberをremote credential ownerへ変換しない
- Authorization URLを生成しbrowser redirectまたはURLを返す

### callback

- UAG Authentication sessionを再確認
- transaction principalと一致確認
- code exchange
- caller principal scopeへtoken保存
- safeな固定UAG pageへredirect

### status

返してよい情報:

```text
connected: true/false
server_name
resource
remote_display_name（取得できる場合）
expires_at（必要なら）
```

返してはならない情報:

```text
access_token
refresh_token
registration_access_token
client_secret
```

### disconnect

caller principalのtokenだけ削除する。

shared client registrationは通常削除しない。

## LogoutとDisconnect

UAG Web logoutとGitLab disconnectは別操作とする。

```text
UAG logout
  → UAG server-side sessionを破棄
  → GitLab refresh tokenは既定では保持

Disconnect GitLab
  → caller principalのGitLab access/refresh tokenを削除
  → shared client registrationは保持
```

企業ポリシーとしてlogout時credential削除を追加できる余地は残すが、既定動作にはしない。

UAG logoutしたAliceのcredentialをBobが利用できることはない。token所有権はsessionではなくstable `principal_id`に紐付く。

## `mcp_servers` tool変更

`mcp_servers_tool.py`のadd / validateでOAuth設定を扱う。

追加パラメータ候補:

```text
oauth_mode
oauth_client_id
oauth_scope
oauth_callback_mode
oauth_callback_host
oauth_callback_port
oauth_callback_path
oauth_web_redirect_uri
```

validation:

- `pre_registered`で`client_id`なし → error
- `none`で`client_id`指定 → warning
- local callback hostがlocalhost以外 → default deny
- callback port範囲不正 → error
- web callbackがHTTPS以外 → localhost開発用途を除きerror
- `web_redirect_uri`をHost headerから暗黙生成しない
- HTTP MCP + OAuthでURLがHTTPS以外 → localhost以外error
- stdio + oauth object → warningまたはstdio server固有認証として無視

## GitLab固有相互運用

GitLab向けにUAG coreへ特殊分岐は入れないが、以下は相互運用条件として確認する。

### endpoint

```text
https://<gitlab-host>/api/v4/mcp
```

### tool name prefix

対応GitLabでは以下headerを利用できる。

```text
X-Gitlab-Mcp-Server-Tool-Name-Prefix: gitlab_
```

### scope

Pre-registered OAuth ApplicationではGitLab公式手順に従い`mcp` scopeを使用する。

### public client

OAuth ApplicationはConfidentialをOFFにし、UAGはPKCEを必ず送る。

## Security

### Credential isolation

- user tokenはprincipal単位
- registrationはapp/callback profile単位
- Room単位でtokenを保存しない
- project単位でtokenを共有しない
- process-global legacy tokenはmulti-user modeで利用しない
- principalなしのWeb/A2A/background実行はfail closed

### OAuth transaction

- stateはsingle-use
- PKCE S256必須
- transaction TTLを短くする
- callbackでcurrent principal一致を確認
- browser bindingを検証
- open redirect禁止
- callback URLのHost header依存禁止

### Prompt injection

GitLab Issue、MR description、comment、repository fileはすべて外部入力として扱う。

MCP toolが返した文章をsystem instructionとして扱わない。

特に以下の操作は既存UAGの確認・承認ポリシーと統合する。

- commit作成
- branch更新
- MR作成・更新
- comment投稿
- pipeline retry / execution
- merge
- repository file変更

MCP serverがtoolを公開していることと、UAGが無条件実行してよいことを同一視しない。

### Token / credential

- access tokenをログへ出さない
- refresh tokenをログへ出さない
- registration_access_tokenをログへ出さない
- OAuth transactionのcode_verifierをログへ出さない
- authorization URL全体をdebug logへ出す場合もsecret query parameterがないことを保証する
- Token Store / CredentialStoreは共有folderへ置かない
- Git repositoryへcredential storeを置かない

### Network

- OAuth endpointは原則HTTPS
- local callbackのみHTTP localhostを許可
- Web callbackはHTTPSを原則必須
- Proxy環境ではlocal callback向け`NO_PROXY=127.0.0.1,localhost`を推奨
- 企業CAは`MCPHTTPConfig.ca_cert`または`SSL_CERT_FILE`で指定
- `verify=False`をGitLab向けshortcutとして追加しない

### Enterprise policy

既存`enterprise_policy.decide_mcp_server()`をOAuth metadata / registration endpointにも適用できる形へ拡張する。

MCP URLだけallowlistされ、OAuth issuerやregistration endpointが別hostの場合に無条件許可してはならない。

## Error codes

追加候補:

```text
MCP_OAUTH_REQUIRED
MCP_OAUTH_BOOTSTRAP_FAILED
MCP_OAUTH_REAUTH_REQUIRED
MCP_OAUTH_REGISTRATION_UNAVAILABLE
MCP_OAUTH_REGISTRATION_HTTP_ERROR
MCP_OAUTH_REGISTRATION_INVALID_RESPONSE
MCP_OAUTH_CLIENT_ID_MISSING
MCP_OAUTH_CALLBACK_BIND_FAILED
MCP_OAUTH_REDIRECT_URI_MISMATCH
MCP_OAUTH_MODE_INVALID
MCP_OAUTH_PRE_REGISTERED_CLIENT_REQUIRED
MCP_OAUTH_PRINCIPAL_REQUIRED
MCP_OAUTH_PRINCIPAL_MISMATCH
MCP_OAUTH_TRANSACTION_INVALID
MCP_OAUTH_TRANSACTION_EXPIRED
MCP_OAUTH_WEB_REDIRECT_URI_REQUIRED
MCP_OAUTH_LEGACY_CREDENTIAL_UNSAFE
```

内部層はI18Nしない。公開tool / Web API側でユーザー向け文言へ変換する。

## 対象ファイル

### 新規

```text
src/uagent/tools/mcp/oauth_registration.py
src/uagent/tools/mcp/oauth_bootstrap.py
src/uagent/tools/mcp/oauth_transactions.py
src/uagent/tools/mcp/connection.py
```

必要に応じて:

```text
src/uagent/tools/mcp/registration_store.py
src/uagent/tools/mcp/principal_credentials.py
```

### 変更

```text
src/uagent/tools/mcp/oauth_callback.py
src/uagent/tools/mcp/oauth_provider.py
src/uagent/tools/mcp/oauth_authorization.py
src/uagent/tools/mcp/oauth_metadata.py
src/uagent/tools/mcp/client.py
src/uagent/tools/mcp/errors.py
src/uagent/tools/mcp_tools_list_tool.py
src/uagent/tools/handle_mcp_v2_tool.py
src/uagent/tools/mcp_resources_tool.py
src/uagent/tools/mcp_prompts_tool.py
src/uagent/tools/mcp_server_discover_tool.py
src/uagent/tools/mcp_servers_tool.py
src/uagent/web_impl/routes_auth.py または専用routes_mcp_auth.py
src/uagent/runtime/identity_context.py（必要なhelperのみ。provider固有処理は追加しない）
docs/MCP_OAUTH_PROXY_GUIDE.md
docs/MCP_OAUTH_PROXY_GUIDE.ja.md
```

## 実装フェーズ

### Phase 0: mcp-remoteによる実機接続確認

目的はUAG coreを変更せずGitLab側の設定・権限・networkを切り分けること。

- local single-user stdio serverとして`mcp-remote`設定
- `mcp_tools_list`でtools取得
- read-only操作で動作確認
- 社内Proxy / CA / VPN条件を確認

### Phase 1: DCR primitive

- `oauth_registration.py`
- registration endpoint trust検証
- DCR request / response parser
- unit test

MCP接続とはまだ統合しない。

### Phase 2: Callback abstraction + Registration persistence

- local fixed callback
- Web fixed callback profile
- RegistrationStore
- callback profile別redirect URI再利用
- Web canonical redirect URI validation

### Phase 3: Principal-scoped credential + OAuth bootstrap

- principal key / resource key
- local legacy migration
- multi-user legacy credential拒否
- metadata discovery
- client identity選択
- DCR
- browser authorization
- token provider生成
- OAuth transaction

### Phase 4: Connection resolver + Public/Web integration

- `mcp_tools_list`
- `handle_mcp_v2`
- resources
- prompts
- server discovery
- TurnContext principal選択
- Web connect/callback/status/disconnect API
- Room / sub-agent credential isolation

### Phase 5: GitLab interop

- Self-Managed DCR enabled
- Self-Managed DCR disabled + pre_registered
- GitLab.com
- local `mcp-remote` fallback
- Web multi-user Alice/Bob isolation
- Proxy + enterprise CA

## テスト計画

### Unit: DCR

- 201 + valid response
- client_id missing
- invalid JSON
- HTTP 4xx / 5xx
- mismatched redirect URI
- unsupported confidential client
- untrusted registration endpoint

### Unit: callback

Local:

- fixed port bind
- port conflict
- wrong path
- state mismatch
- timeout

Web:

- canonical redirect URI
- non-HTTPS rejection
- Host header spoofingでURLが変わらない
- current principal mismatch
- expired UAG session
- browser binding mismatch
- open redirect rejection

### Unit: principal credential

- Alice/Bob同一resourceで別token
- Alice refreshがBobへ影響しない
- principalなしfail closed
- raw principalをcredential nameへ含めない
- local legacy migration成功
- Webでlegacy process-global token拒否

### Unit: registration store

- save/load
- resource別分離
- callback profile別分離
- tokenとregistration分離
- concurrent access
- corrupt record

### Unit: bootstrap

- stored principal tokenあり
- token expired + caller principal refresh成功
- token expired + refresh失敗
- saved registration + no token
- pre_registered
- dynamic
- auto + DCR unavailable
- `none`
- principal mismatch拒否

### Integration fixture

ローカルfake Authorization Server + fake MCP Serverを利用する。

```text
GET /.well-known/oauth-protected-resource
GET /.well-known/oauth-authorization-server
POST /oauth/register
GET /oauth/authorize
POST /oauth/token
POST /mcp
```

最低限次を再現する。

- 初回MCP request → 401
- DCR
- PKCE authorization
- token exchange
- tools/list成功
- access token expiry
- refresh
- tools/call再成功

### Web multi-user integration

最低限次をテストする。

```text
Alice UAG login
 → GitLab OAuth
 → Alice token保存

Bob UAG login
 → Alice tokenを参照できない
 → 未接続状態
 → GitLab OAuth
 → Bob token保存

Alice turn in shared Room
 → Alice token

Bob turn in same Room
 → Bob token

Alice logout
 → Alice GitLab tokenは保持
 → Bobへ露出しない

Alice disconnect
 → Alice tokenのみ削除
 → Bob tokenは維持
```

### Regression

- OAuthなしHTTP MCP
- header tokenを手動指定したHTTP MCP
- stdio MCP
- legacy initialize
- stateless `server/discover`
- local existing `mcp/<resource>` credential
- Proxy / CA configuration
- CLI / GUI current flow
- Web Authentication / Memory V3 principal resolution

### GitLab manual interop

通常CIでは公開GitLabや社内GitLabへ接続しない。

| 環境 | DCR | Entry point | Expected |
|---|---:|---|---|
| GitLab Self-Managed 18.6+ | on | CLI | OAuth + tools/list |
| GitLab Self-Managed 18.6+ | on | Web | principal-scoped OAuth + tools/list |
| GitLab Self-Managed 19.3+ | off | Web + pre_registered | principal-scoped OAuth + tools/list |
| GitLab.com | on | CLI/Web | OAuth + tools/list |
| GitLab | on | local mcp-remote | OAuth + tools/list |
| 社内GitLab + Proxy | on/off | CLI/Web | metadata/token/MCP全経路成功 |
| 社内GitLab + enterprise CA | on/off | CLI/Web | TLS verify成功 |

## 受け入れ条件

### P1必須

- GitLab `/api/v4/mcp`へNode.jsなしで接続できる。
- DCR有効環境で初回browser OAuthから`tools/list`まで完了できる。
- DCR無効環境でpre-registered `client_id`を利用できる。
- PKCE S256を常に使用する。
- callback URIがregistrationと一致する。
- localとWebでcallback strategyを分離できる。
- Web callbackはUAG serverの固定HTTPS routeを利用する。
- Web callbackでUAG current principalとOAuth transaction principalを照合する。
- client registrationをcallback profile単位で再利用できる。
- access token / refresh tokenを`principal_id`単位で分離する。
- Shared Roomでもcredentialを共有しない。
- sub-agentはparent turn principalだけを継承する。
- principal不明のWeb/background処理がglobal tokenへfallbackしない。
- local modeのみlegacy credential migrationを許可する。
- access token expiry後にcaller principalのrefresh tokenだけでrefreshできる。
- refresh失敗時に無限再試行しない。
- OAuth bootstrap前の`server/discover` 401で誤ってLegacy判定しない。
- GitLab以外のOAuth MCP serverでも利用できる汎用実装になっている。
- token / client registration secret / code_verifierをログへ出さない。
- Proxy / CA設定がOAuth metadata、registration、token、MCPの全HTTP経路で共通利用される。
- UAG logoutとGitLab disconnectを分離する。
- stdio / OAuthなしHTTP MCPを壊さない。

### P2候補

- Web UIで接続状態を視覚的に管理
- registration削除
- remote token revoke
- 複数callback profile UI
- headless device flow等の代替認証
- OAuth client管理画面
- per-server tool allowlist
- GitLab toolset selection UI
- enterprise policyによるlogout時credential purge

Web UIはP2でもよいが、Web multi-userでのcredential isolation、callback API、connect/disconnect APIはP1必須とする。

## 運用方針

### 社内GitLab

推奨順:

1. UAGを社内LAN / VPN内へ配置
2. Native HTTP MCP
3. 企業管理下ではpre-registered OAuth Applicationを優先検討
4. Webでは固定HTTPS callback URIをGitLabへ登録
5. CLI/GUIでは固定localhost callback
6. Proxy / CAをUAG側で正式設定
7. GitLab側権限は最小権限
8. write操作はUAG側の承認ポリシーを併用

### Web multi-user

- UAG Identity providerはOIDC / AD / trusted proxy等から独立して扱う。
- MCP OAuth層は`principal_id`だけを信頼境界として受け取る。
- tokenはRoom / Project / processではなくprincipal ownershipとする。
- remote GitLab identityとUAG principalの自動マッピングを行わない。

### クラウドLLM利用時

GitLab自体を社内ネットワーク内へ閉じても、UAGがクラウドLLMを利用する場合は、LLM判断に必要なrepository / MR / Issue情報がLLM providerへ送信される可能性がある。

そのため、GitLab network boundaryとLLM data boundaryを別問題として管理する。

完全社内化が必要な場合は、UAG + GitLab + local/private LLMの構成を利用する。

## 実装時の判断事項

1. local callback既定portを8765で固定するか、UAG専用port rangeを採用するか。
2. Web canonical redirect URIを`mcp_servers.json`に置くか専用env/configへ分離するか。
3. RegistrationStoreを独立fileにするか、CredentialStore abstractionへ統合するか。
4. Principal-scoped credential key helperをMCP専用にするかauth共通へ昇格するか。
5. Web OAuth transaction storeをin-memoryのみとするかmulti-worker対応backendを先に用意するか。
6. browserを開けないheadless環境をP1に含めるか。
7. DCR registration deletion / remote token revokeをP1に含めるか。
8. `mcp_servers.json`の`oauth` objectを`mcp_servers_tool`でどの粒度まで編集可能にするか。

## 推奨PR分割

大きな1PRにしない。5 PR構成を維持するが、Web Authenticationとの境界を各PRへ前倒しする。

```text
PR 1: feat(mcp): add OAuth dynamic client registration primitive
PR 2: feat(mcp): add callback profiles and persist client registrations
PR 3: feat(mcp): add principal-scoped OAuth credentials and bootstrap
PR 4: feat(mcp): integrate connection resolver with public tools and Web OAuth routes
PR 5: docs/test: add GitLab MCP multi-user interoperability guide and tests
```

### PR 1

- DCR primitive
- endpoint trust / enterprise policy
- unit tests
- user token保存には触れない

### PR 2

- local/Web callback abstraction
- callback profile
- registration persistence
- canonical Web redirect URI validation

### PR 3

- principal-scoped token naming
- safe local legacy migration
- OAuth transaction
- bootstrap
- refresh isolation

このPRでmulti-user credential boundaryを完成させる。

### PR 4

- TurnContext principalをconnection resolverへ接続
- public MCP tools統合
- Web connect/callback/status/disconnect route
- Shared Room / sub-agent isolation

### PR 5

- GitLab interop fixture
- Alice/Bob multi-user tests
- Proxy / enterprise CA manual guide
- current OAuth guide更新

各PRでBlack / Ruff / pytestを通してから次へ進む。

## 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-09-23 | 初版。GitLab MCPを主要ユースケースとした汎用MCP OAuth DCR / pre-registered client設計を追加 |
| 2026-09-23 | Web Authentication統合を追加。`principal_id`単位credential分離、Web callback、OAuth transaction、Room/sub-agent境界、logout/disconnect分離をP1へ追加 |
