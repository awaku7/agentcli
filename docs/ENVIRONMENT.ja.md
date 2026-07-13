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

______________________________________________________________________

### 1. プロバイダの選択

- `UAGENT_PROVIDER`（必須）: LLMプロバイダ名。
  サポート値: `azure`, `openai`, `bedrock`, `openrouter`, `ollama`, `gemini`, `vertexai`, `claude`, `grok`, `nvidia`, `deepseek`, `zai`, `alibaba`, `moonshot`, `mimo`, `lmstudio`, `minimax`, `hf`, `novita`, `sakana`, `sakura`。
- `UAGENT_USE_TOOL`: `0`, `false`, `no`, `off` に設定すると、LLMへのツール送信を無効化します。

#### Azure OpenAI

`UAGENT_PROVIDER=azure` の場合に必要：

- `UAGENT_AZURE_BASE_URL`（必須）
- `UAGENT_AZURE_DEPNAME`（必須）: デプロイメント/モデル名
- `UAGENT_AZURE_API_KEY`（必須）
- `UAGENT_AZURE_API_VERSION`（必須、例: `2025-03-01-preview`）

#### OpenAI

`UAGENT_PROVIDER=openai` の場合に必要：

- `UAGENT_OPENAI_API_KEY`（必須）
- `UAGENT_OPENAI_BASE_URL`（省略可、既定: `https://api.openai.com/v1`）
- `UAGENT_OPENAI_DEPNAME`（省略可、既定: `gpt-5.4-nano`）

#### Bedrock

`UAGENT_PROVIDER=bedrock` の場合に必要：

- `UAGENT_BEDROCK_DEPNAME`（必須、例: `us.anthropic.claude-sonnet-4-20250514`）
- `UAGENT_BEDROCK_ACCESS_KEY`（必須）
- `UAGENT_BEDROCK_SECRET_KEY`（必須）
- `UAGENT_BEDROCK_REGION`（省略可、既定: `us-west-2`）

#### OpenRouter

`UAGENT_PROVIDER=openrouter` の場合に必要：

- `UAGENT_OPENROUTER_API_KEY`（必須）
- `UAGENT_OPENROUTER_DEPNAME`（省略可、既定: `gpt-5.4-nano`）

#### Ollama

`UAGENT_PROVIDER=ollama` の場合に必要：

- `UAGENT_OLLAMA_DEPNAME`（必須）
- `UAGENT_OLLAMA_BASE_URL`（省略可、既定: `http://localhost:11434/v1`）

#### Google Gemini

`UAGENT_PROVIDER=gemini` の場合に必要：

- `UAGENT_GEMINI_API_KEY`（必須）
- `UAGENT_GEMINI_DEPNAME`（省略可、既定: `gemini-2.5-pro-exp-03-25`）

#### Google Vertex AI

`UAGENT_PROVIDER=vertexai` の場合に必要：

- `UAGENT_VERTEXAI_PROJECT`（必須）
- `UAGENT_VERTEXAI_LOCATION`（必須、例: `us-central1`）
- `UAGENT_VERTEXAI_DEPNAME`（必須）
- `UAGENT_VERTEXAI_CREDENTIALS`（必須）: Google Cloud サービスアカウント JSON のパス。

#### Claude (Anthropic)

`UAGENT_PROVIDER=claude` の場合に必要：

- `UAGENT_CLAUDE_API_KEY`（必須）
- `UAGENT_CLAUDE_DEPNAME`（省略可、既定: `claude-sonnet-4-20250514`）

#### Grok

`UAGENT_PROVIDER=grok` の場合に必要：

- `UAGENT_GROK_API_KEY`（必須）
- `UAGENT_GROK_DEPNAME`（省略可）

#### NVIDIA

`UAGENT_PROVIDER=nvidia` の場合に必要：

- `UAGENT_NVIDIA_API_KEY`（必須）
- `UAGENT_NVIDIA_DEPNAME`（省略可）

#### DeepSeek

`UAGENT_PROVIDER=deepseek` の場合に必要：

- `UAGENT_DEEPSEEK_API_KEY`（必須）
- `UAGENT_DEEPSEEK_BASE_URL`（省略可、既定: `https://api.deepseek.com`）
- `UAGENT_DEEPSEEK_DEPNAME`（省略可、既定: `deepseek-v4-flash`）

