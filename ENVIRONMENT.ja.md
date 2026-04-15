# 環境変数と設定

`uag` は環境変数を使用して、LLMプロバイダの認証情報やエージェントの動作を制御します。これらの変数は通常、カレントディレクトリの `.env` ファイルに保存されます。

## セットアップウィザード

最も簡単に設定を行うには、以下のコマンドを実行して対話型セットアップウィザードを起動してください：

```bash
uag_setup
# または
python -m uagent.setup_cli
```

### 自動セットアップ
`uag` 起動時に必要な環境変数（プロバイダ設定など）が不足している場合、システムは**自動的にセットアップウィザードを起動**します。ウィザードが完了すると、設定内容が `.env` に保存され、エージェントが利用可能になります。

---

## 主要な環境変数

### 1. プロバイダの選択 (`UAGENT_PROVIDER`)

起動時に使用するメインのプロバイダを指定します（必須）。

- 有効な値: `openai`, `azure`, `anthropic`, `gemini`, `bedrock`, `openrouter`, `ollama`, `grok`, `nvidia`, `claude`

### 2. LLM プロバイダ別の設定

各プロバイダで必要な変数は以下の通りです。モデル名の指定には `UAGENT_<PROVIDER>_DEPNAME` を使用します。

| プロバイダ | 認証・エンドポイント設定 | モデル名指定 (任意) |
| :--- | :--- | :--- |
| **OpenAI** | `UAGENT_OPENAI_API_KEY`, `UAGENT_OPENAI_BASE_URL` | `UAGENT_OPENAI_DEPNAME` |
| **Azure OpenAI** | `UAGENT_AZURE_API_KEY`, `UAGENT_AZURE_BASE_URL`, `UAGENT_AZURE_API_VERSION` | `UAGENT_AZURE_DEPNAME` |
| **Anthropic** | `UAGENT_CLAUDE_API_KEY` | `UAGENT_CLAUDE_DEPNAME` |
| **Google (Gemini)** | `UAGENT_GEMINI_API_KEY` | `UAGENT_GEMINI_DEPNAME` |
| **Google (Vertex AI)** | `UAGENT_VERTEXAI_API_KEY`, `UAGENT_VERTEXAI_PROJECT`, `UAGENT_VERTEXAI_LOCATION` | `UAGENT_VERTEXAI_DEPNAME` |
| **AWS Bedrock** ※ | `UAGENT_BEDROCK_BASE_URL`, `UAGENT_BEDROCK_API_KEY` | `UAGENT_BEDROCK_DEPNAME` |
| **OpenRouter** | `UAGENT_OPENROUTER_API_KEY`, `UAGENT_OPENROUTER_BASE_URL` | `UAGENT_OPENROUTER_DEPNAME` |
| **Ollama** | `UAGENT_OLLAMA_BASE_URL` (既定: `http://localhost:11434/v1`) | `UAGENT_OLLAMA_DEPNAME` |
| **Grok (xAI)** | `UAGENT_GROK_API_KEY`, `UAGENT_GROK_BASE_URL` | `UAGENT_GROK_DEPNAME` |
| **NVIDIA** | `UAGENT_NVIDIA_API_KEY`, `UAGENT_NVIDIA_BASE_URL` | `UAGENT_NVIDIA_DEPNAME` |

> ※ **AWS Bedrock について**: 現在の `uag` 実装では、Bedrock の OpenAI 互換エンドポイントを使用することを想定しています。

### 3. エージェントの基本動作

- `UAGENT_LANG`: ホスト UI の言語 (`ja`, `en`)。
- `UAGENT_WORKDIR`: エージェントが操作を行うデフォルトの作業ディレクトリ。
- `UAGENT_STREAMING`: LLM 応答の逐次表示（ストリーミング）の有効化 (`1`: 有効(既定), `0`: 無効)。
- `UAGENT_VERBOSITY`: ログ出力の冗長性 (`low`, `medium`, `high`)。
- `UAGENT_DEBUG_ENDPOINT`: `1` に設定すると、起動時に使用されるエンドポイントとモデル情報を出力します。

### 4. 高度な機能 (Responses API, 推論等)

- `UAGENT_RESPONSES`: `1` に設定すると、対応プロバイダ（Azure/OpenAI/Bedrock/Ollama）で "Responses API" を有効にします。
- `UAGENT_REASONING`: 推論モデル（o1等）の推論の試行レベル (`auto`, `low`, `medium`, `high`)。
- `UAGENT_STREAMING_DEBUG`: `1` に設定すると、ストリーミング中の各イベント（JSON）を `outputs/streaming_debug/` に保存します。

### 5. 画像の生成と解析

- `UAGENT_IMG_GENERATE_PROVIDER`: 画像生成に使用するプロバイダ (既定: `UAGENT_PROVIDER`)。
- `UAGENT_<PROVIDER>_IMG_GENERATE_DEPNAME`: 画像生成用モデル ID (例: `dall-e-3`)。
- `UAGENT_IMG_ANALYSIS_PROVIDER`: 画像解析に使用するプロバイダ (既定: `UAGENT_PROVIDER`)。
- `UAGENT_IMAGE_OPEN`: 画像生成後に自動で開くかどうか (`0` で無効化)。

### 6. 翻訳機能 (オプション)

- `UAGENT_TRANSLATE_PROVIDER`: 翻訳エンジン (`openai`, `azure`, `openrouter` 等の OpenAI 互換、または `argos`)。
- `UAGENT_TRANSLATE_TO_LLM`: LLM へ送る前の翻訳先言語 (例: `en`)。
- `UAGENT_TRANSLATE_FROM_LLM`: LLM からの応答を翻訳する際の言語 (例: `ja`)。
- `UAGENT_TRANSLATE_DEPNAME`: 翻訳に使用するモデル ID。

### 7. 記憶とセマンティック検索

- `UAGENT_MEMORY_FILE`: 長期記憶メモの保存先パス。
- `UAGENT_SHARED_MEMORY_FILE`: 共有長期記憶の保存先パス。
- `UAGENT_EMBEDDING_API_URL`: 埋め込み (Embedding) API の URL。

---

## セキュリティと暗号化 (`uag_envsec`)

APIキーなどの機密情報を平文の `.env` ファイルに保存したくない場合は、`uag_envsec` を使用してファイルを暗号化できます。

1. **暗号化**: `uag_envsec .env` を実行し、パスワードを入力。
2. **利用**: `uag` 起動時に `.env.sec` が自動的に検出され、パスワード入力により復号・読み込みが行われます。
