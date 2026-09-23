# GitLab MCP / OAuth連携設計

- Status: planned
- Priority: P1
- Source: GitLab公式MCP Server仕様、UAG現行MCP/OAuth実装
- Survey date: 2026-09-23
- Target baseline: UAG `0.7.13` / `main` commit `e7a25540a2931383f43652af73d9824ef7b66ffe`

## 目的

UAGからGitLab.comおよびGitLab Self-Managed / DedicatedのGitLab MCP Serverへ安全に接続し、Issue、Merge Request、Repository、Pipeline等のGitLab機能をMCP toolとして利用できるようにする。

GitLab専用REST toolを大量に追加するのではなく、UAGの汎用MCP OAuth機能を完成させることでGitLabを最初の主要ユースケースとして対応する。

特に社内GitLabでは、UAGを社内LANまたはVPN内で実行し、GitLabをインターネットへ公開せずに接続できる構成を主要対象とする。

## 背景

GitLab公式MCP Serverは以下のエンドポイントを提供する。

```text
https://<gitlab-host>/api/v4/mcp
```

GitLab公式ドキュメントではHTTP transportが推奨されている。HTTP transportはGitLab 18.6で導入された。stdio経路では`mcp-remote`を利用できる。

GitLab MCP ServerはOAuth 2.0 Dynamic Client Registration（DCR）に対応し、初回接続時にクライアントを自動登録できる。また、管理者がDCRを無効化した環境や共有クライアント運用では、事前登録済みOAuth Applicationの`clientId`を利用できる。

GitLab 19.3ではSelf-Managed / DedicatedでDCRを無効化する管理設定が導入され、無効化時は事前登録済みOAuth Applicationが必要になる。

GitLab公式仕様の参照先:

- https://docs.gitlab.com/user/model_context_protocol/mcp_server/
- https://docs.gitlab.com/user/model_context_protocol/mcp_server_tools/
- https://docs.gitlab.com/administration/settings/account_and_limit_settings/

## 現行UAGの状態

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

## 非目標

本計画では以下を直接の対象にしない。

- GitLab REST APIを網羅する専用`gitlab_*_tool.py`群の実装
- GitLabのユーザー認証そのものをUAGのログイン方式として利用すること
- GitLab RunnerやGitLab Serverの管理者操作を自動化すること
- GitLabの権限をUAG側で拡張・迂回すること
- GitLabのアクセス権限を独自キャッシュしてGitLab ACLより優先すること
- LLMへ送信する情報の組織ポリシーを自動決定すること

GitLab側のユーザー権限が最終的な認可境界であり、UAGはそれを越えるアクセスを行わない。

## 設計原則

### 1. GitLab専用認証にしない

DCR、pre-registered client、PKCE、OAuth metadata discoveryはMCP共通機能として実装する。

```text
src/uagent/tools/mcp/
  oauth_registration.py
  oauth_bootstrap.py
  oauth_provider.py
  oauth_metadata.py
  oauth_authorization.py
```

GitLab固有処理は、必要最小限の相互運用テスト・ドキュメント・推奨設定に限定する。

### 2. OAuth bootstrapをprotocol detectionより前に置く

未認証MCP serverでは401はLegacy判定材料ではなく認証要求である。

したがって、次の順序とする。

```text
resolve server config
      ↓
create HTTP client
      ↓
OAuth state / stored credential確認
      ↓
必要ならOAuth bootstrap
      ↓
認証済みHTTP client / authorization_provider生成
      ↓
MCP protocol detection
      ↓
server/discover or initialize
      ↓
tools/list / tools/call
```

401を単純にLegacy fallback対象へ追加してはならない。

### 3. 認証方式を明示する

OAuth設定は次の4モードを定義する。

- `none`: OAuthを使用しない
- `auto`: 保存済みregistration → preconfigured client → CIMD → DCRの順に利用可能な方式を選択
- `dynamic`: DCRを必須とする
- `pre_registered`: 設定された`client_id`のみ利用する

将来CIMDのみを強制する必要が出た場合は`cimd`を追加可能とするが、初期実装では`auto`内の選択肢として扱う。

