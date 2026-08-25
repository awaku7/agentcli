# 変更履歴

## [未リリース]

### 修正

- `:exit` / `:sessions summarize` 時に、前回の要約後に会話が続いたセッションを再要約するよう修正。最新の要約のみスキップ対象となる(従来は要約が存在すれば常にスキップされ、古い要約が残っていた)。
- 終了時の `:sessions summarize` のLLM呼び出し中にCtrl+Cを押すと、残りのセッションの要約を中止して正常終了するよう修正。従来は `KeyboardInterrupt` が `except Exception` で捕捉されず、生のトレースバックが表示されていた。

## [0.6.9] - 2026-08-25

### 追加

- SQLiteへセッション要約を永続保存する機能と `:sessions summarize` を追加。
- `:sessions prune --keep` による安全なセッション保持・削除機能とドライランモードを追加。
- F12キーで現在のLLMラウンドとAuto-Pilotを同時にキャンセルできるよう変更。

### 変更

- SQLiteのセッションストアとメモリストアを既定で有効化。
- セッションやキャッシュの既定保存先を作業ディレクトリからユーザー状態ディレクトリへ変更。
- セッションおよびプラグイン管理の新規メッセージを全ロケールへ追加。
- セッションストアをワーカースレッドで安全に使用できるよう変更。

### 修正

- LLMによる履歴圧縮に失敗した場合、または最小チャンクサイズまで縮小できない場合に、会話履歴を変更せず保持。
- 履歴圧縮中に発生するOpenAIモジュールのデッドロックを再試行。
- Responses APIへの入力から `reasoning_content` を除外しつつ、ローカル履歴には保持。

## [0.6.7] - 2026-08-23

### 追加

- feat: 構造化履歴、検索、ツール監査、要約、確認済みメモ候補に対応するオプトインSQLite Session Storeを追加
- feat: 実行権限レベルと企業YAMLルールを統合するUnifiedPolicyを追加
- feat: CLI、GUI、Web、A2Aの各エントリーポイントへSession Storeを統合
- docs: Session Store、統合Policy、多言語READMEの利用方法を文書化

### 変更

- refactor: エントリーポイント間のSession Store接続・クリーンアップを共通化

## [0.6.6] - 2026-08-22

### 追加

- feat: 予測にローリング起点検証、ドリフト診断、コンフォーマル予測区間を追加
- feat: OpenAI/AzureのサブエージェントにResponses APIネイティブツール実行を追加
- feat: 副作用のあるツールにセッション単位の「all」許可を追加
- feat: Rustツールカタログをツール国際化バッチの対象に追加

### 変更

- fix: GPT-5およびoシリーズのチャット完了系でトークンパラメータを適切に選択
- fix: CLIの補完メニュー操作を改善し、F11でAuto-Pilotを終了可能に変更
- fix: ロケール対応インターフェースでサブエージェントの確認元を保持
- docs: READMEにアーキテクチャ、プラグイン、マーケットプレイス、IoTの説明を追加し、翻訳を更新

### テスト

- test: 補完メニューの矢印キー操作とdelete_fileの確認動作を追加検証

## [0.6.5] - 2026-08-21

### 追加

- feat: プロバイダーとモデルの能力に基づくネイティブStructured Output判定を追加
- feat: Structured Outputの出典メタデータ取得APIを追加
- test: Structured Outputのフォールバック、Azureスコープ、OpenRouter分離のテストを追加

### 変更

- fix: Gemini、Claude、Grok、Ollama、llama.cppにモデル単位のStructured Output判定を適用
- fix: AzureとOpenRouterの能力検索をプロバイダー単位に限定
- fix: CLIで複数行履歴を呼び出した際、カーソルを先頭行の先頭へ移動
- chore: `llmcapa>=0.5.10` を要求
- docs: Structured Outputの実装状況を記録し、Bedrock Converse API対応を保留

## [0.6.4] - 2026-08-20

### 追加

