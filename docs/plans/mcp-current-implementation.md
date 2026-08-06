# MCP現行実装棚卸し

- Status: mostly complete（主要機能実装済み。実Proxy/TLSは残課題）
- Priority: P1
- Related plan: [`mcp-2026-07-28.md`](mcp-2026-07-28.md)
- Survey date: 2026-08-06

## 使用SDK

- Python package: `mcp`
- Installed version during survey: `1.28.1`
- HTTP dependency: `httpx 0.28.1`

現在のコードは公式MCP Python SDKの次を使用している。

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.client.stdio import stdio_client, StdioServerParameters
```

## 現在の接続経路

### `mcp_tools_list_tool.py`

- Streamable HTTPまたはstdioへ接続
- `ClientSession`を作成
- `session.initialize()`を実行
- `session.list_tools()`を実行
- ツール名、説明、input schemaをJSON化
- HTTP headersと環境変数展開に対応

### `handle_mcp_v2_tool.py`

- Streamable HTTPまたはstdioへ接続
- `ClientSession`を作成
- `session.initialize()`を実行
- `session.call_tool()`を実行
- text / resource / binary-like contentを整形
- ダウンロード成果物をローカル保存
- HTTP headersと環境変数展開に対応

## SDKで確認できたClientSession機能

`mcp 1.28.1`では次のメソッドが存在する。

SDKのStreamable HTTP transport内部には、現在のsession IDと`MCP-Protocol-Version`の処理がある。一方、`Mcp-Method` / `Mcp-Name`の処理は確認できない。したがって、2026-07-28 Stateless対応をSDKだけで完結できるとは判断しない。

- `initialize`
- `list_tools`
- `call_tool`
- `list_resources`
- `read_resource`
- `list_prompts`
- `get_prompt`
- `send_ping`

ただし、これらの全機能がuagの公開ツールとして接続済みとは限らない。Resources、Prompts、MRTR、Tasks、Stateless MCP 2026-07-28仕様対応は別途検証が必要である。

## 重複している処理

次の処理が2ファイルに重複している。

- `mcp` SDKのimportと自動インストール
- Streamable HTTP URLの`/mcp`補正
- `httpx.AsyncClient`の生成
- headersの環境変数展開
- stdioパラメータ生成
- `ClientSession`の生成
- `session.initialize()`
- 接続エラー処理

## 現在の対応状況

| 機能 | 現状 |
|---|---|
| Streamable HTTP | 実装済み。SDK経由 |
| stdio | 実装済み。SDK経由 |
| `tools/list` | 実装済み |
| `tools/call` | 実装済み |
| HTTP headers | 実装済み。認証・カスタムheaders |
| 環境変数展開 | 実装済み。`env:VAR` / `${VAR}` |
| Stateless MCP 2026-07-28 | 部分実装。明示`stateless`時のtools/list / tools/call |
| Protocol version negotiation | `server/discover`の`supportedVersions`から選択し、後続要求へ反映 |
| Legacy / Stateless自動判定 | HTTPの`server/discover` probeで部分実装。失敗時はLegacy SDKへfallback |
| `Mcp-Method` / `Mcp-Name` | Stateless Adapterとauto probe経路で実装 |
| `server/discover` | `mcp_server_discover`でStateless実装。auto probeにも使用 |
| Resources公開経路 | `mcp_resources`でlist/readを実装。I18N対応 |
| Prompts公開経路 | `mcp_prompts`でlist/getを実装。I18N対応 |
| MRTR | 未実装 |
| Tasks extension | 未実装 |
| list cache hints | 未実装 |
| MCP Authorization / CIMD / issuer検証 | Metadata・issuer検証・PKCE・code/refresh exchange・暗号化Token Store・認可セッション・stateless/SDK HTTPのBearer付与/401 refresh・localhost callback listener・browser認可統合・CIMD取得/検証・Proxy/TLS設定・Token Store書き込みロック・分散refreshを実装。実Proxy/TLSは残課題 |

## 残課題（OAuth / Proxy / TLS）

### P1: 実TLS証明書チェーンの統合検証

- 自己署名CAとlocalhost証明書をテスト実行時に一時生成する。
- `MCPHTTPConfig.ca_cert`指定時にHTTPS接続が成功することを確認する。
- CA未指定・不正CA指定時にTLS検証が失敗することを確認する。
- 秘密鍵、企業CA、アクセストークンをリポジトリへコミットしない。
- Windows / Linux / macOSで証明書生成方法を統一する（OpenSSL依存を避けるか、明示的な前提条件にする）。

### P1: 実Proxy環境での検証

- HTTP/HTTPS Proxy経由のMetadata、CIMD、Authorization Server Metadata取得を検証する。
- Proxy経由のauthorization code交換とrefresh token交換を検証する。
- Proxy認証（Basicまたは企業固有方式）をsecretから注入する。
- `NO_PROXY=127.0.0.1,localhost`でlocalhost callbackをProxyへ送らないことを確認する。
- Proxy障害、タイムアウト、TLS interception時の構造化エラーを確認する。

### P1: Reverse Proxy配下の検証

- 外部canonical URLと内部MCP URLを分離して設定できるようにする。
- `resource`、issuer、authorization endpoint、CIMDのURLが外部公開URLになることを確認する。
- `X-Forwarded-Host` / `X-Forwarded-Proto`利用時のissuer・resource mismatchを検証する。
- 内部ホスト名や内部IPがMetadataに漏れないことを確認する。

### P2: OAuth実運用の追加検証

- Authorization Serverでのrefresh token rotationを実環境相当で検証する。
- 実Authorization Serverでrefresh token rotationと分散refreshの一度限り動作を検証する。
- 外部注入された`http_client`にもOAuth auth hookを安全に適用できるAPIを整備する。
- refresh token失効、scope変更、token endpointエラーを検証する。
- SDK transportとStateless transportで認証ヘッダー・refresh挙動が一致することを確認する。
- 外部ブラウザーを使用したbrowser OAuthの手動検証手順を文書化する。

### 検証環境に関する注意

公開OAuth/MCP endpointは停止・仕様変更・レート制限・認証情報漏えいのリスクがあるため、CIでは使用しない。CIではリポジトリ内のローカルMCP/OAuth/Proxy fixtureを使用し、実Proxy・企業CA・実Authorization Serverの検証は手動または専用の秘密環境で実施する。

## I18N境界

MCPの内部protocol処理は、公開ツールのI18Nから分離する。

```text
src/uagent/tools/mcp/
  → I18Nなし。構造化エラーコードとprotocol値のみ

