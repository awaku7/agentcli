# AGENTS.md

## 役割

このファイルは、uagent を操作するエージェント向けの実行規約と参照先を定義する。人間向けの解説ではなく、作業時に必要な最小限の判断材料を優先して記載する。

## 参照優先順位

1. `src/uagent/runtime_init.py`（互換・再エクスポート層）
2. `src/uagent/runtime_workdir.py`
3. `src/uagent/runtime_banner.py`
4. `src/uagent/runtime_env.py`
5. `src/uagent/runtime_memory.py`
6. `src/uagent/cli.py`
7. `src/uagent/gui.py`
8. `src/uagent/web.py`
9. `src/uagent/core.py`
10. `src/uagent/tools/`
11. `README.md` / `docs/README.ja.md`
12. `src/uagent/docs/DEVELOP.md` / `src/uagent/docs/DEVELOP.ja.md`
13. `src/uagent/docs/RUNTIME_INIT.md` / `src/uagent/docs/RUNTIME_INIT.ja.md`

## 実行前に確認する項目

- 現在の作業ディレクトリを確認する。
- `.env` と環境変数の設定を確認する。
- `UAGENT_PROVIDER` と `UAGENT_RESPONSES` の値を確認する。
- 必要なツールがロードされているかを確認する。
- 画像、秘密情報、外部送信の有無を確認する。

## 起動時初期化

- 起動時処理は `src/uagent/runtime_init.py` に集約されている。
- workdir 解決、startup banner、長期記憶注入、共有メモリ注入、環境検証はこの層で扱う。
- 起動時の環境検証は `validate_or_exit_startup_env(context=...)` を参照する。
- `runtime_init.py` は import 時に CWD の `.env` を読み込む。
- `runtime_init.py` は `.env.sec` も CWD から読み込める。復号失敗時は `[WARN] Failed to decrypt .env.sec: ...` を stderr に出す。

## LLM / API ルール

- `UAGENT_RESPONSES=1` の場合、OpenAI / Azure / Bedrock / OpenRouter / Ollama の Responses API を優先する。
- `UAGENT_RESPONSES=1` の場合、`analyze_image` はロードされない。
- `UAGENT_RESPONSES=1` でも、provider が非対応なら起動バナーで警告し、ChatCompletions にフォールバックする。
- `UAGENT_RESPONSES=1` でも、Gemini / Claude / Vertex AI はネイティブ API 経路を使い、Responses API 対象外として扱う。
- 画像処理や外部送信の前に、機密情報の混入を確認する。
- provider 切り替え時はセッション継続の挙動を確認する。

## ツール選択ルール

- MCP を使える場合は、まず `mcp_tools_list` で存在を確認し、次に `handle_mcp_v2` を使う。
- 直接コマンド実行は最終手段とする。
- ファイル操作は `workdir` 配下を優先する。
- 破壊的操作は事前確認を要求する。
- `semantic_search_files` / `index_files` / `graph_rag_search` は、Embedding API の到達性に依存する。

## 環境変数

- `UAGENT_WORKDIR`: 作業ディレクトリ。
- `UAGENT_MEMORY_FILE`: 長期記憶ファイル。
- `UAGENT_SHARED_MEMORY_FILE`: 共有長期記憶ファイル。
- `UAGENT_EMBEDDING_PROVIDER`: Embedding provider（既定: `UAGENT_PROVIDER`）。
- `UAGENT_<PROVIDER>_EMBEDDING_BASE_URL` / `UAGENT_<PROVIDER>_EMBEDDING_API_KEY` / `UAGENT_<PROVIDER>_EMBEDDING_API_VERSION` / `UAGENT_<PROVIDER>_EMBEDDING_DEPNAME`。
- `UAGENT_SEMANTIC_SEARCH_DISABLE_IF_UNREACHABLE`: 到達不能時のツール抑止制御。
- `UAGENT_CMD_ENCODING`: 外部コマンド出力のデコード設定。
- `UAGENT_STREAMING`: 起動バナーの streaming 表示に反映される。

## ドキュメント更新ルール

- 実装と差異が出たら、README と関連 docs を更新する。
- 変更後は必要に応じてテストと lint を実行する。

## 禁止事項

- 秘密情報を長期記憶へ保存しない。
- 不要な削除や上書きを行わない。
- 根拠なく推測して操作しない。
