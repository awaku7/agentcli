# RUNTIME_INIT（起動時初期化の共通化）

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
- `python-dotenv` が利用可能な場合、起動初期化中にカレントディレクトリの `.env` と `.env.sec` を読み込む

設計方針:

- `runtime_init.py` は互換・再エクスポート層で、直接の表示処理は原則持ちません。ただし、起動ヘルパは復号失敗などの警告や `.env.sec` 同期メッセージを stderr に出し、対話CLIでは同期確認を表示する場合があります。起動 banner などの表示は UI 側が扱います。
- 起動初期化時の環境読込はベストエフォートです。`UAGENT_*` は dotenv 読込前に取得したプロセス環境の値を最優先し、その後 `.env.sec`、`.env`、アプリケーション既定値の順に解決します。その他の環境変数は `.env` を `override=False` で読み込み、`.env.sec` の値があれば上書きします。
- `.uagent.key` がカレントディレクトリにある場合は、`.env.sec` の復号にそれを使います。

______________________________________________________________________

## 1. 起動時の環境読込

起動初期化の環境検証前に、カレントディレクトリの環境ファイルを `reload_dotenv_custom()` で読み込みます。

`UAGENT_*` の優先順位:

1. dotenv 読込前から存在するプロセス環境変数（シェルで明示した値）
1. `.env.sec` の値
1. `.env` の値
1. アプリケーション既定値

起動前の `UAGENT_*` スナップショットを復元するため、`.env.sec` の値が明示的なプロセス環境変数を上書きすることはありません。`.env.sec` と `.env` の両方に同じキーがある場合は `.env.sec` が優先されます。

補足:

- `.env.sec` は `uag_envsec.secret_core.decrypt_text` で復号します。
- カレントディレクトリに `.uagent.key` があれば、そのキー ファイルを使います。
- `.env.sec` の同期確認は起動時の環境検証で行います。不一致時、対話CLIでは選択を尋ねます。`y` は現在の `UAGENT_*` 値で更新、`s` は `.env.sec` 値を当該セッションに適用、`N` は更新せず起動時スナップショットを維持します。
- 非対話起動など確認入力ができない場合は、現在の `UAGENT_*` スナップショットを `.env.sec` にマージして更新します。`.env.sec` がない場合は、非対話起動で作成します。
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
