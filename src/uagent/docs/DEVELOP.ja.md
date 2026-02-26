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
  - 標準入力ループ、`:cd`/`:ls` 等のコマンド、起動時処理（Mode A では `main()` 内で workdir 初期化）
- **LLM Logic**: `src/uagent/uagent_llm.py`
  - 対話ラウンド実行、tool call の実行、429等のリトライ制御
- **Providers**: `src/uagent/util_providers.py`
  - 環境変数に基づきクライアント生成（OpenAI/Azure/Gemini/Claude/Grok/OpenRouter/NVIDIA 等）
- **Utilities**: `src/uagent/util_tools.py`
  - tools callbacks 注入、初期メッセージ構築、コマンド処理、補助関数
- **Startup init**: `src/uagent/runtime_init.py`
  - workdir 決定/適用、起動バナー生成、長期記憶挿入等
- **Tools**: `src/uagent/tools/`
  - ツールプラグイン群（`TOOL_SPEC` + `run_tool`）

関連ドキュメント:

- ツール作成方法: `src/uagent/docs/DEVELOP_TOOL.md`

______________________________________________________________________

## 2. 全体アーキテクチャ（実行の流れ）

1. `uag` / `uagg` / `uagw` が起動。
1. 起動時初期化（主に `runtime_init.py`）
   - workdir の決定（CLI引数 `--workdir/-C`、環境変数 `UAGENT_WORKDIR`、または自動）
   - 必要ならディレクトリ作成し `chdir`
   - 起動バナー文字列を生成して表示
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

### 3.4 Tool trace（実行ログ）

通常はツール実行前に stdout に 1行のトレースを出します。

- 例: `[TOOL] 2025-... name=<tool> args=<masked-json>`
- 秘匿っぽい key はマスクされます

ツール側で `x_scheck.emit_tool_trace=false` を指定すると抑制できます。
`human_ask` は、ユーザー入力の生値がログに出ないよう抑制しています。

______________________________________________________________________

## 4. 起動時挙動（workdir / banner / 長期記憶）

### 4.1 workdir の決定ルール

workdir は次の優先順位で決定されます。

1. CLI引数: `--workdir` / `-C`
1. 環境変数: `UAGENT_WORKDIR`
1. 自動: カレントディレクトリ

### 4.2 起動バナー

起動時INFO（workdir/provider/base_url/api_version/Responses等）は以下で生成されます。

- `runtime_init.build_startup_banner()`

### 4.3 長期記憶/共有メモ

長期記憶（個人）と共有メモ（共有長期記憶）は、可能な場合 system message として履歴に挿入されます。

______________________________________________________________________
