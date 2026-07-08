# 変更履歴

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
