# MCP現行実装棚卸し

- Status: done
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
| Legacy / Stateless自動判定 | HTTPの`server/discover` probeで部分実装。失敗時はLegacy SDKへfallback |
| `Mcp-Method` / `Mcp-Name` | Stateless Adapterとauto probe経路で実装 |
| `server/discover` | `mcp_server_discover`でStateless実装。auto probeにも使用 |
| Resources公開経路 | `mcp_resources`でlist/readを実装。I18N対応 |
| Prompts公開経路 | `mcp_prompts`でlist/getを実装。I18N対応 |
| MRTR | 未実装 |
| Tasks extension | 未実装 |
| list cache hints | 未実装 |
| MCP Authorization / CIMD / issuer検証 | 未実装 |

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
