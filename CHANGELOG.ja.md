# 変更履歴

## [0.5.53] - 2026-07-20

### 追加
- `echonet_scan` のネットワーク `scope` フィルタ（`all`/`local`/`external`/`self`/`local_other`）。ノードごとの scope 情報と summary 件数。キャッシュキーに scope を含む。
- 依存: Grok/xAI gRPC 用に `xai-sdk>=1.17.0`。

### 変更
- BACnet ツール（`bacnet_scan`/`read`/`write`）が `bacnet_shared` の共有イベントループ経由で BAC0 2025+ の async who_is/read/write/disconnect に対応。refcount と COV 用 keep-alive。

### 修正
- 単体ツール有効化時に対象ツールモジュール（および存在する `*_shared`）を reload し、プロセス再起動なしでソース変更を反映。

## [0.5.52] - 2026-07-19

### 追加
- プラグイン `commands/*` を名前空間付き `:` コマンドとして登録（`:plugin` / `:plugin sub` / `:plugin:sub`）。コア予約名は拒否。activate/deactivate ライフサイクル対応。
- プラグイン enable/起動時に MCP・agents・hooks を有効化。bare の `:plugin install <name>` は登録 marketplace から解決（Claude Code 相当）。
- hooks: SessionStart/Setup/UserPromptSubmit の stdout を `[HOOK]` system コンテキストへ注入。UserPromptSubmit の block を CLI/GUI/Web で処理。`${CLAUDE_PLUGIN_ROOT}` / `${UAGENT_PLUGIN_ROOT}` 展開。
- i18n: `:model` / capa UI の gettext、残存 UI 文字列、`po_i18n_batch`、`:model` の Grok 音声モデル表示、pot/po/mo 更新。
- ランタイム終了方針: ヘルパーは裸の `sys.exit` ではなく例外。ツールホストはツールの `SystemExit`/`Exception` を封じ込め（DEVELOP.md §6.1）。
- mypy: `typings/numpy` スタブ影 + numpy `follow_imports = skip`（3.11 基準）。

### 変更
- プラグイン `remove`: コンポーネント deactivate → `enabledPlugins` キーと `pluginConfigs` 削除 → rmtree（enabled=true の残留なし）。
- auto-unload 表示: 「生産ラウンド」→「LLMラウンド」（全ロケール）。

### 修正
- 空 assistant / no-tool の Grok 向け recovery 強化（履歴/UI-only WARN、次ターン recovery）。
- exec: 子プロセス stdin を隔離し、EOF で CLI が終了しないように。
- エージェントのツールループ、Responses previous_response_id、catalog steering、短いセッションログ。
- OpenRouter SDK import がテスト注入を上書きしないよう修正。provider/client 初期化エラーを安全に。

## [0.5.51] - 2026-07-19

### 追加
- hooks: SessionStart/Setup/UserPromptSubmit の stdout を `[HOOK]` system コンテキストへ注入（プレーンテキストおよび `additionalContext` JSON）。Web/GUI は遅延適用。ログ再読込時は `[SKILL]` と同様に `[HOOK]` を保持。
- `:plugin install <name>`: bare 名を登録 marketplace から自動解決（Claude Code の `/plugin install genshijin` 相当）。
- `:help`: 概要表示と CMD_SPEC を含むコマンド別詳細。
- MCP: HTTP ヘッダ対応、n8n 適応プランのメモ。
- `translate_text`: 翻訳時のブランド/製品名保護。
- ツール JSON i18n 向け tmp ベース一括翻訳。

### 修正
- hooks: Claude Code 互換で `${CLAUDE_PLUGIN_ROOT}` をプラグインディレクトリに解決（環境変数も設定）。
- 空 assistant / no-tool ループ: 空の assistant を履歴から除去、WARN をモデル履歴に入れない、次ターン用 recovery prompt を追加。grok/xai の `UAGENT_EMPTY_NO_TOOL_MAX` 既定を 5 に引き上げ。
- 空 no-tool の続き: recovery を次の実 user にマージ（合成 user の積み上がり防止）、WARN を Web 向け UI-only assistant として記録、空 assistant の事前 append を抑止、sanitize で `_uagent_ui_only`/`_uagent_internal` を除外。
- Grok: CLI ステータスに reasoning effort（`LLM:` / `LLM:auto->...`）を表示。
- Grok/Responses: reasoning を `.` / `!` / `?` で改行せず連続ストリーム表示。
- i18n: 空値・英語のまま残っていた tool JSON を修正、パラメータ名保護、translate_text/audio_speech ロケール適用。
- lint: 未使用変数削除、関連モジュールの ruff/black 整理。

