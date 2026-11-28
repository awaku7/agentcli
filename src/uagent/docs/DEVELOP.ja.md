# DEVELOP（開発者向け）

このドキュメントは **uag（ローカル ツール実行エージェント）** の開発者向けメモです。

- エントリポイント:
  - **CUI**: `python -m uagent`（コマンド: `uag`）
  - **GUI**: `python -m uagent.gui`（コマンド: `uagg`）
  - **Web**: `python -m uagent.web`（コマンド: `uagw`）

______________________________________________________________________

## XLSM静的解析

`spreadsheet_analyze` は `.xlsm` ブックを読み取り専用で解析します。ワークシート構造には `openpyxl`、埋め込みVBAの抽出には `oletools` を使用し、マクロは実行しません。シート、数式、結合範囲、VBAのプロシージャ・呼び出し関係、および注意が必要な処理をJSONまたはMarkdownで出力します。翻訳リソースは `src/uagent/tools/spreadsheet_analyze_tool.json` にあります。

## 0. 動作環境

- Python 3.11 以上（`pyproject.toml` の `requires-python` 準拠）
- Git（バージョン管理および一部ツールで必須）
- Windows / macOS / Linux

______________________________________________________________________

## 1. 主要コンポーネント / 関連ファイル

- **Core**: `src/uagent/core.py`
  - 会話履歴、ログ、Busy状態（ステータス）、UI連携、（圧縮/要約などの）周辺機能
- **CLI**: `src/uagent/cli.py`
  - 標準入力ループ、`:cd`/`:ls`/`:cp`/`:mv`/`:head`/`:tail` 等のコマンド、起動時処理（Mode A では `main()` 内で workdir 初期化）
  - `:head <path> [n]` は先頭 n 行（既定 20 行）を表示し、`:tail <path> [n]` は末尾 n 行（既定 20 行）を表示する
  - `:cp` / `:mv` は workdir 内の安全なファイル操作を使うコマンドとして扱う
- **フルスクリーン CLI 表示**: `src/uagent/cli_impl/console_view.py`
  - 下端のステータス行に、プロバイダーが返した最新ラウンドのトークン使用量を
    既定で表示する。`UAGENT_SHOW_USAGE=0` で非表示にできる。`:tokens` のローカル概算とは別。
- **LLM Orchestration**: `src/uagent/uagent_llm.py`
  - 対話ラウンド実行、tool call の実行、429等のリトライ制御
  - ラウンド / メッセージ / tool call のヘルパは以下に分割済み
    - `src/uagent/llm_helpers.py`
    - `src/uagent/llm_message_helpers.py`
    - `src/uagent/llm_round_helpers.py`
    - `src/uagent/llm_flow_helpers.py`
  - ラウンドループの一部は別モジュールにある（`uagent_llm` から再エクスポート）
    - `src/uagent/llm_loop_guards.py`: ツールのループガード（会話ごとの状態）
    - `src/uagent/llm_turn_context.py`: ターンごとのコンテキスト準備とラウンドのコンテキスト計画
    - `src/uagent/llm_responses_runtime.py`: Responses の続きの状態とリモート復旧
    - `src/uagent/llm_registry_round.py`: プロバイダレジストリ経由のラウンド
    - `src/uagent/llm_computer_use_nav.py`: Computer Use の URL 直接ナビゲーション
  - リトライ / backoff ヘルパは `src/uagent/llm_errors.py`
- **セッションストア（オプトイン、SQLite）**: `src/uagent/runtime/session_store.py`
  - `SessionStore` は接続、スキーマ、セッション、メッセージ、判断ログを持つ。その他の領域は mixin に分かれている: `session_store_tools.py`（ツール呼び出し・結果・コンテキスト）、`session_store_agent_state.py`、`session_store_receipts.py`（サブエージェントの receipt）、`session_store_compaction.py`、`session_store_index.py`（語の索引、検索、要約）
  - 共通の定義は `session_store_common.py`、接続と切断は `session_store_attach.py`。import は `session_store` から行う（公開名を再エクスポートしている）