### 4. Node.js依存はfallbackに限定する

`mcp-remote`は動作確認・互換fallbackとしてサポートするが、最終形はUAGネイティブHTTP + OAuthとする。

## 全体構成

```text
┌──────────────────────────────┐
│ UAG                          │
│                              │
│ mcp_tools_list               │
│ handle_mcp_v2                │
│ mcp_resources                │
│ mcp_prompts                  │
│              │               │
│              ▼               │
│        MCPConnectionResolver │
│              │               │
│              ▼               │
│        MCPOAuthBootstrap     │
│         │          │         │
│         │          └─ DCR    │
│         │                    │
│         ▼                    │
│      MCPClient               │
└─────────┬────────────────────┘
          │ HTTPS / MCP
          ▼
┌──────────────────────────────┐
│ GitLab Self-Managed          │
│                              │
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
start localhost callback listener
 ↓
POST registration_endpoint
 ↓
client_id取得
 ↓
browser authorization + PKCE
 ↓
token exchange
 ↓
registration + token保存
 ↓
MCP接続
```

GitLabでDCRが有効な場合に利用する。

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
browser authorization + PKCE
 ↓
MCP接続
```

DCRが無効なSelf-Managed環境、共有egress IPによるDCR rate limitを避けたい環境、OAuth Applicationを管理者が統制したい環境で利用する。

### C. stdio + mcp-remote

移行・互換fallback。

```text
UAG
 ↓ stdio
npx mcp-remote
 ↓ HTTPS/OAuth
GitLab MCP
```

Node.js 20+が必要。UAG本体のOAuth実装に問題がある場合の切り分けにも利用できる。

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
        "callback_host": "127.0.0.1",
        "callback_port": 8765,
        "callback_path": "/callback"
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
        "callback_host": "127.0.0.1",
        "callback_port": 8765,
        "callback_path": "/callback"
      }
    }
  ]
}
```

### `mcp-remote`

```json
{
  "mcp_servers": [
    {
      "name": "company-gitlab-remote",
      "transport": "stdio",
      "protocol_mode": "auto",
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://gitlab.company.local/api/v4/mcp"
      ],
      "env": {}
    }
  ]
}
```

## OAuth設定schema

初期実装では以下を許可する。

```text
oauth.mode                none | auto | dynamic | pre_registered
oauth.client_id           optional string
oauth.scope               optional string
oauth.callback_host       default 127.0.0.1
oauth.callback_port       default 8765
oauth.callback_path       default /callback
oauth.authorization_timeout default 300
oauth.allow_browser       default true
```

`client_secret`は初期実装では設定schemaへ入れない。MCP public client + PKCEを標準とし、secretが必要なconfidential client対応は別計画とする。

## callback URI設計

### 問題

現行`OAuthCallbackListener`は`port=0`でランダムポートを利用する。

DCRで登録したOAuth clientを再利用する場合、登録済み`redirect_uri`と次回のauthorization requestの`redirect_uri`が一致する必要がある。毎回ランダムポートを選ぶと、保存済み`client_id`を対話再認証時に安全に再利用できない。

### 方針

MCP OAuthでは固定callback portを既定とする。

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

### port競合時

- `pre_registered`では別ポートへ自動変更しない。登録済みredirect URIとの不一致を避けるため、構造化エラーを返す。
- `dynamic` / `auto`で未登録の場合は、設定で`callback_port=0`が明示された場合のみephemeral portを許可する。
- ephemeral portでDCRしたregistrationは、次の対話再認証時に同じredirect URIを再利用できない可能性があることを記録する。
- 企業利用では固定portまたはpre-registered clientを推奨する。

## Dynamic Client Registration

### 新規モジュール

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

送信内容の基本形:

```json
{
  "client_name": "UAG",
  "redirect_uris": ["http://127.0.0.1:8765/callback"],
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none"
}
```

scopeはAuthorization Server / Protected Resource Metadataの対応状況を確認して設定する。GitLab向け既定値は`mcp`とするが、汎用MCPコードではGitLab固有値をハードコードしない。

### DCR応答検証

最低限以下を検証する。

