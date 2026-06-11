# UPnP ツール仕様 TODO

## 目的

`uag` に UPnP 関連ツール群を追加する。
最初は LAN 内の機器一覧取得から始め、将来的に探索・情報取得・制御まで扱える高機能ツールセットへ拡張する。

## 前提

- Tool Genre: `iot`
- 依存ライブラリは最小限にする
- Windows での動作を優先して確認する
- 出力は機械処理しやすい JSON を基本とする
- 必要に応じて text 出力も提供する
- 既存の `uag` のツール体系に合わせる

## 最終仕様イメージ

### 1. 探索

- UPnP / SSDP 機器一覧取得
- インターフェース指定
- タイムアウト指定
- 再試行指定
- スキャン範囲の指定
- フィルタ
  - friendly name
  - manufacturer
  - model name
  - IP / location
  - device type

### 2. 機器情報

- device description 取得
- service 一覧取得
- service 主要属性取得
- 型番 / 製造元 / UUID / location / presentationURL
- device tree の確認
- 取得失敗時の理由を整理して返す

### 3. 制御系

- ルータ系 IGD 操作
  - 外向き IP 取得
  - ポートマッピング一覧
  - ポートマッピング追加 / 削除
  - WAN 状態取得
- AV 系操作
  - メディアサーバー探索
  - メディアレンダラー探索
  - 再生制御
- 将来的に event subscription も扱う

### 4. 実装面

- 既存コードベースのツール定義に合わせる
- ツールは用途ごとに小さく分ける
- エラーは分かりやすく返す
- ネットワーク障害時のメッセージを整理する
- テストしやすい構造にする
- 返却形式は JSON を標準にする
- text は JSON の整形表示または要約として提供する

## ツール設計方針

### 命名方針

- `upnp_*` で統一する
- 1 ツール 1 役を基本にする
- `upnp_scan` は探索専用に留め、ルータ制御は `upnp_igd_*`、DLNA/AV は `upnp_dlna_*` として役割ごとに分離する。
- 探索、詳細、制御を分離する

### 返却形式

- 成功時は `ok: true` と主要データを返す
- 失敗時は `ok: false` と `error` を返す
- 可能なら `count` / `items` / `device` / `services` のように意味のあるキーを使う

### 入力方針

- 探索系は `timeout`, `interface`, `retry`, `limit` などを受ける
- 詳細系は `location` や `device_url`、`uuid` を受ける
- 制御系はサービス URL と操作パラメータを明示する

### 依存方針

- まずは Python で扱いやすい UPnP ライブラリを使う
- 実装が安定しない機能は後回しにする
- ライブラリ依存を増やしすぎない

## 追加予定の段階

### Phase 1

- UPnP 機器一覧取得ツール
- JSON / text 出力
- タイムアウト対応
- LAN 内の主要機器を見つける

### Phase 2

- 機器詳細取得ツール
- サービス一覧取得ツール
- フィルタ機能
- device tree 表示

### Phase 3

- IGD 操作ツール
- ポートマッピング操作
- WAN 情報取得
- ルータ系の安全な読み取り操作
- ルータ系の安全な読み取り操作

### Phase 3 の具体仕様

#### upnp_igd_status
- 役割: ルータの IGD 対応状況と WAN 状態の読み取り
- 入力:
  - `interface`
  - `timeout`
- 出力:
  - `ok`
  - `wan_ip`
  - `external_ip`
  - `connection_status`
  - `uptime`
  - `supports_port_mapping`

#### upnp_igd_portmap_list
- 役割: ポートマッピング一覧の取得
- 入力:
  - `interface`
  - `timeout`
- 出力:
  - `items[]`
  - `count`
  - `protocol`
  - `external_port`
  - `internal_ip`
  - `internal_port`
  - `description`
  - `enabled`

#### upnp_igd_portmap_add
- 役割: ポートマッピングの追加
- 入力:
  - `interface`
  - `external_port`
  - `internal_ip`
  - `internal_port`
  - `protocol`
  - `description`
  - `lease_duration`
- 出力:
  - `ok`
  - `added`
  - `error`

#### upnp_igd_portmap_delete
- 役割: ポートマッピングの削除
- 入力:
  - `interface`
  - `external_port`
  - `protocol`
- 出力:
  - `ok`
  - `deleted`
  - `error`

#### 方針
- まずは読み取り系を優先
- 追加・削除は明示的なパラメータ必須
- 失敗時は理由を短く返す
- `upnp_scan` とは分ける
- 共通処理は別モジュールに寄せる
### Phase 4

- AV / DLNA 系操作
- 再生制御
- イベント購読
- メディア系デバイスの探索強化

### Phase 5

- 高度な検索
- キャッシュ
- ログ強化
- テスト拡充
- 実運用向けのエラーハンドリング改善

## Phase 1 の具体仕様

### upnp_scan

- 役割: LAN 内 UPnP 機器の探索
- 入力例:
  - `timeout`
  - `interface`
  - `retry`
  - `output_format`
- 出力例:
  - `items[]`
  - `count`
  - `interface_used`
  - `elapsed_ms`

### 返したい情報

- `friendly_name`
- `manufacturer`
- `model_name`
- `device_type`
- `uuid`
- `location`
- `presentation_url`
- `services[]`
- `ip_address`

### 表示方針

- text では見やすい一覧を出す
- JSON では機械処理しやすい形を維持する

## 実装メモ

- 探索は SSDP ベースで行う
- 機器の description URL をたどって詳細情報を補完する
- Windows でのマルチキャスト挙動に注意する
- 取得できない項目は null か省略で統一する
- タイムアウトや例外はユーザー向けの短いメッセージに変換する

## DLNA 観点

- DLNA は UPnP AV をベースにしたメディア相互接続規格で、探索・機器情報・制御の一部を UPnP と共有する
- UPnP 探索結果から DLNA らしい機器を判定する補助情報:
  - deviceType の `urn:schemas-upnp-org:device:MediaServer:`
  - `MediaRenderer`
  - XML 内の `DLNA.ORG_` 系属性
  - `serviceType` の `ContentDirectory`, `ConnectionManager`, `AVTransport`
- 追加で検討する機能:
  - メディアサーバー一覧
  - レンダラー一覧
  - `Browse` / `Search` の実行
  - 再生キュー、再生/停止/一時停止/シーク
  - `CurrentConnectionInfo` などの確認
- 実装方針:
  - まずは UPnP 探索・詳細取得の上に DLNA 判定を載せる
  - 制御系は安全な読み取りツールと分ける
  - 返却は JSON を基本にする

## 補足

- まずは一覧取得で実用性を確認する
- その後、詳細取得とサービス解析を追加する
- 最終的にはルータ系と AV 系を両方扱える構成にする