- feat: 対応プロバイダー全体で統一構造化出力をサポート
- docs: エンタープライズポリシー編集ガイドを追加

### 変更

- fix: Geminiの関数応答を対応する`user`コンテンツロールへ変換
- fix: 数字のみの`.org`バックアップ削除で追加確認を省略
- fix: MCPツール結果をJSONとして正規化
- style: プロジェクト全体にRuffとBlackの整形を適用
- test: Ollamaリクエスト互換性のテストを追加

## [0.6.3] - 2026-08-19

### 追加

- feat: 構造化された可観測性イベントエンベロープを追加し、イベント固有ペイロードを標準化
- feat: Mermaidから編集可能なExcelフローチャートへ変換するツールを追加

### 変更

- fix: エンタープライズのエンドポイント許可リストを厳格化
- docs: TaskStoreの対象範囲、生成コードマップ概要、プロバイダー設定案内を更新
- test: Computer Useエラーをロケール非依存化
- refactor: OpenAIのfast modeをセットアップウィザードの対象外に整理

### 削除

- obsoleteなMermaid Excelコンバーターパッケージのソースとテストを削除

## [0.6.2] - 2026-08-18

### 追加

- feat(i18n): 対応ロケール全体で Computer Use メッセージとツールカタログの翻訳を完備
- feat(i18n): 共有ポリシー確認を含むホストおよび Computer Use の国際化連携を追加
- feat(cli): logs、Auto-Pilot、プラグイン、メモリ、プロファイルの `:` コマンドと引数のタブ補完を拡張

### 変更

- docs: Computer Use の国際化実装ガイドを更新
- docs: Auto-Pilotの終了条件を文書化し、ツールフロー文書を英語化
- docs: 各言語READMEのAuto-Pilotキー表記を修正し、翻訳リンクを統一
- docs: リポジトリ内ドキュメントへのリンクをGitHub絶対URL化（PyPIリンクは維持）
- test: Unicode空白を使ったステガノグラフィーのサンプルと検出器を追加

## [0.6.0] - 2026-08-15

### 追加

- feat: 分散リーダーリース調整と永続タスクチェックポイントを追加
- feat: リモートエージェントタスク制御、チェックポイント復旧、A2Aタスクイベントのストリーミングを追加
- feat: 依存関係対応DAGスケジューラーと永続タスクストアを追加
- feat: 認証情報、MCP、スキル、プラグイン全体にエンタープライズポリシー適用を追加
- feat: 共有認証情報ストレージとランタイム間のライフサイクル/可観測性連携を追加

### 変更

- fix(deps): インストール済みの0.5.4リリースに合わせて `llmcapa` の固定バージョンを更新
- ci: 対応プラットフォームのテスト依存関係を分離・整備
- docs: 改善ロードマップ、ローカルCIチェック、アーキテクチャ、ポリシー案内を更新

## [0.5.72] - 2026-08-13

### 変更

- fix(openrouter): 公式OpenRouter SDKのレスポンス（`reasoning` フィールド、`reasoning_content` ではない）から推論を抽出
- fix(bitchat): 全ロケールで `nostr` ステータスの誤訳を修正
- feat(bitchat): BLE受信・接続のデバッグログを追加（`UAGENT_BITCHAT_DEBUG=1` で有効）

## [0.5.71] - 2026-08-11

### 追加

- feat(packaging): 関連ツールの使用時だけ、言語トークナイザーのオプション依存関係を遅延インストール
- feat(packaging): BLE依存関係を遅延インストールし、オプションツールのimportを遅延

### 変更

- fix(packaging): 文書、表計算、PDF、プレゼンテーション、スクリーンショット、セマンティック検索、暗号ツールの遅延オプション依存関係読み込みを完了
- fix(packaging): `pythainlp` のキャッシュ初期化を安全化
- fix(mcp): MCPクライアントのimport処理を修正
- fix(cli): i18nコマンドとオプション構文を修正
- fix(status): Python IDLEシェルのステータス出力からANSIカラー制御文字を除去
- docs: ローカライズ済みツール見出し、説明、READMEのツール一覧を更新
- docs: リポジトリ解析とカバレッジツールを文書化

