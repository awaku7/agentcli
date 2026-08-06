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
- [`responses-api-management.md`](responses-api-management.md): Responses API管理機能
- [`network-toolkit.md`](network-toolkit.md): Network Toolkit運用品質
- [`n8n-integration.md`](n8n-integration.md): n8n連携
- [`ucp-ap2.md`](ucp-ap2.md): UCP / AP2未対応機能
- [`auto-pilot-interrupt.md`](auto-pilot-interrupt.md): Auto-Pilot / Interrupt残課題
- [`mcp-2026-07-28.md`](mcp-2026-07-28.md): MCP 2026-07-28仕様対応