- **Providers**: `src/uagent/providers/util_providers.py`
  - 環境変数に基づきクライアント生成（Azure/OpenAI/Bedrock/OpenRouter/Perplexity Router/Ollama/Gemini/Vertex AI/Grok/Claude/NVIDIA/DeepSeek/Z.AI/Alibaba/Moonshot/MiMo/LM Studio/MiniMax/Sakana/Sakura/Novita/Together/Vercel 等）
  - プロバイダキーの一覧は `src/uagent/providers/provider_caps.py` の `ALL_PROVIDERS` で一元管理。
    `detect_provider()` と `env_validate.py` はそこから参照する。追加時は `ALL_PROVIDERS` に追記すること。
- **Utilities**: `src/uagent/util_tools.py`
  - tools callbacks 注入、初期メッセージ構築、コマンド処理、補助関数
- **Startup init**: `src/uagent/runtime/runtime_init.py`（互換レイヤ）
  - `src/uagent/runtime/runtime_workdir.py`: `decide_workdir()` / `apply_workdir()`
  - `src/uagent/runtime/runtime_banner.py`: `build_startup_banner()`
  - `src/uagent/runtime/runtime_env.py`: `validate_or_exit_startup_env(context=...)`
  - `src/uagent/runtime/runtime_memory.py`: `append_long_memory_system_messages()`
- `runtime/runtime_init.py` は、利用可能なら起動時にカレントディレクトリの `.env` と `.env.sec` を読み込みます（`.env` を先に読み込み、`.env.sec` は `.uagent.key` があれば使って復号します）

関連ドキュメント:

- ツール作成方法: `src/uagent/docs/DEVELOP_TOOL.md`
- ホスト側 i18n: `src/uagent/docs/DEVELOP_I18N.md`（コンパイル: `python scripts/compile_locales.py` / QC: `python scripts/po_qc_summary.py`）

______________________________________________________________________

## 2. 全体アーキテクチャ（実行の流れ）

1. `uag` / `uagg` / `uagw` が起動。
1. 起動時初期化（主に `runtime/runtime_init.py`）
   - workdir の決定（CLI引数 `--workdir/-C`、環境変数 `UAGENT_WORKDIR`、または自動）
   - 必要ならディレクトリ作成し `chdir`
   - 起動バナー文字列を生成して表示
   - 利用可能ならカレントディレクトリの `.env` と `.env.sec` を読み込む
1. ツールをロード（`src/uagent/tools/__init__.py`）
   - 内部ツール: `src/uagent/tools/*.py` を探索して登録
   - 外部ツール: `UAGENT_EXTERNAL_TOOLS_DIR` の `*.py` をロード（任意）
1. プロバイダのクライアントを生成（`util_providers.make_client`）
1. UI（CLI/GUI/Web）が入力を受け取りイベントとしてキューへ積む
1. `uagent_llm.run_llm_rounds()` が対話ラウンドを実行
   - tool call があれば実行し、結果を履歴へ追加して再帰
   - 429 Rate Limit 等の backoff は `llm_errors.py` に実装

### Gemini / Vertex API mode

`UAGENT_GEMINI_API_MODE` は `gemini` と `vertexai` のメインチャット経路を明示的に上書きします。未設定時は `gemini_api_mode(model, provider)` が、llmcapaで該当モデル・プロバイダーの `interactions_api` 対応が確認できた場合のみInteractionsを選択し、不明・非対応なら従来の `generate_content` を使います。Interactionsを明示指定しても、カタログ上で非対応のモデルは拒否します。Interactionsは `providers/llm_gemini_interactions.py` にディスパッチし、`store=false` のステートレス要求でUAGの会話履歴を送ります。思考署名やツール呼び出し履歴を再送できるよう、Interactionsの生ステップをassistantメッセージの `_gemini_content` に保持します。このモードではGenerateContent用キャッシュを作成せず、ストリーミングが有効でもAPI応答完了後に既存コールバック経由で一括表示します。

______________________________________________________________________

## 3. Tools システム（仕組みの概要）

### 3.1 ツールの発見と登録

ツールは `src/uagent/tools/` 配下のプラグインモジュールです。

登録条件:

- `TOOL_SPEC: dict` を持つ（OpenAI function schema 互換のメタデータ）
- `run_tool(args: dict) -> str` を持つ（実行関数）

ロード処理:

- `src/uagent/tools/__init__.py` が import 時に `_load_plugins()` を実行
- 登録情報、`get_tool_specs()`、`run_tool()` も `__init__.py` にある。補助処理は次の非公開モジュールに分かれ、パッケージから再エクスポートされる:
  - `tools/_manifest.py`: 遅延読み込み用のツール spec マニフェスト（キャッシュ）
  - `tools/_catalog.py`: `get_tool_catalog()` と CJK のクエリ分割（初回の検索時に読み込む）
  - `tools/_trace.py`: ツールの trace 行と、翻訳された実行前の説明文
  - `tools/_dynamic_commands.py`: `CMD_SPEC(S)` のコマンド登録（`_DYNAMIC_COMMANDS`）
- 内部ツールは `pkgutil.iter_modules()` で列挙して import/reload される
- `UAGENT_EXTERNAL_TOOLS_DIR` が指定されていれば、そこから `*.py` を追加ロードする

### 3.2 callbacks 注入（host → tools）

ツールからホスト（core）の機能を使うために、callbacks を注入します。

- `util_tools.init_tools_callbacks(core)` → `tools.init_callbacks(cb)`

特に `human_ask` は、stdin_loop/GUI 等と同期するために callbacks を使って状態共有します。

### 3.3 LLM に渡す tool specs

- `tools.get_tool_specs()` は、LLMへ送信するツール定義を返す
- 互換性のため、関数名を top-level `name` にミラーする場合がある
- `function.system_prompt` のような拡張フィールドは LLM送信時に削除される

### 3.5 Tool trace（実行ログ）

既定（`UAGENT_SHOW_TOOL_RESULTS=2`）では、実行前にローカライズ済みのアクション行を
stdout に表示します。専用の説明がないツールも、操作と主な対象（ファイル名・URL など）
だけの短い要約を表示します。内部処理や補助オプションは表示しません。自由形式の本文は
内容を出さずサイズのみ、秘密情報はマスクします。表示行は400文字以内です。

`UAGENT_SHOW_TOOL_RESULTS=0` にすると従来の `[TOOL] 2025-... name=<tool> args=<masked-json>` 形式に戻り、`1` では従来のトレースに実行後の結果要約を加えます。
トレース行の日時はオプトインで、既定では出ません。`UAGENT_TOOL_TRACE_TIMESTAMP=1` のときだけ表示します。
ツール側で `x_scheck.emit_tool_trace=false` を指定するとトレースを抑制できます。
`human_ask` は全モードでトレースを抑制します。`apply_patch` は diff ヘッダーから
対象ファイル名を表示します。詳細は `DEVELOP_TOOL.md` の 3.4.1 を参照してください。

### 3.5.1 大きな Tool Result の Artifact 化

`UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`（既定: `100000`）を超える
テキスト形式の Tool Result は `<state-dir>/artifacts/`（通常は
`~/.uag/artifacts/`）以下へ保存されます。
LLM には全体ではなく、サイズを制限したプレビューと
`artifact://...` 形式の参照だけを渡します。

保存時には、利用可能であれば現在の SessionStore を使用し、一般的な
認証情報らしき値をマスクします。詳細が必要な場合は、読み取り専用の
`artifact_read` ツールで Artifact ID または参照を指定し、必要な行範囲
だけを取得します。現在のセッションに属さない Artifact は取得できません。

この処理はプロバイダ変換より前に行うため、Meta など特定プロバイダ専用の
メタデータを Tool Message に追加せず、全プロバイダで共通に利用できます。

SessionStore と Artifact の SQLite 接続は WAL モード、
`synchronous=NORMAL`、busy timeout を使用します。該当する接続では外部キー
も有効にし、Artifact 書き込みは一時ファイルへのコピー後にアトミック rename
します。共有 SessionStore 接続は直列化され、メッセージ置換と JSONL import は
単一トランザクションで実行します。セッション単位のメッセージ、Tool Call、
Policy Decision、Artifact の検索用インデックスも初期化時に作成します。
セッションを削除すると、新形式のグローバル Artifact のレコードとディレクトリも
削除します。旧形式の workdir 内 Artifact は意図的に変更しません。
SQLite または JSONL へ保存する前に、Tool Message のコピーから画像・音声・
PDF・スクリーンショット・MCP バイナリのインラインデータを bounded marker
へ置換します。メモリ上の UI / リモート向け attachment は変更しません。