src/uagent/tools/mcp_tools_list_tool.py
src/uagent/tools/handle_mcp_v2_tool.py
  → I18Nあり。ユーザー・LLM向けメッセージを翻訳
```

内部層は英語メッセージを返さず、次のような値を返す。

```json
{
  "code": "MCP_TIMEOUT",
  "operation": "tools/list",
  "details": {}
}
```

## 次の実装境界

既存の2ツールを削除・再実装せず、以下の共通層へ接続処理を移す。

```text
src/uagent/tools/mcp/client.py
src/uagent/tools/mcp/protocol.py
src/uagent/tools/mcp/capabilities.py
src/uagent/tools/mcp/errors.py
```

移行対象：

- `src/uagent/tools/mcp_tools_list_tool.py`
- `src/uagent/tools/handle_mcp_v2_tool.py`

最初のAdapterは、既存SDKをラップして次を提供する。

```text
connect()
list_tools()
call_tool()
detect_protocol()
```

既存の`initialize()`方式を壊さず、SDKが2026-07-28仕様を提供する範囲を確認した後にStateless Adapterを追加する。

## TDD先行項目

- 現行のtools/list回帰
- 現行のtools/call回帰
- stdio回帰
- headers展開回帰
- legacy initialize回帰
- Stateless fake server検出
- `MCPClient`経由のStateless list/call統合
- shared client/transportのResources・Prompts呼び出し
- SDK非対応時の構造化エラー
