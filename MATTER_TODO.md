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
- `controller_id` / `bridge_id` / `device_id` / `endpoint` で対象を明確化する
- 取得できない項目は `null` か省略で統一する

## 共通ルール

### 返却形式

- 成功時は `ok: true` と主要データを返す
- 失敗時は `ok: false` と `error` を返す
- 可能なら `count` / `items` / `device` / `endpoints` / `clusters` を使う
- `output_format` の既定値は `json` とする

### 代表的なエラー

- `config_missing`
- `not_found`
- `ambiguous_target`
- `invalid_argument`
- 将来予約: `network_error`, `timeout`, `unsupported_device`

### 入力方針

- コントローラー系は `controller_id`, `endpoint`, `cluster` などを受ける
- ブリッジ系は `bridge_id`, `device_id`, `endpoint` などを受ける
- `controller_id` / `bridge_id` 省略時は全件対象とする
- 操作系は対象デバイスと操作パラメータを明示する

## ツール設計方針

- `matter_*` で統一する
- 1 ツール 1 役を基本にする
- コントローラー系とブリッジ系を分ける
- まずは一覧・状態確認を優先する
- 取得できない項目は `null` か省略で統一する
- Phase 1 は読み取り専用に固定する

## 追加予定の段階

### Phase 1: 読み取り専用

- コントローラー一覧取得ツール
- ブリッジ一覧取得ツール
- デバイス状態取得ツール
- エンドポイント一覧取得ツール
- クラスタ一覧取得ツール
- JSON / text 出力

### Phase 2: 詳細取得

- ルーム / エリア情報の整理
- デバイスタイプごとの最小共通情報の正規化
- 必要なら endpoint / cluster の追加属性拡張

### Phase 3: 制御

- ブリッジ越しの簡易制御ツール
- 代表的な on / off 系操作
- 明示的なパラメータ必須化
- 失敗時の理由整理

### Phase 4: 発展機能

- イベント購読
- 状態更新の追跡
- キャッシュ
- ログ強化
- テスト拡充
- 実運用向けのエラーハンドリング改善

## 現行ツール仕様

### matter_controller_list

- 役割: Matter コントローラー一覧を取得する
- 入力:
  - `controller_id`（任意）
  - `output_format`（省略時は `json`）
- ルール:
  - `controller_id` 省略時は利用可能な全コントローラーを対象にする
  - 1 つのコントローラーに絞る必要がある場合は `controller_id` を受ける
- 出力:
  - `ok`
  - `count`
  - `items[]`
  - `controller`
  - `fetched_at`
- `items[]` の主な要素:
  - `controller_id`
  - `controller_name`
  - `device_count`
  - `bridge_ids`
  - `transport`
  - `reachable`
  - `last_updated`

### matter_bridge_list

- 役割: Matter ブリッジ一覧を取得する
- 入力:
  - `bridge_id`（任意）
  - `output_format`（省略時は `json`）
- ルール:
  - `bridge_id` 省略時は利用可能な全ブリッジを対象にする
  - 1 つのブリッジに絞る必要がある場合は `bridge_id` を受ける
- 出力:
  - `ok`
  - `count`
  - `items[]`
  - `bridge`
  - `fetched_at`
- `items[]` の主な要素:
  - `bridge_id`
  - `bridge_name`
  - `controller_id`
  - `device_count`
  - `device_ids`
  - `transport`
  - `reachable`
  - `last_updated`

### matter_device_status

- 役割: 指定デバイスの状態を取得する
- 入力:
  - `device_id`
  - `controller_id`（任意）
  - `bridge_id`（任意）
  - `endpoint`（任意）
  - `output_format`（省略時は `json`）
- ルール:
  - `device_id` は必須
  - `controller_id` と `bridge_id` は補助指定
  - どちらかで対象が一意に定まらない場合は `ambiguous_target` を返す
- 出力:
  - `ok`
  - `device`
  - `status`
  - `endpoints`
  - `clusters`
  - `fetched_at`
- `device` の主な要素:
  - `device_id`
  - `device_name`
  - `device_type`
  - `vendor`
  - `bridge_id`
  - `controller_id`
  - `reachable`
  - `last_updated`
- `endpoints` の主な要素:
  - `endpoint_id`
  - `clusters`
  - `device_type`
- `clusters` の主な要素:
  - `cluster_id`
  - `cluster_name`
  - `attributes`
  - `commands`

### matter_endpoint_list

- 役割: 指定デバイスのエンドポイント一覧を取得する
- 入力:
  - `device_id`
  - `controller_id`（任意）
  - `bridge_id`（任意）
  - `output_format`（省略時は `json`）
- 出力:
  - `ok`
  - `count`
  - `items[]`
  - `endpoints`
  - `device`
  - `fetched_at`

### matter_cluster_list

- 役割: 指定デバイスのクラスタ一覧を取得する
- 入力:
  - `device_id`
  - `controller_id`（任意）
  - `bridge_id`（任意）
  - `endpoint`（任意）
  - `output_format`（省略時は `json`）
- 出力:
  - `ok`
  - `count`
  - `items[]`
  - `clusters`
  - `endpoints`
  - `device`
  - `fetched_at`

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
