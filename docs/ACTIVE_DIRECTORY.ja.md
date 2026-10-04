# Active Directory / Windows認証 導入ガイド

Status: **現行main向け deployment guide**

この文書では、uag Webを社内のActive Directory（AD）環境へ接続する具体的な方法を説明します。

uagはADのユーザー名・パスワードを直接受け取る独自ログインを持ちません。オンプレミスADでは、**IISまたは社内の認証済みreverse proxyでWindows Integrated Authentication（Kerberos / Negotiate）を終端し、検証済みのstable subjectをuagの `trusted_proxy` identity modeへ渡す構成**を推奨します。

設計上の背景とsecurity invariantは [UAG Memory Architecture V3](UAG_MEMORY_ARCHITECTURE_V3.md)、authenticated Web全般は [Web認証とMemory](WEB_IDENTITY_MEMORY.ja.md) を参照してください。

---

## 1. 推奨構成

推奨production構成は、**Windows認証を終端するproxy hostとuag backend hostを分離**します。

```text
Domain joined browser / Windows client
        |
        | HTTPS
        v
uag-proxy01.corp.example (10.30.40.10)
IIS + Windows Authentication + auth bridge
        |
        | X-Verified-Subject: <SID or other stable subject>
        | X-Verified-Issuer: corp-ad
        | TCP 8000 allowed only from 10.30.40.10
        v
uag-app01.corp.example (10.30.40.20:8000)
        |
        v
TrustedProxyIdentityResolver
        |
        v
opaque principal_id
```

重要な点:

- browserが `X-Verified-Subject` を自由に指定できてはいけません。
- proxyは外部入力のidentity headerを削除し、**Windows認証後に自分で再付与**します。
- uagはproxyの接続元CIDRを検証します。
- uag backendはprivate backend networkだけにbindし、Windows Firewall / network ACLでproxy hostのIPだけを許可します。
- **loopback (`127.0.0.1`) をproductionのidentity trust boundaryにしません。** 同一ホストの全プロセスがloopbackへ接続できるため、uagのローカル実行機能を使える非admin userがidentity headerを偽装できる可能性があります。
- `DOMAIN\username`、UPN、email、display nameはrename可能なので、Memory ownerのstable keyとして直接使いません。
- 本ガイドではWindows SIDをstable subjectとして利用します。組織のforest migration等でSID変更が問題になる場合は、認証ブリッジ側でobjectGUID等のimmutable IDを採用してください。

開発・単一利用者の検証では同一ホストloopback構成も可能ですが、**untrusted multi-user productionのbaselineにはしません**。同一ホストで本番化する場合は、process-authenticated IPC等、別の信頼境界を実装してから利用してください。

---

## 2. 現在実装済みの範囲

現行uagでは以下が実装済みです。

- `UAGENT_IDENTITY_MODE=trusted_proxy`
- `TrustedProxyIdentityResolver`
- trusted source CIDR検証
- identity / issuer headerの必須検証
- `issuer + subject` からopaque `principal_id` を生成
- browser/model payloadからownerを指定できないMemory V3境界
- Project / Room membership authorization
- `UAGENT_ADMIN_PRINCIPALS` によるglobal admin
- custom enterprise identity verifier interface
- `windows_ad` resolver interface

一方、以下は**現時点でbuilt-inの完成済みdeploymentではありません**。

- IISのWindows認証をuagが直接終端する機能
- built-inのKerberos / Negotiate verifier
- SPN設定を含むdirect `windows_ad` adapter
- `trusted_proxy` headerからAD groupを直接取り込むbuilt-in機能
- on-prem AD group membershipのlive refresh

したがって、現時点の実運用では **Windows認証を別ホストのIIS/bridgeで終端し、firewallで到達元をそのproxy hostに限定したうえで `trusted_proxy` へ渡す方式**を推奨します。

---

## 3. 前提

例として次の構成を使用します。

```text
AD DNS domain        : corp.example
uag公開URL           : https://uag.corp.example/
IIS / auth bridge    : uag-proxy01.corp.example / 10.30.40.10
uag backend          : uag-app01.corp.example / 10.30.40.20:8000
identity issuer      : corp-ad
identity header      : X-Verified-Subject
issuer header        : X-Verified-Issuer
```

必要なもの:

1. AD参加済みWindows Server（IIS / auth bridge用）
2. IIS
3. IIS Windows Authentication role service
4. IIS WebSocket Protocol role service
5. HTTPS証明書
6. ASP.NET Core Hosting Bundle
7. .NET SDK（bridgeをbuildする場合）
8. 別ホストのuag backend
9. YARP (`Yarp.ReverseProxy`) を使った小さな認証bridge

IIS Windows AuthenticationはIISの標準機能です。Windows Authenticationを利用する場合、IIS側でAnonymous Authenticationを無効にし、Windows Authenticationを有効にします。

Microsoft reference:

- https://learn.microsoft.com/en-us/iis/configuration/system.webserver/security/authentication/windowsauthentication/
- https://learn.microsoft.com/aspnet/core/security/authentication/windowsauth

---

## 4. uag backendを専用hostで起動する

uag backendはpublic/LAN一般へ公開せず、proxyと通信するprivate backend interfaceだけにbindします。

例ではuag hostを `10.30.40.20`、proxy hostを `10.30.40.10` とします。

`.env` 例:

```env
UAGENT_WEB_HOST=10.30.40.20

UAGENT_IDENTITY_MODE=trusted_proxy
UAGENT_TRUSTED_PROXY_IDENTITY_HEADER=X-Verified-Subject
UAGENT_TRUSTED_PROXY_ISSUER_HEADER=X-Verified-Issuer
UAGENT_TRUSTED_PROXY_CIDRS=10.30.40.10/32
UAGENT_WEB_ALLOWED_ORIGINS=https://uag.corp.example

UAGENT_MEMORY_BACKEND=sqlite
UAGENT_MEMORY_PROJECT=agentcli
```

uag Webのportは現行実装では `8000` です。

起動:

```powershell
uagw
```

backend確認はproxy hostからのみ行います。

```text
http://10.30.40.20:8000/
```

productionではこのbackend URLを利用者へ公開しないでください。

### Firewall / network boundary

uag host側でTCP/8000への到達元を `10.30.40.10` のみに限定します。Windows Firewallやnetwork ACLの両方を利用できる場合は両方で制限してください。

uag host自身や一般client subnetからTCP/8000へ接続しても、`TrustedProxyIdentityResolver` のsource CIDRを満たさない構成にします。

identity headerはbackend networkを通るため、proxy-uag間はisolated networkを使い、必要に応じてIPsec等のauthenticated/encrypted transportを追加してください。

`0.0.0.0/0` および `::/0` はuag側でtrusted proxy CIDRとして拒否されます。

---

## 5. IISでWindows Authenticationを有効にする

Windows Serverの「Add Roles and Features」で次を追加します。

```text
Web Server (IIS)
  Web Server
    Security
      Windows Authentication
    Application Development
      WebSocket Protocol
```

対象site/applicationのIIS Managerで:

```text
Authentication
  Anonymous Authentication : Disabled
  Windows Authentication   : Enabled
```

Windows Authentication providerは通常:

```text
Negotiate
NTLM
```

の順で開始します。

Kerberosを強制したい場合やcustom service accountを利用する場合はSPN、kernel mode、delegation等の設計が別途必要です。まず本ガイドではIISでWindows identityが正常に取得できることを先に確認してください。

### IISだけで `DOMAIN\username` をheaderへコピーしない

IIS URL Rewrite等で `AUTH_USER` / `LOGON_USER` をそのまま `X-Verified-Subject` に設定する構成は推奨しません。

理由:

- usernameはrename可能
- UPNも変更可能
- domain migrationで表現が変わる
- uagのMemory V3設計ではstable subjectをownership keyの入力にする

そのため、次章のbridgeでWindows identityからSIDを取得してuagへ渡します。

---

## 6. Windows認証bridgeを作る

### 6.1 project作成

Windows Server上で:

```powershell
dotnet new web -n UagAdBridge
cd UagAdBridge
dotnet add package Yarp.ReverseProxy
```

YARPはHTTPだけでなくWebSocket proxyも扱えるため、uag Web UIのWebSocket接続も同じbridgeを通せます。

Microsoft reference:

- https://learn.microsoft.com/aspnet/core/fundamentals/servers/yarp/transforms
- https://learn.microsoft.com/aspnet/core/fundamentals/servers/yarp/transforms-request

### 6.2 `Program.cs`

`Program.cs` 全体を次に置き換えます。