## [0.5.70] - 2026-08-11

### 変更

- fix(deps): 検証済みの `llmcapa` 0.5.1 リリースに固定

## [0.5.69] - 2026-08-11

### 追加

- feat(tools): Pintによる単位変換・物理量計算ツール `quantities` を追加
- feat(tools): 候補経路、運賃内訳、検索クエリ付き出典リンクに対応したYahoo!路線情報ツールを追加
- feat(tools): Haversine法による直線距離と任意の逆ジオコーディングに対応した `geodesic_distance` を追加
- feat(transit): 到着地との近さで同名駅を解決するMLIT N02駅マスターを追加

### 変更

- feat(i18n): 新しいツールの多言語カタログを追加
- docs: ツール数、並列実行対応数、経路探索、数量計算、直線距離のドキュメントを更新
- fix(packaging): ツール用データリソースをsdistとwheelに収録
- fix(status): 推論状態を維持しながら一般的なLLM状態ラベルを正規化
- fix(types): token、Cloud API、pybitchatヘルパーのmypy問題を修正

## [0.5.68] - 2026-08-07

### 追加

- feat(code_map): シンボル、関係、manifest、lockfile、キャッシュ、CMake、rendererを備えたモジュール型プロジェクト解析を追加
- feat(code_map): COBOL COPY/CALLおよびObjective-C/Objective-C++のinclude解析を追加
- feat(http): 汎用HTTPリクエストツールを追加
- feat(forecast): 回帰予測モデルとローカライズ済みオプションを追加

### 変更

- feat(code_map): dependency_edges、推移依存メタデータ、ローカルclasspath候補、TFM情報、決定的なバージョン競合報告を公開
- refactor(tools): 分割した内部実装に対する安定したFacadeとして`code_map_tool.py`を維持
- fix(i18n): 公開Facade側の`code_map_tool.json`に完全なカタログを集約
- fix(screenshot): 画像を生成しないモックキャプチャバックエンドに対応
- docs: 多言語ドキュメントとツールカタログを更新

## [0.5.67] - 2026-08-06

### 追加

- feat(tools): ローカライズ対応のCMakeプロジェクトインデクサーとテストを追加
- feat(tools): Visual StudioソリューションおよびMSBuildインデクサーとローカライズを追加

### 変更

- docs: 多言語MCPガイドのリンク表記を標準化
- i18n: ローカライズ検索語の補完とVisual Studioカタログの対応範囲を改善

## [0.5.66] - 2026-08-05

### 追加

- feat(tools): AWS、Azure、GCP、VBA、LotusScript、Makefile向けのツールを追加
- feat(i18n): 実行時ローカライズカタログと翻訳保守スクリプトを追加
- feat(tools): forecastおよびpybitchatのツール仕様を追加

### 変更

- docs: ツール数、クラウドAPI説明、各言語READMEを更新
- fix(config): GUIエントリーポイントを`project.gui-scripts`で公開
- fix(search): 使用中のトークナイザー出力に合わせてJanomeの品詞処理を修正

## [0.5.65] - 2026-08-04

### 追加

- feat(network): pcap解析とローカルプロセス相関を一括実行するoffline `capture_analyze`を追加
- feat(network): 通信を`normal` / `review` / `suspicious` / `unknown`に保守的に分類
- feat(network): 期間・パケット数を制限したloopback限定のexperimental live captureを追加
- feat(network): TCP再送候補を`confirmed`、`possible`、`capture_duplicate`に分類
- test(network): loopbackキャプチャ統合テストとTCP再送分類テストを追加

### ドキュメント

- docs(network): ネットワークツールキットのロードマップ、安全方針、リリース状態、experimental live captureの範囲を文書化

### 国際化

- i18n: Responses APIライフサイクルメッセージとcapture-analysisツールメタデータを対応ロケールへ翻訳

