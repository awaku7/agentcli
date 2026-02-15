# AGENTS.md

## プロジェクト概要

このプロジェクトは **uag** と呼ばれ、ローカル PC 上でコマンド実行、ファイル操作、スクリーンショット取得、PDF/PPTX/Excel の読み取りなどの操作を行うためのローカル AI エージェントです。

主な構成:

- CUI エントリポイント: `src/uagent/cli.py`（実行時は `uag` / `python -m uagent`）
- GUI エントリポイント: `src/uagent/gui.py`（実行時は `uagg` / `python -m uagent.gui`）
- Web エントリポイント: `src/uagent/web.py`（実行時は `uagw` / `python -m uagent.web`）
- コア実装: `src/uagent/core.py`
- LLM処理: `src/uagent/uagent_llm.py`, `src/uagent/llm_gemini.py`, `src/uagent/llm_claude.py`, `src/uagent/llm_openai_responses.py`
- ツール（プラグイン）群: `src/uagent/tools/`

動作環境は Windows/macOS/Linux を想定し、Python は **3.11+** です。

---

## セットアップ

### 1) Python 仮想環境（推奨）

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 2) パッケージのインストール

```bash
pip install -e .
```

依存の全体像は `pyproject.toml` を参照してください。Web UI を利用する場合は `pip install -e ".[web]"` を推奨します。

---

## 環境変数（.env）

推奨: `env.sample.bat` / `env.sample.ps1` / `env.sample.sh` を参考に `.env` を作成して設定してください。

主な環境変数:

- **プロバイダ設定**
  - `UAGENT_PROVIDER`: `azure` / `openai` / `openrouter` / `gemini` / `grok` / `claude` / `nvidia`
  - 各プロバイダ固有の API キー (`UAGENT_OPENAI_API_KEY`, `UAGENT_GEMINI_API_KEY`, `UAGENT_CLAUDE_API_KEY` 等)
  - モデル名（例: `UAGENT_DEPNAME`, `UAGENT_OPENAI_DEPNAME`, `UAGENT_GEMINI_VISION_MODEL` 等）

- **API モード設定**
  - `UAGENT_RESPONSES`: `1`/`true` で OpenAI/Azure の Responses API を使用。
    - 画像入力は原則 Responses 側のマルチモーダル（LLM本体）で扱うため、このモードでは `analyze_image` ツールはロードされません（実装: `src/uagent/tools/analyze_image_tool.py`）。

- **実行制御・リトライ**
  - `UAGENT_429_MAX_RETRIES`: Rate Limit エラー時の最大リトライ回数。
  - `UAGENT_429_BACKOFF_BASE`, `UAGENT_429_BACKOFF_CAP`: リトライ待機時間の調整。

- **Embedding / 検索系**
  - `UAGENT_EMBEDDING_API_URL`: `semantic_search_files` / `index_files` / `graph_rag_search` で使用する Embedding API の URL。
  - `UAGENT_SEMANTIC_SEARCH_DISABLE_IF_UNREACHABLE`: `1`/`true` の場合（既定=`1`）、起動時に Embedding API が到達不能だと `semantic_search_files` をロードしません。`0` を指定すると到達不能でもツールを表示したままにできます。
  - `UAGENT_EMBEDDING_API_HEALTHCHECK_PATH`: ヘルスチェックパス（既定 `/v1/models`）。

  よくある状況:
  - 「`semantic_search_files` / `index_files` がツール一覧に出てこない」
    - Embedding API が到達不能で、起動時にツール登録自体が抑止されている可能性があります。
    - 到達不能でも“ツールだけは見せたい”場合は `UAGENT_SEMANTIC_SEARCH_DISABLE_IF_UNREACHABLE=0` を設定してください（ただし実行時は失敗します）。

- **パス・ログ**
  - `UAGENT_WORKDIR`: 作業ディレクトリ。
  - `UAGENT_LOG_DIR`, `UAGENT_LOG_FILE`: ログ出力先。
  - `UAGENT_MEMORY_FILE`: 長期記憶ファイル。
  - `UAGENT_SHARED_MEMORY_FILE`: 共有長期記憶ファイル。

