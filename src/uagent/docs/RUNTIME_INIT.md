# RUNTIME_INIT (shared startup initialization)

This document describes the shared startup-initialization helpers exposed from `src/uagent/runtime/runtime_init.py`.

`runtime/runtime_init.py` is a compatibility/re-export layer. The concrete implementations live in:

- `src/uagent/runtime/runtime_workdir.py`
- `src/uagent/runtime/runtime_banner.py`
- `src/uagent/runtime/runtime_env.py`
- `src/uagent/runtime/runtime_memory.py`

What it covers (shared across CLI/Web/GUI):

- decide and validate `workdir` (`--workdir/-C`, `UAGENT_WORKDIR`, or auto)
- validate startup environment when needed (`validate_or_exit_startup_env(context=...)`)
- create the directory and `chdir`
- build startup banner text
- append personal long-term memory and shared memory as system messages
- load `.env` and `.env.sec` from the current working directory at import time when `python-dotenv` is available

Design policy:

- `runtime_init.py` does not print by itself; helpers return values and UI code decides how to display them.
- Import-time environment loading is best-effort. `.env` is loaded first with `override=False`, then `.env.sec` is decrypted and loaded with `override=True`.
- If `.uagent.key` exists in the current working directory, it is used to decrypt `.env.sec`.
- If the `.env.sec` sync prompt appears later and the user declines (`n` / `N`), the startup `UAGENT_*` snapshot is restored for the session and `.env.sec` is not updated.

______________________________________________________________________

## 1. Import-time environment loading

`runtime_init.py` loads environment files from the current working directory as soon as it is imported.

Load order:

1. `.env` if it exists (`override=False`)
1. `.env.sec` if it exists (decrypt and then `override=True`)

Notes:

- `.env.sec` is decrypted via `uag_envsec.secret_core.decrypt_text`.
- If `.uagent.key` exists in the current working directory, it is used as the key file.
- If decryption fails, a warning is printed to stderr:
  - `[WARN] Failed to decrypt .env.sec: ...`

______________________________________________________________________

## 2. Workdir decisions

### 2.1 Priority

`decide_workdir()` resolves the working directory in this order:

1. CLI argument: `--workdir` / `-C`
1. Environment variable: `UAGENT_WORKDIR`
1. Auto: the current directory (`./` as an absolute path)

### 2.2 Safety check

- If the resolved path already exists and is a file, `decide_workdir()` raises `NotADirectoryError`.

### 2.3 API

- `decide_workdir(cli_workdir: Optional[str], env_workdir: Optional[str]) -> WorkdirDecision`

`WorkdirDecision` contains:

- `chosen`: the original selection (CLI / ENV / auto)
- `chosen_source`: `"CLI"` / `"ENV(UAGENT_WORKDIR)"` / `"auto"`
- `chosen_expanded`: the `expanduser()`-resolved path

### 2.4 Apply workdir

`apply_workdir()` creates the directory and changes the current process directory.

- `os.makedirs(..., exist_ok=True)`
- `os.chdir(...)`

API:

- `apply_workdir(decision: WorkdirDecision) -> None`

______________________________________________________________________

## 3. Startup banner

`build_startup_banner()` generates the INFO/WARN lines shown during startup.

Representative output:

- `[INFO] workdir = ... (source: ...)`
- `[INFO] provider = ...`
- provider-specific lines:
  - `azure`: `base_url` + `api_version`
  - `openai` / `openrouter` / `grok` / `nvidia` / `bedrock` / `ollama` / `deepseek` / `zai` / `alibaba` / `moonshot`: `base_url`
  - `vertexai`: `project` + `location`
- If `UAGENT_RESPONSES=1` is set and the selected provider is not one of `azure`, `openai`, `bedrock`, `openrouter`, `ollama`, `alibaba`, or `lmstudio` (excluding `gemini`, `claude`, and `vertexai`), a warning is appended:
  - `[WARN] UAGENT_RESPONSES=1 is set, but provider '...' does not support Responses API. Falling back to ChatCompletions.`
- `[INFO] LLM streaming = enabled` or `disabled`

API:

