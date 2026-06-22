# MATTER ツール仕様 TODO

## 目的

`uag` に Matter 関連ツール群を追加する。
現行実装では、ローカル設定(JSON / 環境変数)を読み取り、コントローラー・ブリッジ・デバイスの状態を確認できる構成にする。

## 前提

- Tool Genre: `iot`
- コントローラー経由とブリッジ経由の両方を扱う
- 依存ライブラリは最小限にする
- Windows での動作を優先して確認する
- 出力は機械処理しやすい JSON を基本にする
- 必要に応じて text 出力も提供する
- 秘密情報は長期保存しない
- 必要な環境変数を追加する場合は `UAGENT_` を接頭辞にして統一する
- 既存の `uag` のツール体系に合わせる

## 現状の実装方針

- Matter の接続先ごとに専用アダプタを持たず、まずはローカル設定を正規化して扱う
- 読み取り専用を基本とし、制御は将来拡張とする
- `ctrl` / `bridge` / `dev` / `endpoint` で対象を明確化する
- 取得できない項目は `null` か省略で統一する

## 共通ルール

### 返却形式

- 成功時は `ok: true` と主要データを返す
- 失敗時は `ok: false` と `error` を返す
- 可能なら `count` / `items` / `device` / `endpoints` / `clusters` を使う
- `fmt` の既定値は `json` とする

### 代表的なエラー

- `config_missing`
- `not_found`
- `ambiguous_target`
- `invalid_argument`
- 将来予約: `network_error`, `timeout`, `unsupported_device`

### 入力方針

- コントローラー系は `ctrl`, `endpoint` などを受ける
- ブリッジ系は `bridge`, `dev`, `endpoint` などを受ける
- `ctrl` / `bridge` 省略時は全件対象とする
- 操作系は対象デバイスと操作パラメータを明示する

## ツール設計方針

- `matter_*` で統一する
- 1 ツール 1 役を基本にする
- コントローラー系とブリッジ系を分ける
- まずは一覧・状態確認を優先する
- 取得できない項目は `null` か省略で統一する
- Phase 1 は読み取り専用に固定する

## 実装状況

### Phase 1: 読み取り専用 ✅ 完了

- matter_controller_list / matter_bridge_list / matter_device_status
- matter_endpoint_list / matter_cluster_list
- JSON / text 出力対応済み
- エラーコード: config_missing / not_found / ambiguous_target / invalid_argument

### Phase 2: 詳細取得 ✅ 完了

- Room/Area/Floor 情報の抽出 (全ツール共通 `_extract_location`)
- デバイスタイプ別属性正規化 (light/sensor/lock/thermostat/cover/switch/fan)
- Endpoint/Cluster の構造化

### Phase 3: 制御 ✅ 完了

- matter_control ツール実装済み
- アクション: on / off / open / close / lock / unlock / set_value
- デバイスタイプ別のアクション制限 (dry_run 検証対応)
- UAGENT_MATTER_COMMAND_JSON / UAGENT_MATTER_COMMAND_FILE 経由のキューイング

### Phase 4: 未着手

#### 4-1. イベント購読 (Event Subscription)

目的: Matter デバイスの状態変化をポーリングではなく購読ベースで受け取る。

仕様案:
- 新規ツール `matter_subscribe`（または既存ツールへの subscribe パラメータ追加）
- 入力:
  - `dev`（必須）: 購読対象デバイスID
  - `endpoint`（任意）: 特定エンドポイントのみ購読
  - `cluster`（任意）: 特定クラスタのみ購読
  - `attribute`（任意）: 特定属性のみ購読
  - `min_interval`（任意, 既定: 0）: 最小通知間隔（秒）
  - `max_interval`（任意, 既定: 300）: 最大通知間隔（秒）
  - `duration`（任意, 既定: 3600）: 購読持続時間（秒）
- 出力:
  - `ok`
  - `subscription_id`
  - `subscribed_to`
  - `expires_at`
- 購読管理:
  - 購読一覧ツール `matter_subscription_list`（アクティブな購読を表示）
  - 購読解除ツール `matter_unsubscribe`（subscription_id 指定で解除）
- イベント通知の保存先:
  - 環境変数 `UAGENT_MATTER_EVENTS_JSON` または `UAGENT_MATTER_EVENTS_FILE` に追記
  - 各イベントはタイムスタンプ付きで追記（JSON Lines 形式）
- 制約:
  - 同一デバイスへの重複購読は禁止（上書き or エラー）
  - 購読数上限: 環境変数 `UAGENT_MATTER_MAX_SUBSCRIPTIONS`（既定 10）