- **ツールレベル (`tool_level`)**: `TOOL_SPEC` に指定してロードを制御します。`-1` は無効、`0` は有効、`1` は条件付きロード（デフォルト無効）です。

### 3.6.2 GPT-5.4+ / Responses API のツール送信フロー

`UAGENT_RESPONSES=1` かつ OpenAI/Azure + GPT-5.4+ の場合、ツール送信方法が変わります:

**デフォルト (native mode)**: 全ツールをサーバに送信し、サーバ側 `tool_search` が絞り込みます。管理ツール(`tool_catalog`/`tool_load`/`unload_tool`)も含まれます。サーバ側 compaction が自動適用されます（閾値はローカルの auto-shrink と同じ）。

**`UAGENT_GPT54_TOOL_SEARCH=legacy`**: クライアント側で `_select_tool_specs_legacy()` がツールを絞り込みます。初期は `tool_catalog`/`tool_load`/`unload_tool`/`human_ask` のみ送信され、LLM が `tool_catalog` で発見 → `tool_load` で動的ロードします。

**`UAGENT_GPT54_TOOL_SEARCH=native`**（明示指定）: デフォルトと同じですが、管理ツールが除外されます。`_should_preload_lazy_specs()` が True になり、サーバー側の絞り込み用に利用可能なツール定義が登録されます。

**Gemini/Vertex Interactions Tool Retrieval**: 選択中のモデルについて llmcapa が `tool_search` を肯定し、Gemini API モードが `interactions` の場合、UAG は `{"type":"tool_search"}` と `defer_loading: true` を付けた関数定義を送ります。スキーマはプロバイダ側が必要時に取得しますが、関数の実行は通常の権限チェックを通して UAG が行います。能力情報が不明なら既存の `tool_catalog` フローを使います。`UAGENT_GPT54_TOOL_SEARCH` とは独立しています。Provider extra は `google-genai[httpx]>=3.6.1,<4` を使用します。SDK 3.x の既定が `v1` のため、Gemini Developer API の Tool Retrieval では `v1beta` を明示します。

**Anthropic Messages の Tool Search**: 選択中の Claude モデルについて、llmcapa が Messages API 上のサーバー側 `tool_search` を肯定した場合、公式の `tool_search_tool_bm25_20251119` と登録済みツール定義を送りますが、冗長な管理用ブートストラップの `tool_catalog` / `tool_load` / `unload_tool` は除外します。遅延定義には `defer_loading: true` を付け、よく使うツールの一部は即時利用できる状態にします。`server_tool_use` / `tool_search_tool_result` を含む Anthropic の応答ブロックはそのまま履歴に保持して次のリクエストへ再送し、発見された通常の `tool_use` は従来どおり UAG の権限チェックを通して実行します。能力情報が不明なら既存フローにフォールバックします。`UAGENT_ANTHROPIC_TOOL_SEARCH` は `native`（デフォルト、BM25 優先）、`bm25`、`regex`、`off` を指定できます。選択された形式も llmcapa の能力情報で検証します。

**OpenRouter Responses の Tool Search**: Responses API を使用し、llmcapa が選択中モデルのサーバー側 `tool_search` と `regex` variant を肯定した場合、UAG は `{"type":"openrouter:tool_search"}` と `defer_loading: true` を付けたツール定義を送ります。`human_ask` / `calculator` / `fetch_url` / `search_web` / `python_exec` は即時利用可能にし、`tool_catalog` / `tool_load` / `unload_tool` は除外します。ツール実行は従来どおり UAG が行い、通常の権限チェックを通します。応答がステートレスなため、型付き入力項目と生の Responses 出力項目（推論・検索状態を含む）、対応する `function_call_output` を次のリクエストへ再送します。OpenRouter側機能はベータで、現時点では `regex` variant のみです。`UAGENT_OPENROUTER_TOOL_SEARCH` は `native`（既定、llmcapaで対応確認時）、`legacy`、`off` を指定でき、`UAGENT_GPT54_TOOL_SEARCH` とは独立しています。能力情報が不明、または履歴の生出力がない場合は既存フローにフォールバックします。