- `client_id`が空でない
- `redirect_uris`が返る場合、要求したURIが含まれる
- `token_endpoint_auth_method`が未指定なら`none`として扱う
- confidential clientを要求する応答は初期実装では拒否する
- registration endpointはissuer trust境界を満たす

## Registration Store

Tokenとclient registrationはライフサイクルが異なるため、論理上分離する。

新規抽象:

```text
MCPRegistrationStore
```

初期実装は既存`CredentialStore`をバックエンドとして利用する。

推奨name:

```text
mcp-registration/<resource-key>
```

`CredentialKind.MCP`を利用する。

保存項目:

```text
client_id
issuer
resource
redirect_uri
token_endpoint_auth_method
registration_client_uri
created_at
```

`registration_access_token`がある場合はsecretとして保存する。ない場合はclient_idをsecret slotへ格納し、metadataにもclient_idを保持する。

アクセストークン本体は従来通り`CredentialKind.OAUTH_TOKEN`として別レコードに保存する。

### resource key

生URLをcredential nameへ直接埋め込む方式は将来のstore差異を避けるため使用せず、正規化resource URLのSHA-256短縮値を用いる。

```text
mcp-registration/sha256-<hex>
mcp-token/sha256-<hex>
```

既存`mcp/<resource>` credentialは後方互換の読み取りを残し、新形式へlazy migrationする。

## OAuth Bootstrap

新規モジュール:

```text
src/uagent/tools/mcp/oauth_bootstrap.py
```

責務:

1. MCP server configからOAuth modeを解決
2. 保存済みtokenを確認
3. 保存済みregistrationを確認
4. Protected Resource Metadata取得
5. Authorization Server Metadata取得
6. client identityを決定
7. 必要ならDCR
8. 必要ならbrowser authorization
9. `OAuthTokenProvider`を生成
10. MCPClientへ渡す

想定API:

```python
@dataclass
class MCPOAuthContext:
    provider: OAuthTokenProvider
    issuer: str
    resource: str
    client_id: str
    redirect_uri: str | None

async def resolve_mcp_oauth_context(
    *,
    resource_url: str,
    oauth_config: dict[str, Any],
    http_client: Any,
    credential_store: CredentialStore,
) -> MCPOAuthContext | None:
    ...
```

## Client identity選択順序

`oauth.mode="auto"`では次の順序とする。

```text
1. 保存済みMCPRegistrationStore
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

1. refresh tokenがあれば1回だけrefresh
2. refresh成功なら同じMCP requestを1回だけ再送
3. refresh失敗またはrefresh tokenなしなら`MCP_OAUTH_REAUTH_REQUIRED`
4. public tool側でinteractive authorizationが許可されていれば再認証へ誘導
5. 無限401 loopは禁止

現行`OAuthTokenProvider`の1回refresh方針を維持する。

## MCPClient変更

現行`MCPClient`はtransportとprotocol detectionに集中させる。

OAuth bootstrapそのものを`MCPClient.__aenter__()`へ直接詰め込まず、connection resolver層で認証済みproviderを準備して注入する。

ただし、明示的に`authorization_provider`が渡された場合の既存動作は維持する。

推奨境界:

```text
public tool
  ↓
resolve_mcp_connection()
  ↓
resolve_mcp_oauth_context()
  ↓
MCPClient(... authorization_provider=...)
```

## Connection Resolver

複数public toolに重複する以下を共通化する。

- `mcp_servers.json`読込
- server_name解決
- URL / command / args / env解決
- headers環境変数展開
- protocol_mode解決
- OAuth config解決
- Proxy / CA config解決

候補:

```text
src/uagent/tools/mcp/connection.py
```

主な型:

```python
@dataclass(frozen=True)
class MCPConnectionConfig:
    name: str | None
    url: str | None
    command: str | None
    args: tuple[str, ...]
    env: dict[str, str]
    headers: dict[str, str]
    protocol_mode: str
    oauth: MCPOAuthConfig | None
    http_config: MCPHTTPConfig | None
