# 実装ロードマップ

プロジェクトのドキュメントに記載された「これから実装・検証する内容」を集約した一覧です。

> このファイルは計画の入口です。詳細な設計や実装仕様は、各項目のSourceに記載した現行ドキュメントを参照してください。

## Status / Priority

- **planned**: 計画済み、未着手
- **in-progress**: 実装・検証中
- **done**: 実装済み。現行仕様への反映待ちを含む
- **deferred**: 意図的に保留
- **P0**: 最優先
- **P1**: 高優先
- **P2**: 中長期

## P0: Memory V3 rollout / security completion

- Status: in-progress
- Priority: P0
- Source: [`docs/UAG_0_7_14_IMPLEMENTATION_REVIEW.md`](../UAG_0_7_14_IMPLEMENTATION_REVIEW.md)、[`docs/UAG_MEMORY_V3_SECURITY_HARDENING.md`](../UAG_MEMORY_V3_SECURITY_HARDENING.md)、[`docs/UAG_MEMORY_ARCHITECTURE_V3.md`](../UAG_MEMORY_ARCHITECTURE_V3.md)

### 実装済み

- authenticated Identity / TurnContextとWebSocket identity binding
- OIDC Authorization Code + PKCE、ID token検証、server-side session
- Personal Memory audience / revision-bound read grant
- identity-bound Memory Projectionとaccess-generation invalidation
- principal-keyed Profile
- Personal / shared / Room Memory API
- Project membership、Room-to-Project binding、Room policy
- verified Entra group claimのpolicy inputと、delegated Graph scopeによるlogin-time group overage解決
- membership-approved project selectionをprincipal/configuration/expiryへ結び付けるnon-OIDC ProjectContext
- directory-derived roleのauthoritative reconciliation（manual membership保護とadmin→viewer downgradeを含む）
- safe authentication status / configuration invalidation
- legacy `/api/memories` / `/api/profile` のlocal-mode制限
- Web Memory APIのrequest境界cleanupとauthorization failure時のSQLite store回収

### 残作業（main `dd382cae` の再照合）

1. 必要なdeployment向けに、non-OIDC ProjectContextの既定値を認証済みworkspaceから自動導出するintegrationを追加する（membership検証は常に必須）。
1. Entra groupのlogin後のfreshness/revocationと、Entra以外のtrusted Directory API adapterを設計する。
1. multi-instance / HAを行う前にdurable OIDC session設計を決める。
1. Trusted Proxy / Windows IWA / OAuth / External adapterを実環境trust boundaryで検証する。
1. identity / audience / profile / stale snapshot / revocation / migration / single-user regression gateを全deployment modeで確認する。

Web Memory API request-store cleanup、Entra overageのlogin-time Graph解決とstreaming中のresponse byte制限、non-OIDC ProjectContextの選択cookie、directory role downgrade、およびPrivate Web Roomのidle expiry / cleanupは実装済みであり、再実装対象にしない。

### 受け入れ条件

- browser/model payloadから任意owner/projectを指定して境界を越えられない。
- 未共有Personal Memory、別Project、未所属RoomのMemoryがprojection/APIから取得できない。
- grant / membership / policy取消後、stale snapshotやcontinuationから情報を再利用しない。
- shared evidenceを受信者本人のProfile / Guidanceへ誤帰属しない。
- identity resolver failure時に暗黙 `local` fallbackしない。
- denied requestを繰り返してもSQLite connection resourceが残存しない。

## P0: [Responses API管理機能](responses-api-management.md)

- Status: in-progress
- Priority: P0
- Source: [`src/uagent/docs/TOOL_FLOW.md`](../../src/uagent/docs/TOOL_FLOW.md)

### 対象

- `Retrieve a response`
- `Cancel a response`
- `Count input tokens`
- 手動 `Compact`
- `List input items`
- `Delete a response`
- provider/modelごとのCapability判定

### 実装方針

1. `ResponsesCapabilities` と未対応例外を共通化する（完了）。
1. OpenAI/AzureのRetrieve・Cancel・Compact等を実装する（実装済み、実機検証継続）。
1. `active_response_id` とセッションJSONLの状態管理を統合する（実装済み）。
1. Ctrl-C、Web Stop、タイムアウトからCancelへ接続する（経路確認・テスト継続）。
1. token countとlocal fallbackを実装する（CLI実装済み）。
1. 他プロバイダは実機検証が完了するまで `unknown` / 非対応として扱う。

### 受け入れ条件

- 未対応APIをChat Completionsへ暗黙に切り替えない。
- staleなResponse IDで次の会話が停止しない。
- APIキー、入力本文、秘密情報を状態へ保存しない。
- OpenAI/Azure、非対応プロバイダ、異なるモデル、`:load`をテストする。

