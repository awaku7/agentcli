# n8n × uag 接続キット

実装計画: [`../plans/n8n-integration.md`](../plans/n8n-integration.md)

このディレクトリは **Phase 0（接続実証）** 用のテンプレートです。秘密情報は含めません。

| ファイル | 用途 |
|----------|------|
| `mcp_servers.n8n.template.json` | uag → n8n（MCP）設定テンプレ |
| `a2a_ping.workflow.json` | n8n → uag A2A 最小 WF |
| `README.md` | 本手順 |

______________________________________________________________________

## 1. uag → n8n（MCP）

### 1.1 n8n 側

1. **Settings → Instance-level MCP** で MCP を有効化（owner/admin）
1. **Connection details** を開き:
   - Instance MCP の **URL** を控える
   - **Access Token** を発行し、表示中にコピー（再表示されない）
1. 検証用ワークフローを 1 本作り、**Available in MCP** を ON
1. 可能なら description を書く（エージェントの検索用）

### 1.2 uag 側

1. テンプレをユーザ MCP 設定へコピー（リポジトリの `mcp_servers.json` に生トークンを書かない）:

```text
# 例: ユーザ設定（実際のパスは UAGENT_MCP_CONFIG / ~/.uag/mcps/mcp_servers.json）
copy docs\n8n\mcp_servers.n8n.template.json %USERPROFILE%\.uag\mcps\mcp_servers.n8n.json
```

2. `url` を Connection details の値に置換（末尾 `/mcp` 推奨）
1. トークンを環境変数へ（`.env.sec` 推奨）:

```text
N8N_MCP_ACCESS_TOKEN=...   # 生トークン。git に入れない
```

テンプレの headers は次の形式です（uag が展開）:

```json
"Authorization": "Bearer ${N8N_MCP_ACCESS_TOKEN}"
```

`env:N8N_MCP_ACCESS_TOKEN` 形式も可。

4. 既存の `mcp_servers.json` にマージする場合は、`n8n` / `n8n-docs` エントリだけ追加する。

1. 動作確認（uag 対話またはツール相当）:

```text
mcp_tools_list  server_name=n8n
mcp_tools_list  server_name=n8n-docs
handle_mcp_v2   server_name=n8n  tool_name=search_workflows  args={"limit": 5}
```

`execute_workflow` は published 版が既定。検証時は n8n ドキュメントの manual モードを確認すること。

### 1.3 実装メモ（uag）

- HTTP MCP は `streamable-http`（`handle_mcp_v2` / `mcp_tools_list`）
- `mcp_servers[].headers` を httpx 経由で付与可能（`${VAR}` / `env:VAR` 展開）
- URL が `/mcp` で終わらない場合はクライアントが自動付与する場合あり（明示推奨）

### 1.4 docs MCP（トークン不要）

| name | url |
|------|-----|
| `n8n-docs` | `https://docs.n8n.io/~gitbook/mcp` |

任意: Kapa（forum/blog 含む）`https://n8n.mcp.kapa.ai` — 認証が必要な場合あり。

______________________________________________________________________

## 2. n8n → uag（A2A ping）

### 2.1 uag 側

```text
set UAGENT_A2A_TOKEN=dev-local-token-change-me
set UAGENT_A2A_HOST=0.0.0.0
set UAGENT_A2A_PORT=8765
python -m uagent.a2a.server
```

確認:

```text
GET http://127.0.0.1:8765/.well-known/agent-card.json
```

認証付きエンドポイント:

- `POST /message:send`
- Body 例:

```json
{
  "message": { "role": "user", "content": "Reply with exactly: pong from uag" },
  "returnImmediately": false
}
```

- Header: `Authorization: Bearer <UAGENT_A2A_TOKEN>`

`returnImmediately: true` のときは task が非同期。`GET /tasks/{id}` でポーリング。

### 2.2 n8n 側

1. **Workflows → Import from File** で `a2a_ping.workflow.json` を取り込む
1. n8n の環境変数（または Docker env）:

| 変数 | 例 | 意味 |
|------|-----|------|
| `UAG_A2A_BASE_URL` | `http://host.docker.internal:8765` | uag A2A のベース URL（末尾スラッシュなし） |
| `UAG_A2A_TOKEN` | uag の `UAGENT_A2A_TOKEN` と同じ | Bearer |

3. n8n が Docker、uag が Windows ホストの場合は `host.docker.internal` が有効なことが多い
1. **Execute workflow** を実行
1. `Extract task fields` で `task_status=SUCCEEDED` と `assistant_content` を確認

### 2.3 長時間タスク

- ping WF は `returnImmediately: false`（同期待ち、timeout 120s）
- 長い処理では `returnImmediately: true` にし、別ノードで `GET {base}/tasks/{id}` をポーリングする

### 2.4 ループ防止（運用）

- n8n → uag のメッセージに `correlation_id`（実行 ID）を含める（本 WF はヘッダ `X-Correlation-Id`）
- uag から同じ実行を再度 n8n に投げない、または depth を制限する

______________________________________________________________________

## 3. セキュリティ

| してよい | 禁止 |
|----------|------|
| `.env.sec` / OS 環境変数にトークン | リポジトリへ生トークン commit |
| 検証用 WF のみ MCP 公開 | 全 WF を無差別 Available in MCP |
| ローカル専用 A2A トークン | ログ・report へのトークン出力 |

______________________________________________________________________

## 4. トラブルシュート

| 症状 | 確認 |
|------|------|
| MCP 401/403 | Access Token、`Authorization: Bearer ...`、headers 展開（`${N8N_MCP_ACCESS_TOKEN}` が空でないか） |
| MCP 接続エラー | URL が Connection details と一致するか、`/mcp` 末尾、TLS |
| `search_workflows` は出るが execute できない | 対象 WF の Available in MCP、published 有無、権限 |
| A2A 503 | `UAGENT_A2A_TOKEN` 未設定 |
| A2A 401/403 | n8n の `UAG_A2A_TOKEN` と uag の不一致 |
| A2A 接続不能 | ファイアウォール、Docker からのホスト名、`UAG_A2A_BASE_URL` |
| タイムアウト | uag 側 LLM/ツールが重い → async + poll |

______________________________________________________________________

## 5. Phase 0 チェックリスト

- [ ] n8n Instance MCP ON
- [ ] 検証 WF のみ MCP 公開
- [ ] uag から `mcp_tools_list` (n8n) 成功
- [ ] uag から `search_workflows` 成功
- [ ] （任意）`execute_workflow` 成功
- [ ] uag A2A 起動、agent-card 取得
- [ ] n8n から a2a_ping が SUCCEEDED
- [ ] 秘密が git に含まれていない

______________________________________________________________________

## 6. 参考

- プラン: [`../N8N_ADAPTATION_PLAN.md`](../N8N_ADAPTATION_PLAN.md)
- https://docs.n8n.io/connect/connect-to-n8n-mcp-server
- https://docs.n8n.io/connect/connect-to-n8n-docs-mcp-server
- https://docs.n8n.io/connect/n8n-api