```csharp
using System.Security.Claims;
using System.Security.Principal;
using Yarp.ReverseProxy.Transforms;

var builder = WebApplication.CreateBuilder(args);

var issuer = builder.Configuration["UagIdentityIssuer"];
if (string.IsNullOrWhiteSpace(issuer))
{
    throw new InvalidOperationException(
        "UagIdentityIssuer must be configured.");
}

builder.Services
    .AddReverseProxy()
    .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"))
    .AddTransforms(builderContext =>
    {
        // UAG's trusted_proxy resolver uses request.client.host as its
        // source boundary. Do not let forwarded client-address headers
        // rewrite that boundary on the backend request.
        builderContext.UseDefaultForwarders = false;

        builderContext.AddRequestTransform(transformContext =>
        {
            var httpContext = transformContext.HttpContext;
            var proxyRequest = transformContext.ProxyRequest;

            // Never forward caller-supplied identity or forwarding headers.
            proxyRequest.Headers.Remove("X-Verified-Subject");
            proxyRequest.Headers.Remove("X-Verified-Issuer");
            proxyRequest.Headers.Remove("X-Forwarded-For");
            proxyRequest.Headers.Remove("X-Forwarded-Host");
            proxyRequest.Headers.Remove("X-Forwarded-Proto");
            proxyRequest.Headers.Remove("X-Forwarded-Prefix");
            proxyRequest.Headers.Remove("Forwarded");

            string? subject = null;

            if (httpContext.User.Identity is WindowsIdentity windowsIdentity)
            {
                subject = windowsIdentity.User?.Value;
            }

            subject ??= httpContext.User
                .FindFirst(ClaimTypes.PrimarySid)
                ?.Value;

            if (!(httpContext.User.Identity?.IsAuthenticated ?? false) ||
                string.IsNullOrWhiteSpace(subject))
            {
                httpContext.Response.StatusCode = StatusCodes.Status401Unauthorized;
                return ValueTask.CompletedTask;
            }

            proxyRequest.Headers.TryAddWithoutValidation(
                "X-Verified-Subject",
                subject);

            proxyRequest.Headers.TryAddWithoutValidation(
                "X-Verified-Issuer",
                issuer);

            return ValueTask.CompletedTask;
        });
    });

var app = builder.Build();

app.Use(async (context, next) =>
{
    if (!(context.User.Identity?.IsAuthenticated ?? false))
    {
        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        return;
    }

    await next();
});

app.MapReverseProxy();

app.Run();
```

このbridgeは次を保証します。

- IISで認証されていないrequestはuagへ流さない
- browserが送った `X-Verified-Subject` を削除
- browserが送った `X-Verified-Issuer` を削除
- forwarding headerをbackendへ渡さない
- authenticated Windows identityからSIDを取得
- SIDを `X-Verified-Subject` としてuagへ渡す
- issuerはserver-side固定値を使う

Windows `WindowsIdentity.User` はSID (`SecurityIdentifier`) を返します。

Microsoft reference:

- https://learn.microsoft.com/dotnet/api/system.security.principal.windowsidentity.user

### 6.3 `appsettings.json`

`appsettings.json` 全体:

```json
{
  "UagIdentityIssuer": "corp-ad",
  "ReverseProxy": {
    "Routes": {
      "uag": {
        "ClusterId": "uag",
        "Match": {
          "Path": "{**catch-all}"
        }
      }
    },
    "Clusters": {
      "uag": {
        "Destinations": {
          "backend": {
            "Address": "http://10.30.40.20:8000/"
          }
        }
      }
    }
  },
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning",
      "Yarp.ReverseProxy": "Information"
    }
  },
  "AllowedHosts": "uag.corp.example"
}
```

### 6.4 publish

```powershell
dotnet publish -c Release -o C:\uag\UagAdBridge
```

IISに `C:\uag\UagAdBridge` をapplication/siteとして登録します。

ASP.NET Core Hosting Bundleが正しく入っていれば、publishされた `web.config` からASP.NET Core Module経由で起動できます。

---

## 7. IIS site設定

例:

```text
Site name : UAG
Binding   : https / 443 / uag.corp.example
Physical  : C:\uag\UagAdBridge
```

Authentication / role service:

```text
Anonymous Authentication : Disabled
Windows Authentication   : Enabled
WebSocket Protocol        : Installed
```

TLS証明書を設定します。

Application PoolはASP.NET Core hosting用に構成します。一般には `.NET CLR version: No Managed Code` で問題ありません。

IISからbridgeへWindows identityが渡っていることを確認した後にuagとの疎通を確認してください。

---

