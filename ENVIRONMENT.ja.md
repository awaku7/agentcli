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

- 有効な値: `openai`, `azure`, `bedrock`, `openrouter`, `ollama`, `gemini`, `vertexai`, `grok`, `claude`, `nvidia`

### 2. LLM プロバイダ別の設定

各プロバイダで必要な変数は以下の通りです。モデル名の指定には `UAGENT_<PROVIDER>_DEPNAME` を使用します。

| プロバイダ | 認証・エンドポイント設定 | モデル名指定 (任意) |
| :--- | :--- | :--- |
| **OpenAI** | `UAGENT_OPENAI_API_KEY`, `UAGENT_OPENAI_BASE_URL` | `UAGENT_OPENAI_DEPNAME` |
| **Azure OpenAI** | `UAGENT_AZURE_API_KEY`, `UAGENT_AZURE_BASE_URL`, `UAGENT_AZURE_API_VERSION` | `UAGENT_AZURE_DEPNAME` |
| **Claude (Anthropic)** | `UAGENT_CLAUDE_API_KEY` | `UAGENT_CLAUDE_DEPNAME` |
| **Google (Gemini)** | `UAGENT_GEMINI_API_KEY` | `UAGENT_GEMINI_DEPNAME` |
| **Google (Vertex AI)** | `UAGENT_VERTEXAI_API_KEY`（必須） | `UAGENT_VERTEXAI_DEPNAME`（必須） |
| **AWS Bedrock** ※ | `UAGENT_BEDROCK_BASE_URL`, `UAGENT_BEDROCK_API_KEY` | `UAGENT_BEDROCK_DEPNAME` |
| **OpenRouter** | `UAGENT_OPENROUTER_API_KEY`, `UAGENT_OPENROUTER_BASE_URL` | `UAGENT_OPENROUTER_DEPNAME` |
| **Ollama** | `UAGENT_OLLAMA_BASE_URL` (既定: `http://localhost:11434/v1`) | `UAGENT_OLLAMA_DEPNAME` |
| **Grok (xAI)** | `UAGENT_GROK_API_KEY`, `UAGENT_GROK_BASE_URL` | `UAGENT_GROK_DEPNAME` |
| **NVIDIA** | `UAGENT_NVIDIA_API_KEY`, `UAGENT_NVIDIA_BASE_URL` | `UAGENT_NVIDIA_DEPNAME` |

> ※ **AWS Bedrock について**: 現在の `uag` 実装では、Bedrock の OpenAI 互換エンドポイントを使用することを想定しています。

### 3. エージェントの基本動作

- `UAGENT_LANG`: ホスト UI の言語（例: `en`, `ja`, `zh_CN`, `zh_TW`, `ko`, `th`, `es`, `fr`, `de`, `it`, `pt_BR`, `ru`）。
- `UAGENT_WORKDIR`: エージェントが操作を行うデフォルトの作業ディレクトリ。
- `UAGENT_STREAMING`: LLM 応答の逐次表示（ストリーミング）の有効化 (`1`: 有効(既定), `0`: 無効)。
- `UAGENT_VERBOSITY`: ログ出力の冗長性 (`off`, `low`, `medium`, `high`)。
- `UAGENT_DEBUG_ENDPOINT`: `1` に設定すると、起動時に使用されるエンドポイントとモデル情報を出力します。

### 4. 高度な機能 (Responses API, 推論等)

- `UAGENT_RESPONSES`: `1` に設定すると、対応プロバイダ（Azure/OpenAI/Bedrock/Ollama）で "Responses API" を有効にします。
- `UAGENT_REASONING`: 推論モデル（o1等）の推論の試行レベル (`off`, `auto`, `minimal`, `low`, `medium`, `high`, `xhigh`)。
- `UAGENT_STREAMING_DEBUG`: `1` に設定すると、ストリーミング中の各イベント（JSON）を `outputs/streaming_debug/` に保存します。

### 5. 画像の生成と解析

- `UAGENT_IMG_GENERATE_PROVIDER`: 画像生成に使用するプロバイダ (既定: `UAGENT_PROVIDER`)。
- `UAGENT_<PROVIDER>_IMG_GENERATE_DEPNAME`: 画像生成用モデル ID (例: `dall-e-3`)。
- `UAGENT_IMG_ANALYSIS_PROVIDER`: 画像解析に使用するプロバイダ (既定: `UAGENT_PROVIDER`)。
- `UAGENT_IMAGE_OPEN`: 画像生成後に自動で開くかどうか (`0` で無効化)。

### 6. 翻訳機能 (オプション)

ユーザー入力と LLM 応答の自動翻訳を有効にします。

- `UAGENT_TRANSLATE_PROVIDER`: 翻訳エンジン。
  - `argos`: [Argos Translate](https://github.com/argosopentech/argos-translate) を使うローカル翻訳（`pip install argostranslate` が必要）。
  - `openai`, `azure`, `openrouter`, `openai_compat`: OpenAI 互換 API を使う翻訳。
  - *注意: ネイティブの Gemini / Claude 翻訳はまだ未対応です。*
- `UAGENT_TRANSLATE_TO_LLM`: ユーザー入力の翻訳先言語 (例: `en`)。英語らしい入力はそのまま送られます。
- `UAGENT_TRANSLATE_FROM_LLM`: LLM 応答の翻訳先言語 (例: `ja`)。
- `UAGENT_TRANSLATE_DEPNAME`: 翻訳に使用するモデル ID（API プロバイダでは必須）。
- `UAGENT_TRANSLATE_API_KEY`: 翻訳用 API キー（任意。既定で `UAGENT_API_KEY` を使用）。
- `UAGENT_TRANSLATE_BASE_URL`: 翻訳用のベース URL（任意。既定で `UAGENT_BASE_URL` を使用）。

### 7. 記憶とセマンティック検索

- `UAGENT_MEMORY_FILE`: 長期記憶メモの保存先パス。
- `UAGENT_SHARED_MEMORY_FILE`: 共有長期記憶の保存先パス。
- `UAGENT_EMBEDDING_API_URL`: 埋め込み (Embedding) API の URL。

---

## A2A サーバー

`uaga` は Agent2Agent 互換の HTTP サーバーを提供します。以下で設定できます：

- `UAGENT_A2A_HOST`: サーバーのバインド先ホスト（既定: `0.0.0.0`）。
- `UAGENT_A2A_PORT`: 待受ポート（既定: `8765`）。
- `UAGENT_A2A_RELOAD`: 開発時の自動リロードを有効化します。
- `UAGENT_A2A_PUBLIC_BASE_URL`: クライアントに公開するベース URL。
- `UAGENT_A2A_CONCURRENCY`: タスク実行の同時実行数制限。
- `UAGENT_A2A_ENGINE`: A2A 実行モード。
- `UAGENT_A2A_TOKEN`: 認証済みエンドポイント用の Bearer トークン。空欄なら認証を無効化します。

## セキュリティと暗号化 (`uag_envsec`)

APIキーなどの機密情報を平文の `.env` ファイルに保存したくない場合は、`uag_envsec` を使用してファイルを暗号化できます。

1. **暗号化**: `uag_envsec .env` を実行し、パスワードを入力。
2. **利用**: `uag` 起動時に `.env.sec` が自動的に検出され、パスワード入力により復号・読み込みが行われます。
3. **更新**: 既存の `.env.sec` に変数を追加/更新するには `uag_envsec add --file .env.sec --key NAME --value VALUE` を使います。
