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

### 1. LLM プロバイダ設定

使用するプロバイダに応じて、以下のいずれか（または複数）を設定してください。

| プロバイダ | 必須/推奨変数 |
| :--- | :--- |
| **OpenAI** | `UAGENT_OPENAI_API_KEY` |
| **Anthropic** | `UAGENT_ANTHROPIC_API_KEY` |
| **Google (Gemini)** | `UAGENT_GEMINI_API_KEY` |
| **Azure OpenAI** | `UAGENT_AZURE_OPENAI_API_KEY`, `UAGENT_AZURE_BASE_URL`, `UAGENT_AZURE_DEPLOYMENT_ID` |
| **AWS (Bedrock)** | `UAGENT_AWS_REGION`, `UAGENT_AWS_ACCESS_KEY_ID`, `UAGENT_AWS_SECRET_ACCESS_KEY` |
| **OpenRouter** | `UAGENT_OPENROUTER_API_KEY` |
| **Ollama** | `UAGENT_OLLAMA_BASE_URL` (既定: `http://localhost:11434`) |
| **Grok (xAI)** | `UAGENT_GROK_API_KEY` |
| **NVIDIA** | `UAGENT_NVIDIA_API_KEY` |
| **DeepSeek** | `UAGENT_DEEPSEEK_API_KEY` |

### 2. エージェントの基本動作

- `UAGENT_LANG`: ホスト UI の言語を指定します。
  - `ja`: 日本語
  - `en`: 英語
- `UAGENT_WORKDIR`: エージェントが操作を行うデフォルトの作業ディレクトリ。
- `UAGENT_VERBOSITY`: ログ出力の冗長性（`low`, `medium`, `high`）。

### 3. 会話履歴の管理（オートシュリンク）

トークン消費を抑えるため、会話が長くなった際に古いメッセージを自動的に削除または要約する機能です。

- `UAGENT_SHRINK_CNT`: 自動圧縮を開始するメッセージ数（既定: `100`）。
- `UAGENT_SHRINK_KEEP_LAST`: 圧縮後に最新のメッセージをいくつ保持するか（既定: `20`）。

### 4. 記憶とツール

- `UAGENT_MEMORY_FILE`: 長期記憶メモの保存先パス。
- `UAGENT_SHARED_MEMORY_FILE`: 他のセッションと共有する長期記憶のパス。
- `UAGENT_EMBEDDING_API_URL`: セマンティック検索に使用する埋め込み（Embedding）APIのURL。

---

## セキュリティと暗号化 (`uag_envsec`)

APIキーなどの機密情報を平文の `.env` ファイルに保存したくない場合は、`uag_envsec` を使用してファイルを暗号化できます。

1. **暗号化**:
   ```bash
   uag_envsec .env
   ```
   パスワードを入力すると、暗号化された `.env.sec` と、ローカル鍵ファイル `.uagent.key` が生成されます。
   
2. **利用**:
   `uag` 起動時に自動的に `.env.sec` が復号されて読み込まれます（パスワード入力が必要です）。

---

## 高度な設定

- `UAGENT_RESPONSES`: `1` に設定すると、OpenAI 等のプロバイダで "Responses API" を使用します。
- `UAGENT_REASONING`: 推論モデル（o1等）の推論の試行レベルを指定します（`auto`, `low`, `medium`, `high`）。
- `UAGENT_CMD_ENCODING`: 外部コマンド実行時の標準出力のデコードに使用するエンコーディング。
