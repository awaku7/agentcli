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

## 主要な環境変数

### 1. プロバイダの選択 (`UAGENT_PROVIDER`)

起動時に使用するメインのプロバイダを指定します（必須）。

- 有効な値: `openai`, `azure`, `bedrock`, `openrouter`, `ollama`, `gemini`, `vertexai`, `grok`, `claude`, `nvidia`, `deepseek`, `zai`, `alibaba`, `kimi`, `mimo`, `lmstudio`, `minimax`, `hf`

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
| **DeepSeek** | `UAGENT_DEEPSEEK_API_KEY`, `UAGENT_DEEPSEEK_BASE_URL` (既定: `https://api.deepseek.com`) | `UAGENT_DEEPSEEK_DEPNAME` (既定: `deepseek-v4-flash`) |
| **Z.AI (Zhipu AI)** | `UAGENT_ZAI_API_KEY`, `UAGENT_ZAI_BASE_URL` (既定: `https://api.z.ai/api/paas/v4/`) | `UAGENT_ZAI_DEPNAME` (既定: `glm-5.2`) |
| **Alibaba Cloud (Qwen)** | `UAGENT_ALIBABA_API_KEY`, `UAGENT_ALIBABA_BASE_URL` (既定: `https://dashscope.aliyuncs.com/compatible-mode/v1`) | `UAGENT_ALIBABA_DEPNAME` (既定: `qwen3.5-plus`) |
| **KIMI (Moonshot AI)** | `UAGENT_KIMI_API_KEY`, `UAGENT_KIMI_BASE_URL` (既定: `https://api.moonshot.cn/v1`) | `UAGENT_KIMI_DEPNAME` (既定: `kimi-k2`) |
| **MiniMax** | `UAGENT_MINIMAX_API_KEY`, `UAGENT_MINIMAX_BASE_URL` (既定: `https://api.minimax.io`) | `UAGENT_MINIMAX_DEPNAME` (既定: `MiniMax-M3`) |
| **Xiaomi MiMo** | `UAGENT_MIMO_API_KEY`, `UAGENT_MIMO_BASE_URL` | `UAGENT_MIMO_DEPNAME` (既定: `mimo-v2.5-pro`) |
| **LM Studio** | `UAGENT_LMSTUDIO_BASE_URL` (既定: `http://localhost:1234/v1`) | `UAGENT_LMSTUDIO_DEPNAME` (既定: `local-model`) |
| **HuggingFace** | `UAGENT_HF_API_KEY`, `UAGENT_HF_BASE_URL` (既定: `https://router.huggingface.co/v1`) | `UAGENT_HF_DEPNAME` (既定: `openai/gpt-oss-120b`) |

> ※ **AWS Bedrock について**: 現在の `uag` 実装では、Bedrock の OpenAI 互換エンドポイントを使用することを想定しています。

> ※ **HuggingFace について**: HuggingFace は OpenAI 互換の Inference API エンドポイントを提供します。ツール呼び出しは使用するモデルに依存します。

### 3. エージェントの基本動作

- `UAGENT_LANG`: ホスト UI の言語（例: `en`, `ja`, `zh_CN`, `zh_TW`, `ko`, `th`, `es`, `fr`, `de`, `it`, `pt_BR`, `ru`）。
- `UAGENT_WORKDIR`: エージェントが操作を行うデフォルトの作業ディレクトリ。
- `UAGENT_STREAMING`: LLM 応答の逐次表示（ストリーミング）の有効化 (`1`: 有効(既定), `0`: 無効)。
- `UAGENT_VERBOSITY`: ログ出力の冗長性 (`off`, `low`, `medium`, `high`)。
- `UAGENT_DEBUG_ENDPOINT`: `1` に設定すると、起動時に使用されるエンドポイントとモデル情報を出力します。
- `UAGENT_PARALLEL_WORKERS`: 並列ツール実行のスレッド数（既定: `8`）。I/O バウンドなタスクが多い場合は増やしてください。

### 4. 高度な機能 (Responses API, 推論等)

- `UAGENT_RESPONSES`: `1` に設定すると、対応プロバイダ（Azure/OpenAI/Bedrock/Ollama）で "Responses API" を有効にします。
- `UAGENT_REASONING`: 推論モデル（o1等）の推論の試行レベル (`off`, `auto`, `minimal`, `low`, `medium`, `high`, `xhigh`)。
- `UAGENT_STREAMING_DEBUG`: `1` に設定すると、ストリーミング中の各イベント（JSON）を `outputs/streaming_debug/` に保存します。