## P1: Scheduler durable dispatch

- Status: in-progress
- Priority: P1
- Source: [`docs/UAG_0_7_14_IMPLEMENTATION_REVIEW.md`](../UAG_0_7_14_IMPLEMENTATION_REVIEW.md)、[`docs/SCHEDULER_INSTANCE_ISOLATION_DESIGN.ja.md`](../SCHEDULER_INSTANCE_ISOLATION_DESIGN.ja.md)

### 背景

v0.7.14でSQLite-backed claim / lease、expired lease reclaim、WAL、scheduler instance ownershipが入り、複数processによる同一schedule選択の競合は大幅に改善された。

その後、schedule確定後にin-process sinkが失敗するとexecution eventだけが失われ得る問題に対し、SQLite-backed outboxを導入した。schedule stateとdispatch eventを同じtransactionで確定し、通常のCLI/GUI queueではconsumer dequeueまでoutboxをpending/leasedとして保持する。

### 実装済み

- SQLite `scheduler_events` outboxとpending / delivered / invalid状態
- schedule finalizationとoutbox insertの同一transaction化
- event claim lease、retry可能時刻、attempt count、last error
- sink `put()` failure時のclaim解放と再配信
- CLI/GUI `queue.Queue` のconsumer dequeue ACK
- at-least-once deliveryと、`SchedulerRun` execution stateの分離
- 同一run内の先行pending eventによる順序保証
- `run_id` / `(schedule_id, due_at)` idempotencyによるrun再利用
- 別scheduler instanceによるpending eventの自動取得防止
- 旧instanceのschedule / pending eventを同一transactionで移す明示的orphan reclaim
- reclaim時の旧owner監査情報 `reclaimed_from_instance_id`
- sink failure、run作成後crash、outbox commit後/dequeue前crash、claim lossを模擬する回帰テスト
- ユーザー向け`set_timer`文書の日英更新とdispatch / execution用語の整理

### 残作業

1. `session_id`、principal、project、room、authentication configuration fingerprintを再検証してからreclaimするidentity-bound reclaim serviceを追加する。
1. 実processを複数起動し、schedule claim前／run作成後／outbox commit後／queue put後／consumer ACK前後でprocess killするfailure injection testを追加する。
1. multi-process execution stateまで共有する場合に備え、JSON-backed `SchedulerRunStore` のSQLite統合またはcross-process-safe claim方式を決める。
1. delivered / invalid outbox rowのretention・cleanup方針を決める。
1. authenticated multi-user環境での自動orphan recoveryは、identity-bound reclaim完成まで有効化しない。

### 受け入れ条件

- schedule選択後、sink failureだけでjobがsilent lossしない。**実装済み**
- schedule確定とdispatch event生成の間にtransaction gapがない。**実装済み**
- consumer dequeue前にprocessが停止してもpending outboxが残る。**実装済み**
- crash recoveryで同じidempotent runを再利用してeventを再dispatchできる。**回帰テスト済み**
- 同一`idempotency_key`のrunを二重生成しない。**回帰テスト済み**
- claim lease、dispatch delivery、run execution completionをドキュメント上で混同しない。**反映済み**
- 別instanceへreclaimするときに現在のidentity / authorizationを必ず再検証する。**未完了**
- 実process killを含むmulti-process failure injectionが通る。**未完了**

## P1: [Network Toolkitの運用品質向上](network-toolkit.md)

- Status: in-progress
- Priority: P1
- Source: [`docs/network-toolkit.md`](../network-toolkit.md)

### 対象

- impactランキングとプロセス相関の一括出力強化
- 通信分類の閾値・誤検知評価
- loopback限定ライブキャプチャの継続検証
- LANキャプチャのallowlist設計
- Zeek / Suricata / nmap / tsharkとの高度な連携
- 他端末用の明示的な端末エージェント

### 制約

- 実ネットワークへの送信・キャプチャは明示許可が必要。
- `suspicious` は攻撃確定ではなく要確認状態とする。
- pcapから他端末のプロセス名を推測しない。
- 権限昇格や外部依存の導入を自動化しない。

### 受け入れ条件

- offline解析がlive captureの失敗に影響されない。
- loopback、権限不足、allowlist拒否をテストする。
- 検出結果にcategory、severity、confidence、evidenceを含める。
- LLMへRaw packetやpayloadを既定で返さない。

## P1: [MCP 2026-07-28仕様対応](mcp-2026-07-28.md)

- Status: planned
- Priority: P1
- Source: [`mcp-2026-07-28.md`](mcp-2026-07-28.md)