#### 4-2. 状態更新の追跡 (State Tracking)

目的: デバイスの状態変化を時系列で追跡できるようにする。

仕様案:
- 購読または定周期ポーリングで状態を収集
- 状態履歴は `UAGENT_MATTER_STATE_HISTORY_JSON` / `UAGENT_MATTER_STATE_HISTORY_FILE` に記録
  - 形式: JSON Lines、1行1スナップショット
  - 各エントリ: `{ "ts": "ISO8601", "dev": "...", "attribute": "...", "old": ..., "new": ... }`
- 新規ツール `matter_state_history`:
  - 入力:
    - `dev`（必須）
    - `attribute`（任意）: 特定属性のみフィルタ
    - `since`（任意）: 開始時刻（ISO8601）
    - `until`（任意）: 終了時刻（ISO8601）
    - `limit`（任意, 既定 100）: 最大件数
    - `fmt`（任意, 既定 json）
  - 出力: `ok` / `count` / `items[]` / `device` / `fetched_at`
- 履歴管理:
  - 最大保存件数: `UAGENT_MATTER_STATE_HISTORY_MAX`（既定 10000）
  - 超過時は古いものから削除
  - `matter_state_history_clear` で全消去可能

#### 4-3. キャッシュ (Caching)

目的: 同一デバイスへの同一クエリの再実行によるオーバーヘッドを削減する。

仕様案:
- キャッシュはツール内部で透過的に行う（LLMからは意識不要）
- キャッシュキー: `{dev}:{ctrl}:{bridge}:{endpoint}`
- キャッシュ有効期限: 環境変数 `UAGENT_MATTER_CACHE_TTL`（既定 60 秒）
- キャッシュの保存先:
  - デフォルト: プロセス内メモリ（`dict`）
  - 永続化オプション: `UAGENT_MATTER_CACHE_FILE` 指定時はファイルに保存
- 新規ツール `matter_cache_status`:
  - 入力なし
  - 出力: `ok` / `cached_entries` / `cache_size_bytes` / `cache_ttl`
- キャッシュクリア: ツール内では行わず、プロセス再起動またはファイル削除で対応
- 制約:
  - 制御系（matter_control）の結果はキャッシュしない
  - 書き込み操作後は該当デバイスのキャッシュを削除する

#### 4-4. ログ強化 (Logging)

目的: デバッグと障害追跡を容易にする。

仕様案:
- 各ツールの実行ログを構造化して記録
- ログ保存先: `UAGENT_MATTER_LOG_DIR`（既定: `outputs/matter/`）
  - ファイル名: `matter_{tool_name}_%Y%m%d.log`
- ログフォーマット: JSON Lines
  - 各エントリ: `{ "ts": "ISO8601", "tool": "...", "args": {...}, "ok": true/false, "elapsed_ms": 123, "error": {...} }`
- ログレベル: `UAGENT_MATTER_LOG_LEVEL`（debug / info / warn / error, 既定 info）
- debug レベルのみ raw データ（設定JSONの一部）を含める
- ログローテーション: 1日単位、30日保持（`UAGENT_MATTER_LOG_RETENTION_DAYS`）
- ログには機密情報（APIキーなど）を含めない（マスク処理）
- 既存ツールのログ出力強化（各 run_tool の入出力を構造化ログに追加）

#### 4-5. テスト拡充 (Testing)

目的: 各ツールの品質を担保する。

仕様案:
- テスト用の Matter 設定JSONフィクスチャを作成する
  - コントローラー・ブリッジ・デバイス（light/sensor/lock/thermostat/cover/switch）
  - 正常系データと異常系データ（フィールド欠落、型違い、空配列）
- テストカテゴリ:
  - 正常系: 各ツールの全パラメータ組み合わせ
  - 異常系: config_missing / not_found / ambiguous_target / invalid_argument
  - エッジケース: 空リスト、null 値、想定外のキー
  - text 出力形式の確認
- テストツール: pytest
- テスト配置: `tests/test_matter_tools.py`
  - 各ツールごとにテストクラスを分割
  - `monkeypatch` で環境変数を差し替え
- カバレッジ目標:
  - Phase 1-3 の既存コード: 80%以上
  - Phase 4 追加コード: 70%以上

#### 4-6. エラーハンドリング改善 (Error Handling)

目的: 実運用でのエラーをユーザーとLLMにわかりやすく伝える。

仕様案:
- 新規エラーコード追加:
  - `network_error`: 外部サービスへの接続失敗
  - `timeout`: 操作のタイムアウト
  - `unsupported_device`: 操作対象外のデバイス種別
  - `rate_limit`: レート制限超過