### 5. 組み込み Web 検索機能 (Built-in Web Search)

プロバイダが提供する組み込みの Web 検索（グラウンディング）機能の制御設定です。

- **`UAGENT_GEMINI_WEB_SEARCH`**: Gemini / Vertex AI の組み込み Google 検索（Google Search Grounding）を制御します。
  - `1`, `true`, `yes`, `on` または **未設定（デフォルト）** の場合に有効化され、ローカルの Web 検索ツールは自動的に無効化されます。
  - `0`, `false`, `no`, `off` を指定すると無効化され、従来のローカル Web 検索ツールが有効になります。
- **`UAGENT_OPENAI_WEB_SEARCH`**: OpenAI Responses API の組み込み Web 検索を制御します。
  - `1`, `true`, `yes`, `on` に設定すると有効化されます（デフォルトは無効）。
  - 関連オプションとして `UAGENT_OPENAI_WEB_SEARCH_TYPE` (検索タイプ), `UAGENT_OPENAI_WEB_SEARCH_CONTEXT_SIZE` (コンテキストサイズ) などが指定可能です。

### 5. 画像の生成と解析

- `UAGENT_IMG_GENERATE_PROVIDER`: 画像生成に使用するプロバイダ (既定: `UAGENT_PROVIDER`)。
- `UAGENT_<PROVIDER>_IMG_GENERATE_DEPNAME`: 画像生成用モデル ID (例: `dall-e-3`)。
- `UAGENT_IMG_ANALYSIS_PROVIDER`: 画像解析に使用するプロバイダ (既定: `UAGENT_PROVIDER`)。
  - 対応: `openai`, `azure`, `gemini`, `vertexai`, `ollama`, `alibaba` (Qwen-VL/DashScope), `kimi` (Moonshot AI), `deepseek` (Vision対応エンドポイントが必要)。
  - `UAGENT_IMG_ANALYSIS_DEPNAME`: 画像解析用モデルの上書き (任意)。
  - `UAGENT_<PROVIDER>_API_KEY` / `UAGENT_<PROVIDER>_BASE_URL` が適用される。
  - デフォルトモデル: `gpt-4o-mini` (openai), `qwen-vl-max` (alibaba), `kimi-k2` (kimi)。
- `UAGENT_IMAGE_OPEN`: 画像生成後に自動で開くかどうか (`0` で無効化)。

### 6. 音声の生成と文字起こし

- `UAGENT_AUDIO_PROVIDER`: 音声生成/文字起こしに使用するプロバイダ (既定: `UAGENT_PROVIDER`; 対応: `openai`, `azure`)。- `UAGENT_AUDIO_PROVIDER`: 音声生成/文字起こしに使用するプロバイダ (既定: `UAGENT_PROVIDER`; 対応: `openai`, `azure`, `gemini`, `vertexai`)。
- `UAGENT_AZURE_SPEECH_DEPNAME`: Azure 音声生成のデプロイ名。
- `UAGENT_OPENAI_SPEECH_DEPNAME`: OpenAI 音声生成のモデル/デプロイ名。
- `UAGENT_GEMINI_SPEECH_DEPNAME`: Gemini/VertexAI 音声生成のモデル名 (既定: `ja-JP-Neural2-B`)。
- `UAGENT_GOOGLE_CREDENTIALS`: Google Cloud サービスアカウント JSON のパス、または JSON 文字列。
- `UAGENT_GOOGLE_LOCATION`: Google Cloud のロケーション/リージョン (例: `asia-northeast1`)。
- `UAGENT_AZURE_TRANSCRIBE_DEPNAME`: Azure 文字起こしのデプロイ名。
- `UAGENT_OPENAI_TRANSCRIBE_DEPNAME`: OpenAI 文字起こしのモデル/デプロイ名。
- `UAGENT_AUDIO_OPEN`: 音声生成後に生成ファイルを自動で開くかどうか (`0` で無効化)。

### 7. 翻訳機能 (オプション)

ユーザー入力と LLM 応答の自動翻訳を有効にします。

- `UAGENT_TRANSLATE_PROVIDER`: 翻訳エンジン。
  - `openai`, `azure`, `openrouter`, `openai_compat`: OpenAI 互換 API を使う翻訳。
  - `gemini`: Google Gemini を使う翻訳。
  - `claude`: Anthropic Claude を使う翻訳。