### 対象

- Stateless MCPコアとlegacy session方式の互換接続
- `MCP-Protocol-Version` / `Mcp-Method` / `Mcp-Name`ヘッダー
- `server/discover`と一覧結果のcache hints
- MRTRの`input_required` / `inputResponses`
- Tasks拡張、認証issuer検証、CIMD移行
- 旧HTTP+SSE、Roots、Sampling、Loggingの移行方針

### 前提

- 現行のMCP / stdio / Streamable HTTP接続を壊さない。
- 仕様バージョン、実装能力、legacy fallbackを明示的に管理する。
- MCPのstateless化とuag内部のA2Aタスク状態を混同しない。

## P1: [GitLab MCP / OAuth連携](gitlab-mcp-oauth.md)

- Status: planned
- Priority: P1
- Source: [`gitlab-mcp-oauth.md`](gitlab-mcp-oauth.md)

### 対象

- GitLab MCP `/api/v4/mcp`へのNative HTTP接続
- OAuth 2.0 Dynamic Client Registration
- pre-registered OAuth Application / `client_id`
- PKCEと固定localhost callback
- client registration永続化
- OAuth bootstrapとMCP protocol detectionの順序整理
- Proxy / enterprise CAを含む社内GitLab相互運用
- `mcp-remote`を利用したstdio fallback

### 前提

- GitLab専用REST tool群ではなく汎用MCP OAuth機能として実装する。
- GitLab側のユーザー権限を認可境界とし、UAGから迂回しない。
- write操作は既存UAGの確認・承認ポリシーと統合する。
- OAuthなしHTTP MCP、stdio、legacy MCPを壊さない。

## P1: [UCP / AP2の未対応機能](ucp-ap2.md)

- Status: planned
- Priority: P1
- Source: [`docs/UCP_INTEGRATION.md`](../UCP_INTEGRATION.md)

### 対象候補

- SD-JWT（Selective Disclosure JWT）
- UCP over A2A transport
- 機能ごとのbuyer review / authorization整理
- UCPツールの出力形式・拡張仕様の整理

実装前に、UCP仕様の対象バージョン、認証境界、ユーザー確認が必要な操作を確定する。

## P1: [Auto-Pilot / Interruptの残課題](auto-pilot-interrupt.md)

- Status: planned
- Priority: P1
- Source: [`docs/INTERRUPT.md`](../INTERRUPT.md)、[`src/uagent/docs/AUTO_REVIEW.md`](../../src/uagent/docs/AUTO_REVIEW.md)

### 対象候補

- 他プロバイダのストリーミング中割り込み
- non-streaming経路の遅延対応
- 環境変数による割り込み動作のカスタマイズ
- CLI / Web / GUIでの停止表示と状態同期

## P2: VS Code拡張の追加機能

- Status: planned

- Priority: P2

- Source: [`docs/VSCODE.md`](../VSCODE.md)

- `uag.autoFix` の実装可否を検討する。

- 実装する場合は、編集前確認、差分表示、undo、権限境界を定義する。

- 自動修正を既定で有効化せず、ユーザー確認を必須にする。

## P2: 開発基盤の改善

- Status: in-progress
- Priority: P2
- Source: [`src/uagent/docs/DEVELOP.md`](../../src/uagent/docs/DEVELOP.md)

### 対象候補

- 各開発者向け文書の英日構成同期
- `*2idx` ツールの仕様・非目標の整理
- MCP、Skills、APMの開発手順の統合
- 実装済み機能と古い設計記録の分離
- v0.7.14以前のMemory V3 staged-status記述を現行実装statusへ更新
- ドキュメント内リンクの継続検査

## 完了・保留へ移す基準

### done

- 実装、テスト、ドキュメント更新が完了している。
- 現行仕様書に実装結果が反映されている。
- 受け入れ条件を確認できる。

### deferred

- 依存する外部仕様が未確定。
- 実機・権限・ネットワーク環境が必要で、通常CIでは検証できない。
- 安全性・運用コストに対する優先度が低い。

## 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-09-24 | Scheduler durable dispatchのSQLite outbox、dequeue ACK、明示orphan reclaim実装を反映 |
| 2026-09-24 | Web Memory request cleanup実装を反映し、Memory V3残作業を更新 |
| 2026-09-24 | v0.7.14実装レビューを反映し、Memory V3 rollout/security completionをP0、Scheduler durable dispatchをP1へ追加 |
| 2026-09-23 | GitLab MCP / OAuth連携計画をP1へ追加 |
| 2026-08-06 | 初版。既存ドキュメントの未実装・将来対応項目を集約 |
