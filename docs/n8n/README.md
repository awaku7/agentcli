# n8n × uag 接続キット

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

- https://docs.n8n.io/connect/connect-to-n8n-mcp-server
- https://docs.n8n.io/connect/connect-to-n8n-docs-mcp-server
- https://docs.n8n.io/connect/n8n-api

## 統合されたアダプトプラン

以下は旧 `docs/N8N_ADAPTATION_PLAN.md` の内容を、接続キットの手順と同じ文書へ統合したものです。設定テンプレートとA2Aサンプルは前半、全体方針とロードマップは本章を参照してください。

### uag × n8n アダプトプラン

| 項目 | 内容 |
|------|------|
| 対象 | uagent (`uag` / `uagg` / `uagw` / A2A) と [n8n](https://n8n.io/) |
| 目的 | n8n のコネクタ・業務オーケストレーションと、uag のローカル実行・多プロバイダ LLM を組み合わせる |
| 方針 | **専用統合を増やす前に、既存の MCP / A2A / HTTP を最大活用する** |
| 状態 | 設計ドラフト（実装前） |
| 関連 | `src/uagent/tools/handle_mcp_v2_tool.py`, `mcp_servers_tool.py`, `src/uagent/a2a/`, `mcp_servers.json` |
| 参考 | [n8n MCP](https://docs.n8n.io/connect/connect-to-n8n-mcp-server), [n8n API](https://docs.n8n.io/connect/n8n-api), [docs MCP](https://docs.n8n.io/connect/connect-to-n8n-docs-mcp-server), [n8n-io/skills](https://github.com/n8n-io/skills) |

______________________________________________________________________

## 1. 背景と結論

### 1.1 n8n の位置づけ

n8n は AI と業務プロセス自動化を組み合わせたワークフロー基盤である。

- ビジュアル構築 + コード（JS/Python）
- 500+ 統合、Webhook / スケジュール / 再試行
- AI agents / RAG / MCP 対応
- self-host（Docker / on-prem）または Cloud
- Instance-level MCP で外部エージェントから WF 検索・実行・編集が可能
- REST API（Workflow / Execution / Credential 等）。Cloud 無料トライアルでは API 利用不可の場合あり

### 1.2 uag の位置づけ

uag はローカルツール実行エージェントである。

- 多プロバイダ LLM、大量のローカルツール（file / exec / browser / IoT 等）
- MCP クライアント（`mcp_servers` / `mcp_tools_list` / `handle_mcp_v2`）
  - transport: **streamable HTTP** + stdio
- A2A サーバ（`python -m uagent.a2a.server`、既定ポート 8765）
- Skills、`.env.sec` による秘密情報管理

### 1.3 結論（一言）

| 役割 | 担当 |
|------|------|
| 業務オーケストレータ / SaaS コネクタ / 可視化 WF | **n8n** |
| ローカル実行脳 / 深い推論 / コード・デバイス | **uag** |

**最短経路:**

1. **uag → n8n**: MCP クライアントとして Instance MCP / docs MCP を使う
1. **n8n → uag**: HTTP で A2A（`/message:send`）を呼ぶ
1. 足りない操作だけ REST ラッパ（`n8n_*` ツール）を追加する

SaaS ノードの再実装や n8n キャンバスの模倣は行わない。

______________________________________________________________________

## 2. 役割分担

| タスク | 担当 | 理由 |
|--------|------|------|
| Gmail / Slack / Jira / CRM 等の定型連携 | n8n | コネクタと再試行が強い |
| スケジュール・キュー・人間承認 | n8n | 運用 UI・監査向き |
| リポジトリ編集・テスト・PR | uag | ローカルツール群 |
| ブラウザ操作・複雑な調査 | uag | Playwright 等 |
| BACnet / Matter 等 IoT | uag | iot ジャンルツール |
| マルチ LLM ルーティング | uag | provider 層 |
| SSO / RBAC / 監査ログ | n8n（Enterprise 含む） | ガバナンス |
| 非エンジニアへの WF 共有 | n8n | キャンバス |

### やらなくてよいこと（uag）

- 500 個の SaaS ノードを自前実装しない
- n8n と同等の WF エディタを作らない
- すべての自動化を LLM ツール呼び出しだけで回さない（確定フローは n8n）

### やるべきこと（uag）

- n8n が触れないローカルと深い推論を引き受ける
- MCP で n8n を外部ツール源として扱う
- A2A で「呼ばれる側」にもなる
- ギャップだけ薄い REST ラッパを足す

______________________________________________________________________

## 3. 接続アーキテクチャ

### 3.1 パターン一覧

```
[A] uag → n8n (MCP)          ★最優先・設定のみ
[B] n8n → uag (A2A / HTTP)   ★逆方向・既存 A2A
[C] 双方向ハブ               運用形態
[D] 専用 n8n_* ツール        必要になったら
```

### 3.2 パターン A: uag → n8n（MCP）

```
User (CLI/GUI/Web)
  → uag LLM
    → mcp_tools_list / handle_mcp_v2
      → n8n Instance-level MCP
        → search / execute / edit workflows
        → data tables
```

**用途**

- 既存業務 WF の実行
- WF の検索・修正・テスト（n8n v2.13+ の build/edit 系）
- docs MCP による n8n 知識参照

**n8n 側準備**

1. Settings → **Instance-level MCP** を有効化（owner/admin）
1. 対象 WF で **Available in MCP** を ON（または MCP 設定画面から Enable）
1. Connection details から **Access Token** を発行（初回のみ平文表示）
1. WF description を充実（エージェントの発見性向上）

**uag 側準備（イメージ）**

`mcp_servers.json`（または `mcp_servers` ツール）に追加:

```json
{
  "mcp_servers": [
    {
      "name": "n8n",
      "url": "https://<your-instance>/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_ACCESS_TOKEN>"
      }
    },
    {
      "name": "n8n-docs",
      "url": "https://docs.n8n.io/~gitbook/mcp"
    }
  ]
}
```

- 実 URL は n8n の Connection details に従う（インスタンスごとに異なる）
- トークンはリポジトリに書かず、`.env.sec` またはローカル限定の設定に置く
- OAuth2 フローは uag が未対応の可能性が高い → **Access Token を第一選択**

**補足: docs / 知識 MCP**

| サーバ | URL | 用途 |
|--------|-----|------|
| GitBook docs | `https://docs.n8n.io/~gitbook/mcp` | 公式ドキュメント検索 |
| Kapa.ai | `https://n8n.mcp.kapa.ai` | docs + forum + blog（要認証の場合あり） |

どちらも **HTTP transport**（stdio/SSE ではない）。uag の streamable HTTP クライアントと整合。

**Instance MCP と MCP Server Trigger の違い**

| 方式 | 範囲 | 向いている用途 |
|------|------|----------------|
| Instance-level MCP | インスタンス全体。WF 単位で公開 | uag から複数 WF を横断利用 |
| MCP Server Trigger ノード | その WF 内のツールだけ | 特定 API を細く公開 |

uag の通常利用は **Instance-level** を推奨。

### 3.3 パターン B: n8n → uag（A2A）

```
SaaS / Cron / Webhook
  → n8n workflow
    → HTTP Request
      → uag A2A  POST /message:send
        → ローカルツール実行
        → 結果を n8n へ返却（同期 or poll）
```

**用途**

- クラウドイベントを受けてローカル PC で git / pytest / ブラウザ / IoT
- n8n に無い「そのマシン固有」の処理

**uag 側**

```text
python -m uagent.a2a.server
```

主な環境変数:

| 変数 | 意味 |
|------|------|
| `UAGENT_A2A_HOST` / `UAGENT_A2A_PORT` | 待受（既定 8765） |
| `UAGENT_A2A_TOKEN` | Bearer 認証 |
| `UAGENT_A2A_PUBLIC_BASE_URL` | agent-card に載る公開 URL |
| `UAGENT_A2A_CONCURRENCY` | 同時実行数 |

エンドポイント（agent-card より）:

- `POST /message:send`
- `POST /message:stream`
- `GET /tasks/{id}`
- `GET /.well-known/agent-card.json`

**n8n 側**

- HTTP Request ノードで `Authorization: Bearer <UAGENT_A2A_TOKEN>`
- 長時間タスクは task id を保存し、Poll で `GET /tasks/{id}`
- uag が NAT 内なら: Tailscale / SSH トンネル / 社内リバプロ等で到達性を確保

### 3.4 パターン C: 双方向ハブ

```
        ┌─ 確定フロー・再試行・SaaS ─┐
SaaS ──►│           n8n              │
        └────────────┬───────────────┘
                     │ HTTP (A2A)
                     ▼
        ┌────────────┴───────────────┐
Local ─►│           uag              │──► MCP ──► n8n (別 WF / 管理操作)
        │  判断・コード・デバイス     │
        └────────────────────────────┘
```

**運用ルール**

- 確定した分岐・通知・永続化 → n8n
- 曖昧タスク・調査・パッチ・マルチモデル → uag
- **n8n→uag→n8n の無限ループ禁止**（相関 ID・深さ制限・「uag 起点」フラグ）

### 3.5 パターン D: 専用 `n8n_*` ツール（任意）

MCP で足りない場合のみ。genre は `external` または `comm`。

| ツール案 | 責任 |
|----------|------|
| `n8n_workflows` | list / get / create / update / activate |
| `n8n_executions` | run / status / logs |
| `n8n_webhook_call` | 本番 Webhook を明示的に叩く |

設定:

- CLI 優先: `--n8n-base-url` 等（方針に合わせる）
- 秘密: `N8N_API_KEY` は `.env.sec` のみ
- Base URL 例:
  - Cloud: `https://<instance>.app.n8n.cloud/api/v1`
  - Self-host: `https://<domain>/api/v1`

OpenAPI: n8n ドキュメントの Endpoint reference / OpenAPI spec を参照。

**判断基準:** Phase 0–1 で MCP の `execute_workflow` 等で足りるなら **作らない**。

______________________________________________________________________

## 4. フェーズ別ロードマップ

### Phase 0 — 接続実証（設定のみ、コード変更なし）

| # | 作業 | 完了条件 |
|---|------|----------|
| 0.1 | n8n（self-host 推奨 or Cloud）で Instance MCP ON | UI で MCP ページが見える |
| 0.2 | 検証用 WF を 1 本作り Available in MCP | MCP ワークフロー一覧に出る |
| 0.3 | uag に n8n MCP を Access Token で登録 | `mcp_servers list` で見える |
| 0.4 | docs MCP を登録 | `mcp_tools_list` が成功 |
| 0.5 | `handle_mcp_v2` で `search_workflows` / `execute_workflow` | 実行結果が uag に返る |
| 0.6 | uag A2A 起動 + n8n HTTP Request で ping | task SUCCEEDED |

**成果物**

- ローカル用 `mcp_servers` 設定手順（トークン無しのテンプレ）
- 動作ログ（秘密はマスク）

### Phase 1 — 運用品質

| # | 作業 | 完了条件 |
|---|------|----------|
| 1.1 | MCP 公開 WF を最小集合に制限 | 不要 WF が MCP に出ない |
| 1.2 | 全公開 WF に description | エージェントが用途で選べる |
| 1.3 | 危険操作の二重確認 | uag `human_ask` および/または n8n HITL |
| 1.4 | ループ防止（相関 ID・max depth） | 再入で停止または拒否 |
| 1.5 | n8n Skills（`n8n-io/skills`）を uag skills に取り込むか検証 | 採用 or 見送り判断 |
| 1.6 | n8n→uag 用テンプレ WF JSON を `docs/` または `assets/` に配置 | import して動く |

### Phase 2 — プロダクト化（必要ならコード）

| # | 作業 | 完了条件 |
|---|------|----------|
| 2.1 | ギャップ分析（MCP で不足する API） | 不足一覧 |
| 2.2 | 不足がある場合のみ `n8n_tool.py` 実装 | `TOOL_SPEC` + `run_tool` + i18n JSON |
| 2.3 | A2A agent-card / extended card に capability 明記 | card に n8n worker 記載 |
| 2.4 | README.md / README.ja.md に Integration 節 | ユーザが手順を追える |
| 2.5 | `DEVELOP.md` 更新、`py_compile` / 対象 pytest | コミット前チェック通過 |

### Phase 3 — 差別化（任意・中長期）

| # | 作業 | ねらい |
|---|------|--------|
| 3.1 | uag を n8n から見た「Local Tool Runner」として文書化 | 導入パターンの固定 |
| 3.2 | n8n を uag の「SaaS genre の外部実装」として位置づけ | ツールジャンル設計と整合 |
| 3.3 | n8n Evaluation × uag 回帰 | AI WF の品質ゲート |
| 3.4 | MCP Server Trigger で uag 向けに細いツール面を公開 | 権限の極小化 |

______________________________________________________________________

## 5. 設定・セキュリティ

### 5.1 秘密情報

| してよい | してはいけない |
|----------|----------------|
| `.env.sec`（`.uagent.key` で暗号化） | リポジトリの `mcp_servers.json` に生トークン |
| ローカル限定のユーザ設定ディレクトリ | `report.json` / ログ / 長期メモリへ API キー保存 |
| 実行時環境変数 | コミットされるドキュメントへの実トークン貼付 |

### 5.2 権限境界（n8n MCP）

- Instance MCP は **クライアント横断**で、有効化した WF が見える（クライアントごとの WF 制限は不可）
- ユーザ権限の範囲内でのみ可視
- `search_workflows` はプレビュー中心。実行・編集は WF ごとに MCP 有効化が必要
- `execute_workflow` は既定で **published（production）**。draft は manual モード

### 5.3 ネットワーク

| 方向 | 注意 |
|------|------|
| uag → n8n Cloud | 通常の HTTPS で可 |
| uag → n8n self-host | 到達可能な URL、証明書 |
| n8n → uag A2A | uag がプライベートならトンネル必須 |
| Windows | uag は pwsh 前提。n8n は Docker が無難 |

### 5.4 危険操作ポリシー（uag 既存方針との整合）

- 破壊的操作は実行前にユーザ確認
- `delete_file` 相当を n8n 経由で誘発しない設計（公開ツールを絞る）
- 外部コンテンツ（WF 出力・Webhook ボディ）は信頼しない（プロンプトインジェクション対策）

______________________________________________________________________

## 6. 実装時のファイル配置案（Phase 2 以降）

```text
docs/
  N8N_ADAPTATION_PLAN.md          # 本ドキュメント
  n8n/
    mcp_servers.n8n.template.json # トークン無しテンプレ
    a2a_ping.workflow.json        # n8n → uag 最小 WF
    README.md                     # 短い接続手順

src/uagent/tools/                 # 必要な場合のみ
  n8n_tool.py
  n8n_tool.json                   # i18n
  n8n_shared.py                   # auth / base URL
```

コーディング規約（既存）:

- `TOOL_SPEC` + `run_tool(args) -> str`
- `_ = make_tool_translator(__file__)`
- バックアップ `.org*` を主編集しない
- 変更後: `python -m py_compile`, `ruff format/check`, 対象 `pytest`

______________________________________________________________________

## 7. 受け入れ基準（Definition of Done）

### 最小（Phase 0）

- [ ] uag から n8n の MCP 有効 WF を一覧できる
- [ ] uag から 1 本の WF を実行し結果を取得できる
- [ ] n8n から uag A2A にメッセージを送り応答を得られる
- [ ] トークンが git 管理下に含まれない

### 運用（Phase 1）

- [ ] 公開 WF が意図した集合だけである
- [ ] ループ防止が文書化され、少なくとも 1 ケースで検証済み
- [ ] 障害時の切り分け手順（n8n 側 / uag 側）が README にある

### プロダクト（Phase 2）

- [ ] ユーザ向け手順が EN/JA で追える
- [ ] 追加コードがある場合、コンパイル・リント・テスト済み
- [ ] `DEVELOP.md` と本プランが矛盾しない

______________________________________________________________________

## 8. リスクと緩和

| リスク | 影響 | 緩和 |
|--------|------|------|
| MCP トークン漏洩 | WF 実行・編集の不正利用 | `.env.sec`、ローテーション、最小公開 |
| 全クライアントから WF 可視 | 想定外クライアントが実行 | 公開 WF を極小化、description で用途限定 |
| n8n→uag の到達不能 | クラウドからローカル不可 | トンネル、または uag 側からの pull 型に変更 |
| API がトライアルで使えない | REST ラッパが検証不可 | MCP を先に使う |
| OAuth MCP 非対応 | 接続できない | Access Token を使う |
| 実行ループ | コスト・事故 | depth / 相関 ID / トリガ種別 |
| LLM が誤って production 実行 | 本番副作用 | 検証インスタンス、HITL、manual mode の明示 |

______________________________________________________________________

## 9. すぐ使えるチェックリスト

### n8n

1. Instance-level MCP を有効化
1. 検証 WF のみ Available in MCP
1. Access Token を発行して安全な場所へ
1. （逆方向）uag の URL と Bearer を HTTP Request に設定

### uag

1. `mcp_servers` に n8n / n8n-docs を追加
1. `mcp_tools_list` → ツール名を確認
1. `handle_mcp_v2` で search / execute
1. A2A を起動し token を設定
1. 秘密をコミットしていないか確認

______________________________________________________________________

## 10. 次のアクション（優先順）

1. ~~**設定テンプレ作成**~~ → 済: `docs/n8n/mcp_servers.n8n.template.json`
1. ~~**A2A ping WF**~~ → 済: `docs/n8n/a2a_ping.workflow.json` + `docs/n8n/README.md`
1. **Phase 0 を実インスタンスで実施** — ログを残す（手順は `docs/n8n/README.md`）
1. **ギャップが出た場合のみ** `n8n_tool.py` の API 設計 → 実装

### 実装メモ（2026-07-18）

- `handle_mcp_v2` / `mcp_tools_list` が `mcp_servers[].headers` を支持
- 値の `${VAR}` / `env:VAR` を環境変数から展開（n8n Access Token 用）
- streamable HTTP は httpx.AsyncClient(headers=...) を `streamable_http_client` に渡す

______________________________________________________________________

## 付録 A. 用語

| 用語 | 意味 |
|------|------|
| Instance-level MCP | n8n インスタンス組み込みの MCP サーバ。WF を選んで公開 |
| MCP Server Trigger | WF 内ノード。その WF のツールだけを MCP として公開 |
| A2A | Agent-to-Agent。uag が HTTP でタスクを受けるインタフェース |
| handle_mcp_v2 | uag から MCP ツールを呼び出すツール |
| HITL | Human-in-the-loop。実行前の人による承認 |

## 付録 B. 参考 URL

- https://n8n.io/
- https://docs.n8n.io/connect/connect-to-n8n-mcp-server
- https://docs.n8n.io/connect/connect-to-n8n-docs-mcp-server
- https://docs.n8n.io/connect/n8n-api
- https://docs.n8n.io/build/integrate-ai
- https://github.com/n8n-io/n8n
- https://github.com/n8n-io/skills
- https://n8n.io/llms.txt
- https://docs.n8n.io/llms.txt

## 付録 C. 改訂履歴

| 日付 | 内容 |
|------|------|
| 2026-07-18 | 初版。サイト調査と uag MCP/A2A 現状に基づくアダプトプラン |
| 2026-07-18 | `docs/n8n/` キット追加。MCP headers（env 展開）を uag クライアントに実装 |