```

## `mcp_servers` tool変更

`mcp_servers_tool.py`のadd / validateでOAuth設定を扱う。

追加パラメータ候補:

```text
oauth_mode
oauth_client_id
oauth_scope
oauth_callback_host
oauth_callback_port
oauth_callback_path
```

ただし公開toolの引数肥大化を避けるため、将来的には`oauth` objectをそのまま受け取れるschemaへ移行してよい。

validation:

- `pre_registered`で`client_id`なし → error
- `none`で`client_id`指定 → warning
- callback hostがlocalhost以外 → default deny
- callback port範囲不正 → error
- HTTP MCP + OAuthでURLがHTTPS以外 → localhost以外error
- stdio + oauth object → warningまたはstdio server固有認証として無視

## GitLab固有相互運用

GitLab向けにUAG coreへ特殊分岐は入れないが、以下は公式相互運用仕様としてテストする。

### endpoint

```text
https://<gitlab-host>/api/v4/mcp
```

### tool name prefix

GitLab 18.11以降では以下headerを利用できる。

```text
X-Gitlab-Mcp-Server-Tool-Name-Prefix: gitlab_
```

これは複数GitLab instanceまたは他MCP serverとのtool名衝突回避に有効。

### scope

Pre-registered OAuth ApplicationではGitLab公式手順に従い`mcp` scopeを使用する。

### public client

OAuth ApplicationはConfidentialをOFFにし、UAGはPKCEを必ず送る。

GitLabがpre-registered applicationでPKCEを強制しない場合でも、UAG側ではPKCEを省略しない。

## Security

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
- authorization URL全体をdebug logへ出す場合もsecret query parameterがないことを保証する
- Token Store / CredentialStoreは共有folderへ置かない
- Git repositoryへcredential storeを置かない

### Network

- OAuth endpointは原則HTTPS
- localhost callbackのみHTTP許可
- Proxy環境では`NO_PROXY=127.0.0.1,localhost`を推奨
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
```

内部層はI18Nしない。公開tool側でユーザー向け文言へ変換する。

## 対象ファイル

### 新規

```text
src/uagent/tools/mcp/oauth_registration.py
src/uagent/tools/mcp/oauth_bootstrap.py
src/uagent/tools/mcp/connection.py
```

必要に応じて:

```text
src/uagent/tools/mcp/registration_store.py
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
docs/MCP_OAUTH_PROXY_GUIDE.md
docs/MCP_OAUTH_PROXY_GUIDE.ja.md
```

## 実装フェーズ

### Phase 0: mcp-remoteによる実機接続確認

目的はUAG coreを変更せずGitLab側の設定・権限・networkを切り分けること。

- stdio serverとして`mcp-remote`設定
- `mcp_tools_list`でtools取得
- read-only操作で動作確認
- 社内Proxy / CA / VPN条件を確認

これは最終実装の必須依存ではないが、実GitLab検証では先に実施する。

### Phase 1: DCR primitive

- `oauth_registration.py`
- registration endpoint trust検証
- DCR request / response parser
- unit test

MCP接続とはまだ統合しない。

### Phase 2: callback固定port + registration persistence

- `OAuthCallbackListener(port=...)`
- RegistrationStore
- redirect URI再利用
- legacy credential lazy migration

### Phase 3: OAuth bootstrap

- metadata discovery
- client identity選択
- DCR
- browser authorization
- token provider生成

### Phase 4: connection resolver統合

- `mcp_tools_list`
- `handle_mcp_v2`
- resources
- prompts
- server discovery

で同じOAuth connection pathを利用する。

### Phase 5: GitLab実機interop

- Self-Managed DCR enabled
- Self-Managed DCR disabled + pre_registered
- GitLab.com
- `mcp-remote` fallback
- Proxy + enterprise CA

## テスト計画

### Unit

#### DCR

- 201 + valid response
- client_id missing
- invalid JSON
- HTTP 4xx / 5xx
- mismatched redirect URI
- unsupported confidential client
- untrusted registration endpoint

#### callback

- fixed port bind
- port conflict
- wrong path
- state mismatch
- timeout

#### registration store

- save/load
- resource別分離
- tokenとregistration分離
- concurrent access
- corrupt record

#### bootstrap

