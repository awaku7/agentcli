# Claude (Anthropic) 連携の改善方針とTODO

Anthropic API（Claude）との連携において、最新モデル（Claude 3.7 Sonnetなど）の機能最大化や、極限状態での安定運用のために改善すべき課題と方針です。

## 1. 課題と改善方針

### 課題A: `max_tokens` のハードコーディング（4096トークン制限）
- **現状**: `src/uagent/llm_claude.py` 内で `max_tokens` が `4096` に固定されています。
- **影響**: 最新モデル（Claude 3.5/3.7 Sonnetなど）がサポートする 8,192 トークン以上の出力や、思考（Reasoning）有効時の長大な出力を十分に活かせず、途中で生成が途切れる可能性があります。
- **改善方針**: 
  - 環境変数（例: `UAGENT_MAX_TOKENS`）から動的に取得できるようにする。
  - モデル名や思考の有無に応じて、デフォルト値を `8192` などに引き上げる。

### 課題B: 思考ブロック（`thinking`）のパースと表示対応
- **現状**: Claude 3.7 Sonnet などで思考（Reasoning）を有効にした場合、APIレスポンスの `response.content` に `type == "thinking"` のブロックが含まれますが、現在のコードは `text` と `tool_use` のみを処理しています。
- **影響**: LLMの思考プロセスがコンソールやログに表示されず、ブラックボックス化します。
- **改善方針**:
  - `block.type == "thinking"` を検知し、思考内容を抽出・保持する。
  - 抽出した思考内容を、OpenAIの `reasoning_content` 相当として上位モジュール（`llm_round_helpers.py` など）に引き渡せるようにする。

### 課題C: 画像（マルチモーダル）入力の変換対応
- **現状**: OpenAI形式の `messages` から Anthropic形式への変換ロジックにおいて、`content` が文字列である前提の処理になっており、画像データ（`image_url` など）の構造化データが考慮されていません。
- **影響**: 履歴に画像が含まれるマルチモーダルなセッションにおいて、Claude への変換時に画像データが脱落するか、パースエラーになる可能性があります。
- **改善方針**:
  - `content` がリスト形式（マルチモーダル形式）の場合に、画像ブロック（`type: "image"`）を Anthropic の `image` 形式（base64データなど）に正しくマッピングする処理を追加する。

---

## 2. アクションアイテム（TODO）

- [ ] `src/uagent/llm_claude.py` の `max_tokens` を動的化（環境変数またはモデル別デフォルト値の適用）。
- [ ] `response.content` のループ処理に `block.type == "thinking"` のハンドリングを追加し、思考ログを上位に返す仕組みの実装。
- [ ] `claude_chat_with_tools` 内のメッセージ変換処理を拡張し、`image_url` などのマルチモーダルコンテンツの変換に対応。
