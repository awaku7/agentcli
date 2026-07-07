# 変更履歴

## [0.5.40] - 2026-07-07

### 追加
- `generate_zai`: プロンプトからZhipuAI (ZAI) 互換コードを生成する新ツール。
- `reverse_geocode`: Nominatimを使用した逆ジオコーディングツール（39言語i18n対応）。
- `code_map`: JSON-LDオントロジー出力、import/関係抽出、i18n対応を追加。
- GUI/Web/A2A/VSCode: `.env.sec` ファイルが存在しない場合、自動で作成/上書きされるよう変更。
- `translate_text`: サポート言語を拡張。

### 修正
- Responses のリトライ状態とツールユーティリティのエッジケースを修正。
- 前回のリファクタリングで失われた `browser_playwright_run` と `run_tool` エリアスを復元。
- i18n: `:tools reload` メッセージが全34ロケールで翻訳されるよう修正。

### 変更
- GPT-5.4+ のツールリスト表示を調整。
- ドキュメント: ツール数を171（87並列対応）に更新、全33言語READMEに reverse_geocode をIoTテーブルに追加。
- ドキュメント: JSON-LD オントロジーと Mermaid 依存関係グラフを DEVELOP.md に追加。
- 未使用の skills/servicenow-open/ ディレクトリを削除。

# 変更履歴

## [0.5.39] - 2026-07-06

### 修正
- ECHONET Lite: `echonet_control` の ON/OFF バイト値が逆転していたのを修正（正しくは ON=0x30, OFF=0x31）。
- ECHONET Lite: `echonet_property_get` にリトライ機構を追加。タイムアウト内で最大4回再送信し、ネットワーク混雑時の信頼性を改善。
- `responses_state_*.json`: デフォルト出力先を `~/.uag/` に変更。`UAGENT_RESPONSES_STATE_DIR` 環境変数による上書きをサポート。Windows互換性のため `os.path.expanduser()` への依存を除去。
- ドキュメント: docs/ 移行に伴う QUICKSTART、各国語 README、COMMUNICATION.md の相対リンクを修正。

### 変更
- `responses_state_*.json`: 出力先を `getcwd()` から `UAGENT_WORKDIR`（例: `~/.uag/`）に変更。

### 追加
- ENVIRONMENT.md: `RESPONSES_STATE_FILE` および `RESPONSES_STATE_DIR` 環境変数の説明を追加。

### その他
- `.gitignore` に `responses_state_*.json` を追加、不要な sakura 状態ファイルを削除。

## [0.5.38] - 2026-07-06

### 追加
- ECHONET Lite: 全55のEOJクラス名を34言語に対応。日本語ロケールは日本語名、他言語は `echonet_scan_tool.json` の翻訳を表示。
- ECHONET Lite: スキャン結果にメーカー名、デバイス種別表示、RAW EOJコードマッピングを追加。
- i18n: `_pip_auto.py` の pip インストールメッセージを34言語に翻訳。

### 変更
- ECHONET Lite: pyhems 由来の修正（TID処理、マルチキャスト参加、ポート3610バインド）+ キャッシュTTL + refresh パラメータ。
- ECHONET Lite: `_eoj_class_name()` が EOJ クラス名の翻訳に gettext ではなく `detect_lang()` を直接使用するよう変更。
- i18n: `tools/i18n_helper.detect_lang()` を `uagent.i18n.detect_lang()` と同じフォールバックチェーンに統一（getdefaultlocale + Windows コンソールコードページ検出）。

### パフォーマンス
- `modbus_scan`: ThreadPoolExecutor + TCP事前チェックによる並列化で高速化。

### ドキュメント
- IOT_USECASE.md: echonet_* ツールのEOJクラス名ローカライゼーションに関する説明を追加。

### 修正
- i18n: Windows環境で `locale.getlocale()` が `(None, None)` を返す場合でも、human_ask 他ツールの日本語翻訳が正しく表示されるよう修正。

### その他
- 不要な `_mfr_list.pdf` を削除。
- `.gitignore` に `.mypy_cache/` と `.ruff_cache/` を追加。
- lint: 未使用変数削除、インポート整理。

## [0.5.37] - 2026-07-04

### 追加
- ECHONET Lite: スキャンツールがロケールに応じたEOJクラス名を表示（日本語ロケール→日本語名、他→英語）。

### 修正
- ECHONET Lite: スキャンが `IPPROTO_UDP` でソケットを作成しポート3610で送信するよう修正。マルチキャスト参加をインターフェースごとに適切に実行。
- ECHONET Lite: リクエストパケットの TID を固定値からランダム16ビット値に変更し、重複除去フィルタを回避。

### 変更
- ECHONET Lite: キャッシュ TTL を 600 秒から 30 秒に短縮。`--refresh` フラグでキャッシュをバイパス可能に。
- ECHONET Lite: ノード詳細に `0x8A` プロパティマップから取得したメーカー名を表示。

## [0.5.36] - 2026-07-03

