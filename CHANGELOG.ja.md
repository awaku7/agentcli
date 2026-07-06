# 変更履歴

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
- 外部コンテンツポリシー：bluesky、discord_channel_chat、gmail_read ツールへのプロンプトインジェクション防御を追加。全34言語のツール説明文に外部コンテンツ警告を表示。
- wttrin_tool：Open-Meteo フォールバック対応 + 全34言語の完全 i18n（WMO weather codes、geocoding error、fallback source）。

### 変更
- i18n：geoip/gps ツール説明に「現在地」検索語を全34言語に追加。
- 外部コンテンツポリシー警告を Google 翻訳で全34言語ファイルに翻訳。破損した ja PO エントリを修復。

### ドキュメント
- bluesky、discord_channel_chat、gmail_read のツール JSON 説明に外部コンテンツ警告を全言語で追加。

## [0.5.36] - 2026-07-04

### 追加
- SAKURA AI Engine (sakura) プロバイダ対応：OpenAI 互換 API を使用した新しい LLM バックエンド。
- セットアップウィザード（setup_cli.py）に sakura を追加。プロバイダ検出・クライアント生成に対応。
- llm_round_helpers.py に sakura の temperature 設定を追加。

### 変更
- `runtime_banner.py`：sakura プロバイダの base_url 表示を追加。

### ドキュメント
- README.md、AGENTS.md、DEVELOP.md、DEVELOP.ja.md、ENVIRONMENT.md のプロバイダ一覧に SAKURA AI Engine を追加。
- ENVIRONMENT.md に sakura/sakana の環境変数セクションを追加。

## [0.5.35] - 2026-07-04

### 追加
- `README.md` および全34言語の翻訳 README（`docs/README.*.md`）に Contributing セクションを追加。
- Responses ステートファイル名に Windows のファイル名利用不可文字のサニタイズ処理を `re.sub` で追加。

### 変更
- `core.py` の `_get_responses_state_file`: 従来の `.replace()` チェーンを `re.sub(r'[\\/:*?"<>|]', "_", ...)` に置き換え、クロスプラットフォーム対応を強化。

## [0.5.34] - 2026-07-04

### 追加
- Responses API のサーバサイド compaction 対応（OpenAI/Azure GPT-5.4+、`UAGENT_RESPONSES=1`）。閾値はローカルの auto-shrink と同一。compaction 発生時にログ表示。
- ツールフロー文書（`src/uagent/docs/TOOL_FLOW.md`）を追加。genre mask、tool_catalog 動的ロード、GPT-5.4+ native tool_search を網羅。
- `get_windows_gps` の description を高優先度に、`get_geoip` を低優先度に変更。

### 変更
- `responses_state.json` をプロバイダ/モデル別ファイルに分割（`responses_state_{provider}_{model}.json`）。JSON 破損時は自動削除。
- auto-unload を `previous_response_id` 設定時は全プロバイダでスキップ。
- `_should_preload_lazy_specs` のデフォルトを `False` に修正（GPT-5.4+ 以外で管理ツールが誤って除外される問題を解消）。

### 修正
- `_check_responses_state_provider` の `saved_model` None チェック不足による AttributeError を修正。

## [0.5.33] - 2026-07-02

### 追加
- ツールの自動アンロード機構：未使用ツールは5ラウンド後、使用済みで放置されたツールは `UAGENT_AUTO_UNLOAD_ROUNDS`（デフォルト10）ラウンド後にアンロード。コアツール（`tool_catalog`、`tool_load`、`unload_tool`）は保護対象。
- `:tools list` に自動アンロードまでの残りラウンド数を表示。
- `translate_text` が `.po` ファイル形式と動的プレースホルダ検出に対応。

### 修正
- ツール実行後の `_TOOL_LAST_ROUND` が更新されていなかった問題を修正。`messages[-1]` が tool 結果（role=tool）になっていたため、アシスタントメッセージを逆探索するよう変更。
- 全ラウンドですべてのツールの `_TOOL_LAST_ROUND` がリセットされていた問題を修正（メッセージ履歴全体を走査していた）。
- `run_llm_rounds` の `UnboundLocalError`（`assistant_text` 未割り当て）を修正。
- `:tools list` がコアツール（`tool_catalog`、`tool_load`、`unload_tool`）の残りラウンド数を表示しないよう修正。
- `windows_gps_tool` が非Windows環境で TOOL_SPEC=None を設定し、読み込みとカタログ表示を抑制。

