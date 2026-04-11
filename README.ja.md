```
██╗   ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗ ██████╗██╗     ██╗
██║   ██║██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██║     ██║
██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     ██║     ██║
██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██║     ██║
╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ╚██████╗███████╗██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝╚══════╝╚═╝
```

# uag（ローカルAIエージェント）

uag は、ローカルPC上で **コマンド実行**・**ファイル操作**・**各種データ読取** などを行う対話型エージェントです。

- CUI（CLI）: `uag` / `python -m uagent`
- GUI: `uagg` / `python -m uagent.gui`
- Web: `uagw` / `python -m uagent.web`
- A2Aサーバー: `uaga` / `python -m uagent.a2a.server`

______________________________________________________________________

## 主な特長

- ローカル環境ですぐ使える、実用的で幅広いツール群
- CLI / GUI / Web の3つの入口
- OpenAI互換 / Azure / Bedrock / OpenRouter / Ollama / Gemini / Claude / Grok / NVIDIA に対応
- LLM（プロバイダ/モデル）を切り替えてもセッション継続が可能（会話コンテキストを引き継ぎ）
- エンドツーエンドの i18n 対応: ホストUIの多言語化（`UAGENT_LANG`）と、LLM 通信の TO_LLM/FROM_LLM 翻訳をサポート
- テキスト、PDF、PPTX、Excel、画像、スクリーンショットまで扱える
- セッション継続と履歴制御: `:logs` / `:load`、手動 `:shrink_llm`、任意の自動圧縮
- MCP による外部ツールサーバ連携が可能（`mcp_servers_tool.py`, `mcp_tools_list_tool.py`, `handle_mcp_v2_tool.py`）
- 確認・パス制限・マスキング・スモークテストによる安全性重視
- 起動時初期化は `src/uagent/runtime_*`（workdir / banner / env / memory）に分割し、`src/uagent/runtime_init.py` から互換再エクスポートする形で共通化
- GPT-5.4+ Responses 向けに、軽量な tools prompt、`tool_catalog`、リクエストに応じたツール絞り込みを実装

______________________________________________________________________

## ドキュメント（`uag docs`）

wheel（whl）でインストールした環境でも、同梱ドキュメントを `uag docs` で参照できます。

```bash
uag docs
uag docs webinspect
uag docs develop
uag docs --path webinspect
uag docs --open webinspect
```

______________________________________________________________________

## インストール（配布版: whl）

配布された whl を pip でインストールする手順は **`QUICKSTART.md`** を参照してください。

- 配布先: GitHub の **Releases** ページ（Assets の `.whl`）
- whl 例: `uag-<VERSION>-py3-none-any.whl`
- インストール例:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ./uag-<VERSION>-py3-none-any.whl
```

補足:

- `uag` は **Python 3.11+** が必要です。
- リポジトリを開発用途で使う場合は、`python -m pip install -e .` を推奨します。

______________________________________________________________________

## 使い方（最低限）

## A2A（Agent2Agent）サーバー

`uag` は、既存の CLI/GUI/Web の挙動に影響を与えずに、別プロセスとして A2A 互換の HTTP サーバーを起動できます。

### サーバー起動

```bash
# 認証が必要なエンドポイント用（必須）
export UAGENT_A2A_TOKEN=YOUR_TOKEN

# 既定: host=0.0.0.0, port=8765
uaga
# または
python -m uagent.a2a.server
```

### 設定（環境変数）

- `UAGENT_A2A_TOKEN`: 認証が必要なエンドポイント用。空の場合、認証が必要なエンドポイントは無効化されます。
- `UAGENT_A2A_CONCURRENCY`: 同時リクエスト数の上限（既定: `1`）。
- `UAGENT_A2A_ENGINE`: リクエスト処理のバックエンド（既定: `uag`。テストでは `echo` を使う場合があります）。
- `UAGENT_A2A_BASE_URL`: クライアント側の接続先ベースURL（既定: `http://127.0.0.1:8765`）。
- `UAGENT_SIMPLE_PROMPT`: 既定は `1` です。`0` / `false` / `no` / `off` を設定すると readline ベースのプロンプト経路を無効化します（CLI の描画が不自然な場合に有効）。

