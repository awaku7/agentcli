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

## P0: Enterprise E0 — リモート入口からの全ツール実行隔離

- Status: planned（Enterprise E0の実装・受け入れ検証が未完了）
- Priority: P0（認証付きmulti-user Web / 外部公開A2Aでtool実行を許可する前の必須条件）
- Source: [Enterprise Platform Design — Phase E0](../UAG_ENTERPRISE_PLATFORM_DESIGN.md)

### 必須の実装境界

- 認証付きmulti-user Web（内部ネットワーク限定を含む）、外部到達可能なWeb / WebSocket、ツール実行可能な外部公開A2Aなど、通常のAgent tool loopに到達するremote ingressを漏れなく対象とする。
- **すべてのdata-plane tool action** を **sandbox execution / 狭い権限のbrokered control-plane action / deny** のいずれかに分類し、remote ingressからhost OSへの直接実行を禁止する。shell、filesystem、Python、Computer Use、Skills、Plugin、MCP/A2A helper等をPluginだけに限定せず含める。
- Agent/tool dispatchとhostの間に `ExecutionBroker` 境界を導入する。principal / Project / Room / session、Unified Policy、workspace投影、credential注入、実行資源・network制限、結果回収、cleanup、auditを管理する。
- remote実行プロファイルで隔離backendを利用できない場合は **fail closed** とし、host実行へフォールバックしない。local-trustedなCLI / GUI / 明示的local-only Webとは境界を分ける。
- control-planeの認証情報・policy・監査操作を汎用sandboxへ渡さない。hardware / device操作はremote ingressで既定拒否とする。

### 受け入れ条件

- Web UI / WebSocket / A2Aなどの各remote経路と各ツール種別について、sandbox・broker・deny以外の実行経路がないことを自動テストと実環境検証で確認する。
- 隔離backendの停止、権限不足、scopeの不一致、sandbox終了後cleanup、並行する異なるprincipal / Projectでの漏洩がfail closedとなる。
- Plugin固有のsandbox強化（下記P2候補）を完了しても、このE0の全ツール隔離・`ExecutionBroker` が検証されるまではremote実行隔離の完了としない。

## P0: Memory V3 rollout / security completion

- Status: in-progress
- Priority: P0
- Source: [`docs/UAG_MEMORY_V3_SECURITY_HARDENING.md`](../UAG_MEMORY_V3_SECURITY_HARDENING.md)、[`docs/UAG_MEMORY_ARCHITECTURE_V3.md`](../UAG_MEMORY_ARCHITECTURE_V3.md)

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
- non-OIDCで固定/OIDC/選択済みbindingがない場合、trusted workspaceから既定Projectを導出し、membership確認後だけ利用するProjectContext fallback
- directory-derived roleのauthoritative reconciliation（manual membership保護とadmin→viewer downgradeを含む）
- safe authentication status / configuration invalidation
- legacy `/api/memories` / `/api/profile` のlocal-mode制限
- Web Memory APIのrequest境界cleanupとauthorization failure時のSQLite store回収

### 残作業（workspace-derived ProjectContext統合後）

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

## P0: Responses API管理機能

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
- Source: [`docs/SCHEDULER_INSTANCE_ISOLATION_DESIGN.ja.md`](../SCHEDULER_INSTANCE_ISOLATION_DESIGN.ja.md)

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

## P1: MCP 2026-07-28仕様対応

- Status: planned
- Priority: P1
- Source: [MCP現行実装棚卸し](mcp-current-implementation.md)

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

## P1: UCP / AP2の未対応機能

- Status: planned
- Priority: P1
- Source: [`docs/UCP_INTEGRATION.md`](../UCP_INTEGRATION.md)

### 対象候補

- SD-JWT（Selective Disclosure JWT）
- UCP over A2A transport
- 機能ごとのbuyer review / authorization整理
- UCPツールの出力形式・拡張仕様の整理

実装前に、UCP仕様の対象バージョン、認証境界、ユーザー確認が必要な操作を確定する。

## P1: Auto-Pilot / Interruptの残課題

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

## P2: Context Runtime現行設計との差分確認

- Status: in-progress（旧TODOの基盤項目は実装済み。現行設計の拡張要件は未照合。Vertex AI実環境回帰はユーザー確認済み）
- Priority: P2（現行設計の実装差分の再評価）
- Source: [Context Management Design §32](../UAG_CONTEXT_MANAGEMENT_DESIGN.md)、[旧Context Runtime実装計画](../archive/UAG_CONTEXT_RUNTIME_TODO.md)

### 現行設計の残存課題を再照合する

旧TODOの9つの基盤項目（ActiveContextBuilder、Budget、Retrieval、Token-aware推定、Decision Log、Debug Snapshot、Benchmark等）は実装済みの履歴記録として保管する。ただし、**これはContext Management Designの最終要件がすべて完了したことを意味しない**。2026-10-12にコード・既存テストを読み取り照合した結果、以下は**項目2の基盤実装済み、他9領域の部分実装**と判定した。各領域の根拠・未確認の境界は[現行設計§32.3](../UAG_CONTEXT_MANAGEMENT_DESIGN.md)に記載。全入口・Providerの実行確認や新規テスト実行は行っていない。