## [0.5.50] - 2026-07-18

### 追加
- llmcapa: 共通 `llmcapa_util` lookup（プロバイダ別名）、vision 判定、max-token クランプ、shrink ctx、`:model v` 詳細表示を強化。
- llmcapa: tokenizer 用 model id 解決、Responses/FIM の capability ゲート、Ollama/FIM/Grok の max-token クランプを追加。
- llmcapa: profile/translate/sub-agent の max-token クランプ、sub-agent 利用コスト見積、banner/`:model` の deprecated 警告、統合ドキュメント更新。
- llmcapa: vision ツール (analyze_image 系) で vision 可否チェックと max-token クランプを追加。
- llmcapa: DeepSeek/ZAI/Novita の共有 max_tokens、generate_image/img2img/semantic_search の image/embedding capability チェックを追加。
- llmcapa: STT 向け `supports_audio_input` / `check_audio_input_support` を追加（カタログ欠落は許可、completion max_tokens とは別扱い）。
- llmcapa: TTS 向け `supports_audio_output` / `check_audio_output_support` を追加（カタログ欠落は許可、completion max_tokens とは別扱い）。
- `audio_transcribe`: Grok/xAI バッチ STT を POST `/v1/stt`（multipart file または url）で対応。プロバイダ別名 `grok`/`xai`、既定 model `grok-stt-batch`、diarize/keyterm/filler_words/format 対応。
- `audio_speech`: Grok/xAI TTS を POST `/v1/tts`（requests）で対応。プロバイダ別名 `grok`/`xai`、既定 model `grok-tts` / voice `eve`、language/speed/codec マッピング。
- 管理ツールのループ検出: 対象名単位の fingerprint（`tool_load:name`）。`unload_tool(target)` および auto-unload（`disable_single_tool`）でその対象の load 連続回数をリセットし、unload→reload を誤検知しない。

### 変更
- llmcapa 依存を >=0.4.1 に更新。

## [0.5.49] - 2026-07-15

### 追加
- CLI/GUI/Web 起動後にツールをバックグラウンド予熱し、初回 `:` コマンドの遅延を低減。
- `switchbot-ble`: 公式 BLE API に沿った複数デバイス広告ステータスのデコード対応。
- browser_playwright セッション拡張および scale tool の設計メモを追加。

### 修正
- `shrink_llm`: 履歴要約 system メッセージの積み上げを防止し、既存要約を1件の rolling summary に統合。
- `shrink_llm`: 圧縮直後の再トリガーを抑えるヒステリシスを追加。
- Grok: history compress / profile の LLM 経路で simple_xai_chat を使用。
- Grok: ストリーム応答の二重表示を防止。

### 変更
- ツールプラグインは遅延ロードのまま、起動後バックグラウンドで予熱する方式に変更。

## [0.5.48] - 2026-07-13

### 追加
- TOOL_CREATOR_GUIDE.md を Google翻訳で33言語に翻訳。
- `translate_text` ツール: 改行プレースホルダを ⏎ (U+23CE) に変更（翻訳品質向上）。
- コードブロック保護用 `<<<BLOCKNNNN/>>>` マーカー形式を導入。

### 変更
- `translate_text`: プレースホルダ `[=BR=]` を `⏎` (U+23CE) に置換（Google翻訳による文字化け回避）。
- ツールドキュメント: 33言語版 TOOL_CREATOR_GUIDE.md を `docs/` に追加。

### 修正
- 翻訳文書内のコードブロックマーカーが Google翻訳の構造再編成後も適切に保持されるよう改善。

## [0.5.47] - 2026-07-13

### 追加
- WEB UI: 設定パネルに Reasoning 表示 ON/OFF トグルボタンを追加。
- デスクトップ GUI: ステータスバーに Reasoning 表示 🧠 トグルボタンを追加。
- WEB UI: コマンド実行結果（`:tools list`、`:help` など）がチャットに表示されるよう改善。
- `git_ops`: `rm` コマンドをサポート。