## [0.5.64] - 2026-08-03

### 変更

- ツール結果キャッシュと不要になったキャッシュ再利用テストを削除
- PFNプロバイダーアダプターとテストを追加
- 各言語READMEのドキュメントブロックを翻訳

## [0.5.63] - 2026-08-02

### 修正

- fix(stream): reasoning出力が改行で終わる場合に余分な空行を出力しないよう修正
- fix(bitchat): Android Noise XX相互運用、BLEパディング、ハンドシェイク復旧、フラグメント間隔、重複メッセージ抑止を改善
- fix(skills): 構造化ツール応答に対応し、skill適用時にResponses API/プロバイダーキャッシュを無効化

### ドキュメント

- docs: Android/Python bitchat Noise相互運用の調査結果と残る実行時確認事項を文書化

## [0.5.62] - 2026-07-31

### 追加

- feat(bitchat): BLEメッシュノードの開始・停止コマンド `:bitchat start` / `:bitchat stop` を追加
- feat(bitchat): 実装済みだった `:bitchat peers` コマンドをCMD_SPECSに登録（未登録のバグを修正）
- test: `:bitchat start` / `:bitchat stop` ハンドラとCMD_SPECS登録のTDDテストを追加
- i18n: ノード開始・停止コマンドのen/jaメッセージを追加

### パフォーマンス

- perf(cli): dynamic_commandのタブ補完を高速化 — 補完リクエストごとにコマンドマップを1回だけ取得し、初回プラグインimportでブロックしない（バックグラウンドwarmupが継続し、部分結果で補完）
- perf(tools): `get_dynamic_commands_map()` の結果をキャッシュ（register/unregister時に無効化）。`get_dynamic_subcommands()` と非ブロック `block=False` モードを追加（マップ参照が約80倍高速化）

### 修正