## 8. forwarding headerについて

これは重要です。

uag WebはUvicornのproxy header middlewareを持ち、trusted sourceからの `X-Forwarded-For` があると `request.client.host` が元client addressへ置き換わる可能性があります。

一方、`TrustedProxyIdentityResolver` は現行実装で `request.client.host` を `UAGENT_TRUSTED_PROXY_CIDRS` と照合します。

そのため本ガイドのbridgeは:

- YARP default forwarderを無効化
- `X-Forwarded-For`
- `X-Forwarded-Host`
- `X-Forwarded-Proto`
- `X-Forwarded-Prefix`
- `Forwarded`

をuag backendへ渡しません。

この構成ではuagから見た接続元はbridge host `10.30.40.10` のsocket peerのままなので:

```env
UAGENT_TRUSTED_PROXY_CIDRS=10.30.40.10/32
```

をtrust boundaryとして使えます。

同一hostのloopbackは、他のlocal processも同じsource boundaryを満たすためproduction trust boundaryには使いません。

別のreverse proxy製品を利用する場合も、identity trust boundaryにforwarded client addressを混ぜないよう注意してください。

---

## 9. uagが生成するprincipal ID

uagはSIDそのものをMemory owner IDとしてDBへ露出させません。

概念上:

```text
issuer  = corp-ad
subject = S-1-5-21-...

principal_id =
  trusted_proxy:
  SHA256("corp-ad" + NUL + "S-1-5-21-...")
```

実装は `src/uagent/runtime/enterprise_identity.py` の `opaque_principal_id()` です。

---

## 10. 最初のglobal adminを設定する

Project membershipを管理する最初の管理者をbootstrapする場合、`UAGENT_ADMIN_PRINCIPALS` にopaque principal IDを設定できます。

### 10.1 自分のSIDを確認

domain userでPowerShell:

```powershell
whoami /user
```

例:

```text
CORP\alice  S-1-5-21-111111111-222222222-333333333-1104
```

### 10.2 principal IDを計算

issuerが `corp-ad` の場合:

```powershell
python -c "import hashlib; issuer='corp-ad'; subject='S-1-5-21-111111111-222222222-333333333-1104'; print('trusted_proxy:' + hashlib.sha256((issuer + '\0' + subject).encode('utf-8')).hexdigest())"
```

出力例:

```text
trusted_proxy:<64-hex-digest>
```

### 10.3 .envへ設定

```env
UAGENT_ADMIN_PRINCIPALS=trusted_proxy:<64-hex-digest>
```

複数adminはcomma区切りです。

```env
UAGENT_ADMIN_PRINCIPALS=trusted_proxy:<alice>,trusted_proxy:<bob>
```

server-side設定なのでbrowserからadmin principalを自己申告することはできません。

---

## 11. Project access

固定Project deploymentでは:

```env
UAGENT_MEMORY_PROJECT=agentcli
```

を設定できます。

認証済みprincipalでも、Project access policyで許可されていなければMemory V3のProject/Room操作は拒否されます。

管理API:

```text
GET    /api/projects/{project_id}/members
PUT    /api/projects/{project_id}/members/{principal_id}
DELETE /api/projects/{project_id}/members/{principal_id}
```

global adminまたはProject adminがmembershipを設定します。

---

## 12. AD Group連携の現状

### 12.1 Entra OIDC

Microsoft Entra IDをOIDCで使う場合は、検証済み `groups` claimを `IdentityContext.groups` へ入れる実装があります。

`UAGENT_DIRECTORY_GROUP_POLICY` でgroup IDからProject / Room roleへmappingできます。

例:

```env
UAGENT_DIRECTORY_GROUP_POLICY={"groups":{"engineering":{"administrator":false,"projects":["agentcli"],"rooms":{"development":"editor"}}}}
```

Entra group overageは、必要なGraph scopeとtenant consentがある場合、login時にMicrosoft Graphで解決できます。

### 12.2 trusted_proxy + on-prem AD

**現行 `TrustedProxyIdentityResolver` はgroup headerを読みません。**

したがって、IIS側で例えば:

```text
X-Verified-Groups: ...
```

を追加しても、それだけではuagの `IdentityContext.groups` には入りません。

また `UAGENT_DIRECTORY_GROUP_POLICY` はgroup IDからroleへのmappingであり、ADへ問い合わせてmembershipを取得するclientではありません。

現行で利用できる方法:

1. Project / Room membershipをuag側で手動管理する
2. direct `windows_ad` verifier等、**identity resolver自身が検証済みgroupsを `VerifiedEnterpriseIdentity.groups` に入れる経路**を使う
3. verified groups propagationを追加実装してから `DirectoryGroupPolicyAdapter` / `UAGENT_DIRECTORY_GROUP_POLICY` を利用する
4. 将来のon-prem Directory API adapter実装を待つ

custom `DirectoryGroupPolicyAdapter` を登録するだけでは不十分です。現行 `directory_group_policy_assignments()` は `identity.groups` が空の場合にadapterを呼ばず空assignmentを返すため、`trusted_proxy` のままではAD問い合わせを起動するhookにはなりません。

AD group同期をproduction requirementにする場合は、別PRで**verified groups propagation**または**on-prem directory adapter**を実装してから有効にしてください。

---

## 13. direct `windows_ad` mode

設計上は次があります。

```env
UAGENT_IDENTITY_MODE=windows_ad
UAGENT_AD_REALM=CORP.EXAMPLE
UAGENT_AD_PROVIDER_NAMESPACE=corp-ad
```

ただし現行 `WindowsADIdentityResolver` は、platform-specific Kerberos / Negotiate処理そのものを内蔵していません。

server startup時に:

```python
register_enterprise_identity_verifier("windows_ad", verifier)
```

でtrusted verifierを登録し、そのverifierが:

```python
VerifiedEnterpriseIdentity(
    namespace="corp-ad",
    subject="<stable-object-id>",
    display_name="...",
    groups=(...)
)
```

を返すadapter contractです。

credential未検証の `DOMAIN\username` をそのまま返してはいけません。

direct `windows_ad` はKerberos/SPN/delegation/platform dependencyが強いため、現時点では本ガイドのIIS + trusted proxy方式を推奨します。

---

## 14. Microsoft Entra IDを使える場合

オンプレADがEntra IDと同期されており、Web利用者がEntraでsign-inできる場合は、IIS bridgeよりbuilt-in OIDC pathの方が単純です。

例:

```env
UAGENT_IDENTITY_MODE=oidc
UAGENT_OIDC_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
UAGENT_OIDC_CLIENT_ID=<client-id>
UAGENT_OIDC_CLIENT_SECRET=<client-secret-if-required>
UAGENT_OIDC_REDIRECT_URI=https://uag.corp.example/auth/oidc/callback
UAGENT_OIDC_COOKIE_SECURE=1
UAGENT_MEMORY_BACKEND=sqlite
```

Entra IDの場合は:

- Authorization Code + PKCE
- ID token validation
- server-side session
- verified group claims
- group overage時のGraph lookup

がuag側に実装されています。

AD FSや別のfederation gatewayがOIDCを提供できる場合も、原則 `oidc` modeを優先してください。

---

## 15. 動作確認

### 15.1 IIS Windows Authentication

domain参加clientから:

```text
https://uag.corp.example/
```

を開きます。

期待結果:

- credential promptなしでWindows SSOする
- Anonymous userとして通らない
- 401 loopにならない
- Web UIでmessage送信ができる
- browser developer tools等で `/ws` のWebSocket upgradeが成功する（通常HTTP 101）

### 15.2 uag authentication status

```text
GET /api/auth/status
```

期待:

```text
mode       : trusted_proxy
configured : true
health     : configured
```

status APIはraw SID、token、secretを返さない設計です。

### 15.3 bypass確認

次のbackend URLはproxy host以外から利用できてはいけません。

```text
http://10.30.40.20:8000/
```

一般clientからはWindows Firewall / network ACLで拒否されることを確認します。

さらにuag host自身からidentity headerを付けてbackendへ直接requestしても、sourceがproxy IPではないため `request did not arrive through a trusted proxy` で拒否されることを確認してください。

### 15.4 spoofing確認

clientから任意の:

```text
X-Verified-Subject
X-Verified-Issuer
X-Forwarded-For
Forwarded
```

を送っても、bridgeが削除してserver-sideの値へ置き換えることを確認します。

### 15.5 別ユーザー確認

AD user A / Bでアクセスし、Personal Memory / Profileが混線しないことを確認します。

### 15.6 revocation確認

Project membershipを削除した後:

- Project Memory
- Room Memory
- private Web turn
- stale snapshot / continuation

から旧権限を再利用できないことを確認します。

---

## 16. troubleshooting

### 常に401になる