1. ContextManagerの統合層（`context_manager.py`にfacadeは存在するため、実際の全実行経路への接続を確認）。**加えてProvider Native Tool Searchおよびnative compactionが`ContextPolicy`から一貫して制御されるか**、OpenAI/Azure/Gemini等のProvider固有設定・フォールバックを含めて検証する。facade接続確認だけでは完了としない。 **§7.3/§24/Phase 5のProvider `supports_context_editing` / Anthropic `context_edit`もTool Search/native compactionとは別に、capability検出・Policy制御・未対応時fallbackを検証する。**
2. ToolResultRecordの統一管理（`tool_result_manager.py`にrecordは存在するため、永続化・全呼出元での利用を確認）。
3. Structured Resultから段階的なSummaryを生成する処理（軽量要約と任意のLLM要約の範囲）。
4. Resultの重要度・再取得可能性・evictable・保持期限の判断。
5. Context Budget、Provider/Model別の予算配分、evictionの一元適用。**warning/compaction/emergency閾値の`ContextPolicy`制御と設計§16の例示値との整合**を確認（現行`ContextBudget.usage()`は80%/90%/100%固定）。 **§17に列挙されたResultサイズ閾値、recent_message_count、Tool Search/Result Management/Compaction/Retrievalの機能スイッチもPolicyから一元適用されるか確認する。§20のwarning/compact/emergency判定が準備・履歴圧縮・Tool Result削減・State再構築・Retrievalなどの実処理を発火することも受け入れ条件とする。**
6. Agent State、checkpoint、process restart後の実行状態復旧。設計§12の`failed_steps`/`important_facts`の未充足、および失敗ステップを誤って完了扱いにしない更新規則を確認。
7. 全Tool実行後に共通Result Managerと3系統projectionを通す経路。**主要Tool経路が`projections.llm_context`ではなく`materialized_result`をLLMへ渡している現状**を含め、LLM/UI/Historyの各projectionが実際の受け手へ届くことを検証。
8. 検索・再注入の範囲。**同一Sessionのtext/JSON Artifact先頭最大2,000文字の自動preview取得は実装済み**。残る検証候補は意味検索、関連箇所選択、他メディアの扱い（必要性と権限境界を先に評価）。 **§15/Phase 4に従い、Session履歴（message/search/summary）とMemoryの検索・Context再注入および各入口の認可境界も確認する。`memory_projection.py`の本番投影と`memory_retrieval.py`のshadow観測は別扱い。**
9. 画像・音声・PDF・スクリーンショット・MCP blob等の共通Artifact化と機密データの保護。
10. Resultごとのretention、参照数、孤児データ回収、Artifact quotaと削除。

**2026-10-12 PR 1追補（未マージ）:** Tool Result保存境界の再帰的secret/Binary sanitizer、512 KiB UTF-8レコード上限、Artifact実ファイルの検査を実装・回帰テスト中。保護範囲はSessionStoreの新規Tool Resultレコードおよび新規Tool ResultテキストArtifactであり、過去DB/Artifactの移行、全MediaのArtifact化、Tool messageのLLM projection統合は含まない。PR CI・レビュー・ユーザーによるマージ前の作業ブランチ状態として記録する。

旧設計にあった「`ContextManager`や`ToolResultRecord`が存在しない」という誤記は現行設計§32.3で修正済み。**基盤実装済みと全実行経路での要求充足は異なる**ため、拡張実装の要否は上記の残る差分と受け入れ条件を確認してから決める。

### Vertex AI実環境回帰（確認済み）

2026-10-12、ユーザーから次の3項目について実機検証済みとの報告を受けた。通常動作の推定やCIでの検証完了と混同せず、**ユーザーによる実機確認結果**として記録する。

- [x] Ctrl+Cによる中断・停止。
- [x] 中断・承認後の会話継続と、Userターン／Provider Projectionの整合性。
- [x] `tool_load` 連続実行時のTool定義・応答・コンテキスト復元。

この3項目を未検証の残作業として再起票しない。新たな不具合が報告された場合に限り再現確認・回帰テスト・Provider固有Projectionの修正を検討する。

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

## P2: 旧改善計画からの再評価候補

- Status: planned（必要性と現行実装の再照合待ち）
- Priority: P2（旧文書の優先順位をそのまま引き継がない）
- Source: [2026-08-19時点の改善計画・完了判定](../archive/IMPROVEMENT_PRIORITY.md)、[Enterprise Platform Design](../UAG_ENTERPRISE_PLATFORM_DESIGN.md)、[Distributed Coordination](../DISTRIBUTED_COORDINATION.md)

2026-08-19時点の改善計画は20/20の主要項目を完了と判定した履歴記録です。次の項目はその計画で **主要実装の完了とは別スコープ** とされた候補であり、現行コードとの再照合なしに未実装と断定しません。

- Plugin sandbox: 作業ディレクトリ、ネットワーク、subprocess、リソース制限の実行時隔離要件をEnterprise設計と突き合わせ、既存Policyと役割を分ける。これは上記P0のEnterprise E0リモート入口全ツール実行隔離とは別の改善候補。
- 分散実行: A2Aのlease競合、再接続、二重実行、ネットワーク分断時の安全性を評価する。etcd / ZooKeeper相当のconsensusは具体的な必要性が出た場合だけ検討する。
- Provider metadata: llama.cppの`/props`、Ollamaの`/api/show`に由来する情報をCLI/Web/GUIでどう表示するか再評価する。

OpenTelemetryのtrace/span/exporter実装は [現行OpenTelemetry設計](../UAG_OPENTELEMETRY_DESIGN.md) においてPhase 4Dまで実装済みです。旧計画の「未導入」という記述から実装タスクを再起票しません。Credential CLIおよびイベントの共通envelope/カテゴリ別payloadも旧計画上は実装済みのため、ここでは再実装対象にしません。

### 着手の条件

- 既存実装・テストと現行設計を再確認し、未充足の具体的な要件だけを独立した計画・issueにする。
- 実環境の検証が必要な項目は、机上の仕様上の不足と実機検証待ちを区別する。

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