- fix(cli): CLI で連続する素早い human_ask 返信を保持 — 直前の human_ask 返信直後の stdin typeahead flush をスキップ（例: :skills の番号選択後の y 確認）し、素早い返信が破棄されないように修正。パスワードは常に flush
- fix(bitchat): Phase 2-6 の pybitchat コンポーネントを実装 — `NoiseXXStateMachine` / `TransportCipher`（Noise XXハンドシェイク）、`sign_announce` / `verify_announce` / `PeerRegistry`、`MessageDeduplicator` / `RelayController`、`CourierEnvelope` / `CourierStore`（既存のFragment実装は維持）
- fix(bitchat): `CourierStore.store()` がリロード前の `CourierEnvelope` インスタンスを受け付け（`tools.reload_plugins()` による再importに耐性）
- fix(bitchat): ツールリロード後も `pybitchat_shared` のランタイム状態を保持 — `_load_plugins()` が既にimport済みのヘルパーモジュール（`TOOL_SPEC`/`run_tool` なし）を `importlib.reload()` しないよう変更。`_LLM_EVENT_QUEUE` / `_CHAT_MODE` / `_RUNNING` が `start_tools_warmup()` と `reload_plugins()` を跨いで生存する。chat_mode="llm" で受信メッセージが表示されるだけで LLM に注入されない不具合を修正
- test: `tests/test_pybitchat_llm_inject_reload.py` を追加（`reload_plugins()` 後も LLM イベントキューと chat mode が保持され、注入がキューに到達する）
- fix(gpt54): `uagent_llm` から `_select_tool_specs_for_gpt54` を再エクスポート（`llm_tool_narrowing._select_tool_specs_legacy` のエイリアス）
- fix(gpt54): legacy モードのツール絞り込みを「ヘルパー + カタログヒット + 動的ロード済みツール」に変更（全ロード済みツール送信をやめ、TOOL_FLOW.md に一致）
- fix(gpt54): `test_gpt54_tool_search.py` を現行設計（`UAGENT_GPT54_TOOL_SEARCH=native/legacy/off`、デフォルトnative、openai/azureのみ）に更新
- fix(i18n): pybitchat の nostr/on/via パラメータの en/ja キー欠落を追加。`err.payload_required` の日本語訳を修正
- fix(i18n): pybitchat_shared.py のコメント・メッセージ内の非ASCII矢印/ダッシュを ASCII に置換（utilities i18n チェック対応）
- fix(i18n): 18ツールの JSON の same-as-en キー欠落を `translate_text` エンジンで補充（bacnet/modbus/opcua/browser_playwright/csv2idx/echonet/json2idx/lint_format/log2idx/tools_control など）。browser_playwright_tool/tools_control_tool のリテラル description を `_()` 化。sub_agent_tool のステータス返値を i18n 化。\_matter_common/index_tool_helpers/nostr_transport の非ASCIIを置換
- fix(i18n): ユーティリティ21モジュールのユーザー向け文字列リテラルを `_()` 化（\_genre_control_util/\_matter_log/_secp256k1/bacnet_shared/bitchat_geo/dali_shared/email_utils/generate_grok/generate_zai/modbus_shared/mqtt_shared/nostr_transport/opcua_shared/os_scheduler_helper/rust_helper/ucp_shared/vision_\*）。`make_tool_translator` を追加 — `test_tools_utilities_no_user_facing_string_literals` が通過
- fix(i18n): pybitchat の表示/注入メッセージ（ハンドシェイク・ピア・ファイル・スキャン・サービス・Nostr通知、「sending as plain text (unencrypted)」等）を `_()` + %(name)s プレースホルダで i18n 化。`pybitchat_shared.json`（en/ja 翻訳）を追加
- fix(logs): `:logs` のメッセージ件数を `:load` の報告（「会話メッセージ数」）と一致させた — 再挿入されるシステムプロンプト、保持される `[SKILL]`/`[HOOK]` システムメッセージ、user/assistant/tool メッセージ、およびディレクトリが存在する場合の自動復元 `[CWD]` マーカーを含めてカウント（従来は user+assistant のみで、ツールメッセージ+1件ぶん異なっていた）
- fix(load): `:load` の workdir 自動復元を実際に機能させた — `[CWD]` を正規化後メッセージではなくログの生行から抽出（正規化では `[SKILL]`/`[HOOK]` 以外のシステムメッセージが除去されるため）。復元された `[CWD]` マーカーは報告件数に含まれる
- feat(web): `/api/logs/{index}/preview` の total_messages を CLI `:logs`/`:load` と同じ意味に統一し、`total_tool` / `preserved_system` フィールドを追加
- test: `tests/test_logs_load_count_consistency.py` を追加（CLI `:logs` 件数 == `:load` 件数、`[CWD]` ボーナス、生行からの cwd 抽出を検証）
- fix(i18n): ツールJSONの欠落キー727件を32言語に補充（ユニーク文字列の重複排除 + translate_text。bacnet/modbus/opcua の timeout 説明、browser_playwright の新パラメータ、csv2idx/echonet_scan/json2idx/lint_format/log2idx/tools_control のキー）。cl2idx/dds2idx/excel2idx/ppt2idx/rpg2idx の fa `msg.index_output` に `{total}` プレースホルダを復元。en から削除済みの孤児 extra キー1183件を削除（bluesky/switchbot_batch/upnp_igd_control/usb_camera/vision_deepseek/vision_ollama/echonet_cache/forecast）— `scripts/i18n_tools_check.py` がエラー0で通過

## [0.5.61] - 2026-07-30

### 追加

- feat: Azure OpenAI GPT Realtime対応（GAおよびプレビューのエンドポイント形式）
- feat: Amazon Bedrock Nova Sonic双方向Realtime音声アダプター
- feat: Bedrock選択時のRealtime SDK自動インストール
- feat: Azure、Bedrock、その他Realtimeプロバイダーのsetup wizard設定
- docs: Realtimeプロバイダー対応をREADMEおよび各国語READMEへ反映

### 修正