### クライアント利用（任意）

通常の `uag`（CLI/GUI/Web）利用では、A2A クライアントは不要です。
別プロセス／別アプリから A2A サーバーを呼び出して連携したい場合のみ使用してください。

## 言語（i18n）

ホスト側のUI文言は gettext カタログで多言語化されています。

- 言語選択: `UAGENT_LANG` を設定します（例: `en`, `ja`, `zh_CN`, `zh_TW`, `es`, `fr`, `ko`, `th`）。
- `UAGENT_LANG` が未設定または未対応の場合、英語にフォールバックします。

例:

Windows (cmd):

```bat
set UAGENT_LANG=ko
uag
```

macOS/Linux:

```bash
export UAGENT_LANG=ko
uag
```

新しいロケールの追加方法は `src/uagent/docs/ADD_LOCALE.md` を参照してください。

開発向けメモ:

- `src/uagent/locales/*/LC_MESSAGES/uag.po` を編集したら、`.mo` を再生成します:

```bash
python scripts/compile_locales.py
```

- i18n の簡易QC（レポートは `outputs/i18n/` に出力）:

```bash
python scripts/po_qc_summary.py
```

関連: `src/uagent/docs/DEVELOP_I18N.md`。

### 起動

```bash
uag
# または
python -m uagent
```

#### 作業ディレクトリ（workdir）の指定

通常は指定の必要はありません。

- CLI: `uag -C ./work`
- GUI: `uag gui -C ./work`（または `python -m uagent.gui -C ./work`）
- Web: `UAGENT_WORKDIR=./work uag web`（Web は環境変数で指定）

終了:

- `:exit`

### Tips（会話の継続）

- `:tools`
  ロード済みツール一覧を表示します。
- `:v [0|1|2|3]`（引数なしで現在の設定表示）
  verbosity（出力の詳しさ）を設定します。
- `:logs`\
  セッションログ一覧を表示します。
- `:logs 20`\
  最大20件まで表示します。
- `:logs --all`\
  すべてのログを表示します。
- `:load 0`\
  最新のセッションログを読み込み、会話を継続します。
- `:load <index>`\
- `:skills`\
  Agent Skills を一覧し、選択した `SKILL.md` をセッションに読み込みます。
- `:skills status`\
  有効なスキルの system メッセージを表示します。
- `:skills clear`\
  有効なスキルの system メッセージを解除します。
- 読み込んだスキルはセッションログに保存され、`:load` で復元されます。

______________________________________________________________________

## GPT-5.4+ Responses でのツール探索

Responses API が有効で、選択モデルが GPT-5 系の `5.4` 以上の場合、uag は軽量なツール読み込み経路を使います。

- 毎回すべてのツール定義を先送りしません
- 全ツールを毎回列挙する代わりに、軽量な tools prompt を使います
- `tool_catalog` で関連ツールを先に探索できます
- 実際に LLM へ渡す tool specs は、ユーザーの要求に応じて絞り込みます
- catalog ヒットがない場合も安全な最小集合へフォールバックします

これにより、他モデルの既存挙動を維持しつつ、プロンプトとツール定義のペイロードを削減します。

______________________________________________________________________

## 履歴圧縮（手動 / 自動）

手動コマンド:

- `:shrink [keep_last]`（既定 `keep_last=40`）: system 以外（user/assistant/tool）を末尾 N 件だけ残して削除します。
- `:shrink_llm [keep_last]`（既定 `keep_last=20`）: 古い履歴を LLM で要約して system メッセージ 1 件に圧縮し、末尾 N 件を残します。

自動圧縮（全プロバイダ）:

- `UAGENT_SHRINK_CNT`（既定: `100`）
  - system を除いたメッセージ（user/assistant/tool）の件数がこの値に達すると、自動で `:shrink_llm` 相当を実行します。
  - `0` を設定すると無効化します。
- `UAGENT_SHRINK_KEEP_LAST`（既定: `20`）: 自動要約後に末尾へ残す件数。

ログ書き戻し:

- 圧縮（手動/自動）が動いたとき、現在セッションのログ（`UAGENT_LOG_FILE` / `core.LOG_FILE`）を圧縮後の内容で書き戻します。
- その際、ログ保存フォルダ直下の `<log_dir>/.backup/` に 1世代分のバックアップ（`.org`）を作成します。