- stored tokenあり
- token expired + refresh成功
- token expired + refresh失敗
- saved registration + no token
- pre_registered
- dynamic
- auto + DCR unavailable
- `none`

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

### Regression

- OAuthなしHTTP MCP
- header tokenを手動指定したHTTP MCP
- stdio MCP
- legacy initialize
- stateless `server/discover`
- existing `mcp/<resource>` credential
- Proxy / CA configuration

### GitLab manual interop

通常CIでは公開GitLabや社内GitLabへ接続しない。

手動検証表:

| 環境 | DCR | Transport | Expected |
|---|---:|---|---|
| GitLab Self-Managed 18.6+ | on | HTTP | OAuth + tools/list |
| GitLab Self-Managed 19.3+ | off | HTTP + pre_registered | OAuth + tools/list |
| GitLab.com | on | HTTP | OAuth + tools/list |
| GitLab | on | mcp-remote | OAuth + tools/list |
| 社内GitLab + Proxy | on/off | HTTP | metadata/token/MCP全経路成功 |
| 社内GitLab + enterprise CA | on/off | HTTP | TLS verify成功 |

## 受け入れ条件

### P1必須

- GitLab `/api/v4/mcp`へNode.jsなしで接続できる。
- DCR有効環境で初回browser OAuthから`tools/list`まで完了できる。
- DCR無効環境でpre-registered `client_id`を利用できる。
- PKCE S256を常に使用する。
- callback URIがregistrationと一致する。
- client registrationを再利用できる。
- access token expiry後にrefreshできる。
- refresh失敗時に無限再試行しない。
- OAuth bootstrap前の`server/discover` 401で誤ってLegacy判定しない。
- GitLab以外のOAuth MCP serverでも利用できる汎用実装になっている。
- token / client registration secretをログへ出さない。
- Proxy / CA設定がOAuth metadata、registration、token、MCPの全HTTP経路で共通利用される。
- stdio / OAuthなしHTTP MCPを壊さない。

### P2候補

- Web UIからMCP OAuth接続・切断
- registration削除
- token revoke
- 複数callback profile
- headless device flow等の代替認証
- OAuth client管理画面
- per-server tool allowlist
- GitLab toolset selection UI

## 運用方針

### 社内GitLab

推奨順:

1. UAGを社内LAN / VPN内へ配置
2. Native HTTP MCP
3. 企業管理下ではpre-registered OAuth Applicationを優先検討
4. UAG callback URIを固定
5. Proxy / CAをUAG側で正式設定
6. GitLab側権限は最小権限
7. write操作はUAG側の承認ポリシーを併用

### クラウドLLM利用時

GitLab自体を社内ネットワーク内へ閉じても、UAGがクラウドLLMを利用する場合は、LLM判断に必要なrepository / MR / Issue情報がLLM providerへ送信される可能性がある。

そのため、GitLab network boundaryとLLM data boundaryを別問題として管理する。

完全社内化が必要な場合は、UAG + GitLab + local/private LLMの構成を利用する。

## 実装時の判断事項

実装PR着手時に以下を最終決定する。

1. callback既定portを8765で固定するか、UAG専用port rangeを採用するか。
2. RegistrationStoreを独立fileにするか、CredentialStore abstractionへ統合するか。
3. `mcp_servers.json`の`oauth` objectを`mcp_servers_tool`でどの粒度まで編集可能にするか。
4. browserを開けないheadless環境をP1に含めるか。
5. DCR registration deletion / revokeをP1に含めるか。
6. existing `mcp/<resource>` credentialをいつ新しいresource-key形式へ移行するか。

## 推奨PR分割

大きな1PRにしない。

```text
PR 1: feat(mcp): add OAuth dynamic client registration primitive
PR 2: feat(mcp): persist client registrations and fixed OAuth callback
PR 3: feat(mcp): add OAuth bootstrap and connection resolver
PR 4: feat(mcp): wire OAuth config into public MCP tools
PR 5: docs/test: add GitLab MCP interoperability guide and tests
```

各PRでBlack / Ruff / pytestを通してから次へ進む。

## 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-09-23 | 初版。GitLab MCPを主要ユースケースとした汎用MCP OAuth DCR / pre-registered client設計を追加 |
