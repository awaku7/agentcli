# RUNTIME_INIT (shared startup initialization)

This document describes the purpose and behavior of `src/uagent/runtime_init.py`.

What it does (shared across CLI/Web/GUI):
- Decide and validate `workdir` (`--workdir/-C`, `UAGENT_WORKDIR`, or auto)
- Create the directory and `chdir`
- Build startup banner text (INFO lines)
- Append personal long-term memory and shared memory as system messages

Design policy:
- `runtime_init.py` should not print directly; it returns strings/flags and the UI decides how to display them.

---

# RUNTIME_INIT（起動時初期化の共通化）

このドキュメントは `src/uagent/runtime_init.py` の目的と仕様をまとめます。  
（Mode A: 互換優先。UIごとの差分を最小化しつつ重複を排除する）

---

## 1. 目的

`runtime_init.py` は、CLI/Web/GUI に散在していた「起動時初期化」を共通化するためのヘルパ群です。

- workdir の決定・安全チェック
- workdir の作成と `chdir`
- 起動時INFO（banner）文字列の生成
- 長期記憶/共有メモを system message として履歴に挿入（共通関数）

設計方針:

- `runtime_init.py` 自体は **原則 print しない**（文字列を返し、UIが表示経路を決める）
- UIの互換性を壊さないため、既存の表示文言を保ちつつ共通化する

---

## 2. workdir の決定（decide_workdir）

### 2.1 優先順位

workdir は次の優先順位で決定します。

1. CLI引数: `--workdir` / `-C`
2. 環境変数: `UAGENT_WORKDIR`
3. 自動: カレントディレクトリ（`./` の絶対パス）

### 2.2 安全チェック

- 指定された workdir が「既存ファイル」だった場合はエラー（ディレクトリでなければならない）

### 2.3 API

- `decide_workdir(cli_workdir: Optional[str], env_workdir: Optional[str]) -> WorkdirDecision`

`WorkdirDecision` は次を持ちます。

- `chosen`: 元の指定（CLI/ENV/auto）
- `chosen_source`: `"CLI"` / `"ENV(UAGENT_WORKDIR)"` / `"auto"`
- `chosen_expanded`: expanduser 済みの実パス

---

## 3. workdir の適用（apply_workdir）

- `os.makedirs(..., exist_ok=True)` を行い、ディレクトリを作成します
- `os.chdir(...)` によりカレントディレクトリを移動します

API:
- `apply_workdir(decision: WorkdirDecision) -> None`

---

## 4. 起動時INFO（banner）

`build_startup_banner()` は「起動時に表示していたINFO」を統一的に文字列生成します。

### 4.1 出力内容（代表）

- `[INFO] workdir = ... (source: ...)`
- `[INFO] provider = ...`
- provider別:
  - azure: base_url + api_version
  - openai/openrouter/grok/nvidia: base_url
- Responses API が有効な場合:
  - `[INFO] LLM API mode = Responses (UAGENT_RESPONSES is enabled)`

API:
- `build_startup_banner(core, workdir: str, workdir_source: str) -> str`

注意:
- 機密情報（APIキー等）は出力しません
- base_url は `core.normalize_url()` が存在する場合はそれを使い、なければ簡易正規化します

---

## 5. 長期記憶/共有メモの挿入（append_long_memory_system_messages）

### 5.1 目的

CLI/GUI/Web で重複していた「長期記憶/共有メモの読み込み→system message 挿入」を共通化します。

- 個人長期記憶: `tools.long_memory`
- 共有メモ: `tools.shared_memory`（有効時のみ）

### 5.2 挿入仕様

- 個人長期記憶は `build_long_memory_system_message_fn(raw)` が返した system message を `messages` に append
- 共有メモが有効で system message が生成できた場合:
  - content の先頭に `【共有長期記憶（共有メモ）】\n` を付与して append

### 5.3 API

- `append_long_memory_system_messages(...) -> Dict[str,bool]`

戻り値 flags:

- `personal_appended`: 個人長期記憶が messages に追加された
- `shared_enabled`: 共有メモが有効（is_enabled()がTrue）
- `shared_appended`: 共有メモが messages に追加された

注意:
- この関数は print しません（UI側が従来のINFO/WARNを出す）
- 例外は原則 caller 側で捕捉し、従来通り `[WARN]` を出す想定

---

## 6. UIごとの適用位置（参考）

- CLI: `cli.py` の `main()` の startup-capture 内で workdir適用・banner出力
- Web: `web.py` の `main()` で workdir適用・banner出力、`run_agent_worker` で history 初期化時に長期記憶挿入
- GUI: `gui.py` の `main()` で workdir適用・banner出力、worker 初期化時に長期記憶挿入

（表示経路はUIごとに異なるが、banner生成元・挿入ロジックは統一される）
