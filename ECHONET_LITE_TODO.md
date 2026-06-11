# ECHONET-LITE ツール仕様 TODO

## 目的

`uag` に ECHONET Lite 関連ツール群を追加する。
最初は LAN 内の機器一覧・状態確認から始め、将来的に詳細取得・制御・通知まで扱える構成へ拡張する。

## 前提

- Tool Genre: `iot`
- Windows での動作を優先して確認する
- 出力は機械処理しやすい JSON を基本にする
- 必要に応じて text 出力も提供する
- 既存の `uag` のツール体系に合わせる
- 秘密情報は長期保存しない
- 必要な環境変数を追加する場合は `UAGENT_` を接頭辞にして統一する
- まずは読み取り系を優先する

## 共通ルール

### 返却形式

- 成功時は `ok: true` と主要データを返す
- 失敗時は `ok: false` と `error` を返す
- 可能なら `count` / `items` / `node` / `objects` / `properties` を使う
- `output_format` の既定値は `json` にする

### 代表的なエラー

- `interface_not_found`
- `timeout`
- `network_error`
- `no_devices`
- `invalid_argument`
- `unsupported_property`
- `communication_failed`

### 通信前提

- UDP / multicast ベースで自前実装する
- マルチキャスト探索と個別問い合わせを分ける
- 取得できない項目は `null` か省略で統一する
- 失敗理由は短く返す

## ツール設計方針

- `echonet_*` で統一する
- 1 ツール 1 役を基本にする
- 探索、詳細、制御を分離する
- まずは一覧・状態確認を優先する
- `node_id` がある場合は補助指定として扱う

## 追加予定の段階

### Phase 1: 読み取り専用

- ECHONET Lite ノード一覧取得ツール
- JSON / text 出力
- タイムアウト対応
- LAN 内の主要ノードを見つける
- ノード種別の判定

### Phase 2: 詳細取得

- ノード詳細取得ツール
- object 一覧取得ツール
- property 一覧取得ツール
- property 値取得ツール
- ノード情報の正規化

### Phase 3: 制御

- `echonet_property_set`
- `echonet_control`
- 主要機器タイプへの対応
- 失敗時の理由整理
- 明示的なパラメータ必須化

### `echonet_property_set`

- 役割: 指定ノード / object の property 値を設定する
- 入力:
  - `ip_address`
  - `eoj` または `object_code`
  - `epc`
  - `value` もしくは `edt`
  - `timeout`
  - `output_format`
- ルール:
  - `ip_address` は必須
  - `eoj` 省略時は node profile を対象にする
  - `value` と `edt` は少なくとも片方を必須にする
  - `epc` が未対応なら `unsupported_property` を返す
  - 送信できない値は `invalid_argument` で返す
- 出力:
  - `ok`
  - `node`
  - `status`
  - `property`
  - `elapsed_ms`
- `property` の主な要素:
  - `epc`
  - `name`
  - `value`
  - `format`
  - `access`
  - `raw_hex`

### `echonet_control`

- 役割: 主要機器タイプ向けの基本制御を行う
- 入力:
  - `ip_address`
  - `eoj` または `object_code`
  - `action`
  - `value` 必要時のみ
  - `timeout`
  - `output_format`
- `action` 例:
  - `on`
  - `off`
  - `open`
  - `close`
  - `set_value`
- ルール:
  - 機器タイプごとに対応 action を明示する
  - 非対応 action は `unsupported_property` か `unsupported_device` を返す
  - 制御対象が曖昧なら `ambiguous_target` に相当する失敗を返す
- 出力:
  - `ok`
  - `node`
  - `status`
  - `action`
  - `elapsed_ms`


### Phase 4: 発展機能

- 通知 / 監視系
- 状態更新の追跡
- キャッシュ
- ログ強化
- テスト拡充
- 実運用向けのエラーハンドリング改善

### 監視系の補足

- 定期ポーリングで状態変化を追跡する
- 取得対象は `ip_address` / `eoj` / `object_code` で絞れるようにする
- 変化があった property だけを返せる形を検討する
- 将来的にイベント通知が可能なら別経路で扱う

### 監視系の実装イメージ