______________________________________________________________________

## （任意）Responses API 設定 (reasoning / verbosity)

Azure/OpenAI/Bedrock/Ollama で **Responses API** (`UAGENT_RESPONSES=1`) を使用する場合、推論の試行回数や出力の冗長性を制御できます。

Bedrock では OpenAI互換ゲートウェイの制約に合わせるため、message list ではなく文字列 `input` を使う Bedrock 専用の Responses リクエストビルダーを使用します。

Responses API に未対応のプロバイダで `UAGENT_RESPONSES=1` を指定した場合、実行時に ChatCompletions へフォールバックします。

- `UAGENT_REASONING`:
  - `auto`: リクエストごとに `reasoning.effort` を自動選択（Responses APIのみ。ストリーミングは自動でOFF。低品質出力時に1回だけ再試行する場合があります）
  - `minimal|low|medium|high|xhigh`: `reasoning={"effort":...}` を送信
  - `off` / 未設定 / 空: `reasoning` を送信しない
- `UAGENT_VERBOSITY`:
  - `low|medium|high`: `text={"verbosity":...}` を送信
  - `off` / 未設定 / 空: `text.verbosity` を送信しない

セッション内コマンド（CLI/GUI/Web）:

- `:r [0|1|2|3|auto|minimal|xhigh]`（引数なしで現在値表示）
- `:v [0|1|2|3]`（引数なしで現在値表示）

______________________________________________________________________

## Provider

`uag` は複数のLLMプロバイダを切り替えて利用できます。

- `UAGENT_PROVIDER=openai` は **OpenAI互換**（OpenAI API互換のエンドポイントを含む）として扱います。

  - 必須: `UAGENT_OPENAI_API_KEY`
  - 任意: `UAGENT_OPENAI_BASE_URL`（既定: `https://api.openai.com/v1`）
  - 任意: `UAGENT_OPENAI_DEPNAME`

- `UAGENT_PROVIDER=azure` は **Azure OpenAI** を利用します。

  - 必須: `UAGENT_AZURE_BASE_URL`
  - 必須: `UAGENT_AZURE_API_KEY`
  - 必須: `UAGENT_AZURE_API_VERSION`
  - 任意: `UAGENT_AZURE_DEPNAME`

- `UAGENT_PROVIDER=bedrock` は **Bedrock（OpenAI互換ゲートウェイ）** を利用します。

  - 必須: `UAGENT_BEDROCK_BASE_URL`
  - 必須: `UAGENT_BEDROCK_API_KEY`
  - 任意: `UAGENT_BEDROCK_DEPNAME`

- `UAGENT_PROVIDER=openrouter` は **OpenRouter**（OpenAI互換の統一API）を利用します。

  - 必須: `UAGENT_OPENROUTER_API_KEY`
  - 任意: `UAGENT_OPENROUTER_BASE_URL`（既定: `https://openrouter.ai/api/v1`）
  - 任意: `UAGENT_OPENROUTER_DEPNAME`
  - 任意: OpenRouter のモデルフォールバック（OpenRouter独自拡張）
    - 条件: `UAGENT_OPENROUTER_DEPNAME="openrouter/auto"` のときのみ有効（他プロバイダ・他モデル指定には影響しません）
    - `UAGENT_OPENROUTER_FALLBACK_MODELS`（カンマ区切り）を設定すると、Chat Completions リクエストに `models=[...]` を付与します
      - 例: `UAGENT_OPENROUTER_FALLBACK_MODELS="anthropic/claude-4.5-sonnet,openai/gpt-4o,mistral/mistral-x"`

- `UAGENT_PROVIDER=nvidia` は **NVIDIA（OpenAI互換）** を利用します。

  - 必須: `UAGENT_NVIDIA_API_KEY`
  - 任意: `UAGENT_NVIDIA_BASE_URL`（既定: `https://integrate.api.nvidia.com/v1`）
    - `/v1` を指定してください（`/v1/chat/completions` まで含める指定は推奨しません）
  - 任意: `UAGENT_NVIDIA_DEPNAME`