- `build_startup_banner(core, workdir: str, workdir_source: str) -> str`

Notes:

- Secrets such as API keys are never printed.
- `core.normalize_url()` is used when available; otherwise URLs are trimmed conservatively.
- `build_startup_banner()` does **not** print the Responses/ChatCompletions mode line itself. CLI/Web/GUI may print that separately after the banner.

______________________________________________________________________

## 4. Long-term memory system messages

`append_long_memory_system_messages()` consolidates the personal/shared long-term memory loading path.

- Personal long-term memory is loaded via `tools.long_memory`
- Shared memory is loaded via `tools.shared_memory` only when enabled
- Any generated system message is appended to `messages`
- Added messages are also passed to `core.log_message()`

API:

- `append_long_memory_system_messages(...) -> Dict[str, bool]`

Returned flags:

- `shared_enabled`: whether shared memory is enabled (`shared_memory_mod.is_enabled()`)

Notes:

- The function does not print.
- The function swallows internal exceptions and leaves warning handling to the caller.
- The current implementation does **not** prefix shared-memory content with a special label.
- The current implementation does **not** return `personal_appended` / `shared_appended` flags.

______________________________________________________________________

## 5. UI integration points

- CLI: `cli.py` uses these helpers inside startup capture before the main session loop.
- Web: `web.py` uses the same helpers during startup and history initialization.
- GUI: `gui.py` uses the same helpers during startup and worker initialization.

______________________________________________________________________

## 6. Exported names

`runtime_init.py` re-exports the common helpers used by the UIs:

- `WorkdirDecision`
- `apply_workdir`
- `decide_workdir`
- `build_startup_banner`
- `validate_or_exit_startup_env`
- `append_long_memory_system_messages`

## Detailed implementation record (Japanese)

The former `RUNTIME_INIT.ja.md` content is retained below. The English sections above remain the primary reference for the shared startup initialization API.

このドキュメントは `src/uagent/runtime/runtime_init.py` から提供される起動時初期化ヘルパの目的と仕様をまとめます。

`runtime/runtime_init.py` は互換・再エクスポート層で、実装本体は次のモジュールに分割されています。

- `src/uagent/runtime/runtime_workdir.py`
- `src/uagent/runtime/runtime_banner.py`
- `src/uagent/runtime/runtime_env.py`
- `src/uagent/runtime/runtime_memory.py`

CLI / Web / GUI で共通して行うこと:

- workdir の決定・検証 (`--workdir/-C`、`UAGENT_WORKDIR`、または自動)
- 必要時の起動時環境検証 (`validate_or_exit_startup_env(context=...)`)
- ディレクトリ作成と `chdir`
- 起動時 banner の生成
- 個人長期記憶 / 共有メモを system message として履歴へ追加
- `python-dotenv` が利用可能な場合、import 時にカレントディレクトリの `.env` と `.env.sec` を読み込む

設計方針:

- `runtime_init.py` 自体は原則として print しません。ヘルパは値を返し、UI 側が表示方法を決めます。
- import 時の環境読込はベストエフォートです。`.env` を先に `override=False` で読み込み、その後 `.env.sec` を復号して `override=True` で読み込みます。
- `.uagent.key` がカレントディレクトリにある場合は、`.env.sec` の復号にそれを使います。

______________________________________________________________________

## 1. import 時の環境読込

`runtime_init.py` は import された時点で、カレントディレクトリの環境ファイルを読み込みます。

読み込み順:

1. `.env` があれば読み込む（`override=False`）
1. `.env.sec` があれば復号して読み込む（`override=True`）

補足:

- `.env.sec` は `uag_envsec.secret_core.decrypt_text` で復号します。
- カレントディレクトリに `.uagent.key` があれば、そのキー ファイルを使います。
- 後続の `.env.sec` 同期確認で `n` / `N` を押した場合は、そのセッションでは起動時の `UAGENT_*` スナップショットを復元し、`.env.sec` は更新しません。
- 復号に失敗した場合は stderr に次の警告を出します。
  - `[WARN] Failed to decrypt .env.sec: ...`

______________________________________________________________________

## 2. workdir の決定

