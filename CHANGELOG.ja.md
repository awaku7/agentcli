# 変更履歴


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

### 追加
- `fetch_url` ツールに `save_as` パラメータを追加（バイナリレスポンスを直接ファイルに保存可能に）。
- HTTP GET で HTML コンテンツが検出された場合、browser_playwright の使用を提案する機能を追加。
- `:chat` 応答のマークダウンレンダリングを追加。
- 起動時の git チェックをオプション化（CLI 起動から `check_git_installation` を削除）。

### 修正
- `browser_playwright` の wait アクション: `selector` をオプションにし、KeyError を防止。
- 問題のある markdown JS 変更を差し戻し、チャットパネルの不具合を修正。
- Hindi `Why uag` ドキュメントの箇条書き番号を修正（3→4、デーヴァナーガリー A2A）。

### ドキュメント
- VSCODE.md を追加し、拡張機能の詳細を記載して README からリンク。
- 全翻訳 README ファイルに VS Code 拡張機能の案内を追加。
- 軽微なドキュメント修正。

### その他
- VSCode marketplace リリースの準備。

## [0.5.22] - 2026-06-23

### 追加
- PHPおよびCOBOLソースコード索引付けのための php2idx/cobol2idx ツールを追加。
- 全idxファミリーツールにi18n対応（34ロケール）を追加。
- ツール結果表示のオン/オフを切り替える `:tools output` コマンドを追加（34言語対応）。
- `UAGENT_SEMANTIC_SEARCH_MODE=bm25` 環境変数による BM25 モードを `semantic_search_files` に追加。
- `smart_merge_profiles` に `skip_llm_dedup` オプションを追加（中間マージ時のLLM重複排除をスキップ可能に）。
- `profile_from_logs` に `max_log_files` パラメータを追加（処理するログファイル数を制限）。
- `_sanitize_log_for_profiling` に `max_content_chars` パラメータを追加（画像データなどの特大メッセージをトリミング）。
- `:profile fromlog N` および `:profile-fromlog N` 構文に対応（処理する最近のログファイル数を指定）。

### 変更
- ツール数を 131（全ツール）/ 76（並列セーフ）/ 13（ジャンル）に更新。
- `profile_from_logs` の `chunk_size_limit` を 300 から 500 に引き上げ。
- LLM重複排除をチャンクごとではなく最終マージ時に1回だけ実行するよう最適化。
- 冗長な `:list` コマンドを削除（`:logs` に統一）。

### 修正
- GUI出力HTMLの `white-space` を `pre` から `pre-wrap` に変更し、適切に自動改行されるよう修正。
- BM25モード有効時に `graph_rag_search` が誤って呼び出される問題を修正。

### パフォーマンス
- `sorted(list(...))` ラッパーを削除し、`startswith` をタプルベースのルックアップに最適化。

### その他
- ruff の lint 問題（F821, F841, F401, E741）および ts2idx の深さバグを修正。
- コードベース全体の E722（裸のexcept）を修正。
- rs2idx、py2idx、browser_playwright、scheckgui の mypy エラーを修正。
- コンパクトなパーサー記法のために E701/E702 を ruff の無視リストに追加。

## [0.5.21] - 2026-06-22

### 追加
- VSCode 拡張機能サポート追加: TypeScript スキャフォールド (`vscode-extension/`)、WebSocket クライアント、チャットパネル、ツリープロバイダー。
- `scheckws.py` ラッパー追加: プロジェクトルートから WebSocket サーバーを簡単に起動可能に。
- `ws_server` にチャットハンドラ追加: VSCode パネルから LLM 呼び出しを連携。
- LLM チャット統合: `ws_handler` で `run_cli_startup` + `run_llm_rounds` を利用。

### 修正
- TypeScript コンパイル問題を修正: `@types/node` 追加、`tsconfig.json` 修正。
- VSCode 拡張機能から冗長な `activationEvents` を削除（VS Code が自動検出）。
- チャットハンドラを簡略化し、LLM 未設定時に適切なフォールバックメッセージを表示。
- `ws_handler` の `ToolCallbacks.get_workdir()` を `os.getcwd()` に置き換え。
- WebSocket ハンドラ修正: `tool_genre_mask` の型、`should_exit` チェック、`providers` インポート、タイムアウト設定、ワークディレクトリタイミング。

### 変更
- `MANIFEST.in` と `.gitignore` を更新し、`vscode-extension/` を PyPI 配布から除外。

## [0.5.20] - 2026-06-25

### 追加
- Gmail ツール追加: `gmail_send`（SMTP送信）と `gmail_read`（IMAP受信/検索）。
- `parse_eml` ツール追加: .eml メールファイルの解析。
- メール関連の共通処理を `email_utils.py` に抽出し、コード重複を削減。
- 3つの新ツールに完全な i18n（34ロケール）対応。
- `replace_in_file` に `mode_after` パラメータ追加: anchor_after の正規表現モードを独立指定可能に。

