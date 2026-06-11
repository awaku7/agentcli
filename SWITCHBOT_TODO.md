# SWITCHBOT ツール仕様 TODO

## 目的

`uag` に SwitchBot 関連ツール群を追加する。
最初は Cloud API の一覧・状態確認を実装し、その後 BLE 探索・状態確認、最後に操作系へ拡張する。

## 前提

- Tool Genre: `iot`
- Windows での動作を優先して確認する
- 出力は機械処理しやすい JSON を基本にする
- 必要に応じて text 出力も提供する
- 秘密情報は長期保存しない
- 既存の `uag` のツール体系に合わせる

## 共通仕様

### 返却形式

- 成功時は `ok: true` と主要データを返す
- 失敗時は `ok: false` と `error` を返す
- 可能なら `count` / `items` / `device` / `capabilities` を使う
- `output_format` の既定値は `json`

### 代表的なエラー

- `auth_missing`
- `not_found`
- `ambiguous_target`
- `network_error`
- `timeout`
- `unsupported_device`
- `invalid_argument`

### 認証情報の解決順

- 既存の設定値
- 環境変数
- それでも不足する場合はエラー

### 環境変数候補

- `SWITCHBOT_TOKEN`
- `SWITCHBOT_SECRET`

## ツール設計方針

- `switchbot_*` で統一する
- 1 ツール 1 役を基本にする
- Cloud 系と BLE 系は分ける
- まずは一覧・状態確認を優先する
- 取得できない項目は `null` か省略で統一する

## 追加予定の段階

### Phase 1: Cloud 読み取り

- Cloud 機器一覧取得ツール
- Cloud 機器状態取得ツール
- JSON / text 出力
- 機器名、型、状態を確認できる
- 読み取り専用

### Phase 2: Cloud 操作

- Cloud 機器操作ツール
- on / off / open / close / set value 系
- 主要機器タイプへの対応
- 操作失敗時の理由整理

### Phase 3: BLE 読み取り

- BLE 機器探索ツール
- BLE 機器状態取得ツール
- 機器識別
- 読み取り専用
- 対象指定の安定化

### Phase 4: BLE 操作

- BLE 簡易制御ツール
- 対応機器のみ操作
- 未対応機器は明示的に返す

### Phase 5: 共通基盤

- Cloud と BLE の共通ユーティリティ整理
- キャッシュ
- ログ強化
- テスト拡充
- 実運用向けのエラーハンドリング改善

## Phase 1 の具体仕様

### switchbot_cloud_list

- 役割: Cloud API からアカウント配下の機器一覧を取得する
- 入力:
  - `output_format`（省略時は `json`）
- 出力:
  - `ok`
  - `count`
  - `items[]`
  - `account`
  - `fetched_at`
- `items[]` の主な要素:
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

### switchbot_cloud_status

- 役割: Cloud API から指定機器の状態を取得する
- 入力:
  - `device_id` もしくは `device_name`
  - `output_format`（省略時は `json`）
- ルール:
  - `device_id` を優先する
  - `device_name` は補助指定とする
  - 1 件に確定できない場合は `ambiguous_target` を返す
- 出力:
  - `ok`
  - `device`
  - `status`
  - `capabilities`
  - `last_updated`
- `device` の主な要素:
  - `device_id`
  - `device_name`
  - `device_type`
  - `hub_id`
  - `battery`
  - `online`
  - `reachable`
- `status` の主な要素:
  - `power`
  - `mode`
  - `position`
  - `temperature`
  - `humidity`
  - `lock_state`

## BLE 側の想定

### switchbot_ble_scan

- 役割: 近傍 SwitchBot 機器の探索
- 入力:
  - `timeout`
  - `retry`
  - `limit`
  - `output_format`
  - `device_name`（任意）
  - `mac_address`（任意）
  - `service_uuid`（任意）
- 出力:
  - `ok`
  - `count`
  - `items[]`
  - `elapsed_ms`
  - `interface_used`
- `items[]` の主な要素:
  - `name`
  - `address`
  - `rssi`
  - `device_type`
  - `service_uuids`
  - `manufacturer_data`
  - `connectable`

### switchbot_ble_status

- 役割: BLE 機器の状態読み取り
- 入力:
  - `mac_address` もしくは `device_name`
  - `service_uuid`（任意）
  - `timeout`
  - `output_format`
- ルール:
  - `mac_address` を優先する
  - `device_name` は補助指定とする
- 出力:
  - `ok`
  - `device`
  - `status`
  - `capabilities`
- `status` の主な要素:
  - `power`
  - `position`
  - `temperature`
  - `humidity`
  - `battery`
  - `last_seen`

### switchbot_ble_control

- 役割: BLE 機器の簡易制御
- 入力:
  - `mac_address` もしくは `device_name`
  - `action`
  - `value`（必要な場合のみ）
  - `timeout`
  - `output_format`
- `action` 例:
  - `on`
  - `off`
  - `open`
  - `close`
  - `set_value`
- 出力:
  - `ok`
  - `applied`
  - `device`
  - `result`

## 実装メモ

- Cloud API の認証情報は安全に扱う
- BLE は近距離通信なのでタイムアウトを短めに設計する
- まずは一覧取得で実用性を確認する
- Cloud と BLE は別ツールとして分ける
- 失敗理由はユーザー向けに短く返す

## 補足

- 最初は一覧取得と状態確認で十分に実用性を確認する
- その後、Cloud 操作と BLE 操作を追加する
- 将来的には機器タイプごとの共通ラッパーも検討する
- 秘密情報はログに残さない
