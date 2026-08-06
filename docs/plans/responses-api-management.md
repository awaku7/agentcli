# Responses API管理機能

- Status: planned
- Priority: P0
- Source: [`src/uagent/docs/TOOL_FLOW.md`](../../src/uagent/docs/TOOL_FLOW.md)

## 目的

Responses APIのRetrieve、Cancel、input token count、Compact、履歴管理をプロバイダ差異を隠して提供する。

## 対象

- `ResponsesCapabilities`
- OpenAI/AzureのRetrieve・Cancel
- Ctrl-C / Web Stop / timeout連携
- `previous_response_id` とセッションJSONL
- stale Response IDの安全な破棄
- 非対応プロバイダのlocal fallback

## 受け入れ条件

- 未対応APIをChat Completionsへ暗黙に切り替えない
- stale IDで次の会話が停止しない
- APIキー・入力本文・秘密情報を保存しない
- OpenAI、Azure、非対応プロバイダ、モデル変更、`:load`をテストする