### 2.1 優先順位

`decide_workdir()` は次の順で workdir を決定します。

1. CLI 引数: `--workdir` / `-C`
1. 環境変数: `UAGENT_WORKDIR`
1. 自動: カレントディレクトリ（`./` の絶対パス）

### 2.2 安全チェック

- 解決したパスが既存のファイルだった場合、`decide_workdir()` は `NotADirectoryError` を送出します。

### 2.3 API

- `decide_workdir(cli_workdir: Optional[str], env_workdir: Optional[str]) -> WorkdirDecision`

`WorkdirDecision` が持つ項目:

- `chosen`: 元の選択値（CLI / ENV / auto）
- `chosen_source`: `"CLI"` / `"ENV(UAGENT_WORKDIR)"` / `"auto"`
- `chosen_expanded`: `expanduser()` 済みの実パス

### 2.4 workdir の適用

`apply_workdir()` はディレクトリを作成し、現在のプロセスの作業ディレクトリを移動します。

- `os.makedirs(..., exist_ok=True)`
- `os.chdir(...)`

API:

- `apply_workdir(decision: WorkdirDecision) -> None`

______________________________________________________________________

## 3. 起動時 banner

`build_startup_banner()` は起動時に表示する INFO / WARN 行を生成します。

代表的な出力:

- `[INFO] workdir = ... (source: ...)`
- `[INFO] provider = ...`
- provider 別の情報:
  - azure: `base_url` + `api_version`
  - openai / openrouter / grok / nvidia / bedrock / ollama / deepseek / zai / alibaba / moonshot: `base_url`
  - vertexai: `project` + `location`
- `UAGENT_RESPONSES=1` が有効で、Responses API 対応プロバイダ（`openai` / `azure` / `bedrock` / `openrouter` / `ollama` / `alibaba` / `lmstudio`）以外のプロバイダ（`gemini` / `claude` / `vertexai` を除く）だった場合は warning を出します。
  - `[WARN] UAGENT_RESPONSES=1 is set, but provider '...' does not support Responses API. Falling back to ChatCompletions.`
- `[INFO] LLM streaming = enabled` または `disabled`

API:

- `build_startup_banner(core, workdir: str, workdir_source: str) -> str`

注意:

- API キーなどの機密情報は出力しません。
- `core.normalize_url()` が使える場合はそれを使い、使えない場合は保守的に URL を整形します。
- `build_startup_banner()` 自体は Responses / ChatCompletions のモード行を出しません。CLI / Web / GUI 側が必要に応じて別途表示します。

______________________________________________________________________

## 4. 長期記憶の system message 追加

`append_long_memory_system_messages()` は、個人 / 共有の長期記憶を読み込んで system message を追加する処理を共通化します。

- 個人長期記憶は `tools.long_memory` から読み込みます。
- 共有メモは `tools.shared_memory` が有効な場合のみ読み込みます。
- 生成された system message があれば `messages` に append します。
- 追加したメッセージは `core.log_message()` にも渡します。

API:

- `append_long_memory_system_messages(...) -> Dict[str, bool]`

返却フラグ:

- `shared_enabled`: 共有メモが有効かどうか（`shared_memory_mod.is_enabled()` の結果）

注意:

- この関数は print しません。
- 内部例外は握りつぶし、警告は呼び出し側が出す前提です。
- 現行実装では共有メモに特別な prefix は付けません。
- 現行実装では `personal_appended` / `shared_appended` フラグは返しません。

______________________________________________________________________

## 5. UI での利用箇所

- CLI: `cli.py` の startup capture 内で workdir 適用 / banner 出力 / 長期記憶追加を行います。
- Web: `web.py` の startup と history 初期化で同じヘルパを使います。
- GUI: `gui.py` の startup と worker 初期化で同じヘルパを使います。

______________________________________________________________________

## 6. 公開される名前

`runtime_init.py` は UI から使う共通ヘルパを再公開します。

- `WorkdirDecision`
- `apply_workdir`
- `decide_workdir`
- `build_startup_banner`
- `validate_or_exit_startup_env`
- `append_long_memory_system_messages`