#### Z.AI (Zhipu AI)

`UAGENT_PROVIDER=zai` の場合に必要：

- `UAGENT_ZAI_API_KEY`（必須）: Zhipu AI API キー。
- `UAGENT_ZAI_BASE_URL`（省略可、既定: `https://api.z.ai/api/paas/v4/`）。
- `UAGENT_ZAI_DEPNAME`（省略可、既定: `glm-5.2`）。

#### Alibaba Cloud (Qwen)

`UAGENT_PROVIDER=alibaba` の場合に必要：

- `UAGENT_ALIBABA_API_KEY`（必須）
- `UAGENT_ALIBABA_BASE_URL`（省略可）
- `UAGENT_ALIBABA_DEPNAME`（省略可、既定: `qwen3.5-plus`）

#### Moonshot (KIMI)

`UAGENT_PROVIDER=moonshot` の場合に必要：

- `UAGENT_MOONSHOT_API_KEY`（必須）
- `UAGENT_MOONSHOT_DEPNAME`（省略可、既定: `kimi-k2`）

#### Xiaomi MiMo

`UAGENT_PROVIDER=mimo` の場合に必要：

- `UAGENT_MIMO_API_KEY`（必須）
- `UAGENT_MIMO_BASE_URL`（省略可）
- `UAGENT_MIMO_DEPNAME`（省略可、既定: `mimo-v2.5-pro`）

#### LM Studio

`UAGENT_PROVIDER=lmstudio` の場合に必要：

- `UAGENT_LMSTUDIO_BASE_URL`（省略可、既定: `http://localhost:1234/v1`）
- `UAGENT_LMSTUDIO_DEPNAME`（省略可、既定: `local-model`）

> \* **AWS Bedrock について**: 現在の `uag` 実装では、Bedrock の OpenAI 互換エンドポイントを使用することを想定しています。

#### Google Cloud 設定

Gemini / Vertex AI で Google Cloud アクセスが必要な機能で使用します。

- `UAGENT_GOOGLE_CREDENTIALS`: Google Cloud サービスアカウント JSON のパス、または JSON 文字列（省略可）。
- `UAGENT_GOOGLE_LOCATION`: Google Cloud のロケーション/リージョン（例: `asia-northeast1`）。

#### MiniMax

`UAGENT_PROVIDER=minimax` の場合に必要：

- `UAGENT_MINIMAX_API_KEY`（必須）: MiniMax API キー。
- `UAGENT_MINIMAX_BASE_URL`（省略可、既定: `https://api.minimax.io`）。
- `UAGENT_MINIMAX_DEPNAME`（省略可、既定: `MiniMax-M3`）。

#### HuggingFace (Inference API / Serverless)

`UAGENT_PROVIDER=hf` の場合に必要：

- `UAGENT_HF_API_KEY`（必須）: HuggingFace API トークン (HF_TOKEN)。
- `UAGENT_HF_BASE_URL`（省略可、既定: `https://router.huggingface.co/v1`）。
- `UAGENT_HF_DEPNAME`（省略可、既定: `openai/gpt-oss-120b`）。

> **注**: HuggingFace は OpenAI 互換の Inference API エンドポイントを提供します。ツール呼び出しは使用するモデルに依存します。

#### Novita AI

`UAGENT_PROVIDER=novita` の場合に必要：

- `UAGENT_NOVITA_API_KEY`（必須）: Novita AI API キー。
- `UAGENT_NOVITA_BASE_URL`（省略可、既定: `https://api.novita.ai/openai`）。
- `UAGENT_NOVITA_DEPNAME`（省略可、既定: `tensent/hy3`）。

#### Sakana AI (Fugu)

`UAGENT_PROVIDER=sakana` の場合に必要：

- `UAGENT_SAKANA_API_KEY`（必須）: Sakana AI API キー。
- `UAGENT_SAKANA_BASE_URL`（省略可、既定: `https://api.sakana.ai/v1`）。
- `UAGENT_SAKANA_DEPNAME`（省略可、既定: `fugu`）。

#### SAKURA AI Engine

`UAGENT_PROVIDER=sakura` の場合に必要：

