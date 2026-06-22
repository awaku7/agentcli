# DEVELOP（開発者向け）

このドキュメントは **uag（ローカル ツール実行エージェント）** の開発者向けメモです。

- エントリポイント:
  - **CUI**: `python -m uagent`（コマンド: `uag`）
  - **GUI**: `python -m uagent.gui`（コマンド: `uagg`）
  - **Web**: `python -m uagent.web`（コマンド: `uagw`）

______________________________________________________________________

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
  - 環境変数に基づきクライアント生成（Azure/OpenAI/Bedrock/OpenRouter/Ollama/Gemini/Vertex AI/Grok/Claude/NVIDIA/DeepSeek/Z.AI/Alibaba/Moonshot/MiMo/LM Studio/MiniMax 等）
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
| `rs2idx` | .rs | 正規表現 | mod, struct, enum, trait, impl, fn, const, type alias, macro_rules! |
| `go2idx` | .go | 正規表現 | package, type struct/interface, func（レシーバ付き含む）, const, var |
| `swift2idx` | .swift | 正規表現 | class, struct, enum, protocol, extension, func, init/deinit/subscript, var/let, case |
| `kt2idx` | .kt | 正規表現 | class, interface, object, enum class, data class, fun, val/var, init, companion, extension function |

全 idx ツールは外部依存ゼロ（Python 標準ライブラリのみ）。
