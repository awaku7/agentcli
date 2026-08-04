# Responses API 対応状況と今後の優先順位

## 現在の対応状況

| Responses API | 対応状況 | 備考 |
|---|---:|---|
| Create a response | 対応済み | `client.responses.create()` を通常・ストリーミングで使用 |
| Retrieve a response | 未対応 | `client.responses.retrieve()` は未使用 |
| Delete a response | 未対応 | `client.responses.delete()` は未使用 |
| List input items | 未対応 | `responses.input_items.list()` 相当は未使用 |
| Count input tokens | Responses APIとしては未対応 | ローカルの概算token数計算は存在 |
| Cancel a response | 未対応 | Ctrl-C等のローカル中断はあるが、API側のResponseキャンセルは未実装 |
| Compact a response | 部分対応 | Create時に`context_management`を指定し、サーバー側コンパクションを要求 |

## プロバイダー別の対応レベル

ここでいうレベルは、公式APIの網羅的な実機検証ではなく、agentcliの現在の実装経路に基づく分類である。

| プロバイダー | レベル | Create / streaming | 継続 | 自動compact | 実装上の注意 |
|---|:---:|---|---|---|---|
| OpenAI | A | 対応 | 対応 | 対応 | 標準のResponsesリクエストビルダーを使用 |
| Azure OpenAI | A | 対応 | 対応 | 対応 | OpenAI互換経路。APIバージョン・モデル差異は要確認 |
| Amazon Bedrock | B | 対応 | 送信を試行 | 送信を試行 | inputを単一文字列へ変換し、tool定義もフラット化 |
| OpenRouter | B | 対応 | 無効化 | 無効化 | inputを文字列化。継続はローカル履歴で処理 |
| DeepSeek | B | 対応 | 非対応 | 非対応 | stateless。現状は`deepseek-v4-flash`前提 |
| Ollama | C | 対応 | サーバー依存 | サーバー依存 | `extra_body`と`max_output_tokens`を補正。固有機能は要検証 |
| Alibaba / Qwen | C | 汎用経路で試行 | 要検証 | 要検証 | 専用Responses互換処理なし |
| LM Studio | C | 汎用経路で試行 | 要検証 | 要検証 | ローカルサーバーの対応バージョンに依存 |
| Sakana AI / Fugu | C | 汎用経路で試行 | 要検証 | 要検証 | FuguはResponses APIを自動有効化する対象 |
| llama.cpp | D | 非対応 | 非対応 | 非対応 | 標準`llama-server`はChat Completions中心。Responses API変換プロキシが必要 |

### レベルの意味

- **A**: OpenAI/Azure形式に近く、Create、streaming、tool calling、継続、自動compactを実装上扱える。
- **B**: Create、streaming、tool callingは扱えるが、独自形式または一部機能の無効化が必要。
- **C**: OpenAI互換の汎用経路でCreateを試行できるが、継続・compact等は要検証。
- **D**: 現在の実装ではResponses経路を推奨できない。

## プロバイダー共通の制約

- Retrieve、Delete、List input items、Count input tokens、Cancelを呼び出す実装はまだない。
- 「継続」「自動compact」は、管理エンドポイントではなくCreateリクエストの関連パラメーターを指す。
- OpenRouterは`previous_response_id`と`context_management`を削除し、ローカル履歴を文字列化して送る。
- DeepSeekはstatelessとして扱い、`previous_response_id`と`context_management`を使用しない。
- Bedrock、Ollama、Alibaba/Qwen、LM Studio、Sakanaは、接続するゲートウェイやモデルごとの差異が大きい。
- llama.cppを使う場合は`UAGENT_RESPONSES=0`としてChat Completions経路を使う。

## サポート優先順位

1. **Cancel a response** — Ctrl-C、WebのStop、タイムアウトとAPI側の停止を連携する。
2. **Retrieve a response** — `previous_response_id`の有効性確認とセッション復元に使う。
3. **Count input tokens** — コンテキスト上限、compact、コスト計算を正確にする。
4. **手動 Compact** — 既存の自動compactに`/compact`操作を追加する。
5. **List input items** — サーバー側履歴を正式なストレージとして利用する場合に対応する。
6. **Delete a response** — 履歴削除や機密情報消去が必要になった段階で対応する。

## 今後の方針

1. 共通のResponses管理APIクライアントを追加する。
2. プロバイダーごとに`retrieve`、`cancel`、`input_items.list`、`input_tokens`、`compact`のCapabilityを定義する。
3. Capabilityが不明または非対応の場合は、ローカル履歴・ローカルtoken推定・ローカルshrinkへフォールバックする。
4. 最初の実機検証対象はOpenAI、Azure、OpenRouter、DeepSeekとする。

## 参照

- [llama.cpp #19138: Support OpenAI Responses API](https://github.com/ggml-org/llama.cpp/issues/19138)