### 変更
- ツール数（112→116）、並列セーフ数（66→67）を更新。
- `create_file` が例外送出ではなく JSON `{"ok": false, "error": "..."}` を返すように変更。
- `replace_in_file` の match_hits に insert_before/insert_after/insert_at_line/insert_at_end の挿入位置情報を追加。
- `replace_in_file` insert_at_end で末尾改行がない場合、自動で改行を追加してから追記。
- `replace_in_file` insert_at_line で範囲外の line_no を指定すると ValueError を送出。
- `replace_in_file` の重複計算ブロック（デッドコード）を削除。

## [0.5.19] - 2026-06-22

### 追加
- ソースコードナビゲーションツール用の 'index' ジャンルを追加（py/ts/cs/jv/dart/cpp/rs の11のidxツール）。
- Z.AI プロバイダーをプロバイダー一覧に追加。
- UAGENT_PARALLEL_WORKERS 環境変数でスレッドプールサイズを設定可能に（デフォルト8）。
- idx ファミリーのドキュメントを全33のREADME翻訳、ツールテーブル、DEVELOPドキュメントに追加。

### 変更
- ツール数（111→112）、並列セーフ数（55→66）を更新。
- 並列実行に関するドキュメントを明確化（最大4同時実行、66並列セーフ）。
- UAGENT_PARALLEL_WORKERS および不足していたプロバイダーを ENVIRONMENT.md と ENVIRONMENT.ja.md に追加。

## [0.5.18] - 2026-06-21

### 追加
- MiniMaxプロバイダーを追加（OpenAI互換、エンドポイント https://api.minimax.io）。
- トルコ語（tr）README翻訳を追加。
- ギリシャ語（el）、ヘブライ語（he）、ハンガリー語（hu）、ルーマニア語（ro）のREADME翻訳を追加。
- el/he/hu/ro ロケールをツールJSONに追加。
- 全翻訳言語を示す世界地図SVGを README.translations.md に追加。
- 動的プロバイダー切替のための `:provider` コマンド仕様を追加。
- .poコンパイルとツールJSON翻訳に関するi18n修正計画のドキュメントを追加。

### 変更
- ツールのオン/オフジャンル制御: シェルメタ文字確認をデフォルトで無効化、ファイルジャンルを汎用実行ツールから分離。
- README.translations.md をカテゴリ別テーブルに再構成。
- README.translations.md の言語名をクリック可能なリンクに変更。
- 世界地図をミラー図法で再描画、大陸をより詳細に表示。
- md2idx の翻訳を30言語に拡大。

### 修正
- SVGマップファイルをリポジトリから削除（GitHubがSVGを自動リンクし、インライン表示が壊れるため）。
- SVGをbase64データURIとして埋め込み、GitHubの自動リンクを防止。
- SVGリンクの代わりにインライン画像として世界地図を表示。
- 国境ベースのハードコードされたSVG座標を使用し、首都の位置を正確に配置。
- 地理的中心ではなく首都に言語ドットを配置。
- SVG要素の順序を変更し、背景がパスの後ろに描画されるように修正。
- 地図のアスペクト比を 1200x720（正距円筒図法）に修正。
- SVG凡例テキストのアンパサンドをエスケープ。
- 9つの翻訳READMEファイルの破損したHTML/コードブロックを復元。
- md2idxツールの見出し番号オフセットを修正。

### その他
- 古い設計ドキュメント、TBD、ブレインストーミングノートを削除。

## [0.5.17] - 2026-06-20

### 修正
- `catalog_tool.json` の出力にリテラル `{persist}` プレースホルダーが表示される問題を修正（30言語）。
  - `msg.load.ok` 文字列に `(persist={persist})` のサフィックスが含まれていたが、
    呼び出し側で `persist` パラメータを渡していなかったため展開されていなかった。
  - `tools_control_tool.py` から未使用の `persist` パラメータ参照を削除。
- `human_ask` の `ui.howto` 表示テキストから `"""retry` / `"""end` の記載を削除
  （10言語の翻訳: bn, fa, ko, mr, nb, sw, th, vi, zh_CN, zh_TW）。

### その他
- `.vs/` および `.uagent_web_uploads/` を `.gitignore` に追加。

## [0.5.16] - 2026-06-20

### 修正
- 全77ツールJSONファイルの5408件の翻訳 truncation を修正（29言語）。
  - 自動翻訳時の文字数制限で切れていた翻訳を Google Translate で再翻訳。
  - 対象言語: ar, bn, cs, de, es, fa, fi, fr, hi, id, it, ja, ko, mn, mr, nb, nl,
    pl, pt, pt_BR, ru, sv, sw, th, tr, uk, vi, zh_CN, zh_TW。