- `UAGENT_TRANSLATE_TO_LLM`: ユーザー入力の翻訳先言語 (例: `en`)。英語らしい入力はそのまま送られます。
- `UAGENT_TRANSLATE_FROM_LLM`: LLM 応答の翻訳先言語 (例: `ja`)。
- `UAGENT_TRANSLATE_DEPNAME`: 翻訳に使用するモデル ID（API プロバイダでは必須）。
- `UAGENT_TRANSLATE_API_KEY`: 翻訳用 API キー（任意。既定で `UAGENT_API_KEY` を使用）。
- `UAGENT_TRANSLATE_BASE_URL`: 翻訳用のベース URL（任意。既定で `UAGENT_BASE_URL` を使用）。

### 8. 記憶とセマンティック検索

- `UAGENT_MEMORY_FILE`: 長期記憶メモの保存先パス。
- `UAGENT_SHARED_MEMORY_FILE`: 共有長期記憶の保存先パス。
- `UAGENT_EMBEDDING_PROVIDER`: 埋め込み用プロバイダ（既定: `UAGENT_PROVIDER`）。
- `UAGENT_<PROVIDER>_EMBEDDING_BASE_URL`: 埋め込みプロバイダのベース URL。
- `UAGENT_<PROVIDER>_EMBEDDING_API_KEY`: 埋め込みプロバイダの API キー。
- `UAGENT_<PROVIDER>_EMBEDDING_API_VERSION`: Azure 形式プロバイダの API バージョン。
- `UAGENT_<PROVIDER>_EMBEDDING_DEPNAME`: 埋め込みモデル / デプロイ名。
- `UAGENT_ENABLE_SEMANTIC_SEARCH`: セマンティック検索ツールの有効/無効を切り替える。

### 9. 自律ユーザープロファイリング設定

会話ログからユーザーの開発環境や好みを自動抽出するプロファイリング機能の設定です。

- `UAGENT_ENABLE_PROFILING`: 自律プロファイリング機能の有効/無効 (`1`: 有効(既定), `0`: 無効)。
- `UAGENT_PROFILE_FILE`: プロファイルデータの保存先ファイルパス（既定: `scheck_profile.jsonl`）。

### 10. 専門サブエージェントの個別設定 (オーバーライド)

`run_sub_agent` ツールで実行される専門サブエージェント（`planner`, `reviewer`, `summarizer`, `patch_designer`, `error_analyst`）のプロバイダやモデル、APIキーを個別に上書きできます。未指定時はメインエージェントの設定が引き継がれます。

- **サブエージェント全体の上書き**:
  - `UAGENT_SUB_AGENT_PROVIDER`: サブエージェント全体で使用するプロバイダ。
  - `UAGENT_SUB_AGENT_DEPNAME`: サブエージェント全体で使用するモデル名。
  - `UAGENT_SUB_AGENT_API_KEY`: サブエージェント全体で使用するAPIキー。

- **ファンクション（役割）別の個別上書き (最優先)**:
  - `UAGENT_SUB_AGENT_<AGENT_NAME>_PROVIDER`: 特定のサブエージェント専用のプロバイダ。
  - `UAGENT_SUB_AGENT_<AGENT_NAME>_DEPNAME`: 特定のサブエージェント専用のモデル名。
  - `UAGENT_SUB_AGENT_<AGENT_NAME>_API_KEY`: 特定のサブエージェント専用のAPIキー。
  *(※ `<AGENT_NAME>` は `PLANNER`, `REVIEWER`, `SUMMARIZER`, `PATCH_DESIGNER`, `ERROR_ANALYST` のいずれか)*

  *(例: `UAGENT_SUB_AGENT_SUMMARIZER_PROVIDER=gemini` および `UAGENT_SUB_AGENT_SUMMARIZER_DEPNAME=gemini-2.5-flash` と指定することで、要約タスクのみ高速・安価な Gemini 2.5 Flash に処理させることができます)*

______________________________________________________________________

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
1. **利用**: `uag` 起動時に `.env.sec` が自動的に検出され、パスワード入力により復号・読み込みが行われます。
1. **更新**: 既存の `.env.sec` に変数を追加/更新するには `uag_envsec add --file .env.sec --key NAME --value VALUE` を使います。