確認:

1. IIS Windows AuthenticationがEnabledか
2. Anonymous AuthenticationがDisabledか
3. domain clientからアクセスしているか
4. browserがWindows Integrated Authentication対象siteとして扱っているか
5. bridgeの `HttpContext.User.Identity.IsAuthenticated` がtrueか
6. SIDが取得できているか

### uagが `request did not arrive through a trusted proxy`

確認:

- uag backendがprivate backend IP（例: `10.30.40.20:8000`）にbindしているか
- bridge destinationがそのbackend URL（例: `http://10.30.40.20:8000/`）か
- `UAGENT_TRUSTED_PROXY_CIDRS=10.30.40.10/32` のようにproxy hostだけを許可しているか
- Windows Firewall / network ACLがproxy hostだけを許可しているか
- `X-Forwarded-For` / `Forwarded` がbackendへ残っていないか

### `trusted proxy identity headers are missing`

確認:

- `X-Verified-Subject` がSID付きで付与されているか
- `X-Verified-Issuer` が付与されているか
- header名とuagの環境変数が一致しているか

### 同じ人なのにprincipalが変わった

次を変えるとprincipal IDが変わります。

- issuer namespace
- stable subject
- SID/object ID

`UagIdentityIssuer` と `UAGENT_TRUSTED_PROXY_ISSUER_HEADER` の運用値は、一度productionで使い始めた後に安易に変更しないでください。

### KerberosにならずNTLMになる

uagのidentity境界とは別問題です。

IIS / AD側で:

- DNS
- SPN
- service account
- kernel-mode authentication
- browser intranet zone / policy
- delegation

を確認してください。

uag側はIIS/bridgeが検証済みWindows identityを返した後のprincipal normalizationを担当します。

---

## 17. production security checklist

本番化前に最低限確認してください。

- [ ] IIS/auth bridgeとuag backendを別host / 別trust boundaryへ分離している
- [ ] uag backend TCP/8000はproxy hostからだけ到達可能
- [ ] loopbackをmulti-user productionのidentity trust boundaryにしていない
- [ ] HTTPSを使用
- [ ] proxy-uag間をisolated networkまたはauthenticated transportで保護
- [ ] IIS Anonymous AuthenticationはDisabled
- [ ] IIS Windows AuthenticationはEnabled
- [ ] IIS WebSocket Protocol role serviceはEnabled
- [ ] identity headerはclient入力を削除してからserver-sideで再付与
- [ ] forwarded client-address headersをidentity trust boundaryに使わない
- [ ] `UAGENT_TRUSTED_PROXY_CIDRS` は必要最小限
- [ ] `0.0.0.0/0` / `::/0` をtrustしない
- [ ] username / UPN / emailではなくstable subjectを使用
- [ ] 最初のglobal admin principalをserver-sideで固定
- [ ] Project / Room membershipを検証
- [ ] user A/B間でPersonal Memory / Profileが混線しないことを検証
- [ ] membership revoke後にstale accessが残らないことを検証
- [ ] raw credential / Kerberos ticket / tokenをMemoryやSessionへ保存しない
- [ ] group連携を使う場合、そのgroup sourceが検証済みであることを確認

---

## 18. 関連実装

主要実装:

```text
src/uagent/runtime/enterprise_identity.py
src/uagent/runtime/identity_context.py
src/uagent/runtime/auth_management.py
src/uagent/runtime/project_access.py
src/uagent/runtime/room_access.py
src/uagent/web_impl/connection_identity.py
src/uagent/web_impl/routes_auth.py
src/uagent/web_impl/routes_api.py
```

関連テスト:

```text
tests/test_enterprise_identity.py
tests/test_directory_group_policy.py
tests/test_web_connection_identity.py
tests/test_memory_v3_web_api.py
tests/test_web_authorization_hardening.py
```

---

## 19. 今後の実装候補

on-prem ADをよりnativeに扱う場合の優先候補:

1. `trusted_proxy`向けverified groups contract
2. on-prem Directory API / LDAP adapter
3. group membership freshness / revocation policy
4. Windows Negotiate verifier adapter
5. SPN / Kerberos deployment integration tests
6. Windows Server + IIS + domain joined browserのend-to-end CI/実環境test
7. auth status diagnosticsへのtrusted proxy peer/header health追加

これらが入るまでは、本ガイドの **IIS Windows Authentication + stable SID bridge + trusted_proxy** をproduction baselineとします。
