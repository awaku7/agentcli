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
- **LLM Orchestration**: `src/uagent/uagent_llm.py`
  - 対話ラウンド実行、tool call の実行、429等のリトライ制御
  - ラウンド / メッセージ / tool call のヘルパは以下に分割済み
    - `src/uagent/llm_helpers.py`
    - `src/uagent/llm_message_helpers.py`
    - `src/uagent/llm_round_helpers.py`
    - `src/uagent/llm_flow_helpers.py`
  - リトライ / backoff ヘルパは `src/uagent/llm_errors.py`
- **Providers**: `src/uagent/providers/util_providers.py`
  - 環境変数に基づきクライアント生成（Azure/OpenAI/Bedrock/OpenRouter/Ollama/Gemini/Vertex AI/Grok/Claude/NVIDIA/DeepSeek/Z.AI/Alibaba/Moonshot/MiMo/LM Studio/MiniMax/Sakana/Sakura/Novita/Together/Vercel 等）
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

______________________________________________________________________

## 3. Tools システム（仕組みの概要）

### 3.1 ツールの発見と登録

ツールは `src/uagent/tools/` 配下のプラグインモジュールです。

登録条件:

- `TOOL_SPEC: dict` を持つ（OpenAI function schema 互換のメタデータ）
- `run_tool(args: dict) -> str` を持つ（実行関数）

ロード処理:

- `src/uagent/tools/__init__.py` が import 時に `_load_plugins()` を実行
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

通常はツール実行前に stdout に 1行のトレースを出します。

- 例: `[TOOL] 2025-... name=<tool> args=<masked-json>`
- 秘匿っぽい key はマスクされます

ツール側で `x_scheck.emit_tool_trace=false` を指定すると抑制できます。
`human_ask` は、ユーザー入力の生値がログに出ないよう抑制しています。

### 3.6 ツールレベルとツールジャンル

- **ツールレベル (`tool_level`)**: `TOOL_SPEC` に指定してロードを制御します。`-1` は無効、`0` は有効、`1` は条件付きロード（デフォルト無効）です。
- **ツールジャンル (`tool_genre`)**: ツールを `"basic"`, `"comm"` (通信系), `"office"` (Office系), `"devel"` (開発系), `"iot"`, `"exec"` (実行系), `"external"`, `"media"`, `"file"` に分類します。`TOOL_SPEC` のトップレベルに指定する必要があります。
- **起動時選択**: インタラクティブ起動時、ユーザーは有効化するツールジャンルのマスク値（1=basic, 2=comm, 4=office, 8=devel, 16=iot, 32=exec, 64=external, 128=media, 256=file, 511=all）を選択できます。

### 3.6.2 GPT-5.4+ / Responses API のツール送信フロー

`UAGENT_RESPONSES=1` かつ OpenAI/Azure + GPT-5.4+ の場合、ツール送信方法が変わります:

**デフォルト (native mode)**: 全ツールをサーバに送信し、サーバ側 `tool_search` が絞り込みます。管理ツール(`tool_catalog`/`tool_load`/`unload_tool`)も含まれます。サーバ側 compaction が自動適用されます（閾値はローカルの auto-shrink と同じ）。

**`UAGENT_GPT54_TOOL_SEARCH=legacy`**: クライアント側で `_select_tool_specs_legacy()` がツールを絞り込みます。初期は `tool_catalog`/`tool_load`/`unload_tool`/`human_ask` のみ送信され、LLM が `tool_catalog` で発見 → `tool_load` で動的ロードします。

**`UAGENT_GPT54_TOOL_SEARCH=native`**（明示指定）: デフォルトと同じですが、管理ツールが除外されます。`_should_preload_lazy_specs()` が True になり、genre フィルタをバイパスして全ツールが強制登録されます。

**その他のプロバイダ (DeepSeek, Bedrock, OpenRouter 等)**: 通常の Chat Completions / Responses API パスを使用します。ツールは起動時の genre mask でフィルタされ、`tool_catalog` → `tool_load` で動的ロードできます。`UAGENT_GPT54_TOOL_SEARCH` の影響は受けません。

**`previous_response_id` 継続**:

- OpenAI/Azure Responses: 有効な `resp_*` のときツールループ間で `previous_response_id` を保持。
- **Grok / OpenRouter**: `previous_response_id` は送らない（OpenRouter は schema 上 null 必須、Grok は tools 併用が不安定）。継続はローカル全履歴 + OpenRouter の文字列化 `input`。
- stale rid / `invalid_prompt` / `APIResponseValidationError`（文字列 `error.code` 等）時: rid クリア、`responses_state["_stale_rid_occurred"]` 設定、全履歴で 1 回リトライ。2 回目失敗で continuation クリア。
- Compat 除去: `apply_openrouter_responses_compat` と `_normalize_openrouter_send_kwargs` は常に `previous_response_id` を pop。

**auto-unload**: `previous_response_id` が設定されている場合（全プロバイダ）、または native GPT-5.4 tool_search が有効な場合はスキップされます。

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

## リアルタイム音声アーキテクチャ

- OpenAI Realtime、xAI Grok Voice API、および Google Gemini Multimodal Live API (`gemini-2.0-flash-exp`) をサポート。
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