**OpenRouter Messages の Tool Search**: `UAGENT_OPENROUTER_API=messages` で Anthropic互換 Messages API 経路を選択します。Anthropic SDK の base URL は `https://openrouter.ai/api`（`UAGENT_OPENROUTER_MESSAGES_BASE_URL` で上書き可能）です。llmcapa が Messages のサーバー検索と `regex` を肯定した場合、UAG は `tool_search_tool_regex_20251119` と遅延関数定義を送り、Anthropic形式の応答ブロックをそのまま継続履歴に保持します。ツール実行は UAG の権限チェックを通します。この設定がなければ既存の Chat / Responses API 経路を維持します。

**DeepSeek Responses の client-side Tool Search**: llmcapa が `deepseek-flash` の Responses API 上で client 実行を肯定した場合、UAG は `{"type":"tool_search","execution":"client"}` を送信します。返された `tool_search_call` をローカルの `tool_catalog` 検索に渡し、対応する `tool_search_output` と一致した関数スキーマを履歴へ追加します。実関数の実行は通常の UAG 権限チェックを通します。履歴はステートレスに再送し、`previous_response_id` は使いません。Chat Completionsでは非対応で、llmcapaが非対応とする `deepseek-v4-pro` では有効になりません。`UAGENT_DEEPSEEK_TOOL_SEARCH` は `native`（既定、llmcapaが対応確認時）、`legacy`、`off` を指定でき、GPT-5.4/OpenRouterの設定とは独立しています。

**DeepSeek Messages の Tool Search**: `UAGENT_DEEPSEEK_API=messages` で Anthropic互換 Messages API を選択します。base URL は `https://api.deepseek.com/anthropic`（`UAGENT_DEEPSEEK_MESSAGES_BASE_URL` で上書き可能）です。llmcapa が対応を肯定する `deepseek-flash` では、`tool_catalog` によるローカル検索結果を `tool_reference` ブロックへ変換し、定義済みの遅延ツールを会話中に追加します。発見後の関数実行も UAG が通常の権限チェックを行います。`UAGENT_DEEPSEEK_TOOL_SEARCH=legacy` / `off` で遅延読み込みを無効にできます。`deepseek-v4-pro` は llmcapa が非対応とするため有効になりません。Chat Completions経路は変更しません。

**その他のプロバイダ (Bedrock 等)**: 通常の Chat Completions / Responses API パスを使用します。ツールは `tool_catalog` → `tool_load` で個別に発見・動的ロードできます。`UAGENT_GPT54_TOOL_SEARCH` の影響は受けません。

**発見の診断（オプトイン）**: `UAGENT_DEBUG_TOOL_DISCOVERY=1` を設定すると、ツールを送信するラウンドごとに JSON 1 行がログディレクトリの `tool_discovery.jsonl` に追記されます。各行には発見の判定（`mode`、`reason`）、プロバイダ/モデル、`tool_catalog` が送信ツールに含まれていたか（`catalog_sent`）が入るので、想定外に `tool_catalog` が呼ばれたラウンドを後から確認できます。デフォルトはオフで、オフ時は環境変数の確認だけです。

**プロンプトの誘導文のリコンサイル**: システムプロンプトはセッション開始時に一度だけ作られ、経路が環境変数由来の場合もあるため、tool_catalog の誘導文が後のラウンドの実際の発見モードと食い違うことがあります（例: セッション途中のモデル切替）。`_run_one_round` で意味変換の直前に、そのラウンドの経路でプロンプトを作り直し、古い variant を持つシステムエントリを差し替えます。差し替えが起きたときは `[System Prompt] Rebuilt for ...` と表示します。共有経路に置いているのは意図的で、デフォルトで有効なレジストリ経路は OpenAI 互換フォールバックの前に返るため、フォールバック内に置くとそのラウンドには届きません。また意味変換の前に置いているのも意図的で、翻訳が有効なとき変換はシステムエントリの文面を書き換えるため、変換後にリコンサイルすると送信用の文面を認識できなくなります。sub-agent は役割専用プロンプトを使い誘導文を持たないため、影響を受けません。

**`previous_response_id` 継続**:

- OpenAI/Azure Responses: 有効な `resp_*` のときツールループ間で `previous_response_id` を保持。
- **Grok / OpenRouter / DeepSeek client Tool Search**: `previous_response_id` は送らず、ローカル全履歴を再送します。OpenRouter の通常経路は `input` を文字列化し、OpenRouter native Tool Search と DeepSeek client Tool Search は型付き Responses 項目と検索状態を再生します。
- stale rid / `invalid_prompt` / `APIResponseValidationError`（文字列 `error.code` 等）時: rid クリア、`responses_state["_stale_rid_occurred"]` 設定、全履歴で 1 回リトライ。2 回目失敗で continuation クリア。
- Compat 除去: `apply_openrouter_responses_compat` と `_normalize_openrouter_send_kwargs` は常に `previous_response_id` を pop。

**auto-unload**: `previous_response_id` が設定されている場合（全プロバイダ）、または native GPT-5.4 tool_search / Gemini Interactions Tool Retrieval / OpenRouter Responses Tool Search / DeepSeek Responses client Tool Search が有効な場合はスキップされます。

詳細は `TOOL_FLOW.md` を参照してください。

### 3.7 Agent Skills のライフサイクル

- `:skills` は、選択したスキルを `[SKILL] ...` の専用 system メッセージとして挿入します。
- スキルメッセージはセッションログに保存され、再読込時に復元されます。
- `:skills status` で有効なスキルを確認でき、`:skills clear` で解除できます。
- スキル指示は base の `SYSTEM_PROMPT` とは分けて保持します。

______________________________________________________________________

## 4. 起動時挙動（workdir / banner / 長期記憶）

### 4.1 workdir の決定ルール

workdir は次の優先順位で決定されます。

1. CLI引数: `--workdir` / `-C`
1. 環境変数: `UAGENT_WORKDIR`
1. 自動: カレントディレクトリ

### 4.2 起動バナー

起動時INFO（workdir/provider/base_url/api_version/Responses等）は以下で生成されます。

- `runtime.runtime_init.build_startup_banner()`（`src/uagent/runtime/runtime_banner.py` が実装）

LLM API mode の表示は、Gemini Developer API / Vertex AI では選択中モデルと設定に応じて `Interactions API` または `GenerateContent API`、Claude では `Anthropic Messages API` を示します。OpenAI互換プロバイダーの `Responses` / `ChatCompletions` 表示も従来どおりです。

### 4.3 長期記憶/共有メモ

長期記憶（個人）と共有メモ（共有長期記憶）は、可能な場合 system message として履歴に挿入されます。

______________________________________________________________________

## 5. MCP server ツール補足

MCP 関連ツールには次があります。

- `mcp_servers_tool.py`
- `mcp_tools_list_tool.py`
- `handle_mcp_v2_tool.py`
- `mcp_servers_shared.py`

最近の smoke test では、template 作成と add/list/validate/set_default/remove の基本フローをカバーしています。

`mcp_servers_validate_tool.py` は、callback ベースの truncate が使えない場合でも、そのまま結果文字列を返せるよう安全化されています。

______________________________________________________________________

## 6. ソースコードナビゲーションツール（idx ファミリー）

`*2idx` ツールは、ソースファイルを全体読み込みせずに、番号付きインデックスまたは特定の定義セクションを取得するためのツールです。全ツール共通のインターフェースを持ちます。

```
<tool>(path="...", mode="index")     → 番号付き目次
<tool>(path="...", mode="section", section=N) → N 番目の定義のソースコード
```

