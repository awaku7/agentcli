# Embedding provider 化の実装方針

## 目的
Embedding も音声/画像と同じく provider 選択型にする。

## 採用する命名
- `UAGENT_EMBEDDING_PROVIDER`
- `UAGENT_<PROVIDER>_EMBEDDING_BASE_URL`
- `UAGENT_<PROVIDER>_EMBEDDING_API_KEY`
- `UAGENT_<PROVIDER>_EMBEDDING_API_VERSION`
- `UAGENT_<PROVIDER>_EMBEDDING_DEPNAME`

## 例
- `UAGENT_EMBEDDING_PROVIDER=openai`
- `UAGENT_OPENAI_EMBEDDING_BASE_URL=https://api.openai.com/v1`
- `UAGENT_OPENAI_EMBEDDING_API_KEY=...`
- `UAGENT_OPENAI_EMBEDDING_API_VERSION=...`
- `UAGENT_OPENAI_EMBEDDING_DEPNAME=text-embedding-3-small`

Azure も同様に、`UAGENT_AZURE_EMBEDDING_*` を使う。

## 変更対象
1. `src/uagent/tools/semantic_search_files_tool.py`
   - `UAGENT_EMBEDDING_PROVIDER` を読む
   - `UAGENT_<PROVIDER>_EMBEDDING_*` から接続先を解決する

2. `src/uagent/setup_cli.py`
   - Embedding の provider 選択UIを追加
   - 必要な環境変数入力を追加

3. `src/uagent/env_validate.py`
   - 必須環境変数チェックを追加

4. `ENVIRONMENT.md` / `ENVIRONMENT.ja.md`
   - 新しい命名を記載

5. `src/uagent/docs/...`
   - 起動時や設定説明を更新

6. `AGENTS.md`
   - 開発メモを更新

## 実装順
1. `semantic_search_files_tool.py`
2. `setup_cli.py`
3. `env_validate.py`
4. ドキュメント類

## 補足
- 旧 `UAGENT_EMBEDDING_API_URL` 方式は使わない。
- 画像の `IMG_ANALYSIS` / `IMG_GENERATE` と同じ考え方に揃える。
