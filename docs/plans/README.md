# 実装計画ドキュメント

`docs/plans/` は、これから実装・検証・改善する内容を管理するディレクトリです。

## 使い分け

| ディレクトリ | 内容 |
|---|---|
| `docs/` | 利用者向けガイド、現行仕様、現行設計 |
| `src/uagent/docs/` | 開発者向けの現行実装仕様 |
| `docs/plans/` | 未実装・検証中・将来実装の計画 |
| `docs/archive/` | 完了済みの旧設計・履歴（必要になった場合に追加） |

## 計画ファイルの書式

各計画では、少なくとも以下を記載します。

```markdown
# タイトル

- Status: planned / in-progress / done / deferred
- Priority: P0 / P1 / P2
- Source: 現在の仕様書・課題の参照元

## 目的
## 対象範囲
## 対象ファイル
## 実装内容
## 受け入れ条件
## テスト計画
## 依存関係・リスク
## 更新履歴
```

## 運用ルール

- 実装済みになった項目は計画から完了扱いにし、現行仕様書へ反映する。
- 現行仕様と計画を同じ文書に混在させない。
- 実装前の仮説や未検証情報は、現行仕様として断定しない。
- コードやテストの変更時は、対象計画のStatusと受け入れ条件を更新する。
- ファイルを移動・統合した場合は、参照元のリンクを同じコミットで修正する。

## 一覧

- [`IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md): 実装予定項目の一覧と優先順位
- [`network-toolkit.md`](network-toolkit.md): Network Toolkit運用品質
- [`mcp-current-implementation.md`](mcp-current-implementation.md): MCP現行実装棚卸し
- [`gitlab-mcp-oauth.md`](gitlab-mcp-oauth.md): GitLab MCPを主要ユースケースとした汎用MCP OAuth DCR / pre-registered client設計

Responses API、UCP/AP2、MCP 2026-07-28、Auto-Pilot/Interrupt の残課題は上記ロードマップ内で管理します（未作成の個別計画ファイルにはリンクしません）。

実装済みの [Sub-Agent Job Runtime V1設計](../archive/sub-agent-job-runtime-v1.md) は履歴保管へ移し、現在の機能説明は [Sub-Agent設計](../subagent.md) を参照してください。権限検証用の [Sub-Agentテスト手順](../sub-agent-permissions-test.md) は利用可能な手順書として `docs/` に移動しました。