- fix: Geminiおよびその他プロバイダーでcキー中断処理を統一

## [0.5.60] - 2026-07-29

### 追加

- feat(realtime): Gemini realtime APIプロトコルおよびデフォルトモデル(gemini-3.1-flash-live-preview)の更新
- docs: DEVELOP.mdおよび多言語READMEの\*2idxツール数の最新化 (26)

### 削除

- chore: benchmarkディレクトリおよび不要な開発レビュー用ドキュメントの削除

## [0.5.59] - 2026-07-28

### 追加

- feat: pywebrtc-audio WebRTC AEC3による全二重Realtime音声
- feat: 読み取り専用のget_current_timeに対応したOpenAI Realtime Function Calling
- docs: 全言語版READMEにRealtime/AEC3とFunction Callingの説明を追加

### 修正

- fix: AEC3のfar参照を実際のスピーカー再生と同期
- fix: Realtime音声診断ログを追加、READMEの重複セクションを削除

### 変更

- chore: 全コードをBlackで整形し、Ruffの指摘を解消

## [0.5.58] - 2026-07-27

### 追加

- feat: pybitchat BLE Mesh ツールと chat mode 自動転送
- feat: Nostr トランスポート、Noise XX ハンドシェイク、geo チャネル、bitchat 用 secp256k1 ヘルパー
- feat: get_current_time 出力に OS レベル NTP 同期情報を追加
- docs: docs/BITCHAT.md 追加、COMMUNICATION ドキュメント拡充

### 修正

- fix: human_ask 応答後の古い [REPLY] プロンプト競合を回避
- fix: instruction files プロンプト前の余分な空行を削除
- fix(pybitchat): geo join の TypeError — is_running はメソッドではなく property
- fix: PacketFlag.HAS_RECIPIENT 未定義、CommandResult の TYPE_CHECKING import

### 変更

- chore: src 全体の ruff/black クリーンアップ（未使用 import、E731 lambda→def、フォーマット）

## [0.5.57] - 2026-07-26

### 追加

- feat: :skills list KEYWORD / :skills find KEYWORD — スキルを名前/説明でフィルタリング
- feat: Together AI / Vercel AI Gateway プロバイダ追加、llm_novita reasoning_effort 対応

### 修正

- fix: 29言語 README 内 Forecast カテゴリ重複行を削除

### 変更

- docs: 全34言語 README 更新 — ツール数 170→183、Forecast カテゴリ追加
- docs: docs/README.ja.md と DEVELOP.md のプロバイダ一覧更新、ファイル数更新
- i18n: Together AI / Vercel AI Gateway を 32 翻訳ファイルのプロバイダ一覧に追加
- chore: test/ ディレクトリ（test_apply_patch.py）削除

## [0.5.56] - 2026-07-26

### 追加

- Forecast ツール: LLM ベース時系列予測。依存関係自動インストール、i18n、CI 統合、プロット表示、TDD テスト完備。モデル: StatsForecast, AutoARIMA, AutoETS, Theta, MSTL, Prophet, LightGBM, CatBoost, TimesFM, Chronos。
- `:skills list KEYWORD` / `:skills find KEYWORD`: インストール済みスキルを名前または説明でフィルタリング。

### 修正

- Prophet ラッパー: `predict(int)` が forecast horizon のみ返すよう修正、`predict(DataFrame)` のカラム名リネーム修正、yearly_seasonality を無効化（四半期データへの適合改善）。
- LightGBM/CatBoost: 訓練時と予測時の特徴数不一致を修正、Prophet predict バグ修正、forecast_modules 優先順位リストに基づく auto-select 階層を再構成。
- StatsForecast v2.x API 互換性（forecast に df 引数必須）対応、TimesFM を TimesFM_2p5_200M_torch に更新、LightGBM/CatBoost last_feats バグ修正。全9モデルの End-to-End 検証済み。
- 29言語 README 内の Forecast カテゴリ重複行を削除。

### 変更