- `UAGENT_PROVIDER=grok` は **xAI Grok（OpenAI互換）** を利用します。

  - 必須: `UAGENT_GROK_API_KEY`
  - 任意: `UAGENT_GROK_BASE_URL`（既定: `https://api.x.ai/v1`）
  - 任意: `UAGENT_GROK_DEPNAME`

- `UAGENT_PROVIDER=gemini` は **Google Gemini（google-genai）** を利用します。

  - 必須: `UAGENT_GEMINI_API_KEY`
  - 任意: `UAGENT_GEMINI_DEPNAME`

- `UAGENT_PROVIDER=claude` は **Anthropic Claude** を利用します。

  - 必須: `UAGENT_CLAUDE_API_KEY`
  - 任意: `UAGENT_CLAUDE_DEPNAME`

※共通の正本テンプレートは `samples/env.sample.env` です。

- リポジトリ上では、対話式ウィザード `python -m uagent.setup_cli` を実行すると、意図した文字コード/改行コードで `samples/env.sample.sh` / `samples/env.sample.ps1` / `samples/env.sample.bat` を生成できます。
- pip/whl でインストールした環境では、`uag_setup` を実行すると、カレントディレクトリに `.env`（および任意で `env.sh` / `env.ps1` / `env.bat`）を生成できます。

プロバイダ別は `samples/provider.*.env.sample` を参照してください。詳細は `samples/README.md` を参照。

### env サンプル生成

サンプルは `samples/` 配下にあり、詳細は `samples/README.md` を参照してください。

対話式ウィザードで設定し、シェル別サンプルを生成します。

```bash
python -m uagent.setup_cli
```

生成されるファイルと形式:

- `samples/env.sample.sh` : UTF-8, LF
- `samples/env.sample.ps1` : BOM付きUTF-8（`utf-8-sig`）, CRLF
- `samples/env.sample.bat` : CP932, CRLF

番号選択と `b`（戻る）に対応した対話式です。再実行でいつでも設定を更新できます。

______________________________________________________________________

## uag_envsec

`uag_envsec` は、`.env` などの環境ファイル/値を暗号化・復号する小さな独立パッケージです。

- CLI: `uag_envsec`
- 入力 `.env` を `*.sec` に暗号化（既定: `<入力>.sec`）
- パスワードを尋ね、ローカルの鍵ファイルを使います
- CLI の既定鍵ファイル: カレントディレクトリの `.uagent.key`
- Python ヘルパーを直接使う場合の既定鍵パス: `~/.uag/uag_envsec_key`

使用例:

```bash
uag_envsec .env
uag_envsec .env --output .env.sec --key-file .uagent.key
```

## 翻訳（TO_LLM / FROM_LLM、任意）

既定では uag は **翻訳しません**。

翻訳を有効化するには、以下を設定します:

- `UAGENT_TRANSLATE_PROVIDER`: 翻訳プロバイダ（OpenAI互換の文字列。例: `openai` / `azure` / `openrouter` / `nvidia` / `grok`）
- `UAGENT_TRANSLATE_TO_LLM`: LLMに送る前に **翻訳する先** の言語タグ（例: `en`）
- `UAGENT_TRANSLATE_FROM_LLM`: LLM出力を表示する前に **翻訳する先** の言語タグ（例: `ja`）

OpenAI互換翻訳の追加設定:

- `UAGENT_TRANSLATE_DEPNAME`: 翻訳用モデル名（翻訳を有効化する場合は必須）
- `UAGENT_TRANSLATE_API_KEY`: 任意（未設定時はメインプロバイダのキーを流用）
- `UAGENT_TRANSLATE_BASE_URL`: 任意（未設定時はメインプロバイダの Base URL を流用）

補足:

- 翻訳は **1回ごと（ステートレス）** に行います。
- 翻訳が有効な場合、部分出力の不整合を避けるためストリーミングは **強制的にOFF** になります（`UAGENT_STREAMING` より優先）。

______________________________________________________________________

## 画像生成・解析（Image Generation / Analysis）

### 画像生成（`generate_image`）

