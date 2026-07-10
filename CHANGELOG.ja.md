# 変更履歴

## [0.5.43] - 2026-07-10

### 追加
- 2idx ツール: jv2idx, kt2idx, php2idx, rs2idx, ts2idx にプリプロセス、デコレータ/アノテーションスキップ、関数深度検出、複数行結合を追加。

### 修正
- ruff の無効な構文エラー44件を修正（`except X,Y` → `except (X,Y)`）。
- ruff の警告8件を修正。
- `compress_history_with_llm` から不要な `core=` パラメータを削除。

### 変更
- `cmd_exec_tool` を削除（`cmd_exec_json_tool` に統合）。
- Black フォーマットを49ファイルに適用。
- 2idx ツールの JSON スキーマを新機能に合わせて更新。

## [0.5.42] - 2026-07-10

### 追加
- i18n: 33言語の x_search_terms 翻訳を全ツールJSONファイル（59以上）に適用。
- VSCode: human_ask 統合、推論レベルドロップダウン、FIMコード補完。
- VSCode: ツール結果表示の設定切替（UAGENT_VSCODE_SHOW_TOOL_RESULT）。
- Web UI: マルチモーダル画像入力および表示対応。
- Web UI: data_url 最適化と WebSocket max_size 設定による添付ファイル処理改善。
- Grok/xAI: xai_sdk 統合（全パラメータ＋ツール使用対応）。
- ツール管理: 動的パーツール自動アンロード（Fibonacci バンプ閾値）。
- tool_catalog: クエリ時に最適なツールを自動読み込み。
- ドキュメント: TOOL_TRANSLATION_METHODOLOGY.md 追加（デリミタ戦略セクション含む）。

### 修正
- OpenAI Responses API: 2ラウンド目以降の content 正規化、previous_response_id 対応。
- OpenAI Responses API: previous_response_id の stale エラー処理。
- Web UI: 画像添付の描画とツールメッセージ表示の修正。
- デバッグ出力: sys.__stdout__/sys.__stderr__ へのリダイレクトで診断改善。
- 各種: デバッグログ、一時ファイル、CONFIG デバッグログの削除。

### 変更
- プロバイダ機能を provider_caps に集約。
- デバッグ用一時ファイル削除、.gitignore 更新。

## [0.5.41] - 2026-07-08

### 追加
- 新ツール `lint_js_ts`: Biome を使用した JavaScript/TypeScript リント（34言語対応）。
- 新ツール `mdformat_check`: Markdown フォーマットチェック/自動修正（YAML front matter 対応）。
- 新プロバイダ `novita`: OpenAI 互換 API プロバイダ（推論表示対応）。
- i18n: 全34言語の翻訳をツールに追加（mdformat、lint_js_ts、lint_format）。
- Web UI: reasoning_content 表示（ストリーミング/非ストリーミング）、ツールオーバーレイ、favicon。
- CLI: Responses API で reasoning_content を灰色表示（非ストリーミング時）。

### 修正
- 画像生成: GPT image models のキーワード `fmt` → `output_format` に修正。
- 画像生成: DALL-E 専用 quality 値（standard/hd）を GPT モデルでフィルタリング。
- 画像生成: background 値を有効な値（transparent/opaque/auto）にマッピング。
- ツール登録: `run()` → `run_tool()` にリネーム（登録のため）。
- mypy: echonet_control、responses parser、uagent_llm、web.py の型エラーを修正。
- ruff: reasoning_content の `dir()` → `locals().get()` で置換。
- OpenAI Responses API: gpt-5.x モデルはストリーミング時に reasoning_text.delta を送信しないことを注記。

### 変更
- フロントエンド再ビルド（固定アセットファイル名、SVG favicon）。
- プロバイダ一覧を `provider_caps.ALL_PROVIDERS` に集約。
- バックアップファイル（*.org*）、node_modules を削除、.gitignore 更新。
- mdformat/mdformat-frontmatter をコア依存からオンデマンド自動インストールに変更。

## [0.5.40] - 2026-07-07

### 追加
- `generate_zai`: ZhipuAI (ZAI) 互換コード生成ツール。
- `reverse_geocode`: Nominatim を使用した逆ジオコーディングツール（39言語対応）。
- `code_map`: JSON-LD オントロジー出力、インポート/関連抽出、i18n 対応。
- GUI/Web/A2A/VSCode: `.env.sec` ファイルの自動生成。
- `translate_text`: 対応言語の拡大。

### 修正
- Responses リトライ状態とツールユーティリティのエッジケース。
- `browser_playwright_run` と `run_tool` エイリアスの復元。
- i18n: `:tools reload` メッセージの34言語翻訳。

### 変更
- GPT-5.4+ ツールリスト表示の調整。
- ドキュメント: ツール数 171（うち87並列セーフ）に更新、IoTテーブルに reverse_geocode 追加。
- ドキュメント: DEVELOP.md に JSON-LD オントロジーと Mermaid 依存関係グラフを追加。
- 未使用の skills/servicenow-open/ ディレクトリを削除。
