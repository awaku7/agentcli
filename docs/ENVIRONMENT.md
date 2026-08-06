# Environment Variables and Configuration

`uag` uses environment variables to manage LLM provider credentials and control agent behavior. These variables are typically stored in a `.env` file in your current working directory.

## Setup Wizard

The easiest way to configure your environment is by running the interactive setup wizard:

```bash
uag_setup
# or
python -m uagent.setup_cli
```

### Automatic Setup

If required environment variables (such as provider settings) are missing when you start `uag`, the system will **automatically launch the setup wizard**. Once completed, your settings will be saved to `.env`, and the agent will be ready to use.

______________________________________________________________________

### 1. Provider selection

- `UAGENT_PROVIDER` (required): LLM provider name.
  Supported values: `azure`, `openai`, `bedrock`, `openrouter`, `ollama`, `gemini`, `vertexai`, `claude`, `grok`, `nvidia`, `deepseek`, `zai`, `alibaba`, `moonshot`, `mimo`, `lmstudio`, `minimax`, `hf`, `novita`, `sakana`, `sakura`.
- `UAGENT_USE_TOOL`: Set to `0`, `false`, `no`, or `off` to disable tool sending to LLM.

#### Azure OpenAI

Required if `UAGENT_PROVIDER=azure`:

- `UAGENT_AZURE_BASE_URL` (required)
- `UAGENT_AZURE_DEPNAME` (required): deployment / model name
- `UAGENT_AZURE_API_KEY` (required)
- `UAGENT_AZURE_API_VERSION` (required, e.g. `2025-03-01-preview`)

#### OpenAI / PFN

Required if `UAGENT_PROVIDER=openai`:

- `UAGENT_OPENAI_API_KEY` (required)
- `UAGENT_OPENAI_BASE_URL` (optional, default: `https://api.openai.com/v1`)
- `UAGENT_OPENAI_DEPNAME` (optional, default: `gpt-5.4-nano`)

##### PFN (Preferred Networks / PLaMo)

PLaMo provides an OpenAI-compatible Chat Completions API and is available as the dedicated `pfn` provider.

```bat
set UAGENT_PROVIDER=pfn
set UAGENT_PFN_API_KEY=<PLaMo API key>
set UAGENT_PFN_BASE_URL=https://api.platform.preferredai.jp/v1
set UAGENT_PFN_DEPNAME=plamo-3.0-prime
set UAGENT_RESPONSES=0
```

`UAGENT_PFN_BASE_URL` is optional. PLaMo exposes `/v1/chat/completions`, not the Responses API, so keep `UAGENT_RESPONSES=0`. Tool calling and streaming use the OpenAI-compatible Chat Completions implementation.

#### Bedrock

Required if `UAGENT_PROVIDER=bedrock`:

- `UAGENT_BEDROCK_DEPNAME` (required, e.g. `us.anthropic.claude-sonnet-4-20250514`)
- `UAGENT_BEDROCK_ACCESS_KEY` (required)
- `UAGENT_BEDROCK_SECRET_KEY` (required)
- `UAGENT_BEDROCK_REGION` (optional, default: `us-west-2`)

#### OpenRouter

Required if `UAGENT_PROVIDER=openrouter`:

- `UAGENT_OPENROUTER_API_KEY` (required)
- `UAGENT_OPENROUTER_DEPNAME` (optional, default: `gpt-5.4-nano`)

#### Ollama

Required if `UAGENT_PROVIDER=ollama`:

- `UAGENT_OLLAMA_DEPNAME` (required)
- `UAGENT_OLLAMA_BASE_URL` (optional, default: `http://localhost:11434/v1`)

#### Google Gemini

Required if `UAGENT_PROVIDER=gemini`:

- `UAGENT_GEMINI_API_KEY` (required)
- `UAGENT_GEMINI_DEPNAME` (optional, default: `gemini-2.5-pro-exp-03-25`)

#### Google Vertex AI

Required if `UAGENT_PROVIDER=vertexai`:

- `UAGENT_VERTEXAI_PROJECT` (required)
- `UAGENT_VERTEXAI_LOCATION` (required, e.g. `us-central1`)
- `UAGENT_VERTEXAI_DEPNAME` (required)
- `UAGENT_VERTEXAI_CREDENTIALS` (required): Path to Google Cloud service account JSON.

#### Claude (Anthropic)

Required if `UAGENT_PROVIDER=claude`:

- `UAGENT_CLAUDE_API_KEY` (required)
- `UAGENT_CLAUDE_DEPNAME` (optional, default: `claude-sonnet-4-20250514`)

#### Grok

Required if `UAGENT_PROVIDER=grok`:

- `UAGENT_GROK_API_KEY` (required)
- `UAGENT_GROK_DEPNAME` (optional)

#### NVIDIA

Required if `UAGENT_PROVIDER=nvidia`:

- `UAGENT_NVIDIA_API_KEY` (required)
- `UAGENT_NVIDIA_DEPNAME` (optional)

#### DeepSeek

Required if `UAGENT_PROVIDER=deepseek`:

- `UAGENT_DEEPSEEK_API_KEY` (required)
- `UAGENT_DEEPSEEK_BASE_URL` (optional, default: `https://api.deepseek.com`)
- `UAGENT_DEEPSEEK_DEPNAME` (optional, default: `deepseek-v4-flash`)

#### Z.AI (Zhipu AI)

Required if `UAGENT_PROVIDER=zai`:

- `UAGENT_ZAI_API_KEY` (required): Zhipu AI API key.
- `UAGENT_ZAI_BASE_URL` (optional, default: `https://api.z.ai/api/paas/v4/`).
- `UAGENT_ZAI_DEPNAME` (optional, default: `glm-5.2`).

#### Alibaba Cloud (Qwen)

Required if `UAGENT_PROVIDER=alibaba`:

- `UAGENT_ALIBABA_API_KEY` (required)
- `UAGENT_ALIBABA_BASE_URL` (optional)
- `UAGENT_ALIBABA_DEPNAME` (optional, default: `qwen3.5-plus`)

#### Moonshot (KIMI)

Required if `UAGENT_PROVIDER=moonshot`:

- `UAGENT_MOONSHOT_API_KEY` (required)
- `UAGENT_MOONSHOT_DEPNAME` (optional, default: `kimi-k2`)

#### Xiaomi MiMo

Required if `UAGENT_PROVIDER=mimo`:

- `UAGENT_MIMO_API_KEY` (required)
- `UAGENT_MIMO_BASE_URL` (optional)
- `UAGENT_MIMO_DEPNAME` (optional, default: `mimo-v2.5-pro`)

#### LM Studio

Required if `UAGENT_PROVIDER=lmstudio`:

- `UAGENT_LMSTUDIO_BASE_URL` (optional, default: `http://localhost:1234/v1`)
- `UAGENT_LMSTUDIO_DEPNAME` (optional, default: `local-model`)

> \* **Note on AWS Bedrock**: The current `uag` implementation expects an OpenAI-compatible endpoint for Bedrock.

#### Google Cloud Settings

Used by Gemini / Vertex AI features that need Google Cloud access.

- `UAGENT_GOOGLE_CREDENTIALS`: Path to Google Cloud service account JSON or JSON string (optional).
- `UAGENT_GOOGLE_LOCATION`: Google Cloud location/region (e.g., `asia-northeast1`).

#### AWS / GCP / Azure management tools

AWS tool (`aws_api`):

- `UAGENT_AWS_ACCESS_KEY_ID` (optional)
- `UAGENT_AWS_SECRET_ACCESS_KEY` (optional)
- `UAGENT_AWS_SESSION_TOKEN` (optional)
- `UAGENT_AWS_PROFILE` (optional)
- `UAGENT_AWS_REGION` (optional)

GCP tool (`gcp_api`):

- `UAGENT_GCP_CREDENTIALS_FILE` (optional): path to a service-account JSON file. If omitted, Google Application Default Credentials are used.

Azure tool (`azure_api`):

- `UAGENT_AZURE_TENANT_ID` (for service-principal authentication)
- `UAGENT_AZURE_CLIENT_ID` (for service-principal authentication)
- `UAGENT_AZURE_CLIENT_SECRET` (for service-principal authentication)
- `UAGENT_AZURE_SUBSCRIPTION_ID` (required)

If the Azure service-principal values are incomplete, Azure CLI authentication via `az login` is used. Write APIs execute only when `confirm_write=true` is explicitly provided.

#### MiniMax

Required if `UAGENT_PROVIDER=minimax`:

- `UAGENT_MINIMAX_API_KEY` (required): MiniMax API key.
- `UAGENT_MINIMAX_BASE_URL` (optional, default: `https://api.minimax.io`).
- `UAGENT_MINIMAX_DEPNAME` (optional, default: `MiniMax-M3`).

#### HuggingFace (Inference API / Serverless)

Required if `UAGENT_PROVIDER=hf`:

- `UAGENT_HF_API_KEY` (required): Your HuggingFace API token (HF_TOKEN).
- `UAGENT_HF_BASE_URL` (optional, default: `https://router.huggingface.co/v1`).
- `UAGENT_HF_DEPNAME` (optional, default: `openai/gpt-oss-120b`).

