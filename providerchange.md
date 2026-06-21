# `:provider` コマンド仕様書

## 1. 背景・目的

現在、プロバイダの切り替えは環境変数 `UAGENT_PROVIDER` を変更し、プロセスを再起動する必要がある。
セッション中にプロバイダを動的に切り替えられる `:provider` コマンドを実装し、
再起動不要でシームレスなプロバイダ変更を可能にする。

## 2. 用語

| 用語 | 説明 |
|---|---|
| **プロバイダ** | LLM バックエンド（openai, claude, gemini, deepseek 等）。`UAGENT_PROVIDER` で指定。 |
| **デプロイ名 (depname)** | プロバイダ内のモデル識別子。`UAGENT_{PROVIDER}_DEPNAME` で指定。 |
| **サブプロバイダ** | 画像生成・音声・埋め込み等、LLM 以外の機能に特化したプロバイダ。 |
| **動的環境変数** | `os.environ` の値をランタイムで変更する方式（既に sub_agent_tool.py で採用）。 |

## 3. コマンド仕様

### 3.1 書式

```
:provider                      # 現在のプロバイダ情報を表示
:provider list                 # 利用可能なプロバイダ一覧
:provider switch <name>        # プロバイダを <name> に切り替え（同一セッション継続）
:provider model [<name>]       # 現在のモデル名を表示 / モデルを切り替え
:provider env                  # 現在のプロバイダ関連の環境変数一覧
```

### 3.2 サブコマンド詳細

#### `:provider`（引数なし）

現在のプロバイダ名、モデル名、利用可否を表示する。

出力例:
```
Current provider: openai
  Model: gpt-4o
  Status: OK (quota available)
  Image generation: openai (dall-e-3)
  Audio speech: openai (gpt-4o-mini-tts)
```

#### `:provider list`

設定済み（環境変数が検出された）プロバイダと未設定のプロバイダを一覧表示する。

出力例:
```
Available providers:
  openai    ✅  UAGENT_OPENAI_API_KEY set, model: gpt-4o
  claude    ✅  UAGENT_CLAUDE_API_KEY set, model: claude-sonnet-4-20250514
  gemini    ✅  UAGENT_GEMINI_API_KEY set, model: gemini-2.5-flash
  deepseek  ❌  UAGENT_DEEPSEEK_API_KEY not set
  ollama    ❌  UAGENT_OLLAMA_BASE_URL not set
  azure     ❌  UAGENT_AZURE_API_KEY not set
  bedrock   ❌  (require AWS credentials)
  ...
```

検出ロジック: 各プロバイダの必須環境変数が設定されているかで判定する。

#### `:provider switch <name>`

プロバイダを `<name>` に切り替える。実際に行う処理:

1. `os.environ["UAGENT_PROVIDER"]` を更新（`sub_agent_tool.py` と同様の方式）
2. LLM クライアントを再初期化（`make_client()` を再実行）
3. 会話履歴は保持（同一セッション継続）
4. 画像生成・音声等のサブプロバイダは変更しない（個別に設定されている場合）

制約:
- `<name>` は `detect_provider()` の許可リストに含まれる16プロバイダのいずれか
- 切り替え先の必須環境変数が未設定の場合はエラーメッセージを表示して拒否
- 会話履歴の再フォーマットは行わない（モデル間の互換性は利用者の責任）

#### `:provider model [<name>]`

- 引数なし: 現在のモデル名を表示
- 引数あり: 同一プロバイダ内でモデルを切り替え（`UAGENT_{PROVIDER}_DEPNAME` を更新）

#### `:provider env`

現在のプロバイダに関連する環境変数を一覧表示する。

出力例:
```
UAGENT_PROVIDER=openai
UAGENT_OPENAI_API_KEY=sk-...****
UAGENT_OPENAI_DEPNAME=gpt-4o
UAGENT_IMG_GENERATE_PROVIDER=openai
UAGENT_AUDIO_SPEECH_PROVIDER=openai
```

### 3.3 エラー処理

| 状況 | 動作 |
|---|---|
| 不明なプロバイダ名 | `Unknown provider: '<name>'. Allowed: ...` を表示 |
| 必須環境変数未設定 | `Provider '<name>' is not configured. Required: UAGENT_<NAME>_API_KEY` を表示 |
| 切り替え成功 | `Switched to <name> (model: <depname>)` を表示 |
| 内部エラー（make_client 失敗） | `Failed to initialize <name>: <error>` を表示 |

## 4. 実装詳細

### 4.1 ファイル構成

新規ファイル: `src/uagent/tools/provider_control_tool.py`

```python
# 既存パターンに従う
CMD_SPECS = [
    {
        "command": "provider",
        "subcommand": "",
        "handler": handle_cmd_provider_status,
        "help_text": "  :provider                    Show current provider info",
    },
    {
        "command": "provider",
        "subcommand": "list",
        "handler": handle_cmd_provider_list,
        "help_text": "  :provider list               List available providers with config status",
    },
    {
        "command": "provider",
        "subcommand": "switch",
        "handler": handle_cmd_provider_switch,
        "help_text": "  :provider switch <name>      Switch LLM provider at runtime",
    },
    {
        "command": "provider",
        "subcommand": "model",
        "handler": handle_cmd_provider_model,
        "help_text": "  :provider model [<name>]     Show or change the current model",
    },
    {
        "command": "provider",
        "subcommand": "env",
        "handler": handle_cmd_provider_env,
        "help_text": "  :provider env                Show provider-related environment variables",
    },
]
```

