# MATTER ツール仕様 TODO

## 目的

`uag` に Matter 関連ツール群を追加する。
最初はコントローラー経由とブリッジ経由の一覧・状態確認から始め、将来的に詳細取得・制御・購読まで扱える構成へ拡張する。

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
- 可能なら `count` / `items` / `device` / `endpoints` / `clusters` を使う
- `output_format` の既定値は `json`

### 代表的なエラー

- `config_missing`
- `not_found`
- `ambiguous_target`
- `network_error`
- `timeout`
- `unsupported_device`
- `invalid_argument`

### 設定の解決順

- 既存の設定値
- 環境変数
- それでも不足する場合はエラー

## ツール設計方針

- `matter_*` で統一する
- 1 ツール 1 役を基本にする
- コントローラー系とブリッジ系を分ける
- まずは一覧・状態確認を優先する
- 取得できない項目は `null` か省略で統一する
- Phase 1 は読み取り専用に固定する

## 追加予定の段階

### Phase 1: 読み取り専用

- コントローラー配下のデバイス一覧取得ツール
- ブリッジ配下のデバイス一覧取得ツール
- デバイス状態取得ツール
- JSON / text 出力

### Phase 2: 詳細取得

- エンドポイント / クラスタの詳細取得ツール
- ルーム / エリア情報の整理
- デバイスタイプごとの最小共通情報の正規化

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

## Phase 1 の具体仕様

### matter_controller_list

- 役割: Matter コントローラー経由で管理下デバイス一覧を取得する
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
  - `device_id`
  - `device_name`
  - `device_type`
  - `vendor`
  - `bridge_id`
  - `controller_id`
  - `reachable`
  - `last_updated`

### matter_bridge_list

- 役割: Matter ブリッジ経由で配下デバイス一覧を取得する
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
  - `device_id`
  - `device_name`
  - `device_type`
  - `vendor`
  - `bridge_id`
  - `controller_id`
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

## 実装メモ

- Matter は実装経路が複数あるため、コントローラー別・ブリッジ別のアダプタ構造にする
- 秘密情報やトークンは安全に扱う
- まずは一覧取得で実用性を確認する
- コントローラー系とブリッジ系は別ツールとして分ける
- 失敗理由はユーザー向けに短く返す

## 補足

- 最初は一覧取得と状態確認で十分に実用性を確認する
- その後、詳細取得と簡易制御を追加する
- 最終的にはコントローラー経由とブリッジ経由を両方扱える構成にする
- 秘密情報はログに残さない