- **文字コード**
  - `UAGENT_CMD_ENCODING`: 外部コマンド出力のデコード設定（既定 `utf-8`）。

---

## 起動方法

### CUI（対話モード）

```bash
uag
# または
python -m uagent
```

### CUI（非対話モード）

```bash
uag --non-interactive <path-to-file>
```

### GUI

```bash
uagg
# または
python -m uagent.gui
```

### Web

```bash
uagw
# または
python -m uagent.web
```

---

## ドキュメント（`uag docs`）

wheel（whl）でインストールした環境でも、同梱ドキュメントを `uag docs` で参照できます。

```bash
uag docs
uag docs webinspect
uag docs develop
uag docs --path webinspect
uag docs --open webinspect
```

---

## 利用できるツール（現状）

ツールは `src/uagent/tools/` 配下のプラグインとして実装され、起動時に自動ロードされます。

### MCP（Model Context Protocol）を使う最短例

1) サーバ定義ファイルの雛形を作成（未作成の場合）

```bash
uag mcp_servers_init_template
```

2) サーバを追加（例: streamable-http）

```bash
uag mcp_servers_add
```

3) サーバ上の tools 一覧を取得

```bash
uag mcp_tools_list
```

4) 任意の MCP tool を実行（汎用ラッパ）

```bash
uag handle_mcp_v2
```

※上記は「まずツールの存在確認（mcp_tools_list）→ 実行（handle_mcp_v2）」の流れを意図しています。

代表的なツール:

- **最優先 (MCP)**: `handle_mcp_v2`, `mcp_tools_list`
- **MCP管理**: `mcp_servers_list`, `mcp_servers_add`, `mcp_servers_remove`, `mcp_servers_validate`, `mcp_servers_set_default`, `mcp_servers_init_template`
- **最終手段 (直接実行)**: `cmd_exec`, `pwsh_exec`, `cmd_exec_json`, `python_exec`
- **ファイル操作**: `read_file`, `create_file`, `delete_file`, `rename_path`, `replace_in_file`, `apply_patch`, `search_files`, `zip_ops`
- **情報取得・計算**: `file_exists`, `file_hash`, `find_large_files`, `get_geoip`, `get_current_time`, `get_os`, `get_env`, `list_windows_titles`, `search_web`, `fetch_url`, `playwright_inspector`, `calculator`, `date_calc`
- **データ/ドキュメント**: `read_pptx_pdf`, `excel_ops`, `exstruct`, `db_query`
- **画像**: `screenshot`, `analyze_image`(※UAGENT_RESPONSES 有効時は非ロード), `generate_image`
- **開発支援**: `git_ops`, `run_tests`, `lint_format`, `prompt_get`, `generate_prompt`, `system_reload`
- **付帯**: `human_ask`, `set_timer`, `add_long_memory`, `get_long_memory`, `add_shared_memory`, `get_shared_memory`, `spawn_process`, `change_workdir`, `index_files`, `semantic_search_files`, `graph_rag_search`

---

## 運用ポリシー

- `.env` はコミットしない（`.gitignore` で除外）。
- 変更が入ったら README / DEVELOP / AGENTS など該当ドキュメントも更新。
- コミット前に（可能なら） `lint_format` と `run_tests` を実行。
- ライセンスは Apache License 2.0 を適用。

---

## セキュリティ注意

- API キーなどの秘密情報は `.env` に保存し、Git 管理外にする。
- 長期記憶（個人/共有）へ **パスワードやトークン等の秘匿情報を保存しない**。
- コマンド実行系ツール（`cmd_exec` 等）は強力なため、意図しない破壊的操作に注意。
- ファイル操作は原則 `workdir` 配下に制限され、安全チェック（確認/ブロック）が入る。
- 画像データを LLM に送信する際は、機密情報が含まれていないか確認する（uag は送信前に `human_ask` で確認する場合がある）。