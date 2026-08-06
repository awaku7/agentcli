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

## P0: [Responses API管理機能](responses-api-management.md)

- Status: planned
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

1. `ResponsesCapabilities` と未対応例外を共通化する。
1. OpenAI/AzureのRetrieveを実装する。
1. `active_response_id` とセッションJSONLの状態管理を統合する。
1. Ctrl-C、Web Stop、タイムアウトからCancelへ接続する。
1. token countとlocal fallbackを実装する。
1. 他プロバイダは実機検証が完了するまで `unknown` / 非対応として扱う。

### 受け入れ条件

- 未対応APIをChat Completionsへ暗黙に切り替えない。
- staleなResponse IDで次の会話が停止しない。
- APIキー、入力本文、秘密情報を状態へ保存しない。
- OpenAI/Azure、非対応プロバイダ、異なるモデル、`:load`をテストする。

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

## P1: [n8n連携の実証](n8n-integration.md)

- Status: planned
- Priority: P1
- Source: [`docs/n8n/README.md`](../n8n/README.md)

### Phase 0

- n8n Instance-level MCPを有効化する。
- 検証用WorkflowだけをMCP公開する。
- uagから `mcp_tools_list` と `search_workflows` を確認する。
- uagからWorkflowを1本実行する。
- n8nからuag A2Aへpingする。
- トークンがGit管理下に含まれないことを確認する。

### Phase 1以降

- 公開Workflowの最小集合化
- description整備
- 危険操作の二重確認
- correlation IDとmax depthによるループ防止
- MCPで不足する場合のみ専用`n8n_*`ツールを設計する

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
| 2026-08-06 | 初版。既存ドキュメントの未実装・将来対応項目を集約 |
