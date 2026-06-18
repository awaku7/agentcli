# 変更履歴

このプロジェクトの重要な変更箇所はすべてこのファイルに記録されます。

このフォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に基づいており、
このプロジェクトは [セマンティック バージョニング](https://semver.org/spec/v2.0.0.html) に準拠しています。

## [0.5.13] - 2026-06-18

### 新規追加
- Xiaomi MiMo (`mimo`) プロバイダ対応: OpenAI 互換 API、Reasoning/Thinking モード対応。
  - `UAGENT_MIMO_API_KEY`、`UAGENT_MIMO_BASE_URL`（デフォルト: `https://api.xiaomimimo.com/v1`）、`UAGENT_MIMO_DEPNAME`（デフォルト: `mimo-v2.5-pro`）。
  - DeepSeek の reasoning パスを流用し `reasoning_content` を処理。
  - env_validate、util_providers、setup_cli、runtime_banner を更新。
  - ENVIRONMENT.md ドキュメントを更新。
- 動的ツールカタログ: `tool_catalog` / `tool_load` による実行時検出（全ツールの事前読み込み不要）。
  - GUI/Web/A2A のジャンルチェックボックス切り替え。
  - README を 30 言語に翻訳（マルチプロバイダ、ツールカタログ機能）。
- i18n: 全ツール JSON スペックの 30 言語対応を完了。
  - bn, fa, mn, mr の翻訳を共有 JSON ファイルに追加。
  - 全ツール JSON ファイルを 30 言語に統一、Python コード由来の不足キーを補完。
  - vision_runtime.json を 29 言語に翻訳（10 のバックエンド/プロンプトキー）。
  - 6 ツール JSON ファイルを翻訳（bluesky, switchbot_batch, usb_camera, vision_deepseek, vision_ollama, vision_openai）。

### 修正
- cmd.exe cp932 環境での ANSI エスケープ文字化けを修正: `_reconfigure_stdio()` で `SetConsoleOutputCP(65001)` を呼び出すよう改善。

## [0.5.12] - 2026-06-18

### 修正
- VertexAI: `include_server_side_tool_invocations` をスキップ（Enterprise Agent Platform 非対応）。
- Gemini: ツールスキーマの dangling `required` キーを除去し 400 INVALID_ARGUMENT を回避。
- Claude/Gemini: `_rate_limit_retry_step` でハードコードではなく `provider` パラメータを使用。
- `_call_claude_round` / `_call_gemini_round`: 呼び出し元から `provider` を渡すよう修正（NameError 対策）。

## [0.5.11] - 2026-06-18

### 新規追加
- Z.AI (Zhipu AI) プロバイダ対応 (`UAGENT_PROVIDER=zai`)。デフォルトモデル: `glm-5.2`。
- ローカル GeoIP データベース対応: mmdb ファイルでオフラインIPジオロケーション (`UAGENT_GEOIP_DB_PATH` または同梱 `dbip-city-lite.mmdb`)。
- `get_geoip` に `ip` パラメータ追加（任意IPのルックアップ）。
- ツール並列実行（非同期）対応（`x_parallel_safe` フラグで opt-in）。
- ツールジャンルマスク (`--tool-genre-mask`)、ツールなしモード (`--no-use-tool`)。
- `skills_install` 実行前の安全確認プロンプト。
- UPnP Phase 2: デバイス情報ツール、スキャンフィルター、共有モジュール。
- `TOOL_ASYNC.md` 設計書。
- `LICENSE-THIRD-PARTY.md`（DB-IP Lite CC-BY 4.0 帰属表示）。
- アーカイブマージ: ローカル開発変更を全て復元し、origin/main の更新を維持。

### 修正
- `get_geoip` ツール登録問題を修正（`tool_level` 1 → 0）。
- `:tools on/off` の import 先を `genre_control_tool` に修正。
- `:cp`/`:mv` コマンドの引用符付きパス対応と作業ディレクトリ制限の撤廃。
- DeepSeek 400 エラー復旧と sanitize_messages の改善。

### 変更
- ロケールファイルを復元: Z.AI、--use-tool/--no-use-tool、Basic ジャンルの翻訳を全30ロケールに追加。
- llmcapa 依存関係を 0.2.2 に更新。

## [0.5.10] - 2026-06-18

### 修正
- get_geoip のツール登録がされない問題を修正（`tool_level` 1 → 0）。
- llmcapa 依存関係を 0.2.2 に更新。

## [0.5.9] - 2026-06-16

### 新規追加
- ClawHub マーケットプレイス対応: `skills_mp_search` に `source` パラメータ（`skillsmp` / `clawhub`）を追加。両方のマーケットプレイスから Agent Skill を検索・閲覧可能に。
- skills_mp_search ツールの全30言語 i18n（15キーを全ロケールに翻訳）。

### 変更
- 全30言語の README に SkillsMP および ClawHub マーケットプレイスへのアクセス方法を追記。

## [0.5.8] - 2026-06-15

### 新規追加
- prompt_toolkit TextArea による複数行入力モード（Ctrl+Xで送信、Escでキャンセル、従来の `"""end` 方式にフォールバック）。
- ツールジャンル選択UI: GUI（Toolsメニュー）、Web（ヘッダーのチェックボックス）、A2Aサーバー（起動時ダイアログ）。
- ツールジャンル選択はBUSY中は無効（IDLE時のみ変更可能）。
- get_geoip ツールを IoT ジャンルに移動（ジャンルマスクによる条件付きロード）。
- Web UI: LLM完了後のアシスタントメッセージをリアルタイム同期。
- Web UI: GET/POST /api/tool-genres エンドポイント（動的なジャンル切り替え）。
- human_ask で `[REPLY] >` プロンプトを表示するように改善。

## [0.5.7] - 2026-06-15

### 変更
- プロバイダ識別子を `kimi` から `moonshot` に変更 (UAGENT_PROVIDER=moonshot)。
- 環境変数を `UAGENT_KIMI_*` から `UAGENT_MOONSHOT_*` に変更。
- black フォーマットを39ファイルに適用しコードスタイルを統一。
- ruff の lint エラーを修正（無効な例外構文、未使用インポート、1行文）。
- mypy の型エラーを修正（dict 注釈、used-before-def、truthy-function チェック）。

## [0.5.6] - 2026-06-15

### 新規追加
- USBカメラツール (`usb_camera`): 撮影、デバイス一覧、能力取得（クロスプラットフォーム）。
- 画像解析に Alibaba Cloud (Qwen) プロバイダを追加。
- 画像解析に Kimi (Moonshot AI) プロバイダを追加。
- DeepSeek ビジョンバックエンド（Vision対応エンドポイントが必要）。
- USBカメラに `list_caps` アクション（対応解像度/FPSの表示）。

### 変更
- 全30ロケールのツール説明文を短縮（約8K文字 / 約2Kトークン削減）。
- ツールスペックからエイリアスパラメータを削除（path/filename, root_path/path 等）。
- 全ツールスペックから不要な `system_prompt` フィールドを削除。
- 31個のパラメータキーを短縮 (output_format→fmt, max_results→limit 等)。
- USBカメラのクロスプラットフォーム対応 (dshow/v4l2/avfoundation)。

### 修正
- Ruff警告の修正: 例外構文、未使用変数、未定義名。
- USBカメラのffmpeg cp932デコードエラーを修正。

## [0.5.5] - 2026-06-15

### 新規追加
- SwitchBot赤外線リモコン対応: TV/エアコン/ライトの on/off、明るさ、エアコンモード・風速指定。
- SwitchBotバッチツール: 複数コマンドを一括実行。
- Blueskyツール: 投稿（テキスト＋画像）、プロフィール、検索、タイムライン、スレッド、いいね、通知。
- Bluesky `lang` パラメータ (BCP-47): 多言語投稿対応＋バリデーション。
- Bluesky 画像アップロードと自動保存・表示（CLI/Web/GUI）。
- COMMUNICATION.md: bluesky/discord/teams のコミュニケーションツールドキュメント。
- README.md および全翻訳ファイルに IoT セクションを追加。

### ドキュメント
- IOT_USECASE.ja.md / IOT_USECASE.md を新ツール・バッチ対応に更新。

## [0.5.4] - 2026-06-15

### 修正
- ストリーミング有効時のDeepSeek重複最終出力を抑制。
- DeepSeek 400エラー防止のため auto_user_msg 挿入を遅延。

## [0.5.3] - 2026-06-15

### 新規追加
- DeepSeek専用プロバイダモジュール（thinking mode / reasoning_effort対応）。
- DeepSeekセットアップウィザード統合。
- DeepSeek用 temperature / top_p / presence_penalty / frequency_penalty 設定（非thinking時）。
- zh_CN / zh_TW 翻訳・README。
- provider_caps.py（プロバイダ機能管理用）。

### ドキュメント
- ENVIRONMENT.md / ENVIRONMENT.ja.md のプロバイダ一覧にDeepSeekを追加。

### 修正・改善
- ロケール .mo ファイルを再コンパイル。
- その他修正。

## [0.5.2] - 2026-06-13

### 新規追加
- `llmcapa` 依存関係を `0.1.2` に更新。

### 修正・改善
- Claude の reasoning_effort 判定をモデルファミリに合わせて整理。
- 利用可能な場合に Gemini のサーバーサイド tool invocation を有効化。

## [0.5.1] - 2026-06-12

### 新規追加
- 起動時の genre 選択プロンプトを各ロケールへ翻訳。

### 修正・改善
- 起動メニューの genre 選択フローを整理し、入力まわりを改善。

## [0.5.0] - 2026-06-11

### 新規追加
- UPnP IGD の探索で重複する service エントリを除去し、実際の WANIPConnection を優先するように変更。
- UPnP ポートマッピングの lease_duration 未指定時の既定値を 60分に変更。
- GeoIP ツールの検索優先度を下げ、通常のツール探索に出にくいように変更。

### 修正・改善
- Matter の device / endpoint / cluster 一覧で controller_id と bridge_id で重複排除するよう改善。
- ECHONET Lite の interface 解決で仮想アダプタを避け、フォールバックを強化。
- IoT 用途説明ドキュメントと関連テストを現行のツール構成に合わせて更新。

## [0.4.46] - 2026-06-10

### 新規追加
- **クラシックBluetooth機器のスキャンサポート**:
  - `ble_ops` ツールを拡張し、PySide6 を使用してクラシックBluetooth機器とBLE機器を同時にスキャンできるように改善。
  - `ble_ops` ツールに新しい `scan_mode` パラメータを追加.
  - BLEスキャン時に `BLEDevice` オブジェクトに `rssi` 属性が存在しないバグを修正。

## [0.4.45] - 2026-06-10

### 新規追加
- **推論・思考バジェットの動的判定サポート**:
  - `llmcapa` を使用して、モデルが reasoning_effort (Claude) または thinking_budget (Gemini) をサポートしているかを動的に判定するよう改善。
  - `llmcapa` の依存関係を `0.1.1` に更新。

## [0.4.44] - 2026-06-10

### 新規追加
- **llmcapa の統合**:
  - モデルのコンテキストウィンドウを動的に解決し、自動縮小の上限値を計算するために `llmcapa` ライブラリを統合。
  - ハードコードされていた巨大な `DEFAULT_SHRINK_LIMITS` 辞書を削除し、動的計算に移行。
  - 安全マージンをカスタマイズするための環境変数 `UAGENT_SHRINK_RATIO`（デフォルト: `0.5`）のサポートを追加。

## [0.4.43] - 2026-06-09

### 新規追加
- **トークンベースの自動縮小トリガー**:
  - コンテキストサイズを効率的に管理するため、モデル固有のデフォルト値を持つトークンベースの自動縮小トリガーを実装。
- **パッケージ構造のリファクタリング**:
  - メンテナンス性向上のため、`uagent` パッケージ構造を `providers`、`runtime`、`tools` に再編成。

### 修正・改善
- **設定のデフォルト値**:
  - 予期しないコンテキスト縮小を防ぐため、`UAGENT_SHRINK_CNT` のデフォルト値を 0（無効）に変更。

## [0.4.42] - 2026-06-08

### 新規追加
- **Generative UI (Artifacts) のサポート**:
  - リアルタイムでの HTML/CSS/JS コードブロックの抽出と、専用プレビューパネルでのレンダリング機能を実装。
  - アシスタントが生成した HTML コンテンツに対して、インタラクティブな「✨ Open in Preview」ボタンを追加。
  - チャットUI内でコードブロックを自動的に折りたたむ（`<details>`）機能を追加し、会話をスッキリと整理。

### 修正・改善
- **Web UI の強化**:
  - ダークモード時のチャット吹き出し内の文字コントラストを向上。
  - チャット吹き出し内のアスキーアートやターミナル出力の改行と等幅フォント表示を修正。

## [0.4.41] - 2026-06-07

### 新規追加
- **開発者向けツールジャンルの拡充**:
  - `system_reload`、`git_ops`、`playwright_inspector`、および `binary_edit` ツールに `tool_genre="devel"` を追加。
- **Web UI の強化**:
  - 起動時に外部 URL を表示する機能を追加し、関連するテストを修正。

### 修正・改善
- **国際化 (i18n)**:
  - 400 BadRequest から `_t()` を削除し、すべてのロケールを更新して `same_as_en` エントリを 0 件に。
  - 全28言語の翻訳を完了し、未翻訳（empty）エントリを 0 件に。
  - 新たに抽出された22個の文字列に対する日本語翻訳を追加。
  - `babel.cfg` の対象範囲に基づき、POT および PO/MO ファイルを再構築。
- **Gemini の安定性向上と i18n**:
  - Gemini のストリーム中断エラーメッセージに対する i18n サポートおよび28言語の翻訳を追加。
  - `UAGENT_GEMINI_MAX_OUTPUT_TOKENS` をサポートし、ストリーム中断時にエラーを表示するように修正。

- **Gemini 組み込み Google 検索サポート**:
  - Gemini API および Vertex AI において、組み込みの Google 検索（Google Search Grounding）を直接利用できる機能を追加。
  - 環境変数 `UAGENT_GEMINI_WEB_SEARCH` を用いて制御可能とし、デフォルトで有効（ON）に設定。有効時はローカルの Web 検索ツールを自動的に無効化。
- **動的スキルヘルプの強化**:
  - 動的なスキルコマンドヘルプ機能を追加。
  - スキルインストールツール (`skills_install_tool`) のローカライズ対応。
  - スキル検出パスに `.uag` スキルルートを追加。

### 変更・最適化
- **`replace_in_file` ツールの最適化**:
  - 一致件数制限（`match_hits`）の診断機能を強化し、再帰スキャン時の除外ディレクトリ設定を追加することでパフォーマンスを大幅に向上。
- **Claude 連携の強化**:
  - 動的な `max_tokens` 設定、思考ブロック（thinking block）のパース処理、およびマルチモーダル画像サポートを強化。
  - `UAGENT_CLAUDE_TEMPERATURE` が明示的に設定されていない場合はデフォルトの温度を設定しないように修正。
  - `output_config` 使用時に `temperature` を除外し、非推奨となったパラメータのフォールバック処理を追加。
- **Gemini 安定性の向上**:
  - 空の応答に対するナッジ（促し）処理を適用し、サイレントブロックを防ぐための安全設定を最適化。
  - `test_list_dir_tool` のフォーマット修正、`test_libcst_transform_smoke` の削除、および `sub_agent_tool` の翻訳修正。

## [0.4.39] - 2026-05-22

### 新規追加
- **ロケール MO の再生成**:
  - ロケール更新に合わせて、すべてのコンパイル済み `.mo` 翻訳ファイルを再生成。
  - リポジトリ全体の多言語メッセージカタログを更新。

## [0.4.38] - 2026-05-22

### 新規追加
- **専門サブエージェントツール (`run_sub_agent`)**:
  - 親オーケストレーターの制御下で動作する、安全で高度な専門サブエージェントを新規実装。
  - 対応ロール: `planner` (計画設計), `reviewer` (コード監査), `summarizer` (文脈要約), `patch_designer` (安全なパッチ提案), および `error_analyst` (実行エラー/例外デバッグ)。
  - 同一タスクに対する連続的な無限ループの暴走を厳格に阻止する `DuplicateCallGuard` を標準装備。
  - ファイルアクセスの安全性を強固に確保する厳格なパスピン留めガードレールを実装。
- **多言語対応 (30言語)**:
  - 世界30カ国語を網羅した完全なローカライズリソースファイル (`sub_agent_tool.json`) を構築。
  - I18N多言語スモークテスト (`test_tools_i18n_smoke.py`) における全テストケースの通過を検証完了。
- **サブエージェント拡張ロードマップ (`TODO_subagent.md`)**:
  - 将来的なサブエージェントの拡張構想や開発ログを一元管理するロードマップ台帳を追加。
- **スキルの保守**:
  - すべての SKILL.md の YAML フロントマターの記述不備を修復し、エージェントによる `:skills` コマンド検出機能を完全に復旧。

---

## [0.4.37] - 2026-05-22

### 変更
- **Python 3.11+ への近代化**:
  - リポジトリ内のすべての Python ソースコードを最新の Python 3.11+ 規格に合わせて更新。
  - 最新の型定義構文の標準化、および非推奨となったインポートのクリーンアップ。
- **サブエージェントアーキテクチャ設計**:
  - 親エージェント統治とガードレールを備えたサブエージェント実行方式の設計書を策定。

## [0.4.36] - 2026-05-15

### 変更
- **検索語の正規化**:
  - カタログ検索でよりスマートにマッチするように、ツールスペックJSON内の `x_search_terms` を一括正規化。

## [0.4.35] - 2026-05-10

### 新規追加
- **バッチ状態台帳ツール & 設計**:
  - 進捗や対象ファイルを記録するための `batch_state` 追跡管理ツール、実装設計、および検証用スモークテストを追加。
- **ローカライズと言語プロンプトの刷新**:
  - コアな各種言語ファイルリソース、およびLLMのシステムプロンプト定義を刷新。

## [0.4.34] - 2026-05-02

### 新規追加
- **多言語サポートの拡張**:
  - `bn` (ベンガル語), `fa` (ペルシャ語), `mn` (モンゴル語), `mr` (マラーティー語) の完全な翻訳リソースを追加。
  - ルートの `README.md` にある多言語翻訳リンク一覧を同期・更新。
- **多言語カタログ検索機能の強化**:
  - 英語以外の言語でのツールスペック検索精度を飛躍的に向上させるトークン化処理を追加。

## [0.4.32] - 2026-04-25

### 新規追加
- **リッチログと添付ファイル処理の追加**:
  - ANSIカラー出力ログのパース、および各種添付ファイル構造のハンドリング機能を実装。
  - ターミナルログを美しく出力するための HTML レンダリングヘルパーを追加。
