# MCP OAuth / Proxy 利用ガイド

Remote MCPサーバー（Streamable HTTP）をOAuthで利用する場合の設定と注意点を説明します。

## 対象

- Remote MCP / Streamable HTTP
- OAuth 2.1 Authorization Code + PKCE
- Stateless HTTP transport
- 公式SDKのStreamable HTTP transport

stdio接続では、通常OAuthは使用しません。stdioではOSユーザー権限、環境変数、APIキーなど、MCPサーバー固有の認証を使用します。

## 認証の流れ

初回接続時は、次の流れで認可します。

```text
MCPサーバーのMetadata
  → Authorization Server Metadata
  → CIMD / client_id検証
  → ブラウザー認可
  → localhost callback
  → PKCE code交換
  → Token Store保存
```

保存済みtokenが有効な場合は再認可を行いません。MCPサーバーから`401`が返った場合は、refresh tokenを使って一度だけ再試行します。

## Token Store

Token Storeのデフォルト保存先は、pipのインストール先ではなく、実行ユーザーの状態ディレクトリです。

Windows:

```text
C:\Users\<ユーザー名>\.uag\mcps\oauth_tokens.json
```

Linux/macOS:

```text
~/.uag/mcps/oauth_tokens.json
```

`UAGENT_STATE_DIR`で変更できます。

```powershell
$env:UAGENT_STATE_DIR = "D:\uag-state"
```

```bash
export UAGENT_STATE_DIR="$HOME/.config/uagent"
```

複数MCPのtokenは、`issuer`と`resource`の組み合わせごとに別レコードとして保存されます。Token Storeは暗号化され、refresh tokenを含むため、共有フォルダーやGitリポジトリへ置かないでください。

## Proxy設定

環境変数を利用する場合:

Windows PowerShell:

```powershell
$env:HTTPS_PROXY = "http://proxy.example:8080"
$env:HTTP_PROXY = "http://proxy.example:8080"
$env:NO_PROXY = "127.0.0.1,localhost"
```

Linux/macOS:

```bash
export HTTPS_PROXY="http://proxy.example:8080"
export HTTP_PROXY="http://proxy.example:8080"
export NO_PROXY="127.0.0.1,localhost"
```

`NO_PROXY`には`127.0.0.1`と`localhost`を含めてください。OAuthのlocalhost callbackをProxyへ送らないために必要です。

コードから明示指定する場合:

```python
from uagent.tools.mcp.client import MCPClient
from uagent.tools.mcp.http_client import MCPHTTPConfig

http_config = MCPHTTPConfig(
    proxy_url="http://proxy.example:8080",
    trust_env=True,
    timeout=30,
)

client = MCPClient(
    url="https://mcp.example.com/mcp",
    http_config=http_config,
)
```

SOCKS Proxyを使う場合は、追加依存が必要です。

```bash
pip install "httpx[socks]"
```

## 企業CA証明書

TLS interceptionを行う企業Proxyでは、企業CA証明書を指定します。

```python
http_config = MCPHTTPConfig(
    proxy_url="http://proxy.example:8080",
    ca_cert="C:/certs/company-ca.pem",
    trust_env=False,
)
```

または、httpx / OpenSSLの環境変数を利用します。

```powershell
$env:SSL_CERT_FILE = "C:\certs\company-ca.pem"
```

`verify=False`で証明書検証を無効化する方法は、OAuth tokenを扱うため推奨しません。

## 外部HTTPクライアントを使う場合

Proxy、CA、timeoutなどを自分で管理する場合は、`httpx.AsyncClient`を作成して渡せます。OAuth providerを指定すると、SDK Streamable HTTP transportへ認証フックが適用されます。

```python
import httpx

from uagent.tools.mcp.client import MCPClient
from uagent.tools.mcp.oauth_provider import OAuthTokenProvider

async with httpx.AsyncClient(
    proxy="http://proxy.example:8080",
    verify="C:/certs/company-ca.pem",
) as http_client:
    client = MCPClient(
        url="https://mcp.example.com/mcp",
        http_client=http_client,
        authorization_provider=provider.authorization_header,
    )
```

すでに別の`httpx`認証設定がある場合、OAuth認証と無断で合成・上書きはしません。競合した場合は設定を見直してください。

## Reverse Proxy配下

MCPサーバーがReverse Proxyの背後にある場合、OAuth MetadataのURLにはクライアントから見える外部canonical URLを使用します。

```text
正: https://mcp.example.com/mcp
誤: http://mcp-internal:8000/mcp
```

次の値に内部ホスト名や内部IPを返さないでください。

- `resource`
- `issuer`
- authorization endpoint
- token endpoint
- CIMD `client_id`

Reverse Proxyでは、外部のschemeとhostが正しく伝わるように`X-Forwarded-Proto`と`X-Forwarded-Host`を設定してください。

## よくあるエラー

### `issuer mismatch`

Metadataのissuerと、設定・検証対象のissuerが一致していません。外部canonical URLとReverse Proxyのscheme/host設定を確認してください。

### `CIMD client_id mismatch`

CIMDのJSONにある`client_id`が、取得URLと一致していません。CIMDのURLとJSON内の`client_id`を一致させてください。

### `TLS certificate verify failed`

企業CA証明書が信頼されていません。`ca_cert`または`SSL_CERT_FILE`を確認してください。`verify=False`は避けてください。

### `OAuth callback timeout`

ブラウザーが認可後にlocalhost callbackへ戻れていません。`NO_PROXY`に`127.0.0.1,localhost`が含まれているか確認してください。

### `MCP_OAUTH_REFRESH_TOKEN_MISSING`

Token Storeにrefresh tokenがありません。再認可が必要です。

### `http_client already has a conflicting auth configuration`

外部から渡した`httpx.AsyncClient`に別の認証設定があります。既存authとOAuth authの構成を整理してください。

## セキュリティ上の注意

- access token、refresh token、Proxyパスワードをログへ出力しない
- tokenファイルをGitへコミットしない
- 共有アカウントでToken Storeを共有しない
- `verify=False`を本番で使用しない
- OAuth callbackはlocalhost以外へ公開しない
- 公開OAuth/MCP endpointをCIの固定テスト先にしない
- 実企業Proxy・企業CA・Authorization Serverの検証は専用環境で行う

## ローカル統合テスト

外部サービスなしで、ローカルのMCPサーバー、OAuth endpoint、Proxyを使った統合テストを実行できます。

```bash
python -m pytest -q tests/integration/test_mcp_oauth_proxy_integration.py
python -m pytest -q tests/integration/test_mcp_oauth_security_integration.py
```

これらは実運用の企業ProxyやAuthorization Serverの代替ではありません。実環境では、Proxy認証、TLS interception、refresh token rotationも追加確認してください。