### 修正
- ハイコントラストモード: トグルノブに輪郭線を追加して視認性を改善。
- `catalog_tool.py`: 欠落していた `run_tool()` 関数を復元（開発モードで管理ツールがロード失敗する問題を修正）。
- デスクトップ GUI: フォントサイズメニューのチェックマークが現在のサイズを正しく反映するよう修正。
- `read_file_tool.py`: 末尾改行なしでの切り詰め処理を修正。

### 変更
- `scheck.py` ランチャーを統合: 全モードのエントリポイント（cli, gui, web, a2a, ws, setup）を1つのスクリプトに集約。
- UnifiedPanel.svelte: 一貫した border-radius、余白、ボタンスタイルに整理。
- `create-tool` スキルディレクトリ名を frontmatter 名に合わせて変更。


## [0.5.46] - 2026-07-13

### 追加
- sub-agent Phase 1-3 完了: マルチターン会話、全ツール対応、チェインツール、コスト追跡、動的ロール割り当て、構造化ログ。
- reasoning: `:r` コマンドの引数なしトグル動作（ON/OFF切替）、`max` レベル（`:r max` / `:r m`）、数値エイリアス（4=xhigh, 5=max）、表示オフ制御。
- llmcapa 統合: Claude/DeepSeek/ZAI/OpenRouter プロバイダ向け `reasoning_effort_values` 検証。
- i18n: 8個の新規パラメータの翻訳を34言語に追加、`sub_agent_chain_tool.json` を34言語で作成。

### 修正
- `apply_patch`、`cmd_exec_json`、`replace_in_file`、`list_windows_titles` のクロスプラットフォーム対応とバグ修正。

### 変更
- llmcapa 依存を >=0.3.3 に更新。
- reasoning: `ultra` レベルを削除（`xhigh` と `max` のみ維持）。OpenRouter の effort 値を正しく渡すよう修正。
- リポジトリから未使用ファイルを削除。

# 変更履歴

## [0.5.45] - 2026-07-12

### 追加
- 新ツール: `diff_files`（2ファイルの行比較）と `apply_patch`（unified diff パッチ適用）、全34言語 i18n 対応。
- ツールジャンル: `dev`、`web`、`utility` をジャンルビットマップとジャンル制御システムに追加。

### 修正
- `tests/test_llmcapa.py`: `Llama-3.2-90B-Vision-Instruct` と `Llama-4-Scout-17B-16E` の `expect_vision` フラグを修正（両モデルは vision 対応）。

### 変更
- llmcapa 依存を >=0.3.1 に更新。
- README と33言語翻訳: ツール数170、並列セーフ111に更新。
- AGENTS.md: ツールジャンル一覧に `dev`、`web`、`utility` を追加。

## [0.5.44] - 2026-07-11

### 追加
- llmcapa v0.3.0 対応: `llmcapa.get()` に `provider` 引数を渡して正確なモデル検索を実現。
- テスト `test_llmcapa.py`（37テスト）: 全70プロバイダのモデル諸元を検証。
- ドキュメント: `docs/llmcapa_improvements.md`（llmcapa への改善要望）。
- ドキュメント: i18n ワークフローに `translate_text` ツールの使用方法を追記。

### 修正
- `cmd_exec_json_tool`: subprocess.run の例外捕捉、戻り値 error キーの統一、cwd 空文字列ガード。
- `pwsh_exec_tool`: 全エラーメッセージを i18n 対応、脆弱な confirm 置換削除、タイムアウトプレースホルダ修正。
- `bash_exec_tool`: subprocess.run の例外捕捉、全エラーメッセージを i18n 対応。

### 変更
- i18n ドキュメント統合: `DEVELOP_I18N.md` がホスト側(gettext)・ツール側(JSON)の両方式を1ファイルでカバー。
- README と33言語翻訳: ツール数171、並列セーフ89、プロバイダ数21に更新。
- 全 `.org` バックアップファイルを削除（計73ファイル）。
- スタブ文書 `DEVELOP_TOOL_I18N.md` と `ADD_LOCALE.md` を削除（統合ガイドにマージ）。
- llmcapa 依存を >=0.3.0 に更新。

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