| ツール | 対象ファイル | パーサー | 検出対象 |
|--------|-------------|----------|---------|
| `md2idx` | .md | 見出しパーサー | ATX/setext 見出し |
| `py2idx` | .py | `ast` | class, def, method, decorator |
| `ts2idx` | .ts/.js | 正規表現 | class, interface, type, enum, function, arrow, method, namespace |
| `jv2idx` | .java | 正規表現 | package, class, interface, enum, record, field, constructor, method, throws |
| `cs2idx` | .cs | 正規表現 | namespace, class, struct, record, interface, enum, property, constructor, method, delegate, event, operator |
| `dart2idx` | .dart | 正規表現 | library, mixin, extension on, typedef, class, factory, getter/setter, トップレベル関数 |
| `cpp2idx` | .c/.cpp/.h/.hpp | 正規表現 | namespace, class, struct, union, enum, template, function, constructor, destructor, method, field, typedef, using |
| `cobol2idx` | .cbl/.cob/.cpy | 正規表現 | division, section, paragraph, data（01-66, 77, 78）, program-id, fd, select, copy, declaratives |
| `cl2idx` | .cl/.clp/.clle | 正規表現 | pgm, endpgm, dcl, dclf, label, call, callprc, 制御コマンド, monmsg, include |
| `dds2idx` | .pf/.lf/.dspf/.prtf/.dds | 正規表現（固定列意識） | record, field, key, select/omit, join, file keywords, REF/REFFLD 追従, DSPF indicator/attr/const |
| `rpg2idx` | .rpg/.rpgle/.sqlrpgle | 正規表現（固定/free） | ctl-opt, dcl-f/s/c/ds/pi/pr/proc, begsr, /copy, F/D/P/C-spec, EXEC SQL, /IF |
| `rs2idx` | .rs | 正規表現 | mod, struct, enum, trait, impl, fn, const, type alias, macro_rules! |
| `go2idx` | .go | 正規表現 | package, type struct/interface, func（レシーバ付き含む）, const, var |
| `php2idx` | .php | 正規表現 | namespace, class, interface, trait, enum, function, method, const, property, define |
| `swift2idx` | .swift | 正規表現 | class, struct, enum, protocol, extension, func, init/deinit/subscript, var/let, case |
| `kt2idx` | .kt | 正規表現 | class, interface, object, enum class, data class, fun, val/var, init, companion, extension function |
| `ppt2idx` | .pptx | `python-pptx` | スライドタイトル、テキスト本文、スピーカーノート |
| `excel2idx` | .xlsx/.xlsm | `openpyxl` | シート名、行列数、ヘッダー、シート別セルデータ |
| `pdf2idx` | .pdf | `pdfplumber` | ページ一覧、先頭行・プレビュー、ページ別本文 |
| `json2idx` | .json | `json` | キーパス（JSONPath相当）、要素数、構造概要 |
| `csv2idx` | .csv/.tsv | `csv` | ヘッダープレビュー、行ブロック範囲 |
| `docx2idx` | .docx | `python-docx` | 見出し階層（目次）、段落セクション |
| `html2idx` | .html/.xml | `beautifulsoup4` | 見出し（h1-h6）、セクション構造、本文 |
| `sql2idx` | .sql | 正規表現 | CREATE TABLE/VIEW/PROCEDURE, DDL/DMLブロック |
| `log2idx` | .log/.txt | 正規表現 | タイムスタンプブロック、エラー・警告イベント |

全 idx ツールは外部依存ゼロ（Python 標準ライブラリのみ）。

#### IBM i \*2idx 残件（スコープ外 — 実装オープン作業なし）

`cl2idx` / `dds2idx` / `rpg2idx` の実装トラックは **完了**。以下は意図的な非目標（詳細は `SPEC_CL2IDX_DDS2IDX.md` §5.9 / §10）:

| 領域 | 残件 | 備考 |
|------|------|------|
| 共通 | EBCDIC ソース | `read_index_source` 対応: utf-8-sig / utf-8 / cp932 / shift_jis / euc_jp のみ |
| 共通 | `ibmi2idx` 自動ディスパッチャ | **作らない**（拡張子→ツールは LLM + description） |
| `dds2idx` | マルチライブラリ / 完全オブジェクト解決 | 同一 workdir の REF 追従・深さ 1 のみ |
| `dds2idx` | DSPATR 全ビット組合せの意味論 | 索引ラベルは引数文字列を保持 |
| `dds2idx` | PRTF 座標レンダリング | 索引のみ（印刷レイアウトエンジンは持たない） |
| `dds2idx` | ICF / 特殊デバイス / バイナリソース | 対象外 |
| `rpg2idx` | 固定桁の全方言バリアント | 主要 F/D/P/C/H/I/O パスのみ |
| `rpg2idx` | 埋め込み SQL の詳細意味解析 | `EXEC SQL` の索引化まで |
| `rpg2idx` | `/IF` 式の評価実行 | 条件コンパイル行の検出・索引まで |

