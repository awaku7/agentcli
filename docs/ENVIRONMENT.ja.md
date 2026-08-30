# 環境変数と設定

`uag` は環境変数を使用して、LLMプロバイダの認証情報やエージェントの動作を制御します。これらの変数は通常、カレントディレクトリの `.env` ファイルに保存されます。

## Session Store / 統合Policy

Session StoreはSQLiteベースのセッション履歴です。現在は既定で有効です。無効にする場合は `UAGENT_SESSION_STORE=0` を指定します。

```env
UAGENT_SESSION_STORE=1
UAGENT_SESSION_BACKEND=sqlite
# 未設定時: ユーザー状態ディレクトリ/sessions/sessions.sqlite3
UAGENT_SESSION_STORE_PATH=
UAGENT_MEMORY_BACKEND=sqlite
# 未設定時: ユーザー状態ディレクトリのmemory.sqlite3
UAGENT_MEMORY_DB=
UAGENT_POLICY_FILE=~/.uag/enterprise-policy.yaml
UAGENT_POLICY_LEVEL=read_only
# CLI終了時のLLMセッション要約。0で無効化（デフォルト: 1）。
UAGENT_SUMMARY_ON_EXIT=1
# 要約時のプロフィール抽出。1で有効。
UAGENT_PROFILE_ON_EXIT=0
```

`UAGENT_SESSION_BACKEND` は次の値を指定できます。

- `jsonl`: 従来のJSONLのみ
- `dual`: JSONLとSQLiteの両方（既存環境からの移行時に使用）
- `sqlite`: SQLiteのみ。デフォルト。JSONLの新規保存を停止

SQLite-onlyでは `:logs`、`:load`、`:cont`、`:clean` もSQLiteセッションを対象にします。セッションの管理には次を使用できます。

```text
:sessions list
:sessions search <query>
:sessions summarize [session_id] [--force]
:sessions prune --keep <N> [--dry-run|--yes]
:sessions load <session_id>
:sessions import <jsonl_path-or-directory>
:sessions delete <session_id> --yes
:sessions vacuum
:sessions pdf <session_id> [output.pdf]
```

既存JSONLを移行する場合は、SQLite-onlyへ切り替える前に `:sessions import` を実行してください。

通常は `UAGENT_POLICY_FILE` の企業YAMLだけを設定します。`UAGENT_POLICY_LEVEL` は開発時の簡易制限です。

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
  サポート値: `azure`, `openai`, `pfn`, `bedrock`, `openrouter`, `ollama`, `llama_cpp`, `gemini`, `vertexai`, `claude`, `grok`, `nvidia`, `deepseek`, `zai`, `alibaba`, `moonshot`, `mimo`, `lmstudio`, `minimax`, `hf`, `novita`, `sakana`, `sakura`。
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
- `UAGENT_OLLAMA_FORMAT`（省略可）: `json` または JSON Schema を指定すると、ネイティブAPIの構造化出力を要求します。

#### llama.cpp / llama-server

`UAGENT_PROVIDER=llama_cpp` の場合：

- `UAGENT_LLAMA_CPP_BASE_URL`（必須、既定: `http://localhost:8080/v1`）
- `UAGENT_LLAMA_CPP_DEPNAME`（省略可、既定: `local-model`）
- `UAGENT_LLAMA_CPP_API_KEY`（省略可、既定: `dummy`）
- `UAGENT_LLAMA_CPP_TIMEOUT_SEC`（省略可、既定: `120`）
- `UAGENT_LLAMA_CPP_TOP_K`（省略可）: サンプリング候補を上位 K 個に制限します。小さいほど保守的になり、未設定時は llama-server の既定値を使用します。
- `UAGENT_LLAMA_CPP_MIN_P`（省略可）: 最も確率の高いトークンに対する相対確率がこの値未満の候補を除外します。大きいほど候補が絞られ、未設定時は llama-server の既定値を使用します。
- `UAGENT_LLAMA_CPP_REPEAT_PENALTY`（省略可）: 既出トークンにペナルティをかけます。`1.0` は無効で、値を大きくすると反復を強く抑制します。未設定時は llama-server の既定値を使用します。
- `UAGENT_LLAMA_CPP_FORMAT`（省略可）: `json` または JSON Schema を指定すると、`response_format` による構造化出力を要求します。
- `UAGENT_LLAMA_CPP_GRAMMAR`（省略可）: llama-server の GBNF grammar を指定します。`FORMAT` と併用した場合はサーバー側の互換性に従います。

これらの値は llama-server の `extra_body` サンプリングパラメータとして送信されます。不正な値および 0 以下の値は送信されません。

llama.cpp 連携は現在 Chat Completions を使用します。互換プロキシ／サーバーを構成していない限り、`UAGENT_RESPONSES=0` を維持してください。

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

- `UAGENT_LMSTUDIO_TRANSPORT`（省略可: `sdk`、`chat` または `responses`。既定: `responses`。`UAGENT_RESPONSES` より優先）
- `UAGENT_LMSTUDIO_BASE_URL`（省略可、既定: `http://localhost:1234/v1`）
- `UAGENT_LMSTUDIO_DEPNAME`（省略可、既定: `local-model`）

`UAGENT_LMSTUDIO_TRANSPORT` の選択肢：

- `responses`: OpenAI互換の `POST /v1/responses`（既定。LM Studio 0.3.29以降が必要）
- `chat`: OpenAI互換の `POST /v1/chat/completions`
- `sdk`: LM Studio Python SDK（`lmstudio`。チャット／推論専用）。この値を選択した場合のみパッケージを自動インストールします。

SDK transportでは `UAGENT_RESPONSES` と `previous_response_id` は使用しません。これらのOpenAI互換機能が必要な場合は `chat` または `responses` を使用してください。LM StudioにAPIキーは不要です。

> \* **AWS Bedrock について**: 現在の `uag` 実装では、Bedrock の OpenAI 互換エンドポイントを使用することを想定しています。

#### DeepL 翻訳

`translate_text`で`provider=deepl`を指定した場合、または`provider=auto`でDeepLのキーが設定されている場合に使用します。`deepl` Pythonパッケージは必要時に自動インストールされるか、`tools`オプション依存関係からインストールできます。

- `UAGENT_DEEPL_AUTH_KEY`（任意）: DeepL API認証キー
- `DEEPL_AUTH_KEY` / `DEEPL_API_KEY`（任意の別名）: 互換性のため利用可能

`translate_text` のプロバイダー選択：

- `auto`: キーがあり対象言語がDeepL対応ならDeepLを優先し、それ以外はGoogle Translateを使用します。
- `deepl`: DeepLを強制し、非対応言語は明確なエラーにします。
- `google`: Google Translateを強制します。

DeepLの主なロケール変換は、`fil` → `TL`（タガログ語）、
`zh_CN` → `ZH-HANS`、`zh_TW` → `ZH-HANT`です。英語・ポルトガル語の
地域別ソースコードも、DeepLの入力仕様に合わせて正規化されます。
対応言語の最新情報は公式ドキュメントを参照してください：
<https://developers.deepl.com/docs/getting-started/supported-languages>

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