- `UAGENT_SAKURA_API_KEY`（必須）: SAKURA AI Engine API キー。
- `UAGENT_SAKURA_BASE_URL`（省略可、既定: `https://api.ai.sakura.ad.jp/v1`）。
- `UAGENT_SAKURA_DEPNAME`（省略可、既定: `llm`）。
- `UAGENT_SAKURA_TEMPERATURE`（省略可）: モデルの Temperature 設定。

### 3. エージェントの基本動作

- `UAGENT_LANG`: ホスト UI の言語（例: `en`, `ja`, `zh_CN`, `zh_TW`, `ko`, `th`, `es`, `fr`, `de`, `it`, `pt_BR`, `ru`）。
- `UAGENT_WORKDIR`: エージェントが操作を行うデフォルトの作業ディレクトリ。
- `UAGENT_WEB_HOST`: Web サーバーのバインドアドレス（既定: `127.0.0.1`）。外部アクセスを許可するには `0.0.0.0` に設定します。
- `UAGENT_STREAMING`: LLM 応答のストリーミング表示の有効/無効（`1`: 有効（既定）、`0`: 無効）。
- `UAGENT_VERBOSITY`: ログ出力の冗長性（`off`, `low`, `medium`, `high`）。
- `UAGENT_DEBUG_ENDPOINT`: `1` に設定すると、起動時にエンドポイントとモデル情報を出力します。
- `UAGENT_PARALLEL_WORKERS`: 並列ツール実行のスレッド数（既定: `8`）。I/O バウンドなタスクが多い場合は増やしてください。
- `UAGENT_AUTO_UNLOAD_ROUNDS`: 指定されたラウンド数だけ使用されなかったツールを自動的にアンロードします（既定: `10`）。`0` に設定すると自動アンロードが無効になります。

#### LLM パラメータ（OpenAI 互換）

LLM API に直接渡されるオプションパラメータです。

- `UAGENT_MAX_TOKENS`: 応答の最大トークン数。
- `UAGENT_TOP_P`: Nucleus サンプリングパラメータ（例: `0.9`）。
- `UAGENT_STOP`: カンマ区切りの停止シーケンス（例: `stop,because`）。
- `UAGENT_SEED`: 再現性のある生成のための乱数シード。
- `UAGENT_FREQUENCY_PENALTY`: 頻度ペナルティ（例: `0.5`）。
- `UAGENT_PRESENCE_PENALTY`: 存在ペナルティ（例: `0.5`）。
- `UAGENT_RESPONSE_FORMAT`: 応答形式（JSON モードの場合は `json`）。

### 4. 高度な機能（Responses API, 推論など）

- `UAGENT_RESPONSES`: `1` に設定すると、対応プロバイダ（Azure/OpenAI/Bedrock/OpenRouter/Ollama）で "Responses API" を有効にします。
- `UAGENT_REASONING`: 推論モデルの推論努力レベル（`off`, `auto`, `minimal`, `low`, `medium`, `high`, `xhigh`）。
- `UAGENT_REASONING_EFFORT`: Grok / xAI モデルの推論努力レベル（`none`, `low`, `medium`, `high`）。
- `UAGENT_STREAMING_DEBUG`: `1` に設定すると、ストリーミング中の各イベント（JSON）を `outputs/streaming_debug/` に保存します。
- `UAGENT_RESPONSES_STATE_FILE`: 特定の Responses API 状態ファイルの絶対パス（自動パスを上書き）。
- `UAGENT_RESPONSES_STATE_DIR`: Responses API 状態ファイルのディレクトリ（省略可、既定: `~/.uag/`）。

### 5. 組み込み Web 検索

LLM バックエンドが直接提供する組み込み Web 検索（グラウンディング）機能の設定です。

- **`UAGENT_GEMINI_WEB_SEARCH`**: Gemini / Vertex AI の組み込み Google 検索（Google Search Grounding）を制御します。
  - `1`, `true`, `yes`, `on` または **未設定（デフォルト）** の場合に有効。有効時はローカルの Web 検索ツールが自動的に無効化されます。
  - `0`, `false`, `no`, `off` に設定すると無効化され、ローカルの Web 検索ツールが使用されます。