回帰: `tests/test_cl2idx_tool.py`, `tests/test_dds2idx_tool.py`, `tests/test_rpg2idx_tool.py`。

## コードオントロジーとプロジェクト構造

`code_map`で生成した、現在のプロジェクト全体のコードオントロジーです。

- [code_map_20260907_211403_767100.jsonld](code_map_20260907_211403_767100.jsonld)（JSON-LD形式、`project_only=true`、約5.4MB）

生成コマンド:

```text
code_map(path=".", format="ontology", project_only=true, include_symbols=true, include_relations=true)
```

Mermaid形式のプロジェクト構造図:

- [code_map_20260907_211419_276367.mmd](code_map_20260907_211419_276367.mmd)

## リアルタイム音声アーキテクチャ

- OpenAI Realtime、xAI Grok Voice API、および Google Gemini Multimodal Live API (`gemini-3.1-flash-live-preview`) をサポート。
- テキストCLI側の実行フローに影響を与えないよう、`src/uagent/realtime.py` 内に完全に分離して実装。

## 保守メモ（util_tools 分割・テスト）

- `util_tools.py` は facade とコマンドディスパッチを担当し、機能別実装は `util_common.py`、`util_image.py`、`util_mode.py`、`util_help.py`、`util_message.py`、`util_model.py`、`util_cmd_files.py`、`util_cmd_auto.py`、`util_cmd_session.py` に分割されています。
- Claude 4.6+ は Anthropic API仕様に従い `thinking.type=adaptive` と `output_config.effort` を使用します。effort 対応モデルの判定は可能な限り `llmcapa` の能力情報を利用します。
- テストは英語・日本語の両方で実行します。
  - `UAGENT_LANG=en python -m pytest -q`
  - `UAGENT_LANG=ja python -m pytest -q`
- Matter テストを含め、テスト収集のため `tests/__init__.py` を配置しています。

## 追加整理（英語版との内容同期）

英語版に追加されている運用情報を、日本語版にも反映する。

### 3.6.1 ツール無効化モード（`UAGENT_USE_TOOL` / `:tools on/off`）

- `UAGENT_USE_TOOL=0`（`false` / `no` / `off`）でLLMへのツール送信を無効化できる。
- CLI引数 `--use-tool` / `--no-use-tool` は環境変数より優先される。
- CLIでは `:tools on` / `:tools off` で次のLLMラウンドから切り替えられる。
- Webでは `/api/tools-enabled` のGET/POSTで状態を確認・変更できる。実行中の変更は拒否される。
- 実行時フラグは `core.tools_enabled` で、各ラウンドの `run_llm_rounds()` が参照する。

### 3.8 Batch state

`batch_state_tool.py` は複数ファイル作業の状態と経過をSQLite（`~/.uag/batches/task_history.sqlite3`）に保存する。`UAGENT_BATCHES_DIR` で保存先を変更できる。`conversation_id` と `instructions` も保存され、`init`、`load`、`status`、`current`、`complete_file`、`skip_file`、`error_file`、`reset`、`finalize`、`list` を提供する。WALとトランザクションを使用し、`task_events` に更新履歴を記録する。JSON状態ファイルは使用しない。

### 3.9 OSスケジューラ付きタイマー

`set_timer` に `os_persist=true` を指定すると、uagが停止中でもOSスケジューラから起動できる。Windowsは`schtasks`、Linuxは`systemd-run`（フォールバック`at`）、macOSは`at`を使用する。満了時は `python -m uagent --inject-message ... --workdir ...` で非対話処理を起動する。

### 3.10 APMスキル連携

Microsoft APMが作成した `apm_modules/*/.apm/skills/*/SKILL.md` を `:skills apm list/use/dir/help` から検出・有効化できる。APMのインストール自体はユーザーが行い、uagは生成済みファイルを読み込むだけである。

### 6.1 実行時のプロセス終了方針

復旧可能な実行時エラーでプロセス全体を終了させない。ランタイムヘルパは例外を送出し、CLI/GUI/Web/A2Aがエラーとして処理する。起動時の明示的なfail-fastを除き、裸の`sys.exit`を追加しない。ツールホストはツール内の`Exception`と`SystemExit`をエラー文字列へ変換するが、`KeyboardInterrupt`は握りつぶさない。