- README および33言語翻訳: ツール数を 170→183 に更新、Forecast カテゴリを追加。
- i18n: forecast_tool.json を全34言語に翻訳（tool_json_i18n_batch 使用）。
- test/ ディレクトリ（test_apply_patch.py）を削除 — 未使用テストファイルの整理。

## [0.5.55] - 2026-07-24

### 修正

- WEB 起動リンク i18n: msgid "Starting server on" の he/hu/el/ro/bn/ko msgstr を修正し、localhost URL が自然に読めるようにした。対応 .mo を再生成（CRLF 維持）。
- welcome: 非英語の GitHub README URL を `docs/README.{lang}.md` に修正（英語はルート `README.md` のまま）。

## [0.5.54] - 2026-07-24

### 追加

- IBM i ソース索引ツール（genre=`index`、mode=`index`|`section`）:
  - `cl2idx` — CL/CLP/CLLE（`.cl`/`.clp`/`.clle`）: 継続行結合、複数行コメント、SEU 連番除去、IF/DO/SELECT↔END スタックの `end_line`、DCL ラベル、主要コマンド（RTVJOBA/CHKOBJ/SNDRCVF 等）。
  - `dds2idx` — DDS PF/LF/DSPF/PRTF（`.pf`/`.lf`/`.dspf`/`.prtf`/`.dds`）: 固定桁 SEU 複数レイアウト採点、DSPF const/SFLCTL/INDARA、TEXT/COLHDG フィールドラベル、ファイル種別スコア、**REF/REFFLD の workdir 内簡易追従**（`R` フィールドへ型注釈）、**DSPF インジケータ/表示属性デコード**（条件インジケータ、DSPATR/COLOR/CF 引数、packed 定数行）。
  - `rpg2idx` — RPG/RPGLE/SQLRPGLE（`.rpg`/`.rpgle`/`.sqlrpgle`）: フリーフォーム（`**free`/`**end-free`、ctl-opt、dcl-\*、begsr/endsr、/copy|/include、`...` 継続）と固定フォーム F/D/P/C/H/I/O 仕様（BEGSR 大文字小文字保持、SEU 除去）。
- 回帰テスト: `tests/test_cl2idx_tool.py`、`tests/test_dds2idx_tool.py`、`tests/test_rpg2idx_tool.py`。
- レビュー計画ギャップ向け回帰テスト: `go2idx`、`kt2idx`、`cs2idx`、`swift2idx`、`jv2idx`。
- レビュー計画向け回帰テスト: `md2idx`、`dart2idx`、`php2idx`、`rs2idx`、`ts2idx`。
- 回帰テスト: `tests/test_py2idx_tool.py`、`tests/test_cpp2idx_tool.py`（\*2idx 全 16 ツール揃い）。

### 変更

- `dds2idx`: workdir 内の REF/REFFLD 簡易追従 — `REF(file)`/`REF(lib/file)` を解決し、`R`/`REFFLD` フィールドに参照元の型を注釈（例: `CUSTID R 10A <= CUSTPF.CUSTID`）。未解決は明示。
- `go2idx`: メソッド receiver ラベル、generic func/type、struct|interface ラベル、型エイリアス。
- `kt2idx`: extension fun、data/sealed ラベル、companion 名、複数行 preprocess。
- `cs2idx`: file-scoped namespace、brace スタックの member 付与 / pop 順修正。
- `swift2idx`: actor/protocol/extension ラベル、async/throws 修飾子。
- `jv2idx`: annotation/record ラベル、複数行 text block 状態。
- `ts2idx`: class_stack/brace pop 順（cs パターン）、未使用 `matched` 削除（F841）。
- `dart2idx`: `extension Name on Type` のパターン順。
- `php2idx`: `_parse` が `_preprocess()` を使用（属性 + 複数行結合）。
- `cpp2idx`: brace スタックを `cs2idx` に合わせて修正（同レベル完了スコープを push 前に pop、`inside_function` でネスト誤検出を抑制）。同一行の `struct`/`class` が後続の自由関数をメンバーとして飲み込まないようにした。
- ツール JSON i18n: `cl2idx`/`dds2idx`/`rpg2idx` の非 en 全ロケール（33 言語。`x_search_terms_en` は英語のまま）。

