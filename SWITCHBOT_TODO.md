# SWITCHBOT ツール仕様 TODO

## 目的

`uag` に SwitchBot 関連ツール群を追加する。
まずは Cloud API の一覧・状態確認、次に BLE の探索・状態確認、その後に操作系へ拡張する。

## 前提

- Tool Genre: `iot`
- Cloud API と BLE を別ツールで分ける
- Windows 優先で確認する
- 出力は JSON を基本にする
- 必要なら text も返す
- 秘密情報は長期保存しない
- 既存の `uag` のツール体系に合わせる

## 共通ルール

### 返却形式

- 成功時: `ok: true` と主要データ
- 失敗時: `ok: false` と `error`
- 可能なら `count` / `items` / `device` / `capabilities`
- `output_format` の既定値は `json`

### エラー形式

- `config_missing`
- `auth_missing`
- `not_found`
- `ambiguous_target`
- `network_error`
- `timeout`
- `unsupported_device`
- `invalid_argument`
- `request_failed`

### 入力方針

- Cloud 系は認証情報を内部で解決する
- BLE 系は `interface`, `timeout`, `retry`, `limit` を受ける
- 対象指定は `device_id`, `device_name`, `mac_address`, `service_uuid` を使う
- 操作系は対象と操作パラメータを明示する

## 1. Cloud API

### 認証

- 環境変数から解決する
  - `UAGENT_SWITCHBOT_TOKEN`
  - `UAGENT_SWITCHBOT_SECRET`
- 署名付きリクエストを使う
- 標準ライブラリ中心で実装する

### `switchbot_cloud_list`

**役割**: アカウント配下の機器一覧を取得する。

**入力**
- `output_format` 省略可

**出力**
- `count`
- `items[]`
- `account`
- `fetched_at`

**items の主な要素**
- `device_id`
- `device_name`
- `device_type`
- `hub_id`
- `room_id`
- `model`
- `firmware`
- `online`
- `battery`
- `last_updated`
- `source`

### `switchbot_cloud_status`

**役割**: 1台の状態を取得する。

**入力**
- `device_id` 優先
- `device_name` 補助
- `output_format` 省略可

**ルール**
- `device_id` を優先する
- 複数一致なら `ambiguous_target`
- 見つからなければ `not_found`

**出力**
- `device`
- `status`
- `capabilities`
- `last_updated`

**device の主な要素**
- `device_id`
- `device_name`
- `device_type`
- `hub_id`
- `online`
- `battery`
- `reachable`

## 2. BLE

### `switchbot_ble_scan`

**役割**: 近傍の SwitchBot 機器を探索する。

**入力**
- `interface`
- `timeout`
- `retry`
- `limit`
- `device_name`
- `mac_address`
- `service_uuid`
- `output_format`

**出力**
- `count`
- `items[]`
- `interface_used`
- `elapsed_ms`

**items の主な要素**
- `name`
- `address`
- `rssi`
- `device_type`
- `service_uuids`
- `manufacturer_data`
- `connectable`

### `switchbot_ble_status`

**役割**: BLE 機器の状態を読み取る。

**入力**
- `mac_address` 優先
- `device_name` 補助
- `service_uuid` 任意
- `timeout`
- `output_format`

**出力**
- `device`
- `status`
- `capabilities`

### `switchbot_ble_control`

**役割**: BLE 機器を簡易操作する。

**入力**
- `mac_address` または `device_name`
- `action`
- `value` 必要時のみ
- `timeout`
- `output_format`

**action 例**
- `on`
- `off`
- `open`
- `close`
- `set_value`

## 3. 実装段階

### Phase 1: Cloud 読み取り

- `switchbot_cloud_list`
- `switchbot_cloud_status`
- JSON / text 出力
- 認証情報の解決

### Phase 2: Cloud 操作

- 電源系
- オープン / クローズ系
- 値設定系
- 失敗理由の整理

### Phase 3: BLE 読み取り

- `switchbot_ble_scan`
- `switchbot_ble_status`
- 対象指定の安定化

### Phase 4: BLE 操作

- `switchbot_ble_control`
- 対応機器のみ実行
- 未対応は明示的に返す

### Phase 5: 共通基盤

- 共通ユーティリティ整理
- キャッシュ
- ログ強化
- テスト拡充
- 実運用向けのエラーハンドリング改善

## 実装メモ

- Cloud と BLE は混ぜずに分ける
- 取得できない項目は `null` か省略で統一する
- 失敗理由は短く返す
- まずは一覧取得と状態確認を優先する
- Windows での確認を優先する

## 補足

- 最初は一覧取得と状態確認で十分に実用性を確認する
- その後、Cloud 操作と BLE 操作を追加する
- 将来的には機器タイプごとの共通ラッパーも検討する
- 秘密情報はログに残さない