> **Note**: HuggingFace provides an OpenAI-compatible Inference API endpoint. Tool calling may have limitations depending on the model used.

#### Novita AI

Required if `UAGENT_PROVIDER=novita`:

- `UAGENT_NOVITA_API_KEY` (required): Novita AI API key.
- `UAGENT_NOVITA_BASE_URL` (optional, default: `https://api.novita.ai/openai`).
- `UAGENT_NOVITA_DEPNAME` (optional, default: `tensent/hy3`).

#### Sakana AI (Fugu)

Required if `UAGENT_PROVIDER=sakana`:

- `UAGENT_SAKANA_API_KEY` (required): Sakana AI API key.
- `UAGENT_SAKANA_BASE_URL` (optional, default: `https://api.sakana.ai/v1`).
- `UAGENT_SAKANA_DEPNAME` (optional, default: `fugu`).

#### SAKURA AI Engine

Required if `UAGENT_PROVIDER=sakura`:

- `UAGENT_SAKURA_API_KEY` (required): SAKURA AI Engine API key.
- `UAGENT_SAKURA_BASE_URL` (optional, default: `https://api.ai.sakura.ad.jp/v1`).
- `UAGENT_SAKURA_DEPNAME` (optional, default: `llm`).
- `UAGENT_SAKURA_TEMPERATURE` (optional): Temperature setting for the model.

### 3. Basic Agent Behavior

- `UAGENT_LANG`: Host UI language (e.g., `en`, `ja`, `zh_CN`, `zh_TW`, `ko`, `th`, `es`, `fr`, `de`, `it`, `pt_BR`, `ru`).
- `UAGENT_WORKDIR`: Default working directory for agent operations.
- `UAGENT_WEB_HOST`: Web server bind address (default: `127.0.0.1`). Set to `0.0.0.0` to allow external access.
- `UAGENT_STREAMING`: Enable/disable streaming LLM responses (`1`: Enabled(default), `0`: Disabled).
- `UAGENT_VERBOSITY`: Output verbosity level (`off`, `low`, `medium`, `high`).
- `UAGENT_DEBUG_ENDPOINT`: Set to `1` to output endpoint and model info at startup.
- `UAGENT_PARALLEL_WORKERS`: Number of threads for parallel tool execution (default: `8`). Increase for more concurrency on I/O-bound tasks.
- `UAGENT_AUTO_UNLOAD_ROUNDS`: Automatically unload tools that haven't been used for this many LLM rounds (default: `10`). Set to `0` to disable auto-unload.

#### LLM Parameters (OpenAI-compatible)

Optional parameters passed directly to the LLM API.

- `UAGENT_MAX_TOKENS`: Maximum number of tokens in the response.
- `UAGENT_TOP_P`: Nucleus sampling parameter (e.g. `0.9`).
- `UAGENT_STOP`: Comma-separated stop sequences (e.g. `stop,because`).
- `UAGENT_SEED`: Random seed for reproducible generation.
- `UAGENT_FREQUENCY_PENALTY`: Frequency penalty (e.g. `0.5`).
- `UAGENT_PRESENCE_PENALTY`: Presence penalty (e.g. `0.5`).
- `UAGENT_RESPONSE_FORMAT`: Response format (`json` for JSON mode).

### 4. Advanced Features (Responses API, Reasoning, etc.)

- `UAGENT_RESPONSES`: Set to `1` to enable the "Responses API" for supported providers (Azure/OpenAI/Bedrock/OpenRouter/Ollama).
- `UAGENT_OPENAI_FAST_MODE`: Set to `1`/`true`/`yes`/`on` to request OpenAI Fast mode (`service_tier=fast`). OpenAI only; ignored by Azure and other providers.
- `UAGENT_REASONING`: Reasoning effort level for reasoning models (`off`, `auto`, `minimal`, `low`, `medium`, `high`, `xhigh`).
- `UAGENT_REASONING_EFFORT`: Reasoning effort level for Grok / xAI models (`none`, `low`, `medium`, `high`).
- `UAGENT_STREAMING_DEBUG`: Set to `1` to dump each streaming event (JSON) to `outputs/streaming_debug/`.
- `UAGENT_RESPONSES_STATE_FILE`: absolute path to a specific Responses API state file (overrides auto path).
- `UAGENT_RESPONSES_STATE_DIR`: directory for Responses API state files (optional; default: `~/.uag/`).

### 5. Built-in Web Search

Configuration settings for built-in web search (grounding) features provided directly by LLM backends.

