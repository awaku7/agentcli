# 環境変数

このドキュメントでは、`uag` で使用される環境変数について説明します。

## 必須プロバイダ設定

サポートされているプロバイダと、それに対応する環境変数（例：`UAGENT_OPENAI_API_KEY`, `UAGENT_AZURE_BASE_URL`）の完全なリストについては、メインの README を参照してください。

## 共通設定

- `UAGENT_WORKDIR`: 作業ディレクトリ。
- `UAGENT_MEMORY_FILE`: 長期記憶ファイルのパス。
- `UAGENT_SHARED_MEMORY_FILE`: 共有長期記憶ファイルのパス。
- `UAGENT_EMBEDDING_API_URL`: Embedding API の URL。
- `UAGENT_CMD_ENCODING`: 外部コマンド出力のエンコーディング。
- `UAGENT_LANG`: ホスト UI の言語（例：`en`, `ja`）。

## 高度な機能

- `UAGENT_RESPONSES`: `1` に設定すると Responses API を有効にします。
- `UAGENT_SHRINK_CNT`: 自動圧縮（オートシュリンク）のしきい値（既定: `100`）。
- `UAGENT_SHRINK_KEEP_LAST`: 自動圧縮後に残すメッセージ数（既定: `20`）。
- `UAGENT_REASONING`: 推論の試行レベル（`auto`, `low`, `medium`, `high` など）。
- `UAGENT_VERBOSITY`: 出力の冗長性（`low`, `medium`, `high`）。

## セキュリティと暗号化

`uag` は機密性の高い環境変数の暗号化をサポートしています。

- ツール: `uag_envsec`
- パスワードとローカル鍵を使用して `.env` を `.env.sec` に暗号化します。
- 既定の鍵ファイル: カレントディレクトリの `.uagent.key`。

使用例:
```bash
uag_envsec .env
```
