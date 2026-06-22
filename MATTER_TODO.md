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

- イベント購読
- 状態更新の追跡
- キャッシュ
- ログ強化
- テスト拡充
- 実運用向けのエラーハンドリング改善

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
