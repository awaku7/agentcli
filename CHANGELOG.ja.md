# 変更履歴


## [0.5.27] - 2026-06-27

### 追加
- セットアップウィザードが既存の `.env` / `.env.sec` ファイルや環境変数（UAGENT_*）をデフォルト値として検出するよう改善。
- セットアップウィザードが LM Studio、MiniMax、HuggingFace プロバイダに対応。

### 修正
- 厳格な OpenAI 互換 API（HuggingFace）でツールスキーマ同期をスキップし、HTTP 400 エラーを回避。
- LLM に送信する前に `tool_genre` をツールスペックから除去し、トークン使用量を削減。
- セットアップウィザードで `.env.sec` 復号時にローカルの `.uagent.key` を優先して使用。
- ローカルの `.uagent.key` サポートを削除し、`.env.sec` 操作はデフォルトキーのみを使用。

### ドキュメント
- ENVIRONMENT.md と README に HuggingFace (hf) プロバイダのドキュメントを追加。
- 不足していたプロバイダセクション（Z.AI、MiniMax）を追加し、日本語テーブルの書式を修正。

### その他
- コードベース全体の ruff lint エラーを修正。
- 11ファイルに black フォーマットを適用。


## [0.5.26] - 2026-06-26

### 追加
- `set_timer` が OS レベルのスケジューリングをサポート（`--inject-message` と併用。Windows: schtasks、Linux: systemd-run/at、macOS: at）。
- 新規 `--enable-tool` CLI引数で個別のツール名を有効化可能に。os_persist タイマーでは `--tool-genre-mask` の代わりに使用。
- Z.AI プロバイダを DeepSeek パスから分離。公式 `zhipuai` SDK を優先し、OpenAI 互換クライアントをフォールバックとして使用。
- タイマーバッチファイルに作業ディレクトリを表示。
- schtasks デバッグ用に uag 出力をログファイルにリダイレクト。
- OSスケジュール起動時に現在のツールジャンルマスクを引き渡し。

### 修正
- `sys.argv` フォールバックが `--inject-message` 値をファイルパスとして誤取得する問題を修正。
- Windows スケジュールタスクのバッチファイルで `UAGENT_*` 環境変数を保持。
- Windows 自己削除バッチファイルに一時停止を追加。
- `_genre_control_util` 経由ではなく `TOOL_SPECS` を直接読み取るよう修正（リロード問題の回避）。

### 変更
- os_persist タイマーコマンドから `--tool-genre-mask` を削除し、`--enable-tool` のみを使用。

### 削除
- タイマーバッチファイルからの環境変数キャプチャを削除（平文での秘密情報漏洩防止）。

### その他
- `zhipuai>=2.1.5` 依存を追加。`llm_deepseek` の docstring から z.ai 参照を削除。

このプロジェクトの重要な変更箇所はすべてこのファイルに記録されます。

このフォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に基づいており、
このプロジェクトは [セマンティック バージョニング](https://semver.org/spec/v2.0.0.html) に準拠しています。

## [0.5.25] - 2026-06-26

### 変更
- デフォルト `UAGENT_SHRINK_RATIO` を 0.1 から 0.5 に戻し、圧縮頻度を低減。
- `llmcapa` 依存を 0.2.5 から 0.2.6 に更新。

### リファクタ
- `qrcode` をコア依存から削除。`generate_qr_code_tool` は実行時に遅延インポートに変更。
- YAML値（datetime.date等）のJSON安全変換を行う `_sanitize_for_json` ヘルパーを追加。
- `_read_text_file` と `parse_frontmatter_yaml` に `_sanitize_for_json` を適用。

このプロジェクトの重要な変更箇所はすべてこのファイルに記録されます。

このフォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に基づいており、
このプロジェクトは [セマンティック バージョニング](https://semver.org/spec/v2.0.0.html) に準拠しています。

## [0.5.24] - 2026-06-25

### 追加
- VSCode チャットパネルでツール呼び出し/結果をリアルタイム表示（WebSocket 経由 intermediate メッセージ）。
- エンコーディング修正：stderr/stdout に UTF-8 reconfigure を適用し、日本語出力の文字化けを防止。

### 変更
- デフォルト `UAGENT_SHRINK_RATIO` を 0.5 から 0.1 に変更。
- wsClient の呼び出しタイムアウトを 60秒 から 600秒 に延長。
- ws_handler を `make_client` 直接呼び出しに戻し、shrink の llmcapa フォールバックを追加。
- ruff fix（未使用インポート削除）と black フォーマットを適用。

### 修正
- `a2a/server.py` の相対インポートパスを修正。

### その他
- `patch_markdown.py` とそのバックアップファイル群を削除。
- `package.json` の compile スクリプトを更新。

## [0.5.23] - 2026-06-24