i18n ファイル: `src/uagent/tools/provider_control_tool.json`

### 4.2 依存関数

- `detect_provider()` / `detect_provider_allow_empty()` — 現在のプロバイダ取得（`util_providers.py`）
- `make_client()` — プロバイダクライアント生成（`util_providers.py`）
- `os.environ` — 環境変数の動的更新

### 4.3 プロバイダ検出ロジック（`:provider list` 用）

各プロバイダの必須環境変数:

| プロバイダ | 必須変数 | 任意変数 |
|---|---|---|
| openai | `UAGENT_OPENAI_API_KEY` | `UAGENT_OPENAI_DEPNAME` |
| azure | `UAGENT_AZURE_API_KEY`, `UAGENT_AZURE_BASE_URL`, `UAGENT_AZURE_API_VERSION` | `UAGENT_AZURE_DEPNAME` |
| bedrock | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` | `UAGENT_BEDROCK_DEPNAME` |
| openrouter | `UAGENT_OPENROUTER_API_KEY` | `UAGENT_OPENROUTER_DEPNAME` |
| ollama | `UAGENT_OLLAMA_BASE_URL` | `UAGENT_OLLAMA_DEPNAME` |
| gemini | `UAGENT_GEMINI_API_KEY` | `UAGENT_GEMINI_DEPNAME` |
| vertexai | `UAGENT_GEMINI_API_KEY` or `UAGENT_VERTEXAI_API_KEY` | `UAGENT_VERTEXAI_DEPNAME` |
| grok | `UAGENT_GROK_API_KEY` | `UAGENT_GROK_DEPNAME` |
| claude | `UAGENT_CLAUDE_API_KEY` | `UAGENT_CLAUDE_DEPNAME` |
| nvidia | `UAGENT_NVIDIA_API_KEY` | `UAGENT_NVIDIA_DEPNAME` |
| deepseek | `UAGENT_DEEPSEEK_API_KEY` | `UAGENT_DEEPSEEK_DEPNAME` |
| zai | `UAGENT_ZAI_API_KEY` | `UAGENT_ZAI_DEPNAME` |
| alibaba | `UAGENT_ALIBABA_API_KEY` | `UAGENT_ALIBABA_DEPNAME` |
| moonshot | `UAGENT_MOONSHOT_API_KEY` | `UAGENT_MOONSHOT_DEPNAME` |
| mimo | `UAGENT_MIMO_API_KEY` | `UAGENT_MIMO_DEPNAME`, `UAGENT_MIMO_BASE_URL` |
| lmstudio | `UAGENT_LMSTUDIO_BASE_URL` | `UAGENT_LMSTUDIO_DEPNAME` |

### 4.4 i18n キー一覧

- `cmd.help.provider` — ヘルプテキスト（5エントリ）
- `msg.provider.current` — 現在のプロバイダ情報表示
- `msg.provider.list_header` — 一覧ヘッダ
- `msg.provider.configured` — 設定済み表示
- `msg.provider.not_configured` — 未設定表示
- `msg.provider.switch_ok` — 切り替え成功
- `msg.provider.switch_fail` — 切り替え失敗（環境変数不足）
- `msg.provider.switch_error` — 切り替え失敗（内部エラー）
- `msg.provider.unknown` — 不明なプロバイダ

### 4.5 注意点

- **スレッドセーフティ**: `os.environ` の更新は GIL 保護下にあるが、理論上の競合を避けるため
  `sub_agent_tool.py` と同様に `_PROVIDER_ENV_LOCK`（`threading.Lock()`）を使用する。
- **クライアントキャッシュ**: `make_client()` の結果はキャッシュせず、切り替え都度再生成する。
  既存のクライアントインスタンスはガベージコレクションに任せる。
- **サブプロバイダ**: `UAGENT_IMG_GENERATE_PROVIDER` 等のサブプロバイダは `:provider switch` では変更しない。
  これらは個別の env 設定による分離を維持する。
- **チャット履歴**: 切り替え前の履歴は保持される。ただしモデルによって system prompt の
  フォーマットや対応ツールが異なる場合があるため、利用者は切り替え後に動作を確認すること。
- **`:provider model`**: モデル名のみの変更では `make_client()` を再実行しない（軽量変更）。
  プロバイダの再初期化が必要な場合は個別に対応する。

## 5. 将来拡張

- **自動フォールバック**: 現在のプロバイダが rate limit または API エラーを返した場合、
  自動的に設定済みの別プロバイダにフォールバックする。
- **プロバイダ別コンテキスト保持**: プロバイダごとに会話履歴を分離して保持し、
  切り替え時に適切な履歴を復元する。
- **`UAGENT_PROVIDER_PRIORITY`**: フォールバック順序を環境変数で指定可能にする。