### 変更
- 全ツールの i18n 翻訳を完了。古いキーを削除し、不足していた翻訳を補完。
- POT を再生成し、全34言語の PO ファイルを再構築。

### ドキュメント
- `vup-build-release-whl` スキル：`git remote origin` のURLから配布先（GitHub/GitLab）を自動判定するよう改善。

## [0.5.32] - 2026-07-01

### 追加
- `:profile-fromlog` のデフォルトを直近100件のログファイルに変更。

### 修正
- ホスト側ファイルのユーザー向け print メッセージに不足していた `_()` ラッパーを追加（llm_helpers、llm_round_helpers、profile_manager、llm_deepseek、llm_zai、scheckgui）。

### 変更
- i18n: POT を再生成し、全34言語の PO ファイルを再構築（575エントリ、空欄0）。
- i18n: 全言語の未翻訳エントリを Google 翻訳で翻訳。
- i18n: Google 翻訳で翻訳されたプレースホルダキーを21ロケールファイルで修正。

## [0.5.31] - 2026-07-01

### 追加
- APM（Agent Package Manager）スキル統合：タブ補完、DEVELOP.md ドキュメント、skills_apm_tool.py。

### 修正
- setup_cli.py のループ変数 _ を label に変更し、gettext の _() による UnboundLocalError を回避。

### 変更
- i18n README 翻訳の同期：34言語にわたる書式調整とコンテンツ更新。

### ドキュメント
- AGENTS.md を日本語のエージェント指示から英語のプロジェクト概要に書き換え。

## [0.5.30] - 2026-06-30

### 追加
- オートパイロットモード（`:auto` コマンド）：判定モード、レビュアーフィードバック伝搬、`UAGENT_AP_PROVIDER` による独立した判定LLMをサポート。
- GUI/Web インターフェースにオートパイロットループと Stop ボタンを統合。
- `pdf_export` ツール：会話をPDFにエクスポート。`:logs` に `pdf` サブコマンドを追加。
- `translate_text`：printf 指定子を翻訳時に保持する `protect_placeholders` オプションを追加。

### 修正
- オートパイロットの COMPLETE 判定が1ラウンド遅れる問題を修正。
- `util_tools.py` の print/_ 呼び出し行分割による未終了文字列リテラルを修正。
- `list_dir` の paginate 引数処理を修正。
- Google翻訳で破損した bn, el, hu, mn, ro ロケールファイルの printf 指定子を復元。
- Google翻訳で破損した全ロケールPOファイルの `%(feedback)s` パターンを復元。
- レビュアー判定の `max_tokens` を 10 から 50 に増加。

### 変更
- オートパイロットモード中は `human_ask` をスキップ。
- LLM クライアント生成を once-per-loop パターンにリファクタリング。
- 非 README.md のドキュメントリンクをすべて相対パスに変換。

### ドキュメント
- システムプロンプトに workdir 相対パスに関する注記を追加。
- `fetch_url` ツール説明に `browser_playwright` ヒントを追加。
- オートパイロットドキュメント（`AUTO_REVIEW.md`、`README_AUTO.md`、`docs/README_AUTO.ja.md`）を追加。

### その他
- `tools/__init__.py` と `welcome.py` に ruff フォーマットを適用。
- 全ロケールファイルの空のPOエントリを翻訳で補充（i18n更新）。


## [0.5.29] - 2026-06-29

### 追加
- Sakana AI (Fugu) プロバイダ対応：Responses API 統合による新しい LLM バックエンド。
- sakana（およびその他の RESPONSES_PROVIDERS）で Responses API をデフォルトで自動有効化。
- セットアップウィザード（setup_cli.py）に sakana.ai を追加。
- 割り込み機能：`c` キーまたは Stop ボタンで実行中のツールをキャンセル可能に。

### 変更
- 非対応モデルで 400 エラーが発生した場合、ツール/思考を自動無効化し、冗長なリトライを回避。

### ドキュメント
- Sakana AI (Fugu) をプロバイダ一覧と Responses API ドキュメントに追加。
- 全34言語の README プロバイダ一覧に Sakana AI を追加。
- 全34言語の README プロバイダ一覧に HuggingFace を追加。
- 全34言語の README 翻訳に割り込み機能（c-key/Stop ボタン）を追加。
- 日本語 README.ja.md に割り込み機能（c-key/Stop ボタン）を追加。

### その他
- llmcapa 依存を 0.2.6 から 0.2.8 に更新。


## [0.5.28] - 2026-06-28

### 変更
- zhipuai をオプショナル依存（`[zai]` extra）に変更。未インストール時は OpenAI SDK にフォールバック。


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
