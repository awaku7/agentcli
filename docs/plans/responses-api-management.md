# Responses API管理機能

- Status: in-progress
- Priority: P0
- Source: [`src/uagent/docs/TOOL_FLOW.md`](../../src/uagent/docs/TOOL_FLOW.md)

## 目的

Responses APIのRetrieve、Cancel、input token count、Compact、履歴管理をプロバイダ差異を隠して提供する。

## 実装済み

- `ResponsesCapabilities` と `UnsupportedResponsesOperation`
- OpenAI/Azure の `retrieve` / `cancel` / `delete` / `list_input_items` / `count_input_tokens` / `compact`
- CLI の `:response status|cancel|tokens|compact|items|delete`
- `active_response_id` と `_responses_client` の実行時追跡
- stale Response ID の検証と `:load` 時の継続判定

## 残作業

- OpenAI/Azure の実機検証と回帰テスト拡充
- Ctrl-C / Web Stop / timeout の実機経路確認
- 非対応プロバイダの明示的なフォールバック表示

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
