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

## 共通仕様

### 返却形式

- 成功時は `ok: true` と主要データを返す
- 失敗時は `ok: false` と `error` を返す
- 可能なら `count` / `items` / `node` / `objects` / `properties` を使う
- `output_format` の既定値は `json`

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

## ツール設計方針

- `echonet_*` で統一する
- 1 ツール 1 役を基本にする
- 探索、詳細、制御を分離する
- まずは一覧・状態確認を優先する
- `node_id` がある場合は補助識別子として扱う

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

- property 値設定ツール
- 基本制御ツール
- 主要機器タイプへの対応
- 失敗時の理由整理
- 明示的なパラメータ必須化

### Phase 4: 発展機能

- 通知 / 監視系
- 状態更新の追跡
- キャッシュ
- ログ強化
- テスト拡充
- 実運用向けのエラーハンドリング改善

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