- `echonet_monitor` のような別ツールを用意する
- 入力:
  - `ip_address`
  - `eoj` または `object_code`
  - `interval`
  - `duration`
  - `timeout`
  - `output_format`
- 出力:
  - `ok`
  - `count`
  - `changes`
  - `elapsed_ms`
- `changes[]` の主な要素:
  - `timestamp`
  - `node`
  - `object`
  - `property`
  - `before`
  - `after`
- 監視停止理由は短く返す

### キャッシュの補足

- 直近の探索結果を短時間だけ保持する
- ノード詳細や property 値の再取得を抑える
- キャッシュ有無は明示できるようにする

### ログ・テストの補足

- 失敗理由とタイムアウト箇所を短く記録する
- Windows 優先でテストする
- 探索 / 詳細 / 制御を個別に検証できるようにする
- 既存の JSON/text 出力差分も確認する

### 制御対象の優先順

1. 照明
2. プラグ
3. カーテン / ブラインド
4. エアコン
5. ロック

### まず詰める対象

- 照明系の `on` / `off`
- プラグ系の `on` / `off`
- カーテン / ブラインド系の `open` / `close` / `set_value`
- エアコン系の基本制御
- ロック系の `lock` / `unlock`

### 制御ルールの補足

- `echonet_control` は機器タイプごとに対応 action を分ける
- 照明・プラグは `on` / `off` を基本にする
- カーテン / ブラインドは `open` / `close` / `set_value` を扱う
- ロックは `lock` / `unlock` を扱う
- 未対応の機器タイプは `unsupported_device` を返す
- 未対応の action は `unsupported_property` か `invalid_argument` で返す
- 制御対象が複数にまたがる場合は `ambiguous_target` を返す

## Phase 1 の具体仕様

### echonet_scan

- 役割: LAN 内 ECHONET Lite ノードの探索
- 通信:
  - ECHONET Lite multicast を用いる
  - デフォルトの宛先は `224.0.23.0:3610`
- 入力:
  - `timeout`（受信待ち時間、秒）
  - `interface`（任意の IPv4 か NIC 名）
  - `retry`（探索送信回数）
  - `limit`（最大返却件数）
  - `output_format`（省略時は `json`）
- 出力:
  - `ok`
  - `count`
  - `items[]`
  - `interface_used`
  - `elapsed_ms`
- `items[]` の主な要素:
  - `ip_address`
  - `node_id`
  - `node_profile`
  - `manufacturer`
  - `model`
  - `eoj_list`
  - `reachable`
  - `last_seen`
- 補足:
  - 探索結果は IP 単位でまとめる
  - 同一ノードの重複応答はまとめる

### echonet_node_status

- 役割: 指定ノードの基本状態を取得する
- 入力:
  - `ip_address`
  - `eoj`（任意）
  - `object_code`（任意）
  - `output_format`（省略時は `json`）
- ルール:
  - `ip_address` は必須
  - `eoj` 省略時はノードプロファイルを対象にする
  - `object_code` がある場合は対象 object を絞る
- 出力:
  - `ok`
  - `node`
  - `objects`
  - `properties`
  - `status`
  - `elapsed_ms`
- `node` の主な要素:
  - `ip_address`
  - `node_id`
  - `node_profile`
  - `manufacturer`
  - `model`
  - `available`
  - `reachable`
  - `last_updated`
- `objects` の主な要素:
  - `eoj`
  - `class_name`
  - `instance`
  - `properties`
  - `supported_esv`
- `properties` の主な要素:
  - `epc`
  - `name`
  - `value`
  - `format`
  - `access`
  - `raw_hex`

## 実装メモ

- ECHONET Lite は UDP ベースなのでタイムアウト設計が重要
- LAN 内探索は Windows のネットワーク設定に影響されやすい
- まずは一覧取得で実用性を確認する
- 失敗理由はユーザー向けに短く返す
- 取得できない項目は `null` か省略で統一する

## 補足

- 最初は一覧取得と状態確認で十分に実用性を確認する
- その後、詳細取得と制御を追加する
- 将来的には機器タイプごとの共通ラッパーも検討する
- 秘密情報はログに残さない