### 修正

- `dds2idx`: DSPF インジケータ/表示属性デコード — 条件インジケータ、フィールド付帯の `DSPATR`/`COLOR`/`CFnn` 引数、packed 定数行（`5  2'Name'` → layout。form-type `A` の誤 field 化を修正）。
- `*2idx` の `mode=section` オフバイワン: 1-based の `entry["line"]` を 0-based スライス開始に使っていたため、単一行定義が空文字になっていた。dart/rs/ts/cpp/cs/jv/go/kt/swift の `_source_lines` / `get_section` を修正（他は既に変換済みまたは正しい）。
- Responses API の `previous_response_id` / OpenRouter: OpenRouter では `previous_response_id` を送らない（compat 除去 + プロバイダゲート、Grok と同様）。stale/invalid rid や `invalid_prompt` / `APIResponseValidationError`（文字列 `error.code`）時は rid をクリアし `_stale_rid_occurred` を立て、ローカル全履歴で 1 回リトライ。テスト: `test_previous_response_id_compat.py`、`test_openrouter_round_helpers.py`。

### メモ

- IBM i \*2idx（`cl2idx` / `dds2idx` / `rpg2idx`）の実装トラックは完了。実装オープン作業なし。
- 残件は **スコープ外** として `SPEC_CL2IDX_DDS2IDX.md` §5.9/§10 および DEVELOP に固定: EBCDIC; `ibmi2idx` ディスパッチャ（作らない）; `dds2idx` のマルチ lib/完全オブジェクト解決・DSPATR 全ビット意味論・PRTF 描画・ICF/binary; `rpg2idx` の全固定桁方言・埋め込み SQL 詳細意味・`/IF` 式評価。
- `rpg2idx`: 埋め込み SQL、`/IF` 条件コンパイル、主要固定桁パスは実装済み（SQL//IF は索引レベル）。
- `dds2idx`: REF/REFFLD 追従（同一 workdir・深さ 1）および DSPF インジケータ/表示属性/const デコードは実装済み。

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

## [0.6.0] - 2026-08-15

### 追加

- feat: 分散リーダーリース調整と永続タスクチェックポイントを追加
- feat: リモートエージェントタスク制御、チェックポイント復旧、A2Aタスクイベントのストリーミングを追加
- feat: 依存関係対応DAGスケジューラーと永続タスクストアを追加
- feat: 認証情報、MCP、スキル、プラグイン全体にエンタープライズポリシー適用を追加
- feat: 共有認証情報ストレージとランタイム間のライフサイクル/可観測性連携を追加

### 変更

- fix(deps): インストール済みの0.5.4リリースに合わせて `llmcapa` の固定バージョンを更新
- ci: 対応プラットフォームのテスト依存関係を分離・整備
- docs: 改善ロードマップ、ローカルCIチェック、アーキテクチャ、ポリシー案内を更新

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

## [0.6.0] - 2026-08-15

### 追加

- feat: 分散リーダーリース調整と永続タスクチェックポイントを追加
- feat: リモートエージェントタスク制御、チェックポイント復旧、A2Aタスクイベントのストリーミングを追加
- feat: 依存関係対応DAGスケジューラーと永続タスクストアを追加
- feat: 認証情報、MCP、スキル、プラグイン全体にエンタープライズポリシー適用を追加
- feat: 共有認証情報ストレージとランタイム間のライフサイクル/可観測性連携を追加

### 変更

- fix(deps): インストール済みの0.5.4リリースに合わせて `llmcapa` の固定バージョンを更新
- ci: 対応プラットフォームのテスト依存関係を分離・整備
- docs: 改善ロードマップ、ローカルCIチェック、アーキテクチャ、ポリシー案内を更新

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