- エラーメッセージの多言語対応:
  - 現在は `_.py` の tool translation で一部対応済み
  - 不足しているエラーメッセージキーを `.spec.json` または JSON翻訳に追加
- リトライ機構:
  - `network_error` / `timeout` 発生時に最大 3 回リトライ（`UAGENT_MATTER_RETRY_MAX`）
  - リトライ間隔: 指数バックオフ（1s, 2s, 4s）
  - dry_run と実際のキューイングの両方に適用
- LLM向けエラー情報の充実:
  - エラー時に `recovery_hint` フィールドを追加
  - 例: `"recovery_hint": "Check UAGENT_MATTER_CONTROLLERS_JSON or UAGENT_MATTER_CONTROLLERS_FILE"`
- 警告の構造化:
  - 一部の重要でないエラー（例: 設定ファイルの一部欠落）は warning とし、処理を継続
  - 出力に `warnings[]` フィールドを追加

## 現行ツール仕様

### matter_controller_list ✅

- パラメータ: `ctrl`（任意）/ `fmt`（任意、既定: `json`）
- 出力: `ok` / `count` / `items[]` / `controller` / `fetched_at`
- items[].主キー: `ctrl` / `controller_name` / `device_count` / `bridge_ids` / `transport` / `reachable` / `last_updated`

### matter_bridge_list ✅

- パラメータ: `bridge`（任意）/ `fmt`（任意、既定: `json`）
- 出力: `ok` / `count` / `items[]` / `bridge` / `fetched_at`
- items[].主キー: `bridge` / `bridge_name` / `ctrl` / `device_count` / `device_ids` / `transport` / `reachable` / `last_updated`

### matter_device_status ✅

- パラメータ: `dev`（必須）/ `ctrl`（任意）/ `bridge`（任意）/ `endpoint`（任意）/ `fmt`（任意、既定: `json`）
- ルール: `dev` 必須。`ctrl`/`bridge` は曖昧回避の補助指定。曖昧時は `ambiguous_target`。
- 出力: `ok` / `device` / `status` / `endpoints` / `clusters` / `fetched_at`
- device.主キー: `dev` / `devname` / `device_type` / `vendor` / `bridge` / `ctrl` / `reachable` / `last_updated`
- endpoints[].主キー: `endpoint_id` / `clusters[]` / `device_type`
- clusters[].主キー: `cluster_id` / `cluster_name` / `attributes` / `commands`

### matter_endpoint_list ✅

- パラメータ: `dev`（必須）/ `ctrl`（任意）/ `bridge`（任意）/ `fmt`（任意、既定: `json`）
- 出力: `ok` / `count` / `items[]` / `endpoints` / `device` / `fetched_at`

### matter_cluster_list ✅

- パラメータ: `dev`（必須）/ `ctrl`（任意）/ `bridge`（任意）/ `endpoint`（任意）/ `fmt`（任意、既定: `json`）
- 出力: `ok` / `count` / `items[]` / `clusters` / `endpoints` / `device` / `fetched_at`

### matter_control ✅

- パラメータ: `dev`（必須）/ `action`（必須）/ `value`（任意, 0-100）/ `ctrl`（任意）/ `bridge`（任意）/ `dry_run`（任意）/ `fmt`（任意、既定: `json`）
- action一覧: `on` / `off` / `open` / `close` / `lock` / `unlock` / `set_value`
- デバイスタイプ別にサポートするアクションを制限（`dry_run` で事前検証可能）
- キューイング先: `UAGENT_MATTER_COMMAND_JSON` 環境変数 または `UAGENT_MATTER_COMMAND_FILE`
- 出力: `ok` / `command` / `device` / `fetched_at`

## 実装メモ

- Matter は実装経路が複数あるため、入力の正規化を先に固める
- `UAGENT_MATTER_CONTROLLERS_JSON` / `UAGENT_MATTER_CONTROLLERS_FILE`
- `UAGENT_MATTER_BRIDGES_JSON` / `UAGENT_MATTER_BRIDGES_FILE`
- `UAGENT_MATTER_DEVICES_JSON` / `UAGENT_MATTER_DEVICES_FILE`
- まずは一覧取得で実用性を確認する
- コントローラー系とブリッジ系は別ツールとして分ける
- 失敗理由はユーザー向けに短く返す

## 補足

- 最初は一覧取得と状態確認で十分に実用性を確認する
- その後、詳細取得と簡易制御を追加する
- 最終的にはコントローラー経由とブリッジ経由を両方扱える構成にする
- 秘密情報はログに残さない