- **`UAGENT_GEMINI_WEB_SEARCH`**: Controls Gemini / Vertex AI's built-in Google Search (Google Search Grounding).
  - Set to `1`, `true`, `yes`, `on`, or **leave unset (default)** to enable. When active, local web search tools are automatically disabled.
  - Set to `0`, `false`, `no`, `off` to disable and fall back to local web search tools.

## Realtime Audio

- `UAGENT_AUDIO_REALTIME_PROVIDER`: Provider override (`openai`, `grok`, `xai`, `google`, `gemini`, `vertexai`).
- `UAGENT_GEMINI_API_KEY` / `UAGENT_GOOGLE_API_KEY` / `GEMINI_API_KEY` / `GOOGLE_API_KEY`: API key for Gemini Realtime.
- `UAGENT_GEMINI_REALTIME_DEPNAME` / `UAGENT_GOOGLE_REALTIME_DEPNAME`: Realtime model deployment name (default `gemini-2.0-flash-exp`).
- `UAGENT_GEMINI_REALTIME_VOICE` / `UAGENT_GOOGLE_REALTIME_VOICE`: Prebuilt voice name (default `Puck`).

## Detailed Japanese configuration reference

The former `ENVIRONMENT.ja.md` content is retained below. The English sections above remain the primary configuration reference.

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

#### OpenAI / PFN

`UAGENT_PROVIDER=openai` の場合に必要：

- `UAGENT_OPENAI_API_KEY`（必須）
- `UAGENT_OPENAI_BASE_URL`（省略可、既定: `https://api.openai.com/v1`）
- `UAGENT_OPENAI_DEPNAME`（省略可、既定: `gpt-5.4-nano`）

##### PFN（Preferred Networks / PLaMo）

PLaMoはOpenAI互換のChat Completions APIを提供します。専用の`pfn`プロバイダーとして利用できます。

```bat
set UAGENT_PROVIDER=pfn
set UAGENT_PFN_API_KEY=<PLaMo APIキー>
set UAGENT_PFN_BASE_URL=https://api.platform.preferredai.jp/v1
set UAGENT_PFN_DEPNAME=plamo-3.0-prime
set UAGENT_RESPONSES=0
```

`UAGENT_PFN_BASE_URL`は省略可能です。PLaMoのエンドポイントは`/v1/chat/completions`のみを使用するため、`UAGENT_RESPONSES=0`でResponses APIを無効にしてください。ツール呼び出しとストリーミングは、OpenAI互換のChat Completions経路で処理されます。

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

#### AWS / GCP / Azure 管理ツール

AWSツール（`aws_api`）:

- `UAGENT_AWS_ACCESS_KEY_ID`（任意）
- `UAGENT_AWS_SECRET_ACCESS_KEY`（任意）
- `UAGENT_AWS_SESSION_TOKEN`（任意）
- `UAGENT_AWS_PROFILE`（任意）
- `UAGENT_AWS_REGION`（任意）

GCPツール（`gcp_api`）:

- `UAGENT_GCP_CREDENTIALS_FILE`（任意）: サービスアカウントJSONファイルのパス。未指定時はGoogle Application Default Credentialsを使用します。

Azureツール（`azure_api`）:

- `UAGENT_AZURE_TENANT_ID`（サービスプリンシパル使用時）
- `UAGENT_AZURE_CLIENT_ID`（サービスプリンシパル使用時）
- `UAGENT_AZURE_CLIENT_SECRET`（サービスプリンシパル使用時）
- `UAGENT_AZURE_SUBSCRIPTION_ID`（必須）

Azureのサービスプリンシパル情報が揃っていない場合は、`az login` によるAzure CLI認証を使用します。書き込みAPIは `confirm_write=true` を明示した場合のみ実行されます。

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
- `UAGENT_OPENAI_FAST_MODE`: `1`/`true`/`yes`/`on` に設定すると OpenAI Fast mode（`service_tier=fast`）を要求します。OpenAI 専用で、Azure や他のプロバイダーでは無視されます。
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

## リアルタイム音声環境変数

- `UAGENT_AUDIO_REALTIME_PROVIDER`: プロバイダーの上書き（`openai` / `grok` / `xai` / `google` / `gemini` / `vertexai`）。
- `UAGENT_GEMINI_API_KEY` / `UAGENT_GOOGLE_API_KEY` / `GEMINI_API_KEY` / `GOOGLE_API_KEY`: Gemini Realtime用APIキー。
- `UAGENT_GEMINI_REALTIME_DEPNAME` / `UAGENT_GOOGLE_REALTIME_DEPNAME`: Realtimeモデル名（既定: `gemini-2.0-flash-exp`）。
- `UAGENT_GEMINI_REALTIME_VOICE` / `UAGENT_GOOGLE_REALTIME_VOICE`: プリセットボイス名（既定: `Puck`）。