- `UAGENT_IMG_GENERATE_PROVIDER`: 画像生成用のプロバイダを個別に指定します（未指定時は `UAGENT_PROVIDER` を使用）。
- `UAGENT_IMG_GENERATE_DEPNAME`: 生成用のモデル名またはデプロイ名（例: `dall-e-3`）。
- `UAGENT_IMAGE_OPEN`: 生成後に画像を自動で開くかどうか。
  - `1`: 開く（既定）
  - `0`: 開かない

プロバイダ別の指定例: `UAGENT_OPENAI_IMG_GENERATE_DEPNAME`, `UAGENT_AZURE_IMG_GENERATE_DEPNAME`。

プロバイダ別の認証/エンドポイント:

- `UAGENT_<PROVIDER>_IMG_GENERATE_API_KEY`（必須）
- `UAGENT_<PROVIDER>_IMG_GENERATE_BASE_URL`（多くのプロバイダで任意。既定値がある場合あり）
- Azureのみ: `UAGENT_AZURE_IMG_GENERATE_API_VERSION`（必須）

フォールバック:

- `*_IMG_GENERATE_*` が未設定の場合、メインプロバイダ側の環境変数（例: `UAGENT_OPENAI_API_KEY`, `UAGENT_OPENAI_BASE_URL`）も参照します。

### 画像解析（`analyze_image`）

既定では、`analyze_image` ツールは `UAGENT_PROVIDER` で指定されたプロバイダを使用しますが、専用の環境変数で上書き可能です。

- `UAGENT_RESPONSES=1`: 有効にすると `analyze_image` ツールが非表示になり、代わりに LLM 本体のマルチモーダル機能を使って直接画像を扱います（モデルが対応している場合）。
- `UAGENT_IMG_ANALYSIS_PROVIDER`: 画像解析用のプロバイダを個別に指定します。
- `UAGENT_IMG_ANALYSIS_DEPNAME`: 画像解析用のモデル名を指定します。
- `UAGENT_IMG_ANALYSIS_API_KEY`: 画像解析用の API キーを指定します。
- `UAGENT_IMG_ANALYSIS_BASE_URL`: 画像解析用のベース URL を指定します。

プロバイダ別の指定例: `UAGENT_OPENAI_IMG_ANALYSIS_DEPNAME`, `UAGENT_AZURE_IMG_ANALYSIS_DEPNAME`。

`analyze_image` で利用可能なプロバイダ: `openai`, `azure`。

______________________________________________________________________

## 更新情報

- **自動 shrink_llm** を追加しました（全プロバイダ）。
  - `UAGENT_SHRINK_CNT`（既定: `100`）: system を除いたメッセージ（user/assistant/tool）の件数がこの値に達すると、自動で `:shrink_llm` 相当を実行します。
  - `UAGENT_SHRINK_CNT=0`: 自動圧縮を無効化します。
  - `UAGENT_SHRINK_KEEP_LAST`（既定: `20`）: 要約後に末尾へ残す件数です。
- GPT-5.4+ Responses 向けに `tool_catalog` と軽量 tools prompt による tool narrowing を追加しました。
- MCP server 管理ツールのスモークテストを追加しました。
- 圧縮（手動 `:shrink` / `:shrink_llm` または自動）実行時に、現在セッションのログを圧縮後の履歴で書き戻します。
  - ログ保存フォルダ直下の `<log_dir>/.backup/` に 1世代分のバックアップ（`.org`）を作成します。

______________________________________________________________________

## 開発者向け

開発者向けの情報は `src/uagent/docs/DEVELOP.md` を参照してください。

追加ドキュメント:

- `src/uagent/docs/RUNTIME_INIT.md`（起動時初期化: workdir/banner/長期記憶）
- `src/uagent/docs/WEB_UI_LOGGING.md`（Web UI のログ/メッセージ経路）

______________________________________________________________________

## Web Inspector（playwright_inspector）

Playwright Inspector を使って、手動操作の流れ（URL遷移/DOM/スクリーンショット/イベントログ）を保存できます。

前提:

- `playwright` がインストールされていること
- ブラウザのセットアップが済んでいること（例: `python -m playwright install`）

ドキュメント:

- `src/uagent/docs/WEBINSPECTER.md`
- `uag docs webinspect`（wheel環境でも参照可能）
